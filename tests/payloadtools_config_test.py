#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import (
    collection_for, glob_match, load_config, resolve_repo,
)

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def test_resolve_repo_prefers_cli_arg(tmp_path, monkeypatch):
    monkeypatch.setenv("ARRCONTENT_REPO", str(tmp_path))
    assert resolve_repo(str(REPO)) == REPO.resolve()


def test_resolve_repo_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARRCONTENT_REPO", str(tmp_path))
    assert resolve_repo(None) == tmp_path.resolve()


def test_resolve_repo_defaults_to_cwd(monkeypatch):
    # empty env must not be overridden by a real .env via load_dotenv
    monkeypatch.setenv("ARRCONTENT_REPO", "")
    assert resolve_repo(None) == Path(".").resolve()


def test_glob_match():
    assert glob_match("blog/**/*.md", "blog/alisa/x.md")
    assert glob_match("blog/**/*.md", "blog/x.md")
    assert not glob_match("blog/**/*.md", "docs/x.md")
    assert glob_match("*.md", "x.md")
    assert not glob_match("*.md", "blog/x.md")


def test_collection_for_routes_by_glob():
    config = load_config(REPO)
    assert collection_for(config, "blog/alisa/post.md") == "posts"
    assert collection_for(config, "kategorie_products/x.md") == "pages"


def test_collection_for_defaults(tmp_path):
    (tmp_path / ".arrcontent.yml").write_text(
        "collection: pages\n", encoding="utf-8"
    )
    config = load_config(tmp_path)
    assert collection_for(config, "blog/a/x.md") == "pages"
