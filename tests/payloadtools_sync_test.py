#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import PayloadConfigError, load_config
from wit_pytools.payloadtools.scan import scan_repo
from wit_pytools.payloadtools.sync import build_payload, sync_repo
from wit_pytools.payloadtools.transforms import apply_transforms

from wit_pytools.tests.payloadtools_fakes import FakeClient

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def _statuses(results):
    return {r.relpath: r.status for r in results}


def test_full_sync_statuses():
    config = load_config(REPO)
    results = sync_repo(config, FakeClient())
    statuses = _statuses(results)
    assert statuses == {
        "_kategorie_hidden/page_webtext_online-locked.md": "created",
        "home_webtext_locked.md": "created",
        "kategorie_products/broken_webtext_locked.md": "failed",
        "kategorie_products/prod_webtext_locked.md": "created",
        "notes_webtext_entwurf.md": "skipped",
        "plain_webtext.md": "created",
        "produkt_widget/detail_webtext_locked-online.md": "created",
        "produkt_widget/old_produkt/legacy_webtext_locked.md": "created",
    }


def test_created_payload_content():
    config = load_config(REPO)
    client = FakeClient()
    sync_repo(config, client)
    payloads = {p["sourcePath"]: p for _, p in client.created}
    prod = payloads["kategorie_products/prod_webtext_locked.md"]
    assert prod["slug"] == "prod"
    assert prod["path"] == "/products/prod"
    assert prod["title"] == "Prod SEO Title"
    assert prod["meta"]["description"] == "Prod SEO description here."
    assert "![media:media-1]()" in prod["markdownRaw"]
    assert "[home](/)" in prod["markdownRaw"]
    assert "[widget specs](/widget/detail#specs)" in prod["markdownRaw"]
    assert "<button>Buy now</button>" in prod["markdownRaw"]
    assert prod["sourceRepo"] == "witrepo"


def test_unchanged_when_doc_matches():
    config = load_config(REPO)
    probe = FakeClient()
    sync_repo(config, probe)
    home_payload = next(
        p for _, p in probe.created
        if p["sourcePath"] == "home_webtext_locked.md"
    )
    existing = dict(home_payload)
    existing["id"] = "doc-1"
    client = FakeClient(docs={("pages", "home_webtext_locked.md"): existing})
    results = sync_repo(
        config, client, only_file="home_webtext_locked.md"
    )
    assert _statuses(results) == {"home_webtext_locked.md": "unchanged"}
    assert client.created == []
    assert client.updated == []


def test_updated_when_doc_differs():
    config = load_config(REPO)
    existing = {
        "id": "doc-1",
        "title": "Old",
        "slug": "home",
        "path": "/",
        "markdownRaw": "stale",
        "sourceRepo": "witrepo",
        "meta": {"title": "Old", "description": ""},
    }
    client = FakeClient(docs={("pages", "home_webtext_locked.md"): existing})
    results = sync_repo(
        config, client, only_file="home_webtext_locked.md"
    )
    assert _statuses(results) == {"home_webtext_locked.md": "updated"}
    assert client.updated[0][1] == "doc-1"


def test_dry_run_performs_no_writes():
    config = load_config(REPO)
    client = FakeClient(fail_writes=True)
    results = sync_repo(config, client, dry_run=True)
    statuses = _statuses(results)
    assert statuses["home_webtext_locked.md"] == "created"
    assert statuses["notes_webtext_entwurf.md"] == "skipped"
    assert client.created == []
    assert client.updated == []
    assert client.uploads == []
    assert client.gets > 0  # reads still happen


def test_media_only_pass():
    config = load_config(REPO)
    client = FakeClient()
    results = sync_repo(config, client, media_only=True)
    statuses = _statuses(results)
    assert statuses["kategorie_products/prod_webtext_locked.md"] == "created"
    assert statuses["home_webtext_locked.md"] == "unchanged"
    assert statuses["kategorie_products/broken_webtext_locked.md"] == "failed"
    assert client.created == []
    assert len(client.uploads) == 1


def test_apply_transforms_rules():
    rules = [{"pattern": r"\[Link:\s*(.+?)\]", "replacement": r"<\1>"}]
    assert apply_transforms("[Link: X]", rules) == "<X>"
    assert apply_transforms("unchanged", rules) == "unchanged"


def test_build_payload_title_fallback():
    config = load_config(REPO)
    entries = {e.relpath: e for e in scan_repo(config)}
    entry = entries["plain_webtext.md"]
    payload = build_payload(
        entry, "text", {"title": "", "description": ""}, config
    )
    assert payload["title"] == "plain"
    assert "_status" not in payload  # never publish via API


