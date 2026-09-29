"""Rewrite internal markdown links (.md targets) to derived routes."""

import re
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "data:", "media:", "mailto:")


def split_target(raw):
    """Split a markdown link target into (path, trailing extras like title)."""
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        end = raw.index(">")
        return raw[1:end], raw[end + 1:]
    parts = raw.split(None, 1)
    if not parts:
        return "", ""
    return parts[0], (parts[1] if len(parts) > 1 else "")


def is_external(target):
    return not target or target.startswith(EXTERNAL_PREFIXES)


def rewrite_internal_links(text, entry, repo_root, route_index):
    """Rewrite [text](rel/file.md#frag) to [text](/route#frag) via index."""
    def replace(match):
        target, extra = split_target(match.group(2))
        if is_external(target):
            return match.group(0)
        file_part, _, fragment = target.partition("#")
        if not file_part.lower().endswith(".md"):
            return match.group(0)
        resolved = (entry.path.parent / file_part).resolve()
        try:
            relpath = resolved.relative_to(Path(repo_root).resolve())
        except ValueError:
            return match.group(0)
        route = route_index.get(relpath.as_posix())
        if route is None:
            return match.group(0)
        suffix = f"#{fragment}" if fragment else ""
        extra = f" {extra.strip()}" if extra.strip() else ""
        return f"[{match.group(1)}]({route}{suffix}{extra})"

    return LINK_RE.sub(replace, text)
