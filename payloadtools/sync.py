"""Sync pipeline: per-file processing, upsert decisions, result reporting."""

from dataclasses import dataclass
from pathlib import Path

from .client import PayloadAuthError
from .config import PayloadConfigError
from .links import rewrite_internal_links
from .media import rewrite_image_refs
from .meta import extract_meta
from .scan import build_route_index, scan_repo
from .transforms import apply_transforms

# doc fields compared to decide unchanged vs updated
_COMPARED_FIELDS = ("title", "slug", "path", "markdownRaw", "sourceRepo")
_COMPARED_META_FIELDS = ("title", "description")


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
        text, uploads = rewrite_image_refs(
            text, entry, config, client, dry_run=dry_run
        )
        if media_only:
            status = "created" if uploads else "unchanged"
            return FileResult(
                entry.relpath, status, f"media uploads: {uploads}"
            )
        text = rewrite_internal_links(text, entry, config.repo, route_index)
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
    """Process all (or one) webtext files; returns list of FileResult."""
    entries = scan_repo(config)
    route_index = build_route_index(entries)
    if only_file:
        resolved = Path(only_file)
        if not resolved.is_absolute():
            resolved = (config.repo / resolved).resolve()
        try:
            rel = resolved.relative_to(config.repo.resolve()).as_posix()
        except ValueError:
            rel = Path(only_file).as_posix()
        entries = [e for e in entries if e.relpath == rel]
        if not entries:
            raise PayloadConfigError(
                f"{only_file} does not match include_glob"
            )
    return [
        process_entry(
            entry, config, client, route_index,
            media_only=media_only, dry_run=dry_run,
        )
        for entry in entries
    ]
