import csv
from pathlib import Path

import pytest

from wit_pytools import scrapetools


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise scrapetools.requests.HTTPError(f"HTTP {self.status_code}")


def test_scrape_text_list_writes_values(monkeypatch, tmp_path):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            "<html><body><ul><li> Anna </li><li>Anna</li><li>Peter</li></ul></body></html>"
        )

    monkeypatch.setattr(scrapetools.requests, "get", get)
    output = scrapetools.scrape_text_list(
        "https://example.test",
        "//li",
        tmp_path / "values.csv",
    )

    with output.open(encoding="utf-8", newline="") as handle:
        assert list(csv.reader(handle)) == [["Anna"], ["Peter"]]
    assert calls[0][1]["headers"]["User-Agent"] == scrapetools.DEFAULT_USER_AGENT


def test_scrape_text_list_retries_server_errors(monkeypatch, tmp_path):
    responses = iter([FakeResponse("", 503), FakeResponse("<p>Value</p>")])
    monkeypatch.setattr(scrapetools.requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(scrapetools.time, "sleep", lambda _: None)

    output = scrapetools.scrape_text_list("https://example.test", "//p", tmp_path / "values.csv")
    assert output.read_text(encoding="utf-8") == "Value\n"


def test_scrape_text_list_refuses_existing_output(monkeypatch, tmp_path):
    output = tmp_path / "values.csv"
    output.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(scrapetools.requests, "get", lambda *args, **kwargs: FakeResponse("<p>x</p>"))

    with pytest.raises(FileExistsError):
        scrapetools.scrape_text_list("https://example.test", "//p", output)


def test_scrape_text_list_validates_method_and_status(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        scrapetools.scrape_text_list("https://example.test", "//p", tmp_path / "x.csv", method="browser")

    monkeypatch.setattr(scrapetools.requests, "get", lambda *args, **kwargs: FakeResponse("", 404))
    with pytest.raises(RuntimeError):
        scrapetools.scrape_text_list("https://example.test", "//p", tmp_path / "x.csv")
