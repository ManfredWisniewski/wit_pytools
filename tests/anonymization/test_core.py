import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from wit_pytools.anonymization import (
    CandidateValidationError,
    NameCatalog,
    detect_presidio_candidates,
    MappingValidationError,
    create_mapping,
    detect_text_candidates,
    is_corporate_name,
    is_location_name,
    mapping_path_rows,
    replace_text_parts,
)


def test_is_location_name():
    assert is_location_name("Muster Str")
    assert is_location_name("Muster Str.")
    assert is_location_name("Muster Strasse")
    assert is_location_name("Muster Straße")
    assert is_location_name("Muster Hbf")
    assert is_location_name("Muster Boulevard")
    assert is_location_name("Muster Allee")
    assert is_location_name("Muster District")
    assert is_location_name("Den Haag")
    assert is_location_name("Kuala Lumpur")
    assert is_location_name("Estados Unidos")
    assert is_location_name("New Mexico")
    assert is_location_name("Dubai")
    assert is_location_name("New York")
    assert is_location_name("Las Vegas")
    assert is_location_name("Mexico City")
    assert is_location_name("Hotel New York")
    assert not is_location_name("Muster Person")
    assert not is_location_name("Straße")
    assert not is_location_name("New Yorka")
    assert not is_location_name("Mexico")


def test_is_corporate_name():
    assert is_corporate_name("Bank Muster")
    assert is_corporate_name("Muster Bank")
    assert is_corporate_name("Muster Group")
    assert is_corporate_name("Amazon")
    assert is_corporate_name("Apple")
    assert is_corporate_name("Microsoft")
    assert is_corporate_name("Visa")
    assert is_corporate_name("Amex")
    assert is_corporate_name("Master Card")
    assert is_corporate_name("Charles Tyrwhitt")
    assert is_corporate_name("Coral Consors")
    assert is_corporate_name("Dell")
    assert is_corporate_name("Intel")
    assert is_corporate_name("Tradegate")
    assert is_corporate_name("New Work")
    assert is_corporate_name("Sixt")
    assert is_corporate_name("Sony")
    assert is_corporate_name("Xerox")
    assert is_corporate_name("Hays")
    assert is_corporate_name("Huawei")
    assert is_corporate_name("Pinduoduo")
    assert is_corporate_name("Panasonic")
    assert is_corporate_name("Muster Inc")
    assert is_corporate_name("Sony Center")
    assert is_corporate_name("Apple Store")
    assert is_corporate_name("Die Charles Tyrwhitt GmbH")
    assert not is_corporate_name("Muster Person")
    assert not is_corporate_name("Charles Muster")
    assert not is_corporate_name("Coral Muster")
    assert not is_corporate_name("Master Muster")
    assert not is_corporate_name("Bank")
    assert not is_corporate_name("Group")


def test_detect_text_candidates_skips_protected_spans():
    content = "Contact: Sample Person at sample@example.test. `Sample Person`"
    protected_start = content.index("`Sample Person`")
    protected_spans = [(protected_start, len(content))]

    candidates = detect_text_candidates(content, "sample.md", protected_spans)

    assert {candidate.original_value for candidate in candidates} == {
        "Sample Person",
        "sample@example.test",
    }
    assert all(candidate.locations == ["line 1"] for candidate in candidates)


def test_presidio_candidates_use_common_candidate_model(monkeypatch):
    class Result:
        start = 8
        end = 24
        entity_type = "PERSON"

    class Analyzer:
        def analyze(self, **kwargs):
            return [Result()]

    monkeypatch.setattr(
        "wit_pytools.anonymization.presidio._create_engine",
        lambda language, model_name: Analyzer(),
    )

    candidates = detect_presidio_candidates("Contact Sample Person", "sample.md")

    assert candidates[0].original_value == "Sample Person"
    assert candidates[0].value_type == "name"


def test_presidio_candidates_trim_boundaries_and_skip_multiline_spans(monkeypatch):
    content = "Sample Person\nADAC\n\nPS"

    class Result:
        def __init__(self, start, end):
            self.start = start
            self.end = end
            self.entity_type = "PERSON"

    class Analyzer:
        def analyze(self, **kwargs):
            return [
                Result(0, len("Sample Person\n")),
                Result(content.index("ADAC"), len(content)),
            ]

    monkeypatch.setattr(
        "wit_pytools.anonymization.presidio._create_engine",
        lambda language, model_name: Analyzer(),
    )

    candidates = detect_presidio_candidates(content, "sample.md")

    assert [candidate.original_value for candidate in candidates] == ["Sample Person"]


