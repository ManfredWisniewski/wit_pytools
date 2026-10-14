"""Mailbox polling for verification mails (stdlib IMAP).

Per-mailbox env vars (tag uppercased), e.g. for --mailbox claudia:

  CLAUDIA_IMAP_HOST      IMAP server, e.g. post.witconsult.de
  CLAUDIA_IMAP_PORT      default 993
  CLAUDIA_IMAP_USER      mailbox login
  CLAUDIA_IMAP_PASSWORD  mailbox password
  CLAUDIA_IMAP_FOLDER    default INBOX

JMAP (Stalwart) is not implemented; all persona mailboxes are also
reachable via IMAP4rev1.
"""

import imaplib
import os
import re
import time
from datetime import date, timedelta
from email import message_from_bytes
from email.header import make_header, decode_header
from urllib.request import Request, urlopen

from .config import WebtoolsConfigError, _load_env_files

_URL_RE = re.compile(r"https?://[^\s<>'\"()\]]+")


def load_mailbox_config(tag):
    """Return {host, port, user, password, folder} from <TAG>_IMAP_* env."""
    _load_env_files()
    prefix = tag.upper().replace("-", "_")
    host = os.environ.get(f"{prefix}_IMAP_HOST", "")
    user = os.environ.get(f"{prefix}_IMAP_USER", "")
    password = os.environ.get(f"{prefix}_IMAP_PASSWORD", "")
    if not (host and user and password):
        raise WebtoolsConfigError(
            f"{prefix}_IMAP_HOST, {prefix}_IMAP_USER and "
            f"{prefix}_IMAP_PASSWORD must be set (env or .env)"
        )
    return {
        "host": host,
        "port": int(os.environ.get(f"{prefix}_IMAP_PORT", "993")),
        "user": user,
        "password": password,
        "folder": os.environ.get(f"{prefix}_IMAP_FOLDER", "INBOX"),
    }


def extract_links(text):
    """Return all http(s) URLs found in text."""
    return _URL_RE.findall(text)


def _decode_subject(raw):
    """Decode an RFC2047-encoded subject header."""
    return str(make_header(decode_header(raw or "")))


def _message_text(msg):
    """Concatenate all text/plain and text/html parts, decoded."""
    chunks = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        chunks.append(payload.decode(charset, errors="replace"))
    return "\n".join(chunks)


def search_mail(config, *, sender=None, subject=None, since_days=1):
    """Search the mailbox; returns [(subject, [links])] newest first."""
    criteria = []
    if sender:
        criteria += ["FROM", f'"{sender}"']
    if subject:
        criteria += ["SUBJECT", f'"{subject}"']
    if since_days:
        since = (date.today() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        criteria += ["SINCE", since]
    if not criteria:
        criteria = ["ALL"]

    results = []
    with imaplib.IMAP4_SSL(config["host"], config["port"]) as imap:
        imap.login(config["user"], config["password"])
        imap.select(config["folder"], readonly=True)
        status, data = imap.search(None, *criteria)
        if status != "OK":
            return results
        for uid in reversed(data[0].split()):
            status, fetched = imap.fetch(uid, "(RFC822)")
            if status != "OK" or not fetched or not fetched[0]:
                continue
            msg = message_from_bytes(fetched[0][1])
            subj = _decode_subject(msg.get("Subject"))
            results.append((subj, extract_links(_message_text(msg))))
    return results


def wait_for_link(
    config,
    *,
    sender=None,
    subject=None,
    link_pattern=None,
    since_days=1,
    timeout=1800,
    interval=15,
):
    """Poll the mailbox until a matching mail yields a link.

    link_pattern is an optional regex; the first link matching it wins,
    otherwise the first link in the mail. Returns the URL or None.
    """
    matcher = re.compile(link_pattern) if link_pattern else None
    deadline = time.monotonic() + timeout
    while True:
        try:
            for subj, links in search_mail(
                config, sender=sender, subject=subject, since_days=since_days
            ):
                if not links:
                    continue
                if matcher:
                    hit = next((u for u in links if matcher.search(u)), None)
                else:
                    hit = links[0]
                if hit:
                    print(f"  mail '{subj}': link found")
                    return hit
        except (imaplib.IMAP4.error, OSError) as error:
            print(f"  mailbox poll failed: {error}")
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)


def fetch(url):
    """HTTP-GET a URL (e.g. a verification link); returns the status code."""
    request = Request(url, headers={"User-Agent": "webtools/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.status
    except Exception as error:  # HTTPError has .code; other errors -> 0
        return getattr(error, "code", 0)
