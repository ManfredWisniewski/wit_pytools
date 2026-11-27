"""RFC822 → markdown rendering: one parameterized renderer.

``mail_to_markdown(raw, output_path, frontmatter=...)`` covers both the
archive format (YAML front matter + body + attachments) and the simple
format (``# subject`` + ``- From/To/Date`` bullets, quote-stripped) of the
legacy ``eml_to_markdown``. Stdlib only.
"""

from __future__ import annotations

import email
import email.header
import email.policy
import email.utils
import datetime as dt
import re
from pathlib import Path

# Lines where the quoted history of a reply/forward begins.
_QUOTE_CUT = re.compile(
    r'^\s*(-+\s*(urspr.ngliche\s+nachricht|original\s+message'
    r'|weitergeleitete\s+nachricht|forwarded\s+message)\s*-+'
    r'|(_{2,})\s*$'
    r'|(on|am)\s+.+\s(wrote|schrieb)\s+.+:\s*$)',
    re.IGNORECASE,
)


def strip_quoted_text(text):
    """Remove quoted reply/forward history and '>' quote lines."""
    out = []
    for line in text.splitlines():
        if _QUOTE_CUT.match(line):
            break
        if line.lstrip().startswith('>'):
            continue
        out.append(line)
    return '\n'.join(out).strip()


def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].rstrip("-") or "no-subject")


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    return "".join(
        (b.decode(charset or "utf-8", errors="replace") if isinstance(b, bytes) else b)
        for b, charset in parts
    )


def message_text(msg) -> str:
    body = msg.get_body(preferencelist=("plain",))
    if body is None:
        body = msg.get_body(preferencelist=("html",))
        if body is not None:
            html = links_to_markdown(body.get_content())
            return re.sub(r"<[^>]+>", "", html).strip()
    if body is None:
        try:
            payload = msg.get_payload(decode=True) or b""
            return payload.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""
    try:
        return body.get_content().strip()
    except (LookupError, UnicodeDecodeError):
        return (body.get_payload(decode=True) or b"").decode("utf-8", errors="replace").strip()


def safe_filename(name: str) -> str:
    name = decode_header_value(name) or "attachment.bin"
    name = name.replace("\\", "/").split("/")[-1]
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)[:120] or "attachment.bin"


def write_attachments(msg, att_dir, prefix: str = "") -> list[str]:
    """Decode msg attachments into att_dir as <prefix><safe name>."""
    att_dir = Path(att_dir)
    att_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for part in msg.iter_attachments():
        data = part.get_payload(decode=True)
        if data is None:
            continue
        att_path = att_dir / f"{prefix}{safe_filename(part.get_filename())}"
        att_path.write_bytes(data)
        written.append(att_path.name)
    return written


_LINK_RE = re.compile(
    r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a\s*>',
    re.IGNORECASE | re.DOTALL,
)


def links_to_markdown(html: str) -> str:
    """Keep link targets: <a href="u">t</a> -> [t](u) before tag stripping."""
    def repl(match):
        text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        return f"[{text or match.group(1)}]({match.group(1)})"
    return _LINK_RE.sub(repl, html)


def message_date_str(msg) -> str:
    parsed = email.utils.parsedate_to_datetime(msg.get("Date", ""))
    if parsed is None:
        return dt.date.today().isoformat()
    return parsed.date().isoformat()


def message_month_str(msg) -> str:
    parsed = email.utils.parsedate_to_datetime(msg.get("Date", ""))
    d = parsed.date() if parsed else dt.date.today()
    return f"{d.year:04d}-{d.month:02d}"


def message_doc_id(msg, uid: int) -> str:
    """Filename id: slugified Message-ID like the n8n archive-doc, uid fallback."""
    msgid = decode_header_value(msg.get("Message-ID")).strip()
    return slugify(msgid, 24) if msgid else str(uid)


def yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def mail_to_markdown_text(raw: bytes, *, frontmatter: dict | None = None,
                          attachments: list[str] | None = None,
                          strip_quotes: bool = False, title: str = "") -> str:
    """Render one RFC822 message to markdown text — no file writes.

    - ``frontmatter`` given → YAML front matter + raw body (archive format);
      keys map 1:1 to front matter fields, ``attachments`` list appended
      when attachments were produced.
    - ``frontmatter=None`` → simple format: ``# subject`` + ``- From/To/Date``
      bullets + quote-stripped body (legacy ``eml_to_markdown`` format);
      ``title`` is the heading fallback when the subject is empty.
    - ``attachments`` → names listed in the front matter/bullet line.
    """
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    subject = decode_header_value(msg.get("Subject"))
    body = message_text(msg)
    if strip_quotes or frontmatter is None:
        body = strip_quoted_text(body)
    written = attachments or []

    if frontmatter is None:
        lines = [
            f"# {subject or title}",
            "",
            f"- From: {decode_header_value(msg.get('From'))}",
            f"- To: {decode_header_value(msg.get('To'))}",
        ]
        optional = (
            ("Cc", msg.get("Cc")),
            ("Delivered-To", msg.get("Delivered-To") or msg.get("X-Original-To")),
            ("List-Id", msg.get("List-Id")),
            ("List-Unsubscribe", msg.get("List-Unsubscribe")),
        )
        lines += [
            f"- {label}: {decode_header_value(value)}"
            for label, value in optional
            if value
        ]
        lines.append(f"- Date: {msg.get('Date', '')}")
        if written:
            lines.append(
                f"- Attachments: {', '.join(Path(p).name for p in written)}"
            )
        lines += ["", body]
    else:
        lines = ["---"]
        items = list(frontmatter.items())
        if written and not any(k == "attachments" for k, _ in items):
            items.append(("attachments", written))
        for key, value in items:
            if isinstance(value, list):
                lines.append(f"{key}:")
                lines += [f"  - {yaml_escape(str(v))}" for v in value]
            else:
                lines.append(f"{key}: {yaml_escape(value)}")
        lines.append("---")
        lines += ["", body]
    return "\n".join(lines).strip("\n") + "\n"


def mail_to_markdown(raw: bytes, output_path, *, frontmatter: dict | None = None,
                     attachments_dir=None, attachments_prefix: str = "",
                     strip_quotes: bool = False,
                     settings: dict | None = None) -> tuple[Path, list[str]]:
    """Render one RFC822 message to a markdown file.

    - ``frontmatter`` given → YAML front matter + raw body (archive format);
      keys map 1:1 to front matter fields, ``attachments`` list appended
      when attachments were written.
    - ``frontmatter=None`` → simple format: ``# subject`` + ``- From/To/Date``
      bullets + quote-stripped body (legacy ``eml_to_markdown`` format).
    - ``attachments_dir`` → attachments decoded to that dir, named
      ``<prefix><filename>``; returned paths are relative to ``output_path``'s
      parents when possible.
    Returns ``(output_path, attachment_paths)``.
    """
    del settings  # legacy signature compat
    output_path = Path(output_path)
    written = []
    if attachments_dir is not None:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        written = [
            str(Path(attachments_dir) / name)
            for name in write_attachments(msg, attachments_dir, attachments_prefix)
        ]
    text = mail_to_markdown_text(raw, frontmatter=frontmatter,
                                 attachments=written,
                                 strip_quotes=strip_quotes,
                                 title=output_path.stem)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return output_path, written


def eml_to_markdown(source, output_path, settings=None):
    """Convert an .eml file into a simple Markdown file (legacy signature).

    Thin wrapper over :func:`mail_to_markdown` — kept for backwards
    compatibility (NFR-004). ``settings['attachments_dir']`` enables
    attachment extraction next to the markup.
    """
    source = Path(source)
    settings = settings or {}
    out, _written = mail_to_markdown(
        source.read_bytes(),
        output_path,
        attachments_dir=settings.get('attachments_dir'),
        attachments_prefix=settings.get('attachments_prefix', ''),
        settings=settings,
    )
    return out
