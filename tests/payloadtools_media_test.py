#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import load_config
from wit_pytools.payloadtools.media import rewrite_image_refs, sha256_file
from wit_pytools.payloadtools.scan import scan_repo
from wit_pytools.payloadtools.sync import sync_media_dir

from wit_pytools.tests.payloadtools_fakes import FakeClient

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def _entry(relpath):
    config = load_config(REPO)
    entries = {e.relpath: e for e in scan_repo(config)}
    return config, entries[relpath]


def test_upload_new_image():
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient()
    text = entry.path.read_text(encoding="utf-8")
    rewritten, uploads = rewrite_image_refs(text, entry, config, client)
    assert uploads == 1
    assert "![media:media-1]()" in rewritten
    assert client.uploads[0]["alt"] == "prod pic"
    assert client.uploads[0]["source_path"] == (
        "kategorie_products/img/pic.png"
    )


def test_dedup_existing_source_hash():
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    digest = sha256_file(REPO / "kategorie_products" / "img" / "pic.png")
    client = FakeClient(media={digest: {"id": "existing-9"}})
    text = entry.path.read_text(encoding="utf-8")
    rewritten, uploads = rewrite_image_refs(text, entry, config, client)
    assert uploads == 0
    assert client.uploads == []
    assert "![media:existing-9]()" in rewritten


def test_dedup_across_files_same_run():
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient()
    text = entry.path.read_text(encoding="utf-8")
    rewrite_image_refs(text, entry, config, client)
    rewritten, uploads = rewrite_image_refs(text, entry, config, client)
    assert uploads == 0
    assert "![media:media-1]()" in rewritten


def test_dry_run_uses_hash_placeholder():
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient(fail_writes=True)
    text = entry.path.read_text(encoding="utf-8")
    digest = sha256_file(REPO / "kategorie_products" / "img" / "pic.png")
    rewritten, uploads = rewrite_image_refs(
        text, entry, config, client, dry_run=True
    )
    assert uploads == 0
    assert f"![media:{digest}]()" in rewritten
    assert client.uploads == []


def test_repo_root_media_fallback():
    # media/<file> resolves at the repo root from any page depth
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient()
    rewritten, uploads = rewrite_image_refs(
        "![hero](media/shared.png)", entry, config, client
    )
    assert uploads == 1
    assert client.uploads[0]["source_path"] == "media/shared.png"
    assert "![media:media-1]()" in rewritten


def test_leading_slash_anchors_repo_root():
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient()
    rewritten, uploads = rewrite_image_refs(
        "![hero](/media/shared.png)", entry, config, client
    )
    assert uploads == 1
    assert client.uploads[0]["source_path"] == "media/shared.png"


def test_page_relative_wins_over_repo_root():
    # kategorie_products/img/pic.png exists; no img/pic.png at repo root
    config, entry = _entry("kategorie_products/prod_webtext_locked.md")
    client = FakeClient()
    rewritten, uploads = rewrite_image_refs(
        "![pic](img/pic.png)", entry, config, client
    )
    assert uploads == 1
    assert client.uploads[0]["source_path"] == (
        "kategorie_products/img/pic.png"
    )


def test_media_dir_uploads_new_files():
    config = load_config(REPO)
    client = FakeClient()
    results = sync_media_dir(config, client)
    assert [(r.relpath, r.status) for r in results] == [
        ("media/notes.txt", "skipped"),
        ("media/shared.png", "created"),
    ]
    assert client.uploads[0]["source_path"] == "media/shared.png"


def test_media_dir_unchanged_when_doc_exists():
    config = load_config(REPO)
    digest = sha256_file(REPO / "media" / "shared.png")
    client = FakeClient(media={digest: {"id": "m-1", "sourceHash": digest,
                                        "sourcePath": "media/shared.png", "sourceRepo": "witrepo"}})
    results = sync_media_dir(config, client)
    assert [(r.relpath, r.status) for r in results] == [
        ("media/notes.txt", "skipped"),
        ("media/shared.png", "unchanged"),
    ]
    assert client.deleted == []


def test_media_dir_deletes_remote_for_excluded_type():
    # a .txt file on disk is excluded -> its remote doc is cleaned up
    config = load_config(REPO)
    client = FakeClient(media={
        "txthash": {"id": "m-4", "sourceHash": "txthash",
                    "sourcePath": "media/notes.txt", "sourceRepo": "witrepo"},
    })
    results = sync_media_dir(config, client)
    assert client.deleted == [("media", "m-4")]
    assert ("media/notes.txt", "deleted") in [
        (r.relpath, r.status) for r in results
    ]


def test_media_dir_deletes_missing_remote():
    config = load_config(REPO)
    client = FakeClient(media={
        "oldhash": {"id": "m-9", "sourceHash": "oldhash",
                    "sourcePath": "media/old.png", "sourceRepo": "witrepo"},
    })
    results = sync_media_dir(config, client)
    assert client.deleted == [("media", "m-9")]
    assert ("media/old.png", "deleted") in [
        (r.relpath, r.status) for r in results
    ]


def test_media_dir_keeps_docs_outside_prefix():
    config = load_config(REPO)
    client = FakeClient(media={
        "h1": {"id": "m-5", "sourceHash": "h1",
               "sourcePath": "kategorie_products/img/pic.png"},
    })
    sync_media_dir(config, client)
    assert client.deleted == []


def test_media_dir_keeps_doc_when_hash_still_present():
    # media/old.png is gone but an identical file exists under media/
    config = load_config(REPO)
    digest = sha256_file(REPO / "media" / "shared.png")
    client = FakeClient(media={
        digest: {"id": "m-7", "sourceHash": digest,
                 "sourcePath": "media/old.png", "sourceRepo": "witrepo"},
    })
    sync_media_dir(config, client)
    assert client.deleted == []


def test_media_dir_dry_run_reports_only():
    config = load_config(REPO)
    client = FakeClient(
        media={"oldhash": {"id": "m-9", "sourceHash": "oldhash",
                           "sourcePath": "media/old.png", "sourceRepo": "witrepo"}},
        fail_writes=True,
    )
    results = sync_media_dir(config, client, dry_run=True)
    statuses = {(r.relpath, r.status) for r in results}
    assert ("media/shared.png", "created") in statuses
    assert ("media/old.png", "deleted") in statuses
    assert client.uploads == [] and client.deleted == []


def test_missing_image_raises():
    config, entry = _entry("kategorie_products/broken_webtext_locked.md")
    text = entry.path.read_text(encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        rewrite_image_refs(text, entry, config, FakeClient())


def test_external_and_placeholder_refs_untouched():
    config, entry = _entry("plain_webtext.md")
    text = "![a](https://x/y.png)\n\n![media:abc]()\n"
    rewritten, uploads = rewrite_image_refs(
        text, entry, config, FakeClient()
    )
    assert rewritten == text
    assert uploads == 0
