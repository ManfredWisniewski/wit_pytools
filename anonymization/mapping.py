"""Mapping CSV validation, grouping, and application."""

import csv
import io
import re
from pathlib import Path
from typing import Any, Dict, List

from .candidates import VALUE_TYPES, is_date_string


CANDIDATE_COLUMNS = [
    "original_value",
    "replacement_value",
    "value_type",
    "worksheet",
    "cell",
    "occurrences",
]
MAPPING_COLUMNS = ["replacement_value", "original_value", "value_type"]
MAPPING_STATUS_COLUMNS = [
    "status",
    "replacement_value",
    "original_value",
    "value_type",
    "source_documents",
    "locations",
    "occurrences",
]
VALID_MAPPING_STATUSES = {"keep", "anon", "new"}


class CandidateValidationError(ValueError):
    """Raised when a candidate CSV row is invalid."""


class MappingValidationError(ValueError):
    """Raised when a mapping CSV row is invalid."""


def write_csv(file_path: Path, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def mapping_path_for_candidates(candidate_path: Path) -> Path:
    suffix = "_candidates"
    stem = candidate_path.stem
    if stem.endswith(suffix):
        stem = stem[: -len(suffix)]
    return candidate_path.with_name(f"{stem}_mapping.csv")


def contains_value(container: str, contained: str) -> bool:
    if container.casefold() == contained.casefold():
        return False
    pattern = rf"(?<!\w){re.escape(contained.strip())}(?!\w)"
    return re.search(pattern, container, re.IGNORECASE) is not None


def group_contained_rows(rows: List[Dict[str, str]]) -> None:
    parents = list(range(len(rows)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        first_root = find(first)
        second_root = find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for first, first_row in enumerate(rows):
        for second in range(first + 1, len(rows)):
            second_value = rows[second]["original_value"]
            if contains_value(first_row["original_value"], second_value) or contains_value(
                second_value, first_row["original_value"]
            ):
                union(first, second)

    groups: Dict[int, List[int]] = {}
    for index in range(len(rows)):
        groups.setdefault(find(index), []).append(index)

    for indexes in groups.values():
        name_indexes = [index for index in indexes if rows[index]["value_type"] == "name"]
        representative_index = min(
            name_indexes or indexes,
            key=lambda index: (rows[index]["original_value"].count(" "), index),
        )
        replacement = rows[representative_index]["replacement_value"]
        value_type = rows[representative_index]["value_type"]
        for index in indexes:
            rows[index]["replacement_value"] = replacement
            rows[index]["value_type"] = value_type


def related_mapping_values(mapping: Dict[str, str]) -> set[str]:
    related_values = set()
    items = list(mapping.items())
    for index, (first_value, first_replacement) in enumerate(items):
        for second_value, second_replacement in items[index + 1 :]:
            if first_replacement != second_replacement:
                continue
            if contains_value(first_value, second_value) or contains_value(
                second_value, first_value
            ):
                related_values.update((first_value, second_value))
    return related_values


def aggregate_mapping_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[str, Dict[str, str]] = {}
    originals: Dict[str, List[str]] = {}
    for row in rows:
        replacement = row["replacement_value"]
        if replacement not in grouped:
            grouped[replacement] = {
                "replacement_value": replacement,
                "value_type": row["value_type"],
            }
            originals[replacement] = []
        originals[replacement].append(row["original_value"])

    return [
        {
            "replacement_value": row["replacement_value"],
            "original_value": ";".join(originals[row["replacement_value"]]),
            "value_type": row["value_type"],
        }
        for row in grouped.values()
    ]


def create_mapping(
    candidate_path: Path | str,
    output_path: Path | str | None = None,
    *,
    overwrite: bool = False,
    group_contained_values: bool = False,
) -> Path:
    """Validate a reviewed candidate CSV and write the final mapping CSV."""
    reviewed_path = Path(candidate_path)
    if not reviewed_path.is_file():
        raise FileNotFoundError(reviewed_path)
    mapping_path = (
        Path(output_path)
        if output_path is not None
        else mapping_path_for_candidates(reviewed_path)
    )
    if mapping_path.resolve() == reviewed_path.resolve():
        raise MappingValidationError("The mapping path must differ from the candidate path")
    if mapping_path.exists() and not overwrite:
        raise FileExistsError(mapping_path)

    with reviewed_path.open(encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None or any(
            column not in reader.fieldnames for column in CANDIDATE_COLUMNS
        ):
            raise CandidateValidationError(
                f"Candidate CSV must contain columns: {', '.join(CANDIDATE_COLUMNS)}"
            )
        rows = list(reader)

    mapping_rows = []
    seen_originals = set()
    for row in rows:
        original = row["original_value"]
        replacement = row["replacement_value"]
        value_type = row["value_type"]
        if is_date_string(original):
            continue
        if not original:
            raise CandidateValidationError("Candidate original_value must not be empty")
        if not replacement:
            raise CandidateValidationError(
                f"Replacement for {original!r} must not be empty"
            )
        if value_type not in VALUE_TYPES:
            raise CandidateValidationError(f"Unsupported value_type: {value_type!r}")
        if original in seen_originals:
            raise CandidateValidationError(f"Duplicate original_value: {original!r}")
        seen_originals.add(original)
        mapping_rows.append(
            {
                "original_value": original,
                "replacement_value": replacement,
                "value_type": value_type,
            }
        )

    if group_contained_values:
        group_contained_rows(mapping_rows)

    write_csv(mapping_path, MAPPING_COLUMNS, aggregate_mapping_rows(mapping_rows))
    return mapping_path


def read_mapping_rows(mapping_path: Path) -> List[Dict[str, str]]:
    """Read and validate mapping rows with optional workflow status columns."""
    text = mapping_path.read_text(encoding="utf-8")
    lines = [
        line
        for line in text.splitlines()
        if line.strip() not in {"# NEW / NEU", "# IGNORE / IGNORIEREN"}
    ]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    if reader.fieldnames is None or not all(
        column in reader.fieldnames for column in MAPPING_COLUMNS
    ):
        raise MappingValidationError(
            f"Mapping CSV must contain columns: {', '.join(MAPPING_COLUMNS)}"
        )
    rows = []
    for line_number, row in enumerate(reader, start=2):
        original = row.get("original_value") or ""
        replacement = row.get("replacement_value") or ""
        value_type = row.get("value_type") or ""
        status = (row.get("status") or "anon").strip().lower()
        if status not in VALID_MAPPING_STATUSES:
            raise MappingValidationError(
                f"Mapping line {line_number}: unsupported status {status!r}"
            )
        if not original:
            raise MappingValidationError(
                f"Mapping line {line_number}: original_value must not be empty"
            )
        if value_type not in VALUE_TYPES:
            raise MappingValidationError(
                f"Mapping line {line_number}: unsupported value_type {value_type!r}"
            )
        if status == "anon" and not replacement:
            raise MappingValidationError(
                f"Mapping line {line_number}: replacement_value must not be empty"
            )
        rows.append(
            {
                "replacement_value": replacement,
                "original_value": original,
                "value_type": value_type,
                "status": status,
                "source_documents": row.get("source_documents", "") or "",
                "locations": row.get("locations", "") or "",
                "occurrences": row.get("occurrences", "") or "",
            }
        )
    return rows


def mapping_path_rows(mapping_path: Path) -> Dict[str, str]:
    mapping = {}
    for row in read_mapping_rows(mapping_path):
        if row["status"] != "anon":
            continue
        for original in row["original_value"].split(";"):
            original = original.strip()
            if not original:
                raise MappingValidationError("Mapping original_value contains an empty entry")
            if original in mapping:
                raise MappingValidationError(f"Duplicate original_value: {original!r}")
            mapping[original] = row["replacement_value"]
    return mapping


def replace_related_values(
    value: str,
    mapping: Dict[str, str],
    related_values: set[str],
) -> str:
    keys = [
        key
        for key in related_values
        if key in mapping and key and not is_date_string(key) and key in value
    ]
    if not keys:
        return mapping.get(value, value)

    replacements = []
    position = 0
    while position < len(value):
        matching_keys = [key for key in keys if value.startswith(key, position)]
        if not matching_keys:
            replacements.append(value[position])
            position += 1
            continue

        key = max(matching_keys, key=len)
        replacement_values = [mapping[key]]
        nested_keys = [nested_key for nested_key in keys if nested_key != key and nested_key in key]
        for nested_key in sorted(nested_keys, key=len, reverse=True):
            nested_replacement = mapping[nested_key]
            if nested_replacement not in replacement_values:
                replacement_values.append(nested_replacement)
        replacement_text = replacement_values[0]
        if len(replacement_values) > 1:
            replacement_text += " (" + ", ".join(replacement_values[1:]) + ")"
        replacements.append(replacement_text)
        position += len(key)

    return "".join(replacements)
