"""Presidio-backed candidate detection."""

from functools import lru_cache
import re
from typing import Iterable, List, Optional, Sequence, Tuple

from .candidates import CandidateCollector
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
        if ignore_emails and (entity_type == "EMAIL_ADDRESS" or "@" in value):
            continue
        if ignore_numbers and re.fullmatch(r"[\d\s.,:/()+\-€$%]+", value):
            continue
        if ignore_dictionary and name_catalog is not None and name_catalog.is_dictionary_word(value):
            continue
        if entity_type in {"EMAIL_ADDRESS"}:
            value_type = "email"
        elif entity_type in {"URL"}:
            value_type = "url"
        elif entity_type in {"PERSON", "FIRST_NAME", "LAST_NAME"}:
            value_type = "name"
        else:
            value_type = "string"
        line_number = content.count("\n", 0, start) + 1
        collector.add(value, source_document, f"line {line_number}", value_type=value_type)
    return collector.values()
