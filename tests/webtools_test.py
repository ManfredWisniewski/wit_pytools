#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.webtools import WebtoolsConfigError, load_credentials


def test_load_credentials_from_env(monkeypatch):
    monkeypatch.setenv("AMEX_USERNAME", "user1")
    monkeypatch.setenv("AMEX_PASSWORD", "secret1")
    assert load_credentials("amex") == ("user1", "secret1")


def test_load_credentials_site_prefix(monkeypatch):
    monkeypatch.setenv("MY_BANK_USERNAME", "user2")
    monkeypatch.setenv("MY_BANK_PASSWORD", "secret2")
    assert load_credentials("my-bank") == ("user2", "secret2")


def test_load_credentials_missing(monkeypatch):
    monkeypatch.delenv("AMEX_USERNAME", raising=False)
    monkeypatch.delenv("AMEX_PASSWORD", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    with pytest.raises(WebtoolsConfigError):
        load_credentials("amex")


def test_load_credentials_missing_password(monkeypatch):
    monkeypatch.setenv("AMEX_USERNAME", "user1")
    monkeypatch.delenv("AMEX_PASSWORD", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    with pytest.raises(WebtoolsConfigError):
        load_credentials("amex")


def test_mailbox_config_from_env(monkeypatch):
    from wit_pytools.webtools.mailbox import load_mailbox_config

    monkeypatch.setenv("CLAUDIA_IMAP_HOST", "post.witconsult.de")
    monkeypatch.setenv("CLAUDIA_IMAP_USER", "claudia@wit.gmbh")
    monkeypatch.setenv("CLAUDIA_IMAP_PASSWORD", "secret")
    config = load_mailbox_config("claudia")
    assert config["host"] == "post.witconsult.de"
    assert config["port"] == 993
    assert config["folder"] == "INBOX"


def test_mailbox_config_missing(monkeypatch):
    from wit_pytools.webtools.mailbox import load_mailbox_config

    monkeypatch.delenv("CLAUDIA_IMAP_HOST", raising=False)
    monkeypatch.delenv("CLAUDIA_IMAP_USER", raising=False)
    monkeypatch.delenv("CLAUDIA_IMAP_PASSWORD", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    with pytest.raises(WebtoolsConfigError):
        load_mailbox_config("claudia")


def test_extract_links():
    from wit_pytools.webtools.mailbox import extract_links

    text = (
        "Click https://login.live.com/confirm?code=abc&x=1 to verify.\n"
        "Or visit <https://example.com/help> for support."
    )
    links = extract_links(text)
    assert links[0] == "https://login.live.com/confirm?code=abc&x=1"
    assert links[1] == "https://example.com/help"
