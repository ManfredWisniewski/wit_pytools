import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from wit_pytools.anonymization import (
    CandidateValidationError,
    MappingValidationError,
    create_mapping,
    detect_text_candidates,
    mapping_path_rows,
    replace_text_parts,
)


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


def test_mapping_validation_rejects_empty_original(tmp_path):
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text(
        "replacement_value,original_value,value_type\n"
        "Person-001,,name\n",
        encoding="utf-8",
    )

    with pytest.raises(MappingValidationError):
        mapping_path_rows(mapping_path)
