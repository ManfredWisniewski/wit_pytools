"""CSV transformation tools."""

import csv
from os import PathLike
from typing import Union


Path = Union[str, PathLike[str]]


def csv_transform(
    source_file: Path,
    target_file: Path,
    mapping_file: Path,
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> None:
    """Transform a CSV file using source-to-target column mappings."""
    with open(mapping_file, encoding=encoding, newline="") as file_handle:
        source_info = file_handle.readline().strip()
        target_info = file_handle.readline().strip()
        if not source_info.startswith("Source:"):
            raise ValueError("Mapping file must start with source information")
        if not target_info.startswith("Target:"):
            raise ValueError("Mapping file must contain target information")

        mapping_reader = csv.DictReader(
            line for line in file_handle if line.strip()
        )
        required_fields = {"source_column", "target_column"}
        mapping_fields = set(mapping_reader.fieldnames or [])
        missing_fields = required_fields - mapping_fields
        if missing_fields:
            raise ValueError(
                "Mapping file is missing columns: "
                + ", ".join(sorted(missing_fields))
            )

        mappings = [
            (row["source_column"], row["target_column"])
            for row in mapping_reader
        ]

    if not mappings:
        raise ValueError("Mapping file does not contain any mappings")

    target_columns = [target_column for _, target_column in mappings]

    with open(source_file, encoding=encoding, newline="") as source_handle:
        source_reader = csv.DictReader(source_handle, delimiter=delimiter)
        source_columns = set(source_reader.fieldnames or [])
        missing_columns = {
            source_column
            for source_column, _ in mappings
            if source_column not in source_columns
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
                fieldnames=target_columns,
                delimiter=delimiter,
            )
            target_writer.writeheader()

            for source_row in source_reader:
                target_writer.writerow(
                    {
                        target_column: source_row[source_column]
                        for source_column, target_column in mappings
                    }
                )
