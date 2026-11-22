"""Read-oriented IMAP helpers + mailbox naming for the mail tools.

Read paths use ``EXAMINE``/``BODY.PEEK[]`` — flags are never modified.
Stdlib only (``imaplib``).
"""

from __future__ import annotations

import base64
import datetime as dt
import imaplib
import logging
import re

log = logging.getLogger("mailtools.imap")

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def utf7_decode(name: str) -> str:
    """Decode IMAP modified UTF-7 mailbox names (&AAA- sequences)."""
    def repl(match: re.Match) -> str:
        raw = match.group(1).replace(",", "/")
        pad = "=" * (-len(raw) % 4)
        return base64.b64decode(raw + pad).decode("utf-16-be")
    return re.sub(r"&([^-]*)-", lambda m: "&" if m.group(1) == "" else repl(m), name)


def parse_list_names(list_data: list) -> list[str]:
    """Extract mailbox names from a LIST response."""
    names = []
    for item in list_data:
        if not item:
            continue
        text = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else item
        match = re.search(r'"((?:[^"\\]|\\.)*)"\s*$', text)
        if match:
            name = match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        else:
            name = text.rsplit(" ", 1)[-1].strip()
        if name:
            names.append(utf7_decode(name))
    return names


def list_folders(m) -> list[str]:
    typ, data = m.list()
    if typ != "OK":
        raise RuntimeError(f"LIST failed: {typ}")
    return parse_list_names(data)


def examine(m, box: str) -> str | None:
    """Open a mailbox read-only; returns UIDVALIDITY or None."""
    quoted = f'"{box}"' if " " in box else box
    typ, _ = m.select(quoted, readonly=True)
    if typ != "OK":
        return None
    values = m.untagged_responses.get("UIDVALIDITY") or []
    return values[0].decode() if isinstance(values[0], bytes) else values[0] if values else None


def search_uids(m, after_uid: int = 0) -> list[int]:
    typ, data = m.uid("search", None, "UID", f"{after_uid + 1}:*")
    if typ != "OK" or not data or not data[0]:
        return []
    return [int(u) for u in data[0].split()]


def fetch_raw(m, uid: int) -> bytes | None:
    typ, data = m.uid("fetch", str(uid), "(BODY.PEEK[])")
    if typ != "OK":
        return None
    for part in data or []:
        if isinstance(part, tuple) and part[1]:
            return part[1]
    return None


def staging_folder(prefix: str) -> str:
    return prefix + "Incoming"


def sent_folder(prefix: str) -> str:
    return prefix + "Sent"


def imap_before_date(days: int) -> str:
    d = dt.date.today() - dt.timedelta(days=days)
    return f"{d.day}-{_MONTHS[d.month - 1]}-{d.year}"


def connect(host: str, account: str, password: str, port: int = 993,
            imap_client=None):
    """Return (connection, owned). Pass ``imap_client`` to inject a fake in tests."""
    if imap_client is not None:
        return imap_client, False
    m = imaplib.IMAP4_SSL(host, port)
    if not password:
        raise RuntimeError(f"no password for {account} — set the account password variable in .env")
    m.login(account, password)
    return m, True


def hierarchy_sep(m) -> str:
    """Read the server hierarchy delimiter from a LIST response (e.g. '.' on
    Dovecot, '/' on Stalwart); defaults to '.'."""
    try:
        _typ, boxes = m.list()
        for b in boxes:
            match = re.search(rb'"([^"\\])"', b)
            if match:
                return match.group(1).decode()
    except Exception:
        pass
    return "."
