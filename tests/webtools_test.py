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
