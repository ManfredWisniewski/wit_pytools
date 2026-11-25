#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools import cli
from wit_pytools.payloadtools.config import load_config
from wit_pytools.payloadtools.preflight import (
    check_publishable_html,
    find_html_outside_code,
)


def _repo(tmp_path, files):
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_find_html_flags_tag():
    assert find_html_outside_code("text\n<div>x</div>\nmore") == [
        (2, "<div>x</div>"),
    ]


def test_find_html_ignores_fenced_block():
    text = "intro\n```\n<div>x</div>\n```\noutro"
    assert find_html_outside_code(text) == []


def test_find_html_ignores_inline_code():
    assert find_html_outside_code("use `<br>` and `` `<i>` `` here") == []


def test_find_html_flags_entity_and_comment():
    assert find_html_outside_code("a&nbsp;b") == [(1, "a&nbsp;b")]
    assert find_html_outside_code("<!-- note -->") == [(1, "<!-- note -->")]


def test_find_html_ignores_autolink_and_math():
    assert find_html_outside_code("<https://x.de> and a < b") == []


def test_find_html_ignores_custom_elements():
    text = '<witSpace size="800" maxTilt="38" />\n<my-widget a="1"></my-widget>'
    assert find_html_outside_code(text) == []


def test_check_publishable_skips_drafts(tmp_path):
    repo = _repo(tmp_path, {
        ".arrcontent.yml": "collection: pages\n",
        "page_webtext.md": "hi <div>x</div>\n",
        "draft_webtext_entwurf.md": "hi <b>y</b>\n",
    })
    findings = check_publishable_html(load_config(repo))
    assert findings == [("page_webtext.md", 1, "hi <div>x</div>")]


def test_check_publishable_skips_slides(tmp_path):
    repo = _repo(tmp_path, {
        ".arrcontent.yml": "",
        "deck_webtext.md": "---\ntype: slide\n---\n<style>x</style>\n",
        "tpl_webtext.md": "---\ntemplate: slide\n---\n<div>y</div>\n",
        "page_webtext.md": "hi <div>x</div>\n",
    })
    findings = check_publishable_html(load_config(repo))
    assert findings == [("page_webtext.md", 1, "hi <div>x</div>")]


def test_check_publishable_front_matter_offset(tmp_path):
    repo = _repo(tmp_path, {
        ".arrcontent.yml": "",
        "page_webtext.md": "---\ntitle: t\n---\n<div>x</div>\n",
    })
    findings = check_publishable_html(load_config(repo))
    assert findings[0][1] == 4


def test_preflight_cli_exit_codes(tmp_path, capsys):
    repo = _repo(tmp_path, {
        ".arrcontent.yml": "collection: pages\n",
        "page_webtext.md": "hi <div>x</div>\n",
    })
    assert cli.main(["preflight", "--repo", str(repo)]) == 1
    assert "page_webtext.md:1" in capsys.readouterr().out
    (repo / "page_webtext.md").write_text("clean\n", encoding="utf-8")
    assert cli.main(["preflight", "--repo", str(repo)]) == 0
