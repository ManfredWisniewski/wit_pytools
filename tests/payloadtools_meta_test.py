#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.meta import extract_meta

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def test_front_matter_meta():
    path = REPO / "produkt_widget" / "detail_webtext_locked-online.md"
    meta = extract_meta(path.read_text(encoding="utf-8"), path.parent)
    assert meta == {
        "title": "Widget Detail",
        "description": "All about the widget.",
    }


def test_key_value_lines_meta():
    text = "Some intro.\n\ntitle: KV Title\ndescription: KV desc.\n"
    meta = extract_meta(text, REPO)
    assert meta["title"] == "KV Title"
    assert meta["description"] == "KV desc."


def test_briefing_fallback():
    path = REPO / "kategorie_products" / "prod_webtext_locked.md"
    meta = extract_meta(
        path.read_text(encoding="utf-8"), path.parent,
        briefing_glob="SEO_*",
    )
    assert meta["title"] == "Prod SEO Title"
    assert meta["description"] == "Prod SEO description here."


def test_heading_fallback():
    path = REPO / "plain_webtext.md"
    meta = extract_meta(
        path.read_text(encoding="utf-8"), path.parent,
        briefing_glob="SEO_*",
    )
    assert meta["title"] == "Plain Page"
    assert meta["description"] == ""


def test_meta_fields_not_in_content():
    text = "# Heading\n\nSome text without meta lines.\n"
    meta = extract_meta(text, REPO)
    assert meta["title"] == "Heading"
    assert meta["description"] == ""
