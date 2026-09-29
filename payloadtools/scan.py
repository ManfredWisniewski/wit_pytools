"""Repository scanning: filename/status parsing and route derivation."""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

WEBTEXT_MARKER = "_webtext"


@dataclass
class ScanEntry:
    relpath: str          # repo-relative path, posix separators
    path: Path            # absolute path
    slug: str
    status: str | None    # None = no status suffix -> publishable
    publishable: bool
    route: str


def parse_stem(stem, status_pattern):
    """Split a file stem into (base, status). status is None if absent.

    status_pattern may be a regex string or a compiled re.Pattern.
    """
    if isinstance(status_pattern, str):
        status_pattern = re.compile(status_pattern)
    match = status_pattern.search(stem)
    if match:
        return stem[: match.start()], match.group("status")
    if stem.endswith(WEBTEXT_MARKER):
        return stem[: -len(WEBTEXT_MARKER)], None
    return stem, None


def is_publishable(status, publishable_statuses):
    """No-status files are publishable; others need whitelist membership."""
    return status is None or status in publishable_statuses


def derive_slug(base, slug_prefixes):
    """Strip configured filename prefixes (e.g. SEOP_) from the slug."""
    slug = base
    for prefix in slug_prefixes:
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
    return slug


def _clean_dirname(name, route_cfg):
    for prefix in route_cfg.strip_dir_prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in route_cfg.strip_dir_suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if route_cfg.strip_leading_underscore and name.startswith("_"):
        name = name[1:]
    return name


def derive_route(relpath, slug, route_cfg):
    """Derive the public route from directory structure plus slug."""
    if relpath in route_cfg.overrides:
        return route_cfg.overrides[relpath]
    dirnames = PurePosixPath(relpath).parent.parts
    segments = [
        cleaned
        for cleaned in (_clean_dirname(d, route_cfg) for d in dirnames)
        if cleaned
    ]
    return "/" + "/".join([*segments, slug])


def scan_repo(config):
    """Scan the repo for webtext files and return ScanEntry list."""
    entries = []
    status_pattern = re.compile(config.status_regex)
    for path in sorted(config.repo.glob(config.include_glob)):
        if not path.is_file():
            continue
        relpath = path.relative_to(config.repo).as_posix()
        base, status = parse_stem(path.stem, status_pattern)
        slug = derive_slug(base, config.slug_prefixes)
        entries.append(ScanEntry(
            relpath=relpath,
            path=path,
            slug=slug,
            status=status,
            publishable=is_publishable(status, config.publishable_statuses),
            route=derive_route(relpath, slug, config.route),
        ))
    return entries


def build_route_index(entries):
    """Map relpath -> route for all publishable entries (link rewriting)."""
    return {e.relpath: e.route for e in entries if e.publishable}
