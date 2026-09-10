import csv
import os
import sys
from pathlib import Path

import openpyxl
import pytest

# Allow importing wit_pytools when running tests directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.documenttools import (
    anonymize_xlsx,
    create_xlsx_mapping,
    document_find_regex,
    identify_xlsx_strings,
)

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


def test_xlsx_anonymization_workflow_preserves_formulas(tmp_path):
    source_path = tmp_path / "source.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Data"
    worksheet["A1"] = "Alice Example"
    worksheet["A2"] = "Alice Example"
    worksheet["A3"] = "alice@example.com"
    worksheet["A4"] = 42
    worksheet["A5"] = "=SUM(A4,1)"
    worksheet["A6"] = "31.03.2020"
    workbook.save(source_path)

    candidates_path = identify_xlsx_strings(source_path)
    with candidates_path.open(encoding="utf-8", newline="") as file_handle:
        candidate_rows = list(csv.DictReader(file_handle))

    assert [row["original_value"] for row in candidate_rows] == [
        "Alice Example",
        "alice@example.com",
    ]
    assert "31.03.2020" not in [
        row["original_value"] for row in candidate_rows
    ]
    assert candidate_rows[0]["occurrences"] == "2"
    assert candidate_rows[0]["cell"] == "A1; A2"

    candidate_rows[0]["replacement_value"] = "Person-1"
    candidate_rows[1]["replacement_value"] = "person-1@example.invalid"
    with candidates_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=candidate_rows[0].keys())
        writer.writeheader()
        writer.writerows(candidate_rows)

    mapping_path = create_xlsx_mapping(candidates_path)
    output_path = anonymize_xlsx(source_path, mapping_path)

    anonymized = openpyxl.load_workbook(output_path, data_only=False)
    anonymized_sheet = anonymized["Data"]
    assert anonymized_sheet["A1"].value == "Person-1"
    assert anonymized_sheet["A2"].value == "Person-1"
    assert anonymized_sheet["A3"].value == "person-1@example.invalid"
    assert anonymized_sheet["A4"].value == 42
    assert anonymized_sheet["A5"].value == "=SUM(A4,1)"
    assert anonymized_sheet["A6"].value == "31.03.2020"
    anonymized.close()


def test_create_xlsx_mapping_rejects_invalid_rows(tmp_path):
    candidate_path = tmp_path / "source_candidates.csv"
    with candidate_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(
            file_handle,
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
                "original_value": "same",
                "replacement_value": "one",
                "value_type": "string",
                "worksheet": "Sheet",
                "cell": "A1",
                "occurrences": "1",
            }
        )
        writer.writerow(
            {
                "original_value": "same",
                "replacement_value": "two",
                "value_type": "string",
                "worksheet": "Sheet",
                "cell": "A2",
                "occurrences": "1",
            }
        )

    with pytest.raises(ValueError, match="Duplicate original_value"):
        create_xlsx_mapping(candidate_path)


def test_create_xlsx_mapping_groups_contained_values(tmp_path):
    candidate_path = tmp_path / "source_candidates.csv"
    with candidate_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=[
            "original_value",
            "replacement_value",
            "value_type",
            "worksheet",
            "cell",
            "occurrences",
        ])
        writer.writeheader()
        for value, replacement, value_type in [
            ("Lia", "value-lia", "string"),
            ("Barfuss", "value-bar", "string"),
            ("Lia Barfuss", "Person-54b", "name"),
            ("Herr Barfuss", "value-herr", "name"),
        ]:
            writer.writerow({
                "original_value": value,
                "replacement_value": replacement,
                "value_type": value_type,
                "worksheet": "Sheet",
                "cell": "A1",
                "occurrences": "1",
            })

    mapping_path = create_xlsx_mapping(
        candidate_path,
        group_contained_values=True,
    )
    with mapping_path.open(encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        mapping_rows = list(reader)

    assert reader.fieldnames == [
        "replacement_value",
        "original_value",
        "value_type",
    ]
    assert len(mapping_rows) == 1
    assert mapping_rows[0]["original_value"] == (
        "Lia;Barfuss;Lia Barfuss;Herr Barfuss"
    )
    assert {row["replacement_value"] for row in mapping_rows} == {"Person-54b"}


def test_anonymize_xlsx_preserves_personenkonten_substring_matches(tmp_path):
    source_path = tmp_path / "source.xlsx"
    mapping_path = tmp_path / "source_mapping.csv"
    output_path = tmp_path / "source_anonymized.xlsx"

    workbook = openpyxl.Workbook()
    personenkonten = workbook.active
    personenkonten.title = "Personenkonten"
    personenkonten["F3"] = "Barfuss"
    personenkonten["AM3"] = "Prüfung:"
    kontoauszuege = workbook.create_sheet("Kontoauszüge")
    kontoauszuege["F1"] = "Klassenkasse 6A Lia Barfuss RINP Dauerauftrag"
    workbook.save(source_path)

    with mapping_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=["original_value", "replacement_value", "value_type"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "original_value": "Barfuss",
                    "replacement_value": "value-48a",
                    "value_type": "string",
                },
                {
                    "original_value": "Klassenkasse 6A Lia Barfuss RINP Dauerauftrag",
                    "replacement_value": "value-48a",
                    "value_type": "string",
                },
            ]
        )

    anonymize_xlsx(source_path, mapping_path, output_path)

    anonymized = openpyxl.load_workbook(output_path, data_only=False)
    assert anonymized["Personenkonten"]["F3"].value == "value-48a"
    assert anonymized["Personenkonten"]["AM3"].value == "Prüfung:"
    assert anonymized["Kontoauszüge"]["F1"].value == "value-48a"
    anonymized.close()
