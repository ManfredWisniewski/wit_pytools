"""Sync pipeline: per-file processing, upsert decisions, result reporting."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .client import PayloadAuthError
from .config import PayloadConfigError
from .links import rewrite_internal_links, rewrite_markers
from .media import rewrite_image_refs
from .meta import extract_meta, strip_front_matter
from .scan import build_route_index, scan_repo
from .transforms import apply_transforms

# doc fields compared to decide unchanged vs updated
_COMPARED_FIELDS = ("title", "slug", "path", "markdownRaw", "sourceRepo",
                    "template")
_COMPARED_META_FIELDS = ("title", "description",)

# +structure/*.yml|*.yaml each map to one `structures` document (name = stem)
STRUCTURE_PATTERNS = ("+structure/*.yml", "+structure/*.yaml")


@dataclass
class FileResult:
    relpath: str
    status: str
    detail: str = ""


def build_payload(entry, markdown, meta_values, config):
    """Assemble the Payload page document body."""
    title = meta_values.get("title") or entry.slug
    return {
        "title": title,
        "slug": entry.slug,
        "path": entry.route,
        "markdownRaw": markdown,
        "sourcePath": entry.relpath,
        "sourceRepo": config.source_repo,
        "template": meta_values.get("template") or "",
        "meta": {
            "title": meta_values.get("title") or "",
            "description": meta_values.get("description") or "",
        },
    }


def _unchanged(existing, payload):
    """True when the remote doc already matches the payload fields."""
    for field_name in _COMPARED_FIELDS:
        if (existing.get(field_name) or "") != payload[field_name]:
            return False
    existing_meta = existing.get("meta") or {}
    return all(
        (existing_meta.get(key) or "") == payload["meta"][key]
        for key in _COMPARED_META_FIELDS
    )


def scan_structures(config):
    """+structure/*.yml|*.yaml files, each -> one `structures` document."""
    paths = [
        path
        for pattern in STRUCTURE_PATTERNS
        for path in config.repo.glob(pattern)
    ]
    return sorted(path for path in paths if path.is_file())


def _unchanged_structure(existing, payload):
    """True when name, data, sourcePath and sourceRepo already match."""
    return (
        existing.get("name") == payload["name"]
        and (existing.get("data") or {}) == payload["data"]
        and (existing.get("sourcePath") or "") == payload["sourcePath"]
        and (existing.get("sourceRepo") or "") == payload["sourceRepo"]
    )


def process_structure(path, config, client, *, dry_run=False):
    """Upsert one structure YAML into `structures`; drafts only.

    Upsert key is `name` (unique per collection) — a file move therefore
    updates the existing doc's sourcePath instead of creating a duplicate.
    """
    relpath = path.relative_to(config.repo).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        payload = {
            "name": path.stem,
            "data": data,
            "sourcePath": relpath,
            "sourceRepo": config.source_repo,
        }
        existing = client.find_doc("structures", "name", path.stem)
        if existing is None:
            if not dry_run:
                client.create_doc("structures", payload)
            return FileResult(relpath, "created")
        if (existing.get("sourceRepo") or "") != payload["sourceRepo"]:
            return FileResult(
                relpath, "failed",
                f"name '{path.stem}' already used by repo "
                f"'{existing.get('sourceRepo')}'",
            )
        if _unchanged_structure(existing, payload):
            return FileResult(relpath, "unchanged")
        if not dry_run:
            client.update_doc("structures", existing["id"], payload)
        return FileResult(relpath, "updated")
    except PayloadAuthError:
        raise  # auth errors are run-level, not per-file
    except Exception as error:
        return FileResult(relpath, "failed", str(error))


def process_entry(entry, config, client, route_index, *,
                  media_only=False, dry_run=False):
    """Run the per-file pipeline; never aborts on per-file errors."""
    if not entry.publishable:
        return FileResult(entry.relpath, "skipped", f"status={entry.status}")
    try:
        text = entry.path.read_text(encoding="utf-8")
        meta_values = extract_meta(
            text, entry.path.parent, config.meta.get("briefing_glob", "")
        )
        stripped = strip_front_matter(text)
        line_offset = text.count("\n") - stripped.count("\n")
        text, uploads = rewrite_image_refs(
            stripped, entry, config, client, dry_run=dry_run,
            line_offset=line_offset,
        )
        if media_only:
            status = "created" if uploads else "unchanged"
            return FileResult(
                entry.relpath, status, f"media uploads: {uploads}"
            )
        text = rewrite_internal_links(text, entry, config.repo, route_index)
        text = rewrite_markers(text, config.links)
        text = apply_transforms(text, config.transforms)
        payload = build_payload(entry, text, meta_values, config)

        existing = client.find_doc(
            config.collection, "sourcePath", entry.relpath
        )
        if existing is None:
            if not dry_run:
                client.create_doc(config.collection, payload)
            return FileResult(entry.relpath, "created")
        if _unchanged(existing, payload):
            return FileResult(entry.relpath, "unchanged")
        if not dry_run:
            client.update_doc(config.collection, existing["id"], payload)
        return FileResult(entry.relpath, "updated")
    except PayloadAuthError:
        raise  # auth errors are run-level, not per-file
    except Exception as error:
        return FileResult(entry.relpath, "failed", str(error))


def sync_repo(config, client, *, only_file=None,
              media_only=False, dry_run=False):
    """Process all (or one) webtext + structure files; -> FileResult list."""
    entries = scan_repo(config)
    route_index = build_route_index(entries)
    structures = [] if media_only else scan_structures(config)
    if only_file:
        resolved = Path(only_file)
        if not resolved.is_absolute():
            resolved = (config.repo / resolved).resolve()
        try:
            rel = resolved.relative_to(config.repo.resolve()).as_posix()
        except ValueError:
            rel = Path(only_file).as_posix()
        entries = [e for e in entries if e.relpath == rel]
        structures = [
            p for p in structures
            if p.relative_to(config.repo).as_posix() == rel
        ]
        if not entries and not structures:
            raise PayloadConfigError(
                f"{only_file} does not match include_glob "
                f"or {STRUCTURE_PATTERNS[0]}"
            )
    results = [
        process_entry(
            entry, config, client, route_index,
            media_only=media_only, dry_run=dry_run,
        )
        for entry in entries
    ]
    results += [
        process_structure(path, config, client, dry_run=dry_run)
        for path in structures
    ]
    return results