def test_build_payload_includes_template():
    config = load_config(REPO)
    entries = {e.relpath: e for e in scan_repo(config)}
    entry = entries["plain_webtext.md"]
    payload = build_payload(
        entry, "text",
        {"title": "", "description": "", "template": "landing"},
        config,
    )
    assert payload["template"] == "landing"
    assert "_status" not in payload


NAV_YAML = "items:\n  - {label: Home, path: /}\n  - {label: MDM, path: /mdm}\n"


def _structure_repo(tmp_path, body):
    """Minimal config + ++structure/navigation.yml in a temp repo."""
    (tmp_path / ".arrcontent.yml").write_text(
        "collection: pages\n", encoding="utf-8"
    )
    (tmp_path / "+structure").mkdir()
    (tmp_path / "+structure" / "navigation.yml").write_text(
        body, encoding="utf-8"
    )
    return load_config(tmp_path)


def test_structure_created(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    client = FakeClient()
    results = sync_repo(config, client)
    assert _statuses(results) == {"+structure/navigation.yml": "created"}
    collection, payload = client.created[0]
    assert collection == "structures"
    assert payload["name"] == "navigation"
    assert payload["data"]["items"][1] == {"label": "MDM", "path": "/mdm"}
    assert payload["sourcePath"] == "+structure/navigation.yml"
    assert "_status" not in payload


def test_structure_unchanged(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    probe = FakeClient()
    sync_repo(config, probe)
    existing = dict(probe.created[0][1])
    existing["id"] = "s-1"
    client = FakeClient(
        docs={("structures", "navigation"): existing}
    )
    results = sync_repo(config, client)
    assert _statuses(results) == {"+structure/navigation.yml": "unchanged"}
    assert client.created == [] and client.updated == []


def test_structure_updated(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    existing = {
        "id": "s-1", "name": "navigation",
        "data": {"items": []}, "sourceRepo": config.source_repo,
    }
    client = FakeClient(
        docs={("structures", "navigation"): existing}
    )
    results = sync_repo(config, client)
    assert _statuses(results) == {"+structure/navigation.yml": "updated"}
    assert client.updated[0][1] == "s-1"


def test_structure_moved_file_updates_sourcepath(tmp_path):
    """Same name at a new path -> update, not duplicate create."""
    config = _structure_repo(tmp_path, NAV_YAML)
    existing = {
        "id": "s-1", "name": "navigation",
        "data": {"items": [{"label": "Home", "path": "/"},
                           {"label": "MDM", "path": "/mdm"}]},
        "sourcePath": "structure/navigation.yml",
        "sourceRepo": config.source_repo,
    }
    client = FakeClient(
        docs={("structures", "navigation"): existing}
    )
    results = sync_repo(config, client)
    assert _statuses(results) == {"+structure/navigation.yml": "updated"}
    assert client.created == []
    assert client.updated[0][2]["sourcePath"] == "+structure/navigation.yml"


def test_structure_name_used_by_other_repo(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    existing = {
        "id": "s-9", "name": "navigation",
        "data": {}, "sourceRepo": "other-repo",
    }
    client = FakeClient(
        docs={("structures", "navigation"): existing}
    )
    results = sync_repo(config, client)
    assert _statuses(results) == {"+structure/navigation.yml": "failed"}
    assert client.created == [] and client.updated == []


def test_structure_dry_run_no_writes(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    client = FakeClient(fail_writes=True)
    results = sync_repo(config, client, dry_run=True)
    assert _statuses(results) == {"+structure/navigation.yml": "created"}
    assert client.created == []


def test_structure_malformed_yaml(tmp_path):
    config = _structure_repo(tmp_path, "items: [unclosed\n")
    results = sync_repo(config, FakeClient())
    assert _statuses(results) == {"+structure/navigation.yml": "failed"}


def test_media_only_skips_structures(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    results = sync_repo(config, FakeClient(), media_only=True)
    assert results == []


def test_only_file_structure(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    results = sync_repo(
        config, FakeClient(), only_file="+structure/navigation.yml"
    )
    assert _statuses(results) == {"+structure/navigation.yml": "created"}


def test_only_file_unknown_raises(tmp_path):
    config = _structure_repo(tmp_path, NAV_YAML)
    with pytest.raises(PayloadConfigError):
        sync_repo(config, FakeClient(), only_file="+structure/missing.yml")
