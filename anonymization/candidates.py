"""Generic candidate detection and classification."""

import re
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from .models import Candidate


VALUE_TYPES = {"email", "url", "name", "string"}
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_NAME_PATTERN = re.compile(
    r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t]+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}"
)
_DATE_FORMATS = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")
_TEXT_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_TEXT_NAME_PATTERN = re.compile(
    r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t]+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}"
)


class CandidateCollector:
    """Collect unique candidates and aggregate their locations."""

    def __init__(self) -> None:
        self._candidates: dict[str, Candidate] = {}

    def add(self, value: str, source_document: str, location: str) -> None:
        value_type = value_type_for(value)
        candidate = self._candidates.setdefault(
            value,
            Candidate(
                original_value=value,
                replacement_value=replacement_for(value, value_type),
                value_type=value_type,
            ),
        )
        candidate.add_location(source_document, location)

    def values(self) -> List[Candidate]:
        return list(self._candidates.values())


def parse_date(value: str, date_format: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, date_format)
    except ValueError:
        return None


def is_date_string(value: str) -> bool:
    value = value.strip()
    return any(parse_date(value, date_format) is not None for date_format in _DATE_FORMATS)


def value_type_for(value: str) -> str:
    if _EMAIL_PATTERN.fullmatch(value):
        return "email"
    if _URL_PATTERN.fullmatch(value):
        return "url"
    if _NAME_PATTERN.fullmatch(value):
        return "name"
    return "string"


def replacement_for(value: str, value_type: str) -> str:
    import hashlib

    token = hashlib.sha256(value.encode("utf-8")).hexdigest()[:3]
    if value_type == "email":
        return f"person-{token}@example.invalid"
    if value_type == "url":
        return f"https://example.invalid/{token}"
    if value_type == "name":
        return f"Person-{token}"
    return f"value-{token}"


def detect_text_candidates(
    content: str,
    source_document: str,
    protected_spans: Iterable[Tuple[int, int]] = (),
) -> List[Candidate]:
    """Detect names and e-mail addresses outside supplied protected spans."""
    spans = tuple(protected_spans)
    collector = CandidateCollector()
    patterns = (_TEXT_EMAIL_PATTERN, _TEXT_NAME_PATTERN)
    for pattern in patterns:
        for match in pattern.finditer(content):
            if any(match.start() < end and match.end() > start for start, end in spans):
                continue
            original = match.group(0).rstrip(".,;:!?")
            if not original:
                continue
            line_number = content.count("\n", 0, match.start()) + 1
            collector.add(original, source_document, f"line {line_number}")
    return collector.values()
