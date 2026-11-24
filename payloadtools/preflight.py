"""Preflight checks on publishable content (local scan, no API calls)."""

import re

from .config import PayloadConfigError
from .meta import strip_front_matter
from .scan import scan_repo

# fenced code blocks: ``` or ~~~ marker with up to 3 leading spaces
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")

# inline code spans: `x` or ``x`y`` — matched backtick pairs
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")

# html tags, comments and named entities (autolinks <scheme:..> excluded)
HTML_RE = re.compile(
    r"<!--"
    r"|</?[a-zA-Z][a-zA-Z0-9-]*(?:\s[^<>]*)?/?>"
    r"|&[a-zA-Z][a-zA-Z0-9]+;"
)


def find_html_outside_code(text):
    """Return (lineno, line) for each line with HTML outside code blocks."""
    findings = []
    fence = None
    for lineno, line in enumerate(text.split("\n"), start=1):
        marker = FENCE_RE.match(line)
        if marker:
            marker = marker.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        if HTML_RE.search(INLINE_CODE_RE.sub("", line)):
            findings.append((lineno, line.strip()))
    return findings


def check_publishable_html(config):
    """(relpath, lineno, line) findings across publishable webtext files."""
    findings = []
    for entry in scan_repo(config):
        if not entry.publishable:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8")
        except OSError as error:
            raise PayloadConfigError(
                f"Cannot read {entry.relpath}: {error}"
            ) from error
        stripped = strip_front_matter(text)
        offset = text.count("\n") - stripped.count("\n")
        findings += [
            (entry.relpath, lineno + offset, line)
            for lineno, line in find_html_outside_code(stripped)
        ]
    return findings
