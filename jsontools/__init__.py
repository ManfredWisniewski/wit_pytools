"""JSON file helper tools."""

import json
from os import PathLike
from typing import Any, Dict, Optional, Union

from wit_pytools.mappingtools import (
    apply_json_mappings,
    get_path,
    load_mapping_file,
)


Path = Union[str, PathLike[str]]


def load_json(json_file: Path, *, encoding: str = "utf-8") -> Any:
    """Load a JSON file and return the parsed object."""
    with open(json_file, encoding=encoding) as file_handle:
        return json.load(file_handle)


def write_json(
    json_file: Path,
    data: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Write an object to a JSON file with a trailing newline."""
    with open(json_file, "w", encoding=encoding, newline="") as file_handle:
        json.dump(data, file_handle, indent=indent, ensure_ascii=ensure_ascii)
        file_handle.write("\n")


def json_transform(
    source_file: Path,
    target_file: Path,
    mapping_file: Path,
    *,
    source_path: str,
    target_key: str = "items",
    extra: Optional[Dict[str, Any]] = None,
    encoding: str = "utf-8",
) -> None:
    """Transform a JSON export into a mapped JSON document.

    Reads the entry array at source_path, applies the mapping to each
    entry and writes {**extra, target_key: [mapped entries]}.
    """
    spec = load_mapping_file(mapping_file, encoding=encoding)
    source = load_json(source_file, encoding=encoding)
    entries = get_path(source, source_path) or []
    document = dict(extra or {})
    document[target_key] = [
        apply_json_mappings(entry, spec.mappings) for entry in entries
    ]
    write_json(target_file, document, encoding=encoding)
