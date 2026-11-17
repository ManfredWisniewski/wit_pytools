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
            html = body.get_content()
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
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    subject = decode_header_value(msg.get("Subject"))
    body = message_text(msg)
    if strip_quotes or frontmatter is None:
        body = strip_quoted_text(body)

    written = []
    if attachments_dir is not None:
        att_dir = Path(attachments_dir)
        att_dir.mkdir(parents=True, exist_ok=True)
        for part in msg.iter_attachments():
            data = part.get_payload(decode=True)
            if data is None:
                continue
            att_path = att_dir / f"{attachments_prefix}{safe_filename(part.get_filename())}"
            att_path.write_bytes(data)
            written.append(str(att_path))

    if frontmatter is None:
        lines = [
            f"# {subject or output_path.stem}",
            "",
            f"- From: {decode_header_value(msg.get('From'))}",
            f"- To: {decode_header_value(msg.get('To'))}",
            f"- Date: {msg.get('Date', '')}",
            "",
            body,
        ]
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).strip("\n") + "\n", encoding="utf-8")
    return output_path, written


def eml_to_markdown(source, output_path, settings=None):
    """Convert an .eml file into a simple Markdown file (legacy signature).

    Thin wrapper over :func:`mail_to_markdown` — kept for backwards
    compatibility (NFR-004).
    """
    source = Path(source)
    out, _written = mail_to_markdown(source.read_bytes(), output_path, settings=settings)
    return out
