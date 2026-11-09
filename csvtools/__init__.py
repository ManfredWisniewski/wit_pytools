"""CSV transformation tools."""

import csv
import json
import re
from datetime import datetime
from os import PathLike
from typing import Callable, Dict, Union


Path = Union[str, PathLike[str]]


def _escape_formula(value: str) -> str:
    """Prefix leading spreadsheet-formula trigger characters."""
    if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _transform_flatten_custom_fields(value: str) -> str:
    """Flatten Passman custom_fields JSON into 'label: value' lines."""
    try:
        fields = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(fields, list):
        return value
    return "\n".join(
        f"{field['label']}: {field['value']}"
        for field in fields
        if field.get("label") and field.get("value") is not None
    )


def _transform_parse_custom_fields(value: str) -> str:
    """Convert PasswordsApp 'label, type: value' lines into Passman JSON."""
    fields = []
    for line in value.splitlines():
        if not line.strip():
            continue
        label, _, rest = line.partition(", ")
        field_type, _, field_value = rest.partition(": ")
        secret = field_type == "secret"
        fields.append(
            {
                "label": label,
                "value": field_value,
                "secret": secret,
                "field_type": "password" if secret else "text",
            }
        )
    return json.dumps(fields)


def _transform_unix_timestamp(value: str) -> str:
    """Convert 'Wed Jul 09 2025 16:39:35 GMT+0200 (...)' to unix seconds."""
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", value)
    parsed = datetime.strptime(cleaned, "%a %b %d %Y %H:%M:%S GMT%z")
    return str(int(parsed.timestamp()))


TRANSFORMS: Dict[str, Callable[[str], str]] = {
    "flatten_custom_fields": _transform_flatten_custom_fields,
    "parse_custom_fields": _transform_parse_custom_fields,
    "unix_timestamp": _transform_unix_timestamp,
}


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
            (
                row["source_column"],
                row["target_column"],
                row.get("target_default") or "",
                row.get("transform") or "",
            )
            for row in mapping_reader
        ]

    if not mappings:
        raise ValueError("Mapping file does not contain any mappings")

    unknown_transforms = {
        transform
        for _, _, _, transform in mappings
        if transform and transform not in TRANSFORMS
    }
    if unknown_transforms:
        raise ValueError(
            "Unknown transforms: " + ", ".join(sorted(unknown_transforms))
        )

    target_columns = [target_column for _, target_column, _, _ in mappings]

    with open(source_file, encoding=encoding, newline="") as source_handle:
        source_reader = csv.DictReader(source_handle, delimiter=delimiter)
        source_columns = set(source_reader.fieldnames or [])
        missing_columns = {
            source_column
            for source_column, _, _, _ in mappings
            if source_column and source_column not in source_columns
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
                target_row = {}
                for (
                    source_column,
                    target_column,
                    target_default,
                    transform,
                ) in mappings:
                    if source_column:
                        value = source_row[source_column]
                        if transform:
                            value = TRANSFORMS[transform](value)
                        value = _escape_formula(value)
                    else:
                        value = target_default
                    if target_column in target_row:
                        if target_row[target_column] and value:
                            target_row[target_column] += "\n" + value
                        elif value:
                            target_row[target_column] = value
                    else:
                        target_row[target_column] = value
                target_writer.writerow(target_row)
