"""Archive operations: Sent drain, delete-after-commit, staging purge,
and the directory skeleton the n8n Write node needs.

Stdlib only. Host/repo paths and the rules csv come from the caller.
"""

from __future__ import annotations

import csv
import email
import email.policy
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


def archive_message(repo: Path, slug: str, box: str, prefix: str, uid: int, raw: bytes,
                    mail_subdir: str = "+INBOX/emails") -> Path:
    """Write one message + its attachments under the archive tree; returns the doc path."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    date_str = _render.message_date_str(msg)
    month_str = _render.message_month_str(msg)
    doc_id = _render.message_doc_id(msg, uid)
    subject = _render.decode_header_value(msg.get("Subject"))
    doc_dir = Path(repo) / mail_subdir / slug / folder_relpath(box, prefix)
    doc_path = doc_dir / f"{date_str}_{_render.slugify(subject)}_{doc_id}.md"
    att_dir = Path(repo) / mail_subdir / slug / "attachments" / month_str
    frontmatter = {
        "account": slug,
        "folder": box,
        "uid": str(uid),
        "messageId": msg.get("Message-ID", ""),
        "from": _render.decode_header_value(msg.get("From")),
        "to": _render.decode_header_value(msg.get("To")),
        "subject": subject,
        "date": msg.get("Date", ""),
        "attachments": [str((att_dir / f"{doc_id}-{_render.safe_filename(p.get_filename())}").relative_to(repo).as_posix())
                        for p in msg.iter_attachments() if p.get_payload(decode=True) is not None],
    }
    out, _ = _render.mail_to_markdown(
        raw, doc_path, frontmatter=frontmatter,
        attachments_dir=att_dir, attachments_prefix=f"{doc_id}-")
    return out


def archive_account(acct: dict, repo: Path, password: str, imap_client=None,
                    dry_run: bool = False, mail_subdir: str = "+INBOX/emails") -> list[int]:
    """Drain the account's Sent folder; returns the captured UIDs."""
    m, owned = _imap.connect(acct["host"], acct["account"], password, imap_client=imap_client)
    slug = acct["slug"]
    box = _imap.sent_folder(acct["prefix"])
    captured = []
    try:
        if _imap.examine(m, box) is None:
            log.warning("%s: cannot examine %s", slug, box)
            return captured
        for uid in _imap.search_uids(m):
            raw = _imap.fetch_raw(m, uid)
            if raw is None:
                continue
            if not dry_run:
                try:
                    archive_message(repo, slug, box, acct["prefix"], uid, raw, mail_subdir)
                except Exception as error:
                    log.warning("%s: skipping message uid %s in %s: %s", slug, uid, box, error)
                    continue
            captured.append(uid)
    finally:
        if owned:
            m.logout()
    log.info("%s: archived %d message(s)%s", acct["account"], len(captured), " [dry-run]" if dry_run else "")
    return captured


def delete_sent(acct: dict, uids: list[int], password: str, imap_client=None,
                dry_run: bool = False) -> int:
    """Delete captured UIDs in ``<prefix>Sent`` — runs only after a successful commit."""
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
            m.uid("store", uid_set, "+FLAGS.SILENT", "(\\Deleted)")
            m.expunge()
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
