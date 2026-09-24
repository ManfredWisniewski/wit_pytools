import os
import sys
from urllib.error import URLError

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from wit_pytools.anonymization import detect_text_candidates
from wit_pytools.anonymization.name_datasets import (
    NameDatasetUnavailableError,
    NameCatalog,
    load_name_catalog,
)
import wit_pytools.anonymization.name_datasets as name_datasets


FORENAMES_CSV = """Country,Localized Name,Romanized Name
ZZ,Qira,Qira
"""
SURNAMES_CSV = """Country,Localized Name,Romanized Name
ZZ,Zol,Zol
"""


def test_dataset_names_detect_single_and_compound_values():
    catalog = NameCatalog(frozenset({"ZZ"}), frozenset({"qira"}), frozenset({"zol"}))

    candidates = detect_text_candidates(
        "Qira Zol contacted Qira.",
        "sample.txt",
        name_catalog=catalog,
    )

    assert {candidate.original_value for candidate in candidates} >= {
        "Qira",
        "Zol",
        "Qira Zol",
    }


def test_load_name_catalog_downloads_and_reuses_unchanged_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(name_datasets, "_fetch_commit", lambda: "commit-1")
    monkeypatch.setattr(
        name_datasets,
        "_fetch_text",
        lambda dataset: FORENAMES_CSV if dataset == "forenames" else SURNAMES_CSV,
    )

    catalog = load_name_catalog(["ZZ"], cache_dir=tmp_path)
    assert catalog is not None
    assert catalog.is_name("Qira")

    monkeypatch.setattr(
        name_datasets,
        "_fetch_text",
        lambda dataset: (_ for _ in ()).throw(AssertionError("downloaded again")),
    )
    cached = load_name_catalog(["ZZ"], cache_dir=tmp_path)
    assert cached is not None
    assert cached.is_name("Zol")


def test_load_name_catalog_uses_cache_when_repository_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(name_datasets, "_fetch_commit", lambda: "commit-1")
    monkeypatch.setattr(
        name_datasets,
        "_fetch_text",
        lambda dataset: FORENAMES_CSV if dataset == "forenames" else SURNAMES_CSV,
    )
    load_name_catalog(["ZZ"], cache_dir=tmp_path)

    monkeypatch.setattr(
        name_datasets,
        "_fetch_commit",
        lambda: (_ for _ in ()).throw(URLError("offline")),
    )
    cached = load_name_catalog(["ZZ"], cache_dir=tmp_path)

    assert cached is not None
    assert cached.is_name("Qira")


def test_load_name_catalog_fails_without_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(
        name_datasets,
        "_fetch_commit",
        lambda: (_ for _ in ()).throw(URLError("offline")),
    )

    with pytest.raises(NameDatasetUnavailableError):
        load_name_catalog(["ZZ"], cache_dir=tmp_path)


def test_load_name_catalog_rejects_unknown_country(tmp_path, monkeypatch):
    monkeypatch.setattr(name_datasets, "_fetch_commit", lambda: "commit-1")
    monkeypatch.setattr(
        name_datasets,
        "_fetch_text",
        lambda dataset: FORENAMES_CSV if dataset == "forenames" else SURNAMES_CSV,
    )

    with pytest.raises(ValueError, match="not present"):
        load_name_catalog(["YY"], cache_dir=tmp_path)
