"""Preflight checks on publishable content (local scan, no API calls)."""

import re

from .config import PayloadConfigError
from .meta import extract_meta, strip_front_matter
from .scan import scan_repo

# fenced code blocks: ``` or ~~~ marker with up to 3 leading spaces
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")

# inline code spans: `x` or ``x`y`` — matched backtick pairs
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")

# standard html element names — custom elements like <witSpace/>
# (payload block modules) are not html and never flag
HTML_TAGS = frozenset(
    "a abbr address area article aside audio b base bdi bdo blockquote "
    "body br button canvas caption cite code col colgroup data datalist "
    "dd del details dfn dialog div dl dt em embed fieldset figcaption "
    "figure footer form h1 h2 h3 h4 h5 h6 head header hgroup hr html i "
    "iframe img input ins kbd label legend li link main map mark math "
    "menu meta meter nav noscript object ol optgroup option output p "
    "picture pre progress q rp rt ruby s samp script search section "
    "select slot small source span strong style sub summary sup svg "
    "table tbody td template textarea tfoot th thead time title tr "
    "track u ul var video wbr".split()
)

# tag candidates, comments and named entities (autolinks excluded)
TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)(?:\s[^<>]*)?/?>")
COMMENT_RE = re.compile(r"<!--")
ENTITY_RE = re.compile(r"&[a-zA-Z][a-zA-Z0-9]+;")


def line_has_html(line):
    """True when the line contains a real html tag, comment or entity."""
    if COMMENT_RE.search(line) or ENTITY_RE.search(line):
        return True
    return any(
        match.group(1).lower() in HTML_TAGS
        for match in TAG_RE.finditer(line)
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
        if line_has_html(INLINE_CODE_RE.sub("", line)):
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
        if extract_meta(text, entry.path.parent).get("template") == "slide":
            continue  # slide decks (reveal.js) legitimately embed html
        stripped = strip_front_matter(text)
        offset = text.count("\n") - stripped.count("\n")
        findings += [
            (entry.relpath, lineno + offset, line)
            for lineno, line in find_html_outside_code(stripped)
        ]
    return findings
