"""Archive operations: Sent drain into staging objects, delete-after-PUT,
staging purge, and the directory skeleton filesystem consumers need.

Stdlib only. Object-store sink, host paths and the rules csv come from the
caller (spec: ``+wit/specs/iac-n8n/staging-inbox-s3``).
"""

from __future__ import annotations

import csv
import email
import email.policy
import email.utils
import hashlib
import logging
import re
from pathlib import Path

from . import imap as _imap
from . import render as _render

log = logging.getLogger("mailtools.archive")


def folder_relpath(box: str, prefix: str) -> str:
    """`INBOX.FAW.Shopping` -> `FAW/Shopping`; `INBOX` -> `INBOX`."""
    rel = box[len(prefix):] if prefix and box.startswith(prefix) else box
    sep = "." if "." in rel else "/"
    parts = [re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", p) or "_" for p in rel.split(sep) if p]
    return "/".join(parts) or "INBOX"


def rule_folders(rules_csv: Path) -> list[str]:
    """Target folders from a mail-sort csv — the dirs the archive writer can hit."""
    folders = set()
    if Path(rules_csv).exists():
        for row in csv.reader(open(rules_csv, encoding="utf-8")):
            if row and not row[0].lstrip().startswith("#"):
                folders.add(row[0].strip())
    return sorted(folders)


def init_dirs(accounts: list[dict], repo: Path, rules_csv: Path,
              mail_subdir: str = "+INBOX/emails") -> None:
    """Pre-create every directory the archive writer can hit.

    The n8n Read/Write Files node does not create intermediate directories —
    so the folder tree is created host-side: every rule target folder +
    INBOX/Sent + attachments + proposals, per account slug.
    """
    static = ["INBOX", "Sent", "attachments", "proposals"]
    for acct in accounts:
        base = Path(repo) / mail_subdir / acct["slug"]
        for rel in [folder_relpath(f, acct["prefix"]) for f in rule_folders(rules_csv)] + static:
            (base / rel).mkdir(parents=True, exist_ok=True)
        log.info("%s: ensured dirs under %s", acct["account"], base)


def message_objects(slug: str, box: str, prefix: str, uid: int, raw: bytes,
                    source: str = "mail-archive") -> list[dict]:
    """Render one message to staging objects; returns ``[{key, data,
    content_type, metadata}]``.

    Keys are deterministic: message date (or ``undated``), account slug,
    folder, subject slug, and a stable message identifier; attachments add a
    one-based ordinal so repeated filenames in one message cannot collide.
    """
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    try:
        parsed_date = email.utils.parsedate_to_datetime(msg.get("Date", ""))
    except (TypeError, ValueError, OverflowError):
        parsed_date = None
    day = parsed_date.date().isoformat() if parsed_date else "undated"
    message_id = _render.decode_header_value(msg.get("Message-ID")).strip()
    if message_id:
        digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:12]
        doc_id = f"{_render.message_doc_id(msg, uid)}-{digest}"
    else:
        digest = hashlib.sha256(raw).hexdigest()[:12]
        doc_id = f"uid-{uid}-{digest}"
    subject = _render.decode_header_value(msg.get("Subject"))
    base = f"{source}/{day}/{slug}"
    meta = {"source": source, "account": slug, "folder": box}
    att_parts = [p for p in msg.iter_attachments()
                 if p.get_payload(decode=True) is not None]
    att_keys = [
        f"{base}/attachments/{doc_id}-{index:03d}-{_render.safe_filename(part.get_filename())}"
        for index, part in enumerate(att_parts, 1)
    ]
    frontmatter = {
        "account": slug,
        "folder": box,
        "uid": str(uid),
        "messageId": msg.get("Message-ID", ""),
        "from": _render.decode_header_value(msg.get("From")),
        "to": _render.decode_header_value(msg.get("To")),
        "subject": subject,
        "date": msg.get("Date", ""),
        "attachments": att_keys,
    }
    text = _render.mail_to_markdown_text(raw, frontmatter=frontmatter)
    doc_name = f"{day}_{_render.slugify(subject)}_{doc_id}.md"
    objects = [{
        "key": f"{base}/{folder_relpath(box, prefix)}/{doc_name}",
        "data": text.encode("utf-8"),
        "content_type": "text/markdown; charset=utf-8",
        "metadata": meta,
    }]
    for part, key in zip(att_parts, att_keys):
        objects.append({
            "key": key,
            "data": part.get_payload(decode=True),
            "content_type": part.get_content_type() or "application/octet-stream",
            "metadata": meta,
        })
    return objects


