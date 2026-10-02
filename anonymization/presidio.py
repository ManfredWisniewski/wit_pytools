"""Presidio-backed candidate detection."""

from bisect import bisect_right
from functools import lru_cache
from typing import Iterable, List, Optional, Sequence, Tuple

from .candidates import CandidateCollector, is_date_string, replacement_for
from .models import Candidate


DEFAULT_PRESIDIO_ENTITIES = (
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "ORGANIZATION",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "CRYPTO",
    "IBAN_CODE",
    "NRP",
    "MEDICAL_LICENSE",
)


class PresidioUnavailableError(RuntimeError):
    """Raised when Presidio cannot be imported or initialized."""


@lru_cache(maxsize=4)
def _create_engine(language: str, model_name: str):
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine.nlp_engine_provider import NlpEngineProvider
    except ImportError as exc:
        raise PresidioUnavailableError(
            "Presidio mode requires a compatible presidio-analyzer package"
        ) from exc

    try:
        if language == "de":
            provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [
                        {"lang_code": language, "model_name": model_name},
                    ],
                }
            )
            return AnalyzerEngine(
                nlp_engine=provider.create_engine(),
                supported_languages=[language],
            )
        return AnalyzerEngine()
    except Exception as exc:
        raise PresidioUnavailableError(
            f"Presidio could not initialize language {language!r} "
            f"with model {model_name!r}"
        ) from exc


def detect_presidio_candidates(
    content: str,
    source_document: str,
    protected_spans: Iterable[Tuple[int, int]] = (),
    *,
    language: str = "en",
    model_name: str = "de_core_news_sm",
    score_threshold: float = 0.5,
    entities: Optional[Sequence[str]] = None,
    replacement_length: int = 4,
    name_catalog=None,
    ignore_dictionary: bool = False,
    ignore_numbers: bool = False,
    ignore_emails: bool = False,
    ignore_dates: bool = False,
    ignored_candidates: Optional[List[Candidate]] = None,
) -> List[Candidate]:
    """Detect PII with Presidio and return the common candidate model."""
    analyzer = _create_engine(language, model_name)
    results = analyzer.analyze(
        text=content,
        language=language,
        score_threshold=score_threshold,
        entities=list(entities) if entities is not None else list(DEFAULT_PRESIDIO_ENTITIES),
    )
    spans = tuple(protected_spans)
    collector = CandidateCollector(replacement_length=replacement_length)
    # Newline offsets once: line_number lookup becomes O(log n) per result
    newline_offsets = [
        index for index, char in enumerate(content) if char == "\n"
    ]
    for result in results:
        if any(result.start < end and result.end > start for start, end in spans):
            continue
        raw_value = content[result.start : result.end]
        leading = len(raw_value) - len(raw_value.lstrip())
        trailing = len(raw_value) - len(raw_value.rstrip())
        start = result.start + leading
        end = result.end - trailing
        value = content[start:end]
        if not value or "\n" in value or "\r" in value:
            continue
        if "person-" in value.casefold():
            continue
        entity_type = result.entity_type.upper()
        if entity_type in {"EMAIL_ADDRESS"}:
            value_type = "email"
        elif entity_type in {"URL"}:
            value_type = "url"
        elif entity_type in {"PERSON", "FIRST_NAME", "LAST_NAME"}:
            value_type = "name"
        else:
            value_type = "string"
        ignored = (
            (ignore_emails and (entity_type == "EMAIL_ADDRESS" or "@" in value))
            or (ignore_numbers and any(character.isdigit() for character in value))
            or (ignore_dates and (entity_type == "DATE_TIME" or is_date_string(value)))
            or (
                ignore_dictionary
                and name_catalog is not None
                and name_catalog.is_dictionary_word(value)
            )
        )
        line_number = bisect_right(newline_offsets, start - 1) + 1
        if ignored:
            if ignored_candidates is not None:
                candidate = Candidate(
                    original_value=value,
                    replacement_value=replacement_for(
                        value,
                        value_type,
                        replacement_length,
                    ),
                    value_type=value_type,
                )
                candidate.add_location(source_document, f"line {line_number}")
                ignored_candidates.append(candidate)
            continue
        collector.add(value, source_document, f"line {line_number}", value_type=value_type)
    return collector.values()
