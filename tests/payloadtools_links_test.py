#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import load_config
from wit_pytools.payloadtools.links import rewrite_internal_links
from wit_pytools.payloadtools.scan import build_route_index, scan_repo

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def _setup():
    config = load_config(REPO)
    entries = {e.relpath: e for e in scan_repo(config)}
    index = build_route_index(entries.values())
    return config, entries, index


def test_internal_links_rewritten():
    config, entries, index = _setup()
    entry = entries["kategorie_products/prod_webtext_locked.md"]
    text = entry.path.read_text(encoding="utf-8")
    rewritten = rewrite_internal_links(text, entry, config.repo, index)
    assert "[home](/)" in rewritten
    assert "[widget specs](/widget/detail#specs)" in rewritten


def test_link_to_skipped_file_untouched():
    config, entries, index = _setup()
    entry = entries["kategorie_products/prod_webtext_locked.md"]
    text = entry.path.read_text(encoding="utf-8")
    rewritten = rewrite_internal_links(text, entry, config.repo, index)
    assert "[draft](../notes_webtext_entwurf.md)" in rewritten


def test_external_and_non_md_links_untouched():
    config, entries, index = _setup()
    entry = entries["plain_webtext.md"]
    text = ("[ext](https://example.com)\n"
            "[anchor](#section)\n"
            "[pdf](doc.pdf)\n"
            "![img](pic.png)\n")
    rewritten = rewrite_internal_links(text, entry, config.repo, index)
    assert rewritten == text


def test_unknown_md_link_untouched():
    config, entries, index = _setup()
    entry = entries["plain_webtext.md"]
    text = "[gone](missing_webtext_locked.md)\n"
    rewritten = rewrite_internal_links(text, entry, config.repo, index)
    assert rewritten == text


def test_link_title_preserved():
    config, entries, index = _setup()
    entry = entries["plain_webtext.md"]
    text = '[home](home_webtext_locked.md "Home title")\n'
    rewritten = rewrite_internal_links(text, entry, config.repo, index)
    assert rewritten == '[home](/ "Home title")\n'
