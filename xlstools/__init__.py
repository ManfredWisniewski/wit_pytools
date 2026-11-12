"""Generic XLS/XLSX reading and normalisation helpers."""

from .core import (
    DEFAULT_PLACEHOLDER,
    clean_frame,
    clean_value,
    find_header_row,
    first_content_sheet,
    formula_guard,
    is_number,
    load_replacements,
    read_raw,
)

__all__ = [
    "DEFAULT_PLACEHOLDER",
    "clean_frame",
    "clean_value",
    "find_header_row",
    "first_content_sheet",
    "formula_guard",
    "is_number",
    "load_replacements",
    "read_raw",
]