def archive_account(acct: dict, sink, password: str | None = None,
                    imap_client=None, dry_run: bool = False,
                    source: str = "mail-archive") -> tuple[list[int], list[int]]:
    """Drain the account's Sent folder into staging objects via ``sink.put``.

    ``sink`` is any object store view exposing
    ``put(key, data, content_type, metadata)`` — e.g. ``wit_pytools.s3``'s
    ``BucketSink``. Returns ``(captured, failed)``: only captured UIDs may be
    deleted by the caller — the staging PUT is the durable write that gates
    Sent deletion (spec FR-003).
    """
    m, owned = _imap.connect(acct["host"], acct["account"], password, imap_client=imap_client)
    slug = acct["slug"]
    box = _imap.sent_folder(acct["prefix"])
    captured, failed = [], []
    try:
        if _imap.examine(m, box) is None:
            log.warning("%s: cannot examine %s", slug, box)
            return captured, failed
        for uid in _imap.search_uids(m):
            if dry_run:
                captured.append(uid)
                continue
            raw = _imap.fetch_raw(m, uid)
            if raw is None:
                continue
            try:
                objects = message_objects(slug, box, acct["prefix"], uid, raw, source)
                for obj in objects:
                    try:
                        sink.put(
                            obj["key"], obj["data"],
                            obj["content_type"], obj["metadata"])
                    except Exception as error:
                        log.warning(
                            "%s: PUT failed for %s (%s)",
                            acct["account"], obj["key"], type(error).__name__)
                        raise
                    log.info("%s: PUT %s", acct["account"], obj["key"])
            except Exception as error:
                log.warning(
                    "%s: keeping Sent uid %s after staging failure (%s)",
                    acct["account"], uid, type(error).__name__)
                failed.append(uid)
                continue
            captured.append(uid)
    finally:
        if owned:
            m.logout()
    log.info("%s: staged %d message(s), %d failed%s", acct["account"],
             len(captured), len(failed), " [dry-run]" if dry_run else "")
    return captured, failed


def delete_sent(acct: dict, uids: list[int], password: str, imap_client=None,
                dry_run: bool = False) -> int:
    """Delete only captured Sent UIDs after all their objects were PUT."""
    if not uids:
        return 0
    box = _imap.sent_folder(acct["prefix"])
    m, owned = _imap.connect(acct["host"], acct["account"], password, imap_client=imap_client)
    try:
        quoted = f'"{box}"' if " " in box else box
        typ, _ = m.select(quoted)
        if typ != "OK":
            log.warning("%s: no Sent folder %s", acct["account"], box)
            return 0
        if not dry_run:
            uid_set = b",".join(str(u).encode() for u in uids)
            typ, _ = m.uid("store", uid_set, "+FLAGS.SILENT", "(\\Deleted)")
            if typ != "OK":
                raise RuntimeError(f"{acct['account']}: could not mark captured Sent UIDs deleted")
            typ, _ = m.uid("expunge", uid_set)
            if typ != "OK":
                raise RuntimeError(f"{acct['account']}: UID EXPUNGE failed for captured Sent UIDs")
    finally:
        if owned:
            m.logout()
    log.info("%s: deleted %d captured message(s) from %s%s", acct["account"], len(uids), box, " [dry-run]" if dry_run else "")
    return len(uids)


def purge_staging(acct: dict, days: int, password: str, imap_client=None,
                  dry_run: bool = False) -> int:
    """Delete read copies older than ``days`` in the staging folder."""
    box = _imap.staging_folder(acct["prefix"])
    m, owned = _imap.connect(acct["host"], acct["account"], password, imap_client=imap_client)
    removed = 0
    try:
        quoted = f'"{box}"' if " " in box else box
        typ, _ = m.select(quoted)
        if typ != "OK":
            log.warning("%s: no staging folder %s", acct["account"], box)
            return 0
        typ, data = m.uid("search", None, "SEEN", "BEFORE", _imap.imap_before_date(days))
        uids = data[0].split() if typ == "OK" and data and data[0] else []
        if uids and not dry_run:
            m.uid("store", b",".join(uids).decode(), "+FLAGS.SILENT", "(\\Deleted)")
            m.expunge()
        removed = len(uids)
    finally:
        if owned:
            m.logout()
    log.info("%s: purged %d read staging copie(s)%s", acct["account"], removed, " [dry-run]" if dry_run else "")
    return removed
