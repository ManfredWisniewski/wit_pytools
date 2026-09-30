#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.payloadtools import cli

from wit_pytools.tests.payloadtools_fakes import FakeClient

REPO = Path(__file__).parent / "payloadtools" / "witrepo"


def test_missing_config_exit_2():
    assert cli.main(["sync", "--repo", str(REPO / "nope")]) == 2


def test_missing_credentials_exit_2(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("PAYLOAD_BASE_URL", "")
    monkeypatch.setenv("PAYLOAD_API_KEY", "")
    assert cli.main(["sync", "--repo", str(REPO)]) == 2


def test_check_exit_1_with_failed_file(capsys):
    code = cli.main(
        ["check", "--repo", str(REPO), "-v"],
        client=FakeClient(fail_writes=True),
    )
    # one fixture file (broken_webtext_locked) fails -> exit 1
    assert code == 1
    out = capsys.readouterr().out
    assert "skipped" in out
    assert "notes_webtext_entwurf.md" in out


def test_sync_single_file_exit_0():
    code = cli.main(
        ["sync", "--repo", str(REPO), "--file", "plain_webtext.md",
         "--dry-run"],
        client=FakeClient(fail_writes=True),
    )
    assert code == 0


def test_sync_failed_file_exit_1():
    code = cli.main(
        ["sync", "--repo", str(REPO),
         "--file", "kategorie_products/broken_webtext_locked.md",
         "--dry-run"],
        client=FakeClient(fail_writes=True),
    )
    assert code == 1


def test_sync_unknown_file_exit_2():
    code = cli.main(
        ["sync", "--repo", str(REPO), "--file", "nonexistent.md"],
        client=FakeClient(),
    )
    assert code == 2


def test_theme_command(monkeypatch, tmp_path):
    fake = FakeClient()
    monkeypatch.setattr(
        cli, "load_credentials", lambda: ("https://x.test", "key")
    )
    monkeypatch.setattr(cli, "PayloadClient", lambda *a, **k: fake)
    css = tmp_path / "light.css"
    css.write_text(":root{--a:1}")
    code = cli.main(["theme", "--css-light", str(css)])
    assert code == 0
    slug, payload = fake.globals[0]
    assert slug == "theme"
    assert payload == {"cssLight": ":root{--a:1}"}


def test_theme_missing_css_exit_2(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli, "load_credentials", lambda: ("https://x.test", "key")
    )
    monkeypatch.setattr(
        cli, "PayloadClient", lambda *a, **k: FakeClient()
    )
    code = cli.main(
        ["theme", "--css-light", str(tmp_path / "missing.css")]
    )
    assert code == 2


def test_invalid_status_regex_exit_2(tmp_path):
    (tmp_path / ".arrcontent.yml").write_text(
        'status_regex: "([bad"\n', encoding="utf-8"
    )
    code = cli.main(
        ["sync", "--repo", str(tmp_path), "--dry-run"],
        client=FakeClient(),
    )
    assert code == 2


def test_malformed_config_exit_2(tmp_path):
    (tmp_path / ".arrcontent.yml").write_text(
        "collection: [unclosed\n", encoding="utf-8"
    )
    code = cli.main(
        ["sync", "--repo", str(tmp_path)], client=FakeClient()
    )
    assert code == 2
