import os
import sys
from pathlib import Path

import pytest

# Allow importing wit_pytools when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.documenttools import document_find_regex

TEST_DOC = Path(__file__).parent / "documenttools" / "testdocument.pdf"


def test_document_find_regex_literal_real_document():
    results = document_find_regex(TEST_DOC, "manfred@mustermann.de", context_chars=10)

    assert len(results) >= 1
    assert results[0]["match"].lower() == "manfred@mustermann.de"


def test_document_find_regex_regex_real_document():
    pattern = r"[A-Za-z]+@mustermann\.de"
    results = document_find_regex(TEST_DOC, pattern, regex=True)

    assert any(res["match"].lower().endswith("@mustermann.de") for res in results)


def test_document_find_regex_requires_pdfplumber(monkeypatch):
    monkeypatch.setattr("wit_pytools.documenttools.pdfplumber", None)

    with pytest.raises(RuntimeError):
        document_find_regex(TEST_DOC, "anything")
