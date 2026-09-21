import csv
import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from eliot import log_message

try:  # Optional dependency that is only needed for XLSX operations
    import openpyxl
except ImportError:  # pragma: no cover - exercised without openpyxl
    openpyxl = None

try:  # Optional dependency that is only needed for PDF operations
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - exercised in environments without pdfplumber
    pdfplumber = None

_LAZY_EXPORTS = {"pdf_to_markdown", "pdf_to_markdown_text"}


def __getattr__(name: str):
    # Lazy re-export keeps `python -m wit_pytools.documenttools.pdf2md` free of double imports
    if name in _LAZY_EXPORTS:
        import importlib

        return getattr(importlib.import_module(f"{__name__}.pdf2md"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def document_find_regex(
    file_path: Path | str,
    query: str,
    *,
    regex: bool = False,
    context_chars: int = 40,
    max_pages: Optional[int] = None,
    flags: int = re.IGNORECASE,
) -> List[Dict[str, Any]]:
    """Search a PDF for a literal string or regex pattern and return contexts.

    Args:
        file_path: Path to the PDF document.
        query: Literal string or regex pattern to search for.
        regex: When ``True`` the ``query`` is treated as a regular expression;
            otherwise a literal search is performed.
        context_chars: Number of characters of context to capture on both sides
            of each match.
        max_pages: Optional maximum number of pages to scan. ``None`` scans all
            pages.
        flags: Regular expression flags passed to :func:`re.compile`.

    Returns:
        A list of dictionaries containing ``page_number``, ``match``, and
        ``context`` keys for each occurrence found.

    Raises:
        RuntimeError: If ``pdfplumber`` is not available in the current
            environment.
    """

    if not pdfplumber:
        raise RuntimeError(
            "pdfplumber is required for document_find_regex. Install pdfplumber to use this function."
        )

    pattern = re.compile(query if regex else re.escape(query), flags)
    pdf_path = Path(file_path)
    results: List[Dict[str, Any]] = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = pdf.pages
            if max_pages is not None:
                pages = pages[:max_pages]

            for page_index, page in enumerate(pages, start=1):
                page_text = page.extract_text() or ""
                for match in pattern.finditer(page_text):
                    start = max(match.start() - context_chars, 0)
                    end = min(match.end() + context_chars, len(page_text))
                    context = page_text[start:end].replace("\n", " ")
                    results.append(
                        {
                            "page_number": page_index,
                            "match": match.group(0),
                            "context": context,
                        }
                    )
    except Exception as exc:
        log_message(f"Failed to search PDF {pdf_path}: {exc}", level="ERROR")
        raise

    return results


_CANDIDATE_COLUMNS = [
    "original_value",
    "replacement_value",
    "value_type",
    "worksheet",
    "cell",
    "occurrences",
]
_MAPPING_COLUMNS = ["replacement_value", "original_value", "value_type"]
_OLD_MAPPING_COLUMNS = ["original_value", "replacement_value", "value_type"]
_VALUE_TYPES = {"email", "url", "name", "string"}
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_NAME_PATTERN = re.compile(
    r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}"
)
_DATE_FORMATS = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")


def _is_date_string(value: str) -> bool:
    value = value.strip()
    return any(
        _parse_date(value, date_format) is not None
        for date_format in _DATE_FORMATS
    )


def _parse_date(value: str, date_format: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, date_format)
    except ValueError:
        return None


def _require_openpyxl() -> None:
    if openpyxl is None:
        raise RuntimeError(
            "openpyxl is required for XLSX operations. "
            "Install the dependencies from requirements.txt."
        )


def _xlsx_path(file_path: Path | str) -> Path:
    path = Path(file_path)
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Only .xlsx files are supported")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _default_output_path(input_path: Path, suffix: str, extension: str) -> Path:
    return input_path.with_name(f"{input_path.stem}_{suffix}{extension}")


def _check_output_path(output_path: Path, input_path: Path, overwrite: bool) -> None:
    if output_path.resolve() == input_path.resolve():
        raise ValueError("The output path must differ from the source path")
    if output_path.exists() and not overwrite:
        raise FileExistsError(output_path)


def _value_type(value: str) -> str:
    if _EMAIL_PATTERN.fullmatch(value):
        return "email"
    if _URL_PATTERN.fullmatch(value):
        return "url"
    if _NAME_PATTERN.fullmatch(value):
        return "name"
    return "string"


def _replacement_for(value: str, value_type: str) -> str:
    token = hashlib.sha256(value.encode("utf-8")).hexdigest()[:3]
    if value_type == "email":
        return f"person-{token}@example.invalid"
    if value_type == "url":
        return f"https://example.invalid/{token}"
    if value_type == "name":
        return f"Person-{token}"
    return f"value-{token}"


def _write_csv(file_path: Path, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def identify_xlsx_strings(
    file_path: Path | str,
    output_path: Optional[Path | str] = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Identify string cell values and write a reviewed-candidate CSV."""
    _require_openpyxl()
    input_path = _xlsx_path(file_path)
    candidate_path = Path(output_path) if output_path is not None else _default_output_path(
        input_path, "candidates", ".csv"
    )
    _check_output_path(candidate_path, input_path, overwrite)

    candidates: Dict[str, Dict[str, Any]] = {}
    workbook = openpyxl.load_workbook(
        input_path,
        data_only=False,
        keep_links=True,
    )
    try:
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f" or not isinstance(cell.value, str):
                        continue
                    if not cell.value or _is_date_string(cell.value):
                        continue
                    candidate = candidates.setdefault(
                        cell.value,
                        {
                            "original_value": cell.value,
                            "replacement_value": _replacement_for(
                                cell.value, _value_type(cell.value)
                            ),
                            "value_type": _value_type(cell.value),
                            "worksheets": [],
                            "cells": [],
                            "occurrences": 0,
                        },
                    )
                    candidate["worksheets"].append(worksheet.title)
                    candidate["cells"].append(cell.coordinate)
                    candidate["occurrences"] += 1
    finally:
        workbook.close()

    rows = [
        {
            "original_value": candidate["original_value"],
            "replacement_value": candidate["replacement_value"],
            "value_type": candidate["value_type"],
            "worksheet": "; ".join(candidate["worksheets"]),
            "cell": "; ".join(candidate["cells"]),
            "occurrences": candidate["occurrences"],
        }
        for candidate in candidates.values()
    ]
    _write_csv(candidate_path, _CANDIDATE_COLUMNS, rows)
    return candidate_path


def _mapping_path_for_candidates(candidate_path: Path) -> Path:
    suffix = "_candidates"
    if candidate_path.stem.endswith(suffix):
        stem = candidate_path.stem[: -len(suffix)]
    else:
        stem = candidate_path.stem
    return candidate_path.with_name(f"{stem}_mapping.csv")


def _contains_value(container: str, contained: str) -> bool:
    if container.casefold() == contained.casefold():
        return False
    pattern = rf"(?<!\w){re.escape(contained.strip())}(?!\w)"
    return re.search(pattern, container, re.IGNORECASE) is not None


def _group_contained_rows(rows: List[Dict[str, str]]) -> None:
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
            if _contains_value(first_row["original_value"], second_value) or _contains_value(
                second_value, first_row["original_value"]
            ):
                union(first, second)

    groups: Dict[int, List[int]] = {}
    for index in range(len(rows)):
        groups.setdefault(find(index), []).append(index)

    for indexes in groups.values():
        name_indexes = [
            index for index in indexes if rows[index]["value_type"] == "name"
        ]
        representative_index = min(
            name_indexes or indexes,
            key=lambda index: (rows[index]["original_value"].count(" "), index),
        )
        replacement = rows[representative_index]["replacement_value"]
        value_type = rows[representative_index]["value_type"]
        for index in indexes:
            rows[index]["replacement_value"] = replacement
            rows[index]["value_type"] = value_type


def _related_mapping_values(mapping: Dict[str, str]) -> set[str]:
    related_values = set()
    items = list(mapping.items())
    for index, (first_value, first_replacement) in enumerate(items):
        for second_value, second_replacement in items[index + 1 :]:
            if first_replacement != second_replacement:
                continue
            if _contains_value(first_value, second_value) or _contains_value(
                second_value, first_value
            ):
                related_values.update((first_value, second_value))
    return related_values


def _aggregate_mapping_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
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


def create_xlsx_mapping(
    candidate_path: Path | str,
    output_path: Optional[Path | str] = None,
    *,
    overwrite: bool = False,
    group_contained_values: bool = False,
) -> Path:
    """Validate a reviewed candidate CSV and write the final mapping CSV."""
    reviewed_path = Path(candidate_path)
    if not reviewed_path.is_file():
        raise FileNotFoundError(reviewed_path)
    mapping_path = Path(output_path) if output_path is not None else _mapping_path_for_candidates(
        reviewed_path
    )
    if mapping_path.resolve() == reviewed_path.resolve():
        raise ValueError("The mapping path must differ from the candidate path")
    if mapping_path.exists() and not overwrite:
        raise FileExistsError(mapping_path)

    with reviewed_path.open(encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None or any(
            column not in reader.fieldnames for column in _CANDIDATE_COLUMNS
        ):
            raise ValueError(
                f"Candidate CSV must contain columns: {', '.join(_CANDIDATE_COLUMNS)}"
            )
        rows = list(reader)

    mapping_rows = []
    seen_originals = set()
    for row in rows:
        original = row["original_value"]
        replacement = row["replacement_value"]
        value_type = row["value_type"]
        if _is_date_string(original):
            continue
        if not original:
            raise ValueError("Candidate original_value must not be empty")
        if not replacement:
            raise ValueError(
                f"Replacement for {original!r} must not be empty"
            )
        if value_type not in _VALUE_TYPES:
            raise ValueError(f"Unsupported value_type: {value_type!r}")
        if original in seen_originals:
            raise ValueError(f"Duplicate original_value: {original!r}")
        seen_originals.add(original)
        mapping_rows.append(
            {
                "original_value": original,
                "replacement_value": replacement,
                "value_type": value_type,
            }
        )

    if group_contained_values:
        _group_contained_rows(mapping_rows)

    _write_csv(
        mapping_path,
        _MAPPING_COLUMNS,
        _aggregate_mapping_rows(mapping_rows),
    )
    return mapping_path


def _mapping_path_rows(mapping_path: Path) -> Dict[str, str]:
    with mapping_path.open(encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise ValueError("Mapping CSV must contain a header row")
        if all(column in reader.fieldnames for column in _MAPPING_COLUMNS):
            original_column = "original_value"
            replacement_column = "replacement_value"
        elif all(column in reader.fieldnames for column in _OLD_MAPPING_COLUMNS):
            original_column = "original_value"
            replacement_column = "replacement_value"
        else:
            raise ValueError(
                f"Mapping CSV must contain columns: {', '.join(_MAPPING_COLUMNS)}"
            )

        mapping = {}
        for line_number, row in enumerate(reader, start=2):
            original_column_value = row.get(original_column) or ""
            replacement = row.get(replacement_column) or ""
            value_type = row.get("value_type")
            if value_type is None or not value_type.strip():
                raise ValueError(
                    f"Mapping line {line_number}: missing value_type "
                    f"(replacement {replacement!r}); check that the row has "
                    "exactly three columns and quoted fields where needed"
                )
            if not replacement:
                raise ValueError(
                    f"Mapping line {line_number}: replacement_value must not be empty"
                )
            if value_type not in _VALUE_TYPES:
                raise ValueError(
                    f"Mapping line {line_number}: unsupported value_type "
                    f"{value_type!r} (replacement {replacement!r}); "
                    f"allowed: {', '.join(sorted(_VALUE_TYPES))}"
                )
            for original in original_column_value.split(";"):
                if not original:
                    raise ValueError(
                        f"Mapping line {line_number}: empty original_value entry "
                        f"(replacement {replacement!r}); check for ';;' or a "
                        "trailing ';'"
                    )
                if original in mapping:
                    raise ValueError(
                        f"Mapping line {line_number}: duplicate original_value "
                        f"{original!r} (already mapped to {mapping[original]!r})"
                    )
                mapping[original] = replacement
    return mapping


def _anonymized_path_for_mapping(mapping_path: Path) -> Path:
    suffix = "_mapping"
    if mapping_path.stem.endswith(suffix):
        stem = mapping_path.stem[: -len(suffix)]
    else:
        stem = mapping_path.stem
    return mapping_path.with_name(f"{stem}_anonymized.xlsx")


def _replace_related_values(
    value: str,
    mapping: Dict[str, str],
    related_values: set[str],
) -> str:
    keys = [
        key
        for key in related_values
        if key in mapping and key and not _is_date_string(key) and key in value
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
        nested_keys = [
            nested_key
            for nested_key in keys
            if nested_key != key and nested_key in key
        ]
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


def explain_xlsx_replacement(
    file_path: Path | str,
    mapping_path: Path | str,
    replacement: str,
) -> List[Dict[str, Any]]:
    """List every cell whose anonymized value contains ``replacement``.

    Each entry reports the worksheet, cell, original value, resulting value,
    and the mapping keys that caused the match. Nothing is written.
    """
    _require_openpyxl()
    input_path = _xlsx_path(file_path)
    mapping = _mapping_path_rows(Path(mapping_path))
    related_values = _related_mapping_values(mapping)
    results: List[Dict[str, Any]] = []

    workbook = openpyxl.load_workbook(input_path, data_only=False, read_only=True)
    try:
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows():
                for cell in row:
                    value = cell.value
                    if (
                        cell.data_type == "f"
                        or not isinstance(value, str)
                        or _is_date_string(value)
                    ):
                        continue
                    result = _replace_related_values(value, mapping, related_values)
                    if replacement not in result:
                        continue
                    if mapping.get(value) == replacement:
                        keys = [value]
                    else:
                        keys = sorted(
                            key
                            for key in related_values
                            if mapping.get(key) == replacement and key in value
                        )
                    results.append(
                        {
                            "worksheet": worksheet.title,
                            "cell": cell.coordinate,
                            "original": value,
                            "result": result,
                            "matched_keys": keys,
                        }
                    )
    finally:
        workbook.close()
    return results


def anonymize_xlsx(
    file_path: Path | str,
    mapping_path: Path | str,
    output_path: Optional[Path | str] = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Apply a reviewed mapping to string cells in an XLSX workbook."""
    _require_openpyxl()
    input_path = _xlsx_path(file_path)
    reviewed_mapping_path = Path(mapping_path)
    if not reviewed_mapping_path.is_file():
        raise FileNotFoundError(reviewed_mapping_path)
    mapping = _mapping_path_rows(reviewed_mapping_path)
    anonymized_path = (
        Path(output_path)
        if output_path is not None
        else _anonymized_path_for_mapping(reviewed_mapping_path)
    )
    if anonymized_path.suffix.lower() != ".xlsx":
        raise ValueError("The anonymized output must be an .xlsx file")
    _check_output_path(anonymized_path, input_path, overwrite)

    workbook = openpyxl.load_workbook(
        input_path,
        data_only=False,
        keep_links=True,
    )
    related_values = _related_mapping_values(mapping)
    temporary_path = None
    try:
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows():
                for cell in row:
                    if (
                        cell.data_type != "f"
                        and isinstance(cell.value, str)
                        and not _is_date_string(cell.value)
                    ):
                        replacement = _replace_related_values(
                            cell.value,
                            mapping,
                            related_values,
                        )
                        if replacement != cell.value:
                            cell.value = replacement

        anonymized_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=anonymized_path.parent,
            prefix=f".{anonymized_path.stem}-",
            suffix=".xlsx",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        workbook.save(temporary_path)
        os.replace(temporary_path, anonymized_path)
    finally:
        workbook.close()
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return anonymized_path
