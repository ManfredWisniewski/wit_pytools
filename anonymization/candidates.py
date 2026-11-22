"""Generic candidate detection and classification."""

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .models import Candidate
from .name_datasets import NameCatalog, TOKEN_PATTERN


VALUE_TYPES = {"email", "url", "name", "string"}
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_NAME_PATTERN = re.compile(
    r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t]+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}"
)
_DATE_FORMATS = ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")
_ASSETS_DIR = Path(__file__).parent / "assets"


def _asset_words(*parts: str) -> frozenset:
    """Load a ``#``-commented word list from ``assets/``."""
    path = _ASSETS_DIR.joinpath(*parts)
    return frozenset(
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _asset_phrases(*parts: str) -> frozenset:
    """Load a word list as tuples of consecutive tokens."""
    return frozenset(tuple(entry.split()) for entry in _asset_words(*parts))


_LOCATION_SUFFIXES = _asset_words("international", "location-suffixes.txt")
_LOCATION_NAMES = _asset_phrases("international", "location-names.txt")
_CORPORATE_PREFIXES = _asset_words("international", "corporate-prefixes.txt")
_CORPORATE_SUFFIXES = _asset_words("international", "corporate-suffixes.txt")
_CORPORATE_NAMES = _asset_phrases("international", "corporate-names.txt")
_TEXT_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_TEXT_NAME_PATTERN = re.compile(
    r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[ \t]+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+){1,3}"
)


class CandidateCollector:
    """Collect unique candidates and aggregate their locations."""

    def __init__(
        self,
        name_catalog: Optional[NameCatalog] = None,
        replacement_length: int = 4,
    ) -> None:
        self._candidates: dict[str, Candidate] = {}
        self._name_catalog = name_catalog
        self._replacement_length = replacement_length

    def add(
        self,
        value: str,
        source_document: str,
        location: str,
        value_type: Optional[str] = None,
    ) -> None:
        value_type = value_type or value_type_for(value, self._name_catalog)
        candidate = self._candidates.setdefault(
            value,
            Candidate(
                original_value=value,
                replacement_value=replacement_for(
                    value,
                    value_type,
                    self._replacement_length,
                ),
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


def is_location_name(value: str) -> bool:
    """Whether ``value`` looks like ``<name> <location suffix>`` or a known place."""
    tokens = value.split()
    if not tokens:
        return False
    words = [token.rstrip(".,").casefold() for token in tokens]
    if len(words) >= 2 and words[-1] in _LOCATION_SUFFIXES:
        return True
    return any(
        tuple(words[index : index + len(name)]) == name
        for name in _LOCATION_NAMES
        for index in range(len(words) - len(name) + 1)
    )


def is_corporate_name(value: str) -> bool:
    """Whether ``value`` looks like a company name, not a person."""
    tokens = value.split()
    if not tokens:
        return False
    words = [token.rstrip(".,").casefold() for token in tokens]
    if len(tokens) == 1:
        return (words[0],) in _CORPORATE_NAMES
    if words[0] in _CORPORATE_PREFIXES or words[-1] in _CORPORATE_SUFFIXES:
        return True
    return any(
        tuple(words[index : index + len(name)]) == name
        for name in _CORPORATE_NAMES
        for index in range(len(words) - len(name) + 1)
    )


def value_type_for(
    value: str,
    name_catalog: Optional[NameCatalog] = None,
) -> str:
    if _EMAIL_PATTERN.fullmatch(value):
        return "email"
    if _URL_PATTERN.fullmatch(value):
        return "url"
    if _NAME_PATTERN.fullmatch(value):
        return "name"
    if name_catalog is not None and name_catalog.is_name(value):
        return "name"
    return "string"


def replacement_for(value: str, value_type: str, token_length: int = 4) -> str:
    if token_length < 1:
        raise ValueError("token_length must be at least 1")
    import hashlib

    token = hashlib.sha256(value.encode("utf-8")).hexdigest()[:token_length]
    if value_type == "email":
        return f"person-{token}@example.invalid"
    if value_type == "url":
        return f"https://example.invalid/{token}"
    if value_type == "name":
        return f"Person-{token}"
    return f"value-{token}"


def replacement_token_length(replacement: str, value_type: str) -> int:
    prefixes = {
        "email": "person-",
        "url": "https://example.invalid/",
        "name": "Person-",
        "string": "value-",
    }
    prefix = prefixes.get(value_type, "")
    token = replacement[len(prefix):] if replacement.startswith(prefix) else replacement
    if value_type == "email":
        token = token.split("@", 1)[0]
    return len(token)


def detect_text_candidates(
    content: str,
    source_document: str,
    protected_spans: Iterable[Tuple[int, int]] = (),
    name_catalog: Optional[NameCatalog] = None,
    replacement_length: int = 4,
) -> List[Candidate]:
    """Detect names and e-mail addresses outside supplied protected spans."""
    spans = tuple(protected_spans)
    collector = CandidateCollector(name_catalog, replacement_length)
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

    if name_catalog is not None:
        for match in TOKEN_PATTERN.finditer(content):
            if any(match.start() < end and match.end() > start for start, end in spans):
                continue
            original = match.group(0)
            if name_catalog.is_name(original):
                line_number = content.count("\n", 0, match.start()) + 1
                collector.add(original, source_document, f"line {line_number}")
    return collector.values()
