#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools.config import resolve_repo

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
