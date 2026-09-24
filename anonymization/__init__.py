"""Format-independent anonymization functionality."""

from .candidates import (
    VALUE_TYPES,
    CandidateCollector,
    detect_text_candidates,
    is_date_string,
    replacement_for,
    value_type_for,
)
from .mapping import (
    CANDIDATE_COLUMNS,
    CandidateValidationError,
    MappingValidationError,
    create_mapping,
    group_contained_rows,
    mapping_path_for_candidates,
    mapping_path_rows,
    read_mapping_rows,
    related_mapping_values,
    replace_related_values,
    write_csv,
)
from .models import Candidate
from .name_datasets import (
    NameCatalog,
    NameDatasetUnavailableError,
    load_name_catalog,
)
from .text import mapping_matches_parts, replace_text_part, replace_text_parts

__all__ = [
    "CANDIDATE_COLUMNS",
    "Candidate",
    "CandidateCollector",
    "CandidateValidationError",
    "MappingValidationError",
    "NameCatalog",
    "NameDatasetUnavailableError",
    "VALUE_TYPES",
    "create_mapping",
    "detect_text_candidates",
    "group_contained_rows",
    "is_date_string",
    "load_name_catalog",
    "mapping_matches_parts",
    "mapping_path_for_candidates",
    "mapping_path_rows",
    "read_mapping_rows",
    "related_mapping_values",
    "replace_related_values",
    "replace_text_part",
    "replace_text_parts",
    "replacement_for",
    "value_type_for",
    "write_csv",
]
