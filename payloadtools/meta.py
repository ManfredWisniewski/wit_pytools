"""Meta extraction: front matter, SEO_* briefings, heading fallback."""

import re
from pathlib import Path

import yaml

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,2}\s+(.+?)\s*#*\s*$", re.MULTILINE)
KEY_VALUE_RE = re.compile(
    r"^(?:meta[-_])?(title|description)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_TITLE_KEYS = ("title", "meta_title", "meta-title")
_DESC_KEYS = ("description", "meta_description", "meta-description")


def _front_matter(text):
    """Parse a leading YAML front matter block into a dict."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else {}


def _pick(mapping, keys):
    """Pick the first non-empty key value, also checking a nested meta map."""
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value).strip()
    nested = mapping.get("meta")
    if isinstance(nested, dict):
        for key in keys:
            value = nested.get(key)
            if value:
                return str(value).strip()
    return ""


def _meta_from_text(text):
    """Extract (title, description) from front matter or key: value lines."""
    data = _front_matter(text)
    title = _pick(data, _TITLE_KEYS)
    description = _pick(data, _DESC_KEYS)
    if not title or not description:
        for match in KEY_VALUE_RE.finditer(text):
            key, value = match.group(1).lower(), match.group(2)
            if key == "title" and not title:
                title = value
            elif key == "description" and not description:
                description = value
    return title, description


def extract_meta(text, file_dir, briefing_glob=""):
    """Return {"title": ..., "description": ...} for a webtext file.

    Order: file front matter / key lines, then companion briefing files
    matching briefing_glob in the same directory, then first heading.
    """
    title, description = _meta_from_text(text)
    if briefing_glob and (not title or not description):
        for briefing in sorted(Path(file_dir).glob(briefing_glob)):
            if not briefing.is_file():
                continue
            b_title, b_desc = _meta_from_text(
                briefing.read_text(encoding="utf-8")
            )
            title = title or b_title
            description = description or b_desc
            if title and description:
                break
    if not title:
        heading = HEADING_RE.search(text)
        title = heading.group(1).strip() if heading else ""
    return {"title": title, "description": description}
