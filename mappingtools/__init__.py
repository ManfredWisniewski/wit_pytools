"""Mapping definitions and value transforms between data formats."""

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from typing import Callable, Dict, List, NamedTuple, Union


Path = Union[str, PathLike[str]]


class Mapping(NamedTuple):
    """One source-to-target column mapping."""

    source_column: str
    target_column: str
    target_default: str = ""
    transform: str = ""


@dataclass
class MappingSpec:
    """Parsed mapping file: header info plus column mappings."""

    source_info: str
    target_info: str
    mappings: List[Mapping]

    @property
    def target_columns(self) -> List[str]:
        return [mapping.target_column for mapping in self.mappings]


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


def load_mapping_file(
    mapping_file: Path, *, encoding: str = "utf-8"
) -> MappingSpec:
    """Parse a Source:/Target: mapping file into a MappingSpec."""
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
            Mapping(
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
        mapping.transform
        for mapping in mappings
        if mapping.transform and mapping.transform not in TRANSFORMS
    }
    if unknown_transforms:
        raise ValueError(
            "Unknown transforms: " + ", ".join(sorted(unknown_transforms))
        )

    return MappingSpec(source_info, target_info, mappings)


def apply_mappings(row: Dict[str, str], mappings: List[Mapping]) -> Dict[str, str]:
    """Apply mappings to a row dict; repeated targets merge with newline."""
    target_row = {}
    for mapping in mappings:
        if mapping.source_column:
            value = row[mapping.source_column]
            if mapping.transform:
                value = TRANSFORMS[mapping.transform](value)
        else:
            value = mapping.target_default
        if mapping.target_column in target_row:
            if target_row[mapping.target_column] and value:
                target_row[mapping.target_column] += "\n" + value
            elif value:
                target_row[mapping.target_column] = value
        else:
            target_row[mapping.target_column] = value
    return target_row
