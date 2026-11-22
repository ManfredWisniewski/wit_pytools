"""Data models for generic anonymization."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Candidate:
    """A detected value and its anonymization metadata."""

    original_value: str
    replacement_value: str
    value_type: str
    source_documents: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    occurrences: int = 0

    def add_location(self, source_document: str, location: str) -> None:
        self.source_documents.append(source_document)
        self.locations.append(location)
        self.occurrences += 1
