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
DE,Qira,Qira
"""
SURNAMES_CSV = """Country,Localized Name,Romanized Name
ZZ,Zol,Zol
DE,Zol,Zol
"""
GERMAN_NOUNS = """Garten
Sommer
"""
GERMAN_FORENAMES = """Qira
"""
GERMAN_SURNAMES = """Zol
"""
GERMAN_TEXTS = {
    "abbreviations": "Bu\n",
    "adjectives": "online\n",
    "adverbs": "online\n",
    "articles": "der\n",
    "comparatives": "besser\n",
    "conjunctions": "und\n",
    "contractions": "aufs\n",
    "interjections": "hallo\n",
    "noun_plurals": "Einkünfte\nWünsche\n",
    "nouns": GERMAN_NOUNS,
    "numbers": "drei\n",
    "particle_answers": "bitte\n",
    "particles": "nicht\n",
    "postpositions": "zufolge\n",
    "preposition_articles": "beim\n",
    "prepositions": "mit\n",
    "pronouns": "unser\nsie\nihre\nihnen\nmeine\n",
    "subjunctions": "sobald\n",
    "superlatives": "besten\n",
    "verbs": "gehen\n",
    "forenames": GERMAN_FORENAMES,
    "surnames": GERMAN_SURNAMES,
}


def test_german_nouns_filter_single_name_candidates():
    catalog = NameCatalog(
        frozenset({"DE"}),
        frozenset({"qira", "sommer"}),
        frozenset({"zol"}),
        frozenset({"sommer"}),
    )

    assert catalog.is_name("Qira")
    assert not catalog.is_name("Sommer")
    assert catalog.is_name("Qira Zol")


def test_dictionary_matching_uses_substrings():
    catalog = NameCatalog(
        frozenset({"DE"}),
        frozenset(),
        frozenset(),
        frozenset({"aufname", "monat", "gläubiger", "mitglied", "service", "ag"}),
    )

    assert catalog.is_dictionary_word("Aufnahme-Monat")
    assert catalog.is_dictionary_word("Gläubiger-Nr")
    assert catalog.is_dictionary_word("Mitgliederservice")
    assert not catalog.is_dictionary_word("ADAC e.V.")


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


def test_load_name_catalog_loads_german_wordlist(tmp_path, monkeypatch):
    monkeypatch.setattr(name_datasets, "_fetch_commit", lambda: "popular-1")
    monkeypatch.setattr(name_datasets, "_fetch_german_commit", lambda: "german-1")
    monkeypatch.setattr(
        name_datasets,
        "_fetch_text",
        lambda dataset: FORENAMES_CSV if dataset == "forenames" else SURNAMES_CSV,
    )
    monkeypatch.setattr(
        name_datasets,
        "_fetch_german_text",
        lambda dataset: GERMAN_TEXTS[dataset],
    )

    catalog = load_name_catalog(["DE"], cache_dir=tmp_path)

    assert catalog is not None
    assert catalog.is_name("Qira")
    assert catalog.is_name("Qira Zol")
    assert not catalog.is_name("Sommer")
    for value in (
        "Unser Online",
        "Sie Ihre Einkünfte",
        "Ihre Wünsche",
        "Sobald Ihnen",
        "Meine Einkünfte",
        "Der Online",
        "Der Bu",
        "Und nicht drei",
        "Beim Gehen",
        "Hallo besser",
        "Aufs Haus",
        "Der Brief zufolge",
    ):
        assert catalog.is_dictionary_word(value)

    monkeypatch.setattr(
        name_datasets,
        "_fetch_german_text",
        lambda dataset: (_ for _ in ()).throw(AssertionError("downloaded again")),
    )
    cached = load_name_catalog(["DE"], cache_dir=tmp_path)
    assert cached is not None
    assert cached.is_dictionary_word("Sie Ihre Einkünfte")


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
