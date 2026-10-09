#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.matrixtools import create_user, login, login_as_user


class _FakeResponse:
    def __init__(self, body, ok=True, status_code=200, text=""):
        self._body = body
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._body


def test_matrixtools_importable():
    # smoke test: package can be imported
    import wit_pytools.matrixtools  # noqa: F401


def test_create_user(monkeypatch):
    calls = []

    def fake_request(method, url, headers=None, json=None, timeout=None):
        calls.append((method, url, headers, json))
        return _FakeResponse({"name": "@pirx:example.org"})

    monkeypatch.setattr("requests.request", fake_request)
    result = create_user(
        "@pirx:example.org",
        "secret",
        displayname="Pirx (KI-Bot)",
        server="https://example.org",
        admin_token="tok",
    )
    assert result["name"] == "@pirx:example.org"
    method, url, headers, body = calls[0]
    assert method == "PUT"
    assert url == "https://example.org/_synapse/admin/v2/users/@pirx:example.org"
    assert headers["Authorization"] == "Bearer tok"
    assert body == {"password": "secret", "displayname": "Pirx (KI-Bot)"}


def test_create_user_from_env(monkeypatch):
    monkeypatch.setenv("MATRIX_SERVER", "https://example.org")
    monkeypatch.setenv("MATRIX_ADMIN_TOKEN", "envtok")

    def fake_request(method, url, headers=None, json=None, timeout=None):
        assert headers["Authorization"] == "Bearer envtok"
        return _FakeResponse({})

    monkeypatch.setattr("requests.request", fake_request)
    create_user("@pirx:example.org", "secret")


def test_create_user_missing_token(monkeypatch):
    monkeypatch.delenv("MATRIX_ADMIN_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_user("@pirx:example.org", "secret", server="https://example.org")


def test_login(monkeypatch):
    def fake_request(method, url, headers=None, json=None, timeout=None):
        assert method == "POST"
        assert url == "https://example.org/_matrix/client/v3/login"
        assert json["identifier"]["user"] == "pirx"
        return _FakeResponse({"access_token": "tok123"})

    monkeypatch.setattr("requests.request", fake_request)
    assert login("pirx", "secret", server="https://example.org") == "tok123"


def test_login_as_user(monkeypatch):
    def fake_request(method, url, headers=None, json=None, timeout=None):
        assert method == "POST"
        assert url == "https://example.org/_synapse/admin/v1/users/@pirx:example.org/login"
        assert headers["Authorization"] == "Bearer tok"
        return _FakeResponse({"access_token": "tok123"})

    monkeypatch.setattr("requests.request", fake_request)
    assert (
        login_as_user(
            "@pirx:example.org", server="https://example.org", admin_token="tok"
        )
        == "tok123"
    )


def test_login_error(monkeypatch):
    def fake_request(method, url, headers=None, json=None, timeout=None):
        return _FakeResponse({}, ok=False, status_code=403, text="forbidden")

    monkeypatch.setattr("requests.request", fake_request)
    with pytest.raises(RuntimeError):
        login("pirx", "secret", server="https://example.org")
