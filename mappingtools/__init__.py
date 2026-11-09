"""Mapping definitions and value transforms between data formats."""

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from os import PathLike
from typing import Any, Callable, Dict, List, NamedTuple, Union


Path = Union[str, PathLike[str]]


class Mapping(NamedTuple):
    """One source-to-target column mapping."""

    source_column: str
    target_column: str
    target_default: Any = ""
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


def _transform_flatten_custom_fields(value: Any) -> str:
    """Flatten Passman custom_fields JSON into 'label: value' lines."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    if not isinstance(value, list):
        return value
    return "\n".join(
        f"{field['label']}: {field['value']}"
        for field in value
        if isinstance(field, dict)
        and field.get("label")
        and field.get("value") is not None
    )


def _transform_ncp_custom_fields(value: Any) -> list:
    """Convert Nextcloud Passwords customFields into Bitwarden fields."""
    if not isinstance(value, list):
        return []
    # Bitwarden field types: 0 text, 1 hidden, 2 boolean, 3 linked
    type_map = {"secret": 1}
    return [
        {
            "name": field["label"],
            "type": type_map.get(field.get("type"), 0),
            "value": field.get("value", ""),
        }
        for field in value
        if isinstance(field, dict) and field.get("label")
    ]


def _transform_to_int(value: Any) -> int:
    """Coerce a value to int."""
    return int(value)


def _transform_to_bool(value: Any) -> bool:
    """Coerce a value to bool ('true'/'1'/1/True)."""
    if isinstance(value, str):
        return value.lower() in ("true", "1")
    return bool(value)


def _transform_unix_to_iso(value: Any) -> str:
    """Convert a unix timestamp to ISO 8601 UTC ('...Z')."""
    parsed = datetime.fromtimestamp(int(value), tz=timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.") + f"{parsed.microsecond // 1000:03d}Z"


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


TRANSFORMS: Dict[str, Callable[[Any], Any]] = {
    "flatten_custom_fields": _transform_flatten_custom_fields,
    "ncp_custom_fields": _transform_ncp_custom_fields,
    "parse_custom_fields": _transform_parse_custom_fields,
    "to_bool": _transform_to_bool,
    "to_int": _transform_to_int,
    "unix_timestamp": _transform_unix_timestamp,
    "unix_to_iso": _transform_unix_to_iso,
}


def _load_csv_mapping(mapping_file: Path, encoding: str) -> tuple:
    """Parse a CSV mapping file ('Source:'/'Target:' header + table)."""
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

    return source_info, target_info, mappings


def _load_json_mapping(mapping_file: Path, encoding: str) -> tuple:
    """Parse a JSON mapping file ({source, target, mappings: [...]})."""
    with open(mapping_file, encoding=encoding) as file_handle:
        document = json.load(file_handle)

    source_info = document.get("source", "")
    target_info = document.get("target", "")
    if not source_info or not target_info:
        raise ValueError(
            "Mapping file must contain source and target information"
        )
    raw_mappings = document.get("mappings")
    if not isinstance(raw_mappings, list):
        raise ValueError("Mapping file 'mappings' must be a list")

    mappings = []
    for entry in raw_mappings:
        if "target" not in entry:
            raise ValueError(f"Mapping entry is missing target: {entry!r}")
        mappings.append(
            Mapping(
                entry.get("source", ""),
                entry["target"],
                entry.get("default", ""),
                entry.get("transform", ""),
            )
        )
    return source_info, target_info, mappings


def load_mapping_file(
    mapping_file: Path, *, encoding: str = "utf-8"
) -> MappingSpec:
    """Parse a mapping file (.csv or .json) into a MappingSpec."""
    if str(mapping_file).lower().endswith(".json"):
        source_info, target_info, mappings = _load_json_mapping(
            mapping_file, encoding
        )
    else:
        source_info, target_info, mappings = _load_csv_mapping(
            mapping_file, encoding
        )

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


def get_path(obj: Any, path: str) -> Any:
    """Read a dotted path ('a.b.0.c') from nested dicts/lists; None if missing."""
    for part in path.split("."):
        if isinstance(obj, list):
            if not part.isdigit() or int(part) >= len(obj):
                return None
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            if part not in obj:
                return None
            obj = obj[part]
        else:
            return None
    return obj


def set_path(obj: Union[dict, list], path: str, value: Any) -> None:
    """Write a value at a dotted path, creating dicts/lists as needed."""
    parts = path.split(".")
    for index, part in enumerate(parts[:-1]):
        if isinstance(obj, list):
            position = int(part)
            while len(obj) <= position:
                obj.append({})
            obj = obj[position]
        elif parts[index + 1].isdigit():
            obj = obj.setdefault(part, [])
        else:
            obj = obj.setdefault(part, {})
    last = parts[-1]
    if isinstance(obj, list):
        position = int(last)
        while len(obj) <= position:
            obj.append(None)
        obj[position] = value
    else:
        obj[last] = value


def apply_json_mappings(
    row: Dict[str, Any], mappings: List[Mapping]
) -> Dict[str, Any]:
    """Apply mappings with dotted source/target paths to a dict entry."""
    target: Dict[str, Any] = {}
    for mapping in mappings:
        if mapping.source_column:
            value = get_path(row, mapping.source_column)
        else:
            value = mapping.target_default
        if mapping.transform:
            value = TRANSFORMS[mapping.transform](value)
        set_path(target, mapping.target_column, value)
    return target
