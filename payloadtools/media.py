"""Media reference rewriting: sha256 dedup and upload via the Payload API."""

import hashlib
import re
from pathlib import Path

from .links import is_external, split_target

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def sha256_file(path):
    """SHA-256 hex digest of a file, used as media dedup key."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_image_path(target, entry, repo):
    """Resolve an image ref to a file path.

    Page-relative first; falls back to repo-root relative so a shared
    `media/` directory works from any page depth. A leading '/' anchors
    at the repo root. Returns the first hit, else the root-relative
    candidate for error reporting. Paths resolving outside the repo are
    never probed (prevents UNC/SMB access on Windows before the
    containment check downstream).
    """
    root = repo.resolve()

    def inside(path):
        resolved = path.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return None
        return resolved

    if target.startswith("/"):
        return inside(root / target.lstrip("/")) or root / "__missing__"
    page_path = inside(entry.path.parent / target)
    if page_path is not None and page_path.is_file():
        return page_path
    return inside(root / target) or root / "__missing__"


def ensure_media_doc(image_path, config, client, *, dry_run=False, alt=""):
    """Return (media_id, uploaded) for a local file inside the repo.

    Dedup key is the file's sha256; in dry-run the digest stands in as
    deterministic id and nothing is uploaded.
    """
    source_path = image_path.relative_to(config.repo.resolve()).as_posix()
    digest = sha256_file(image_path)
    existing = client.find_doc(config.media_collection, "sourceHash", digest)
    if existing is not None:
        return str(existing.get("id")), False
    if dry_run:
        return digest, False
    media_id = client.upload_media(
        image_path,
        collection=config.media_collection,
        alt=alt,
        source_hash=digest,
        source_path=source_path,
        source_repo=config.source_repo,
    )
    return media_id, True


def rewrite_image_refs(text, entry, config, client, *, dry_run=False,
                       line_offset=0):
    """Rewrite ![alt](relpath) to ![media:<docId>]() placeholders.

    Uploads the image when no Media doc matches its sha256; in dry-run no
    upload happens and the hash itself is used as deterministic placeholder.
    line_offset shifts reported line numbers (stripped front matter).
    Returns (rewritten_text, upload_count).
    """
    uploads = 0

    def replace(match):
        nonlocal uploads
        alt, raw_target = match.group(1), match.group(2)
        target, _extra = split_target(raw_target)
        if is_external(target):
            return match.group(0)
        image_path = resolve_image_path(target, entry, config.repo)
        if not image_path.is_file():
            line = line_offset + text[:match.start()].count("\n") + 1
            try:
                expected = image_path.relative_to(
                    config.repo.resolve()
                ).as_posix()
            except ValueError:
                expected = str(image_path)
            raise FileNotFoundError(
                f"{entry.relpath}:{line}: missing image '{target}' "
                f"(expected at {expected})"
            )
        media_id, uploaded = ensure_media_doc(
            image_path, config, client, dry_run=dry_run, alt=alt
        )
        uploads += int(uploaded)
        return f"![media:{media_id}]()"

    return IMAGE_RE.sub(replace, text), uploads
