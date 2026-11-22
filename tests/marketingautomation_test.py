#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.marketingautomation import (
    MarketingConfigError,
    load_google_settings,
    load_meta_settings,
    normalize_domain,
    site_url_for_domain,
)
from wit_pytools.marketingautomation import google_analytics, meta_conversions


# --- util -----------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("example.com", "example.com"),
    ("https://www.example.com/", "example.com"),
    ("http://Example.COM/path?q=1", "example.com"),
    ("www.example.com", "example.com"),
    ("  sub.example.co.uk  ", "sub.example.co.uk"),
])
def test_normalize_domain(value, expected):
    assert normalize_domain(value) == expected


@pytest.mark.parametrize("value", ["", "not a domain", "ftp://x", "localhost"])
def test_normalize_domain_invalid(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_site_url_for_domain():
    assert site_url_for_domain("example.com") == "sc-domain:example.com"
    assert (
        site_url_for_domain("example.com", "url_prefix")
        == "https://www.example.com/"
    )


# --- config ---------------------------------------------------------------

def test_load_google_settings_missing(monkeypatch):
    for name in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REFRESH_TOKEN",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None, raising=False)
    with pytest.raises(MarketingConfigError):
        load_google_settings()


def test_load_google_settings_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "rtoken")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    settings = load_google_settings()
    assert settings["client_id"] == "cid"
    assert settings["refresh_token"] == "rtoken"


def test_load_google_settings_service_account(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/sa.json")
    settings = load_google_settings()
    assert settings["service_account_file"] == "/tmp/sa.json"


def test_load_meta_settings_missing(monkeypatch):
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
    with pytest.raises(MarketingConfigError):
        load_meta_settings()


def test_load_meta_settings_from_env(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
    settings = load_meta_settings()
    assert settings["access_token"] == "tok"


# --- meta -----------------------------------------------------------------

def test_build_event_payload():
    payload = meta_conversions.build_event_payload(
        "Purchase",
        event_id="evt-1",
        event_source_url="https://example.com/thanks",
        user_data={"em": ["hash"]},
        custom_data={"value": 10},
        test_event_code="TEST123",
    )
    assert payload["test_event_code"] == "TEST123"
    event = payload["data"][0]
    assert event["event_name"] == "Purchase"
    assert event["event_id"] == "evt-1"
    assert event["custom_data"] == {"value": 10}


def test_build_event_payload_minimal():
    payload = meta_conversions.build_event_payload("PageView")
    assert payload == {"data": [{"event_name": "PageView"}]}


def test_send_events(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"events_received": 1}

    def fake_post(url, params=None, json=None, timeout=None):
        calls["url"] = url
        calls["params"] = params
        calls["json"] = json
        return FakeResponse()

    monkeypatch.setattr("requests.post", fake_post)
    result = meta_conversions.send_events(
        "token", "123", [{"event_name": "PageView"}]
    )
    assert result == {"events_received": 1}
    assert calls["url"].endswith("/123/events")
    assert calls["params"]["access_token"] == "token"


# --- google analytics (fake services) --------------------------------------

class _Execute:
    def __init__(self, value):
        self._value = value

    def execute(self, **kwargs):
        return self._value


class _Method:
    def __init__(self, value):
        self._value = value

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return _Execute(self._value)


class _FakeAnalytics:
    """Minimal fake of the analyticsadmin v1beta service."""

    def __init__(self):
        self.accounts = [{
            "account": {
                "name": "accounts/1",
                "displayName": "Acme",
            },
            "propertySummaries": [],
        }]
        self.created_property = None
        self.streams = []

    def accountSummaries(self):
        outer = self

        class _AS:
            def list(self, **kwargs):
                return _Execute({"accountSummaries": outer.accounts})

        return _AS()

    def properties(self):
        outer = self

        class _Props:
            def create(self, parent, body):
                outer.created_property = {"parent": parent, "body": body}
                return _Execute({"name": "properties/99"})

            def dataStreams(self):
                class _DS:
                    def list(self, parent, **kwargs):
                        return _Execute({"dataStreams": outer.streams})

                    def create(self, parent, body):
                        stream = {
                            "name": "properties/99/dataStreams/7",
                            "type": body["type"],
                            "displayName": body["displayName"],
                            "webStreamData": body["webStreamData"],
                        }
                        outer.streams.append(stream)
                        return _Execute(stream)

                return _DS()

        return _Props()


def test_find_account_by_name():
    service = _FakeAnalytics()
    assert google_analytics.find_account_by_name(service, "Acme") == "accounts/1"
    assert google_analytics.find_account_by_name(service, "Nope") is None


def test_create_property():
    service = _FakeAnalytics()
    name = google_analytics.create_property(
        service, "Acme", "Acme - Production", currency="EUR"
    )
    assert name == "properties/99"
    assert service.created_property["parent"] == "accounts/1"
    assert service.created_property["body"]["displayName"] == "Acme - Production"


def test_ensure_property_idempotent():
    service = _FakeAnalytics()
    first = google_analytics.ensure_property(
        service, "Acme", "Acme - Production"
    )
    assert first["created"] is True
    # simulate the property now existing in the account summary
    service.accounts[0]["propertySummaries"] = [{
        "property": "properties/99",
        "displayName": "Acme - Production",
    }]
    second = google_analytics.ensure_property(
        service, "Acme", "Acme - Production"
    )
    assert second == {"property": "properties/99", "created": False}


def test_ensure_web_data_stream_creates_once():
    service = _FakeAnalytics()
    stream = google_analytics.ensure_web_data_stream(
        service, "properties/99", "Main Web", "https://example.com"
    )
    assert stream["webStreamData"]["defaultUri"] == "https://example.com"
    # second call returns the existing stream, no duplicate
    again = google_analytics.ensure_web_data_stream(
        service, "properties/99", "Main Web", "https://example.com"
    )
    assert again["name"] == stream["name"]
    assert len(service.streams) == 1
