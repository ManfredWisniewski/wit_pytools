"""Format-independent anonymization functionality."""

from .candidates import (
    VALUE_TYPES,
    CandidateCollector,
    detect_text_candidates,
    is_date_string,
    replacement_for,
    replacement_token_length,
    value_type_for,
)
from .mapping import (
    ANON_COLUMNS,
    CANDIDATE_COLUMNS,
    MAPPING_STATUS_COLUMNS,
    CandidateValidationError,
    MappingValidationError,
    anon_path_for_mapping,
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
from .presidio import (
    DEFAULT_PRESIDIO_ENTITIES,
    PresidioUnavailableError,
    detect_presidio_candidates,
)
from .text import mapping_matches_parts, replace_text_part, replace_text_parts

__all__ = [
    "ANON_COLUMNS",
    "CANDIDATE_COLUMNS",
    "DEFAULT_PRESIDIO_ENTITIES",
    "Candidate",
    "CandidateCollector",
    "CandidateValidationError",
    "MappingValidationError",
    "MAPPING_STATUS_COLUMNS",
    "NameCatalog",
    "NameDatasetUnavailableError",
    "PresidioUnavailableError",
    "VALUE_TYPES",
    "anon_path_for_mapping",
    "create_mapping",
    "detect_text_candidates",
    "group_contained_rows",
    "is_date_string",
    "load_name_catalog",
    "mapping_matches_parts",
    "mapping_path_for_candidates",
    "mapping_path_rows",
    "detect_presidio_candidates",
    "read_mapping_rows",
    "related_mapping_values",
    "replace_related_values",
    "replace_text_part",
    "replace_text_parts",
    "replacement_for",
    "replacement_token_length",
    "value_type_for",
    "write_csv",
]
