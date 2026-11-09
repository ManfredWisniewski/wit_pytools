"""JSON file helper tools."""

import json
from os import PathLike
from typing import Any, Union


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