def test_presidio_ignores_generated_person_replacements(monkeypatch):
    content = "Person-001"

    class Result:
        start = 0
        end = 10
        entity_type = "PERSON"

    class Analyzer:
        def analyze(self, **kwargs):
            return [Result()]

    monkeypatch.setattr(
        "wit_pytools.anonymization.presidio._create_engine",
        lambda language, model_name: Analyzer(),
    )

    assert detect_presidio_candidates(content, "sample.md") == []


def test_presidio_recommendation_filters(monkeypatch):
    content = "test@example.com 12345 Garden 12.03.2025"

    class Result:
        def __init__(self, start, end, entity_type):
            self.start = start
            self.end = end
            self.entity_type = entity_type

    class Analyzer:
        def analyze(self, **kwargs):
            return [
                Result(0, 16, "EMAIL_ADDRESS"),
                Result(17, 22, "PHONE_NUMBER"),
                Result(23, 29, "PERSON"),
                Result(30, 40, "DATE_TIME"),
            ]

    monkeypatch.setattr(
        "wit_pytools.anonymization.presidio._create_engine",
        lambda language, model_name: Analyzer(),
    )
    catalog = NameCatalog(
        frozenset({"DE"}),
        frozenset(),
        frozenset(),
        frozenset({"garden"}),
    )

    ignored_candidates = []
    candidates = detect_presidio_candidates(
        content,
        "sample.md",
        name_catalog=catalog,
        ignore_dictionary=True,
        ignore_numbers=True,
        ignore_emails=True,
        ignore_dates=True,
        ignored_candidates=ignored_candidates,
    )

    assert candidates == []
    assert [
        candidate.original_value for candidate in ignored_candidates
    ] == [
        "test@example.com",
        "12345",
        "Garden",
        "12.03.2025",
    ]


def test_presidio_location_names_filtered(monkeypatch):
    content = "Anna Muster Str Karl Beispiel"

    class Result:
        def __init__(self, start, end):
            self.start = start
            self.end = end
            self.entity_type = "PERSON"

    class Analyzer:
        def analyze(self, **kwargs):
            return [
                Result(0, len("Anna Muster Str")),
                Result(len("Anna Muster Str "), len(content)),
            ]

    monkeypatch.setattr(
        "wit_pytools.anonymization.presidio._create_engine",
        lambda language, model_name: Analyzer(),
    )

    ignored_candidates = []
    candidates = detect_presidio_candidates(
        content,
        "sample.md",
        ignore_locations=True,
        ignored_candidates=ignored_candidates,
    )

    assert [candidate.original_value for candidate in candidates] == [
        "Karl Beispiel"
    ]
    assert [candidate.original_value for candidate in ignored_candidates] == [
        "Anna Muster Str"
    ]


def test_replacement_proposals_are_deterministic():
    first = detect_text_candidates("Sample Person", "one.md")[0]
    second = detect_text_candidates("Sample Person", "two.md")[0]

    assert first.replacement_value == second.replacement_value


def test_create_mapping_rejects_invalid_rows(tmp_path):
    candidate_path = tmp_path / "candidates.csv"
    with candidate_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "original_value",
                "replacement_value",
                "value_type",
                "worksheet",
                "cell",
                "occurrences",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "original_value": "Sample Person",
                "replacement_value": "",
                "value_type": "name",
                "worksheet": "Sheet",
                "cell": "A1",
                "occurrences": "1",
            }
        )

    with pytest.raises(CandidateValidationError):
        create_mapping(candidate_path)


def test_mapping_application_preserves_protected_parts(tmp_path):
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text(
        "replacement_value,original_value,value_type\n"
        "Person-001,Sample Person,name\n",
        encoding="utf-8",
    )
    mapping = mapping_path_rows(mapping_path)

    result = replace_text_parts(
        [(True, "Sample Person "), (False, "`Sample Person`")],
        mapping,
    )

    assert result == "Person-001 `Sample Person`"


def test_mapping_path_rows_uses_sibling_anon_file(tmp_path):
    mapping_path = tmp_path / "customer-mapping.csv"
    mapping_path.write_text(
        "status,replacement_value,original_value,value_type,vip,source_documents,locations,occurrences\n"
        "new,Person-002,Other Person,name,,doc.md,line 1,1\n",
        encoding="utf-8",
    )
    anon_path = tmp_path / "customer-anon.csv"
    anon_path.write_text(
        "replacement_value,original_value,value_type,vip\n"
        "Person-001,Sample Person,name,yes\n",
        encoding="utf-8",
    )

    assert mapping_path_rows(mapping_path) == {"Sample Person": "Person-001"}


def test_mapping_validation_rejects_empty_original(tmp_path):
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text(
        "replacement_value,original_value,value_type\n"
        "Person-001,,name\n",
        encoding="utf-8",
    )

    with pytest.raises(MappingValidationError):
        mapping_path_rows(mapping_path)
