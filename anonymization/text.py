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
    result = pattern.sub(lambda match: mapping[match.group(0)], part)
    # collapse consecutive identical replacements (e.g. "TIM Tim" -> "Person-x Person-x")
    replacements = sorted(
        {value for value in mapping.values() if value},
        key=len,
        reverse=True,
    )
    if replacements:
        collapse = re.compile(
            r"(?<!\w)("
            + "|".join(re.escape(value) for value in replacements)
            + r")((?:\s+)\1)+(?!\w)"
        )
        result = collapse.sub(lambda match: match.group(1), result)
    return result


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
