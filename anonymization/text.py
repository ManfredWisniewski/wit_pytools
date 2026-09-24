"""Generic text replacement helpers."""

import re
from typing import Dict, Iterable, Tuple


def replace_text_part(part: str, mapping: Dict[str, str]) -> str:
    keys = sorted((key for key in mapping if key), key=len, reverse=True)
    if not keys:
        return part
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(key) for key in keys) + r")(?!\w)"
    )
    return pattern.sub(lambda match: mapping[match.group(0)], part)


def replace_text_parts(
    parts: Iterable[Tuple[bool, str]],
    mapping: Dict[str, str],
) -> str:
    """Replace values in editable parts and preserve protected parts exactly."""
    return "".join(
        replace_text_part(part, mapping) if editable else part
        for editable, part in parts
    )


def mapping_matches_parts(
    parts: Iterable[Tuple[bool, str]],
    mapping: Dict[str, str],
) -> bool:
    return any(
        key in part
        for editable, part in parts
        if editable
        for key in mapping
    )
