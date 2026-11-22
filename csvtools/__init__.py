"""CSV transformation tools."""

import csv
from os import PathLike
from typing import Union

from wit_pytools.mappingtools import apply_mappings, load_mapping_file


Path = Union[str, PathLike[str]]


def _escape_formula(value: str) -> str:
    """Prefix leading spreadsheet-formula trigger characters."""
    if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def csv_transform(
    source_file: Path,
    target_file: Path,
    mapping_file: Path,
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> None:
    """Transform a CSV file using source-to-target column mappings."""
    spec = load_mapping_file(mapping_file, encoding=encoding)

    with open(source_file, encoding=encoding, newline="") as source_handle:
        source_reader = csv.DictReader(source_handle, delimiter=delimiter)
        source_columns = set(source_reader.fieldnames or [])
        missing_columns = {
            mapping.source_column
            for mapping in spec.mappings
            if mapping.source_column
            and mapping.source_column not in source_columns
        }
        if missing_columns:
            raise ValueError(
                "Source file is missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        with open(
            target_file,
            "w",
            encoding=encoding,
            newline="",
        ) as target_handle:
            target_writer = csv.DictWriter(
                target_handle,
                fieldnames=spec.target_columns,
                delimiter=delimiter,
            )
            target_writer.writeheader()

            for source_row in source_reader:
                target_row = apply_mappings(source_row, spec.mappings)
                target_writer.writerow(
                    {
                        column: _escape_formula(value)
                        for column, value in target_row.items()
                    }
                )
