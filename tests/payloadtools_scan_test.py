#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import load_config
from wit_pytools.payloadtools.scan import (
    build_route_index,
    derive_route,
    derive_slug,
    is_publishable,
    parse_stem,
    scan_repo,
)

REPO = Path(__file__).parent / "payloadtools" / "witrepo"
STATUS_RE = r"_webtext(?P<sep>[-_])(?P<status>[a-z-]+)$"
PUBLISHABLE = ["locked", "locked-online", "online-locked"]


def test_parse_stem_simple_status():
    assert parse_stem("prod_webtext_locked", STATUS_RE) == ("prod", "locked")


def test_parse_stem_hyphenated_status():
    assert parse_stem("detail_webtext_locked-online", STATUS_RE) == (
        "detail", "locked-online",
    )
    assert parse_stem("page_webtext_online-locked", STATUS_RE) == (
        "page", "online-locked",
    )


def test_parse_stem_prefixed_name():
    assert parse_stem("SEOP_foo_webtext_locked", STATUS_RE) == (
        "SEOP_foo", "locked",
    )


def test_parse_stem_no_status():
    assert parse_stem("plain_webtext", STATUS_RE) == ("plain", None)


def test_parse_stem_marker_without_separator():
    assert parse_stem("x_webtexty", STATUS_RE) == ("x_webtexty", None)


def test_is_publishable():
    assert is_publishable(None, PUBLISHABLE) is True
    assert is_publishable("locked", PUBLISHABLE) is True
    assert is_publishable("locked-online", PUBLISHABLE) is True
    assert is_publishable("entwurf", PUBLISHABLE) is False


def test_derive_slug_strips_prefixes():
    assert derive_slug("SEOP_foo", ["SEOP_"]) == "foo"
    assert derive_slug("plain", ["SEOP_"]) == "plain"


def test_derive_route_directory_styles():
    route_cfg = load_config(REPO).route
    assert derive_route(
        "kategorie_products/prod_webtext_locked.md", "prod", route_cfg
    ) == "/products/prod"
    assert derive_route(
        "produkt_widget/detail_webtext_locked-online.md", "detail", route_cfg
    ) == "/widget/detail"
    assert derive_route(
        "_kategorie_hidden/page_webtext_online-locked.md", "page", route_cfg
    ) == "/hidden/page"
    assert derive_route(
        "produkt_widget/old_produkt/legacy_webtext_locked.md",
        "legacy", route_cfg,
    ) == "/widget/old/legacy"


def test_derive_route_root_and_override():
    route_cfg = load_config(REPO).route
    assert derive_route(
        "home_webtext_locked.md", "home", route_cfg
    ) == "/"
    assert derive_route(
        "plain_webtext.md", "plain", route_cfg
    ) == "/plain"


def test_scan_repo_publishable_flags():
    entries = {e.relpath: e for e in scan_repo(load_config(REPO))}
    assert len(entries) == 8
    assert entries["notes_webtext_entwurf.md"].publishable is False
    assert entries["notes_webtext_entwurf.md"].status == "entwurf"
    assert entries["plain_webtext.md"].publishable is True
    assert entries["plain_webtext.md"].status is None
    assert entries["home_webtext_locked.md"].route == "/"
    assert entries["kategorie_products/prod_webtext_locked.md"].route == (
        "/products/prod"
    )


def test_build_route_index_excludes_skipped():
    entries = scan_repo(load_config(REPO))
    index = build_route_index(entries)
    assert "notes_webtext_entwurf.md" not in index
    assert index["home_webtext_locked.md"] == "/"
    assert index["kategorie_products/prod_webtext_locked.md"] == "/products/prod"
