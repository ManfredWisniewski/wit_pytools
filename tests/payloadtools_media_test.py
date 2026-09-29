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
