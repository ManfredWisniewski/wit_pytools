"""Optional country-aware name datasets."""

import csv
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)
REPOSITORY = "sigpwned/popular-names-by-country-dataset"
GERMAN_REPOSITORY = "ynsrc/german-categorized-wordlist"
BRANCH = "main"
COMMIT_URL = f"https://api.github.com/repos/{REPOSITORY}/commits/{BRANCH}"
GERMAN_COMMIT_URL = (
    f"https://api.github.com/repos/{GERMAN_REPOSITORY}/commits/{BRANCH}"
)
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}"
GERMAN_RAW_BASE_URL = (
    f"https://raw.githubusercontent.com/{GERMAN_REPOSITORY}/{BRANCH}/v1"
)
DATASET_FILES = {
    "forenames": "common-forenames-by-country.csv",
    "surnames": "common-surnames-by-country.csv",
}
GERMAN_DATASET_FILES = {
    "nouns": "noun.txt",
    "forenames": "noun-proper-first-name.txt",
    "surnames": "noun-proper-surname.txt",
}
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
DEFAULT_NAME_EXCLUSIONS = frozenset(
    {"and", "contact", "email", "for", "password", "server", "test", "the", "user"}
)


class NameDatasetUnavailableError(RuntimeError):
    """Raised when configured name data is unavailable and uncached."""


@dataclass(frozen=True)
class NameCatalog:
    """Normalized forename and surname sets for selected countries."""

    countries: frozenset[str]
    forenames: frozenset[str]
    surnames: frozenset[str]
    noun_words: frozenset[str] = frozenset()
    exclusions: frozenset[str] = frozenset()

    def is_dictionary_word(self, value: str) -> bool:
        tokens = [_normalize(token) for token in TOKEN_PATTERN.findall(value)]
        return bool(tokens) and bool(self.noun_words) and all(
            token in self.noun_words for token in tokens
        )

    def is_name(self, value: str) -> bool:
        tokens = [_normalize(token) for token in TOKEN_PATTERN.findall(value)]
        if any(token in self.exclusions for token in tokens):
            return False
        if len(tokens) == 1:
            if tokens[0] in self.noun_words:
                return False
            return tokens[0] in self.forenames or tokens[0] in self.surnames
        if len(tokens) < 2:
            return False
        return any(token in self.forenames for token in tokens) and any(
            token in self.surnames for token in tokens
        )


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "wit_pytools" / "anonymization" / "names"


def _option_bool(value: Optional[bool], environment_name: str, default: bool) -> bool:
    if value is not None:
        return value
    environment_value = os.getenv(environment_name)
    if environment_value is None:
        return default
    return environment_value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_name_options(
    countries: Optional[Sequence[str]],
    use_name_datasets: Optional[bool],
    offline: Optional[bool],
) -> tuple[tuple[str, ...], bool, bool]:
    if countries is None:
        configured = os.getenv("ANONYMIZATION_NAME_COUNTRIES", "")
        countries = tuple(item.strip() for item in configured.split(",") if item.strip())
    normalized = tuple(sorted({country.strip().upper() for country in countries}))
    use_data = _option_bool(use_name_datasets, "ANONYMIZATION_USE_NAME_DATASETS", bool(normalized))
    offline_mode = _option_bool(offline, "ANONYMIZATION_NAME_DATASET_OFFLINE", False)
    return normalized, use_data, offline_mode


def _fetch_commit() -> str:
    request = Request(COMMIT_URL, headers={"User-Agent": "wit-pytools-anonymization"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    commit = payload.get("sha")
    if not isinstance(commit, str) or not commit:
        raise NameDatasetUnavailableError("GitHub commit response did not contain a commit")
    return commit


def _fetch_german_commit() -> str:
    request = Request(
        GERMAN_COMMIT_URL,
        headers={"User-Agent": "wit-pytools-anonymization"},
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    commit = payload.get("sha")
    if not isinstance(commit, str) or not commit:
        raise NameDatasetUnavailableError(
            "German wordlist commit response did not contain a commit"
        )
    return commit


def _fetch_text(dataset_name: str) -> str:
    filename = DATASET_FILES[dataset_name]
    request = Request(
        f"{RAW_BASE_URL}/{filename}",
        headers={"User-Agent": "wit-pytools-anonymization"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def _fetch_german_text(dataset_name: str) -> str:
    filename = GERMAN_DATASET_FILES[dataset_name]
    request = Request(
        f"{GERMAN_RAW_BASE_URL}/{filename}",
        headers={"User-Agent": "wit-pytools-anonymization"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def _cache_files(cache_dir: Path) -> tuple[Path, Path, Path]:
    return (
        cache_dir / DATASET_FILES["forenames"],
        cache_dir / DATASET_FILES["surnames"],
        cache_dir / "metadata.json",
    )


def _german_cache_files(cache_dir: Path) -> tuple[Path, Path, Path]:
    return (
        cache_dir / GERMAN_DATASET_FILES["nouns"],
        cache_dir / GERMAN_DATASET_FILES["forenames"],
        cache_dir / GERMAN_DATASET_FILES["surnames"],
    )


def _cache_is_complete(cache_dir: Path, german: bool = False) -> bool:
    paths = list(_cache_files(cache_dir))
    if german:
        paths.extend(_german_cache_files(cache_dir))
    return all(path.is_file() for path in paths)


def _load_cache(
    cache_dir: Path,
    countries: tuple[str, ...],
    *,
    exclusions: frozenset[str] = DEFAULT_NAME_EXCLUSIONS,
    debug: bool = False,
    german: bool = False,
) -> NameCatalog:
    forenames_path, surnames_path, metadata_path = _cache_files(cache_dir)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    german_contents = None
    if german:
        german_contents = tuple(
            path.read_text(encoding="utf-8-sig")
            for path in _german_cache_files(cache_dir)
        )
    catalog = _catalog_from_csv(
        forenames_path.read_text(encoding="utf-8-sig"),
        surnames_path.read_text(encoding="utf-8-sig"),
        countries,
        exclusions,
        german_contents,
    )
    if debug:
        LOGGER.debug(
            "Using cached name datasets commit=%s countries=%s",
            metadata.get("commit"),
            ",".join(countries),
        )
    return catalog


def _write_cache(
    cache_dir: Path,
    commit: str,
    forenames: str,
    surnames: str,
    german_commit: Optional[str] = None,
    german_contents: Optional[tuple[str, str, str]] = None,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    forenames_path, surnames_path, metadata_path = _cache_files(cache_dir)
    forenames_path.write_text(forenames, encoding="utf-8")
    surnames_path.write_text(surnames, encoding="utf-8")
    if german_contents is not None:
        for path, content in zip(_german_cache_files(cache_dir), german_contents):
            path.write_text(content, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "repository": REPOSITORY,
                "branch": BRANCH,
                "commit": commit,
                "files": DATASET_FILES,
                "german_repository": GERMAN_REPOSITORY if german_commit else None,
                "german_commit": german_commit,
                "german_files": GERMAN_DATASET_FILES if german_commit else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _catalog_from_csv(
    forenames_csv: str,
    surnames_csv: str,
    countries: tuple[str, ...],
    exclusions: frozenset[str] = DEFAULT_NAME_EXCLUSIONS,
    german_contents: Optional[tuple[str, str, str]] = None,
) -> NameCatalog:
    requested = set(countries)
    forenames = set()
    surnames = set()
    noun_words = set()
    available = set()

    for row in csv.DictReader(forenames_csv.splitlines()):
        country = (row.get("Country") or "").strip().upper()
        if country in requested:
            available.add(country)
            for key in ("Localized Name", "Romanized Name"):
                value = (row.get(key) or "").strip()
                if value:
                    forenames.add(_normalize(value))

    for row in csv.DictReader(surnames_csv.splitlines()):
        country = (row.get("Country") or "").strip().upper()
        if country in requested:
            available.add(country)
            for key in ("Localized Name", "Romanized Name"):
                value = (row.get(key) or "").strip()
                if value:
                    surnames.add(_normalize(value))

    if german_contents is not None and "DE" in requested:
        noun_text, german_forenames, german_surnames = german_contents
        noun_words.update(
            _normalize(line)
            for line in noun_text.splitlines()
            if line.strip()
        )
        forenames.update(
            _normalize(line)
            for line in german_forenames.splitlines()
            if line.strip()
        )
        surnames.update(
            _normalize(line)
            for line in german_surnames.splitlines()
            if line.strip()
        )
        available.add("DE")

    missing = requested - available
    if missing:
        raise ValueError(
            "Configured countries are not present in the name datasets: "
            + ", ".join(sorted(missing))
        )
    return NameCatalog(
        frozenset(requested),
        frozenset(forenames),
        frozenset(surnames),
        frozenset(noun_words),
        exclusions,
    )


def load_name_catalog(
    countries: Optional[Sequence[str]] = None,
    *,
    use_name_datasets: Optional[bool] = None,
    cache_dir: Optional[Path | str] = None,
    offline: Optional[bool] = None,
    debug: bool = False,
    name_exclusions: Optional[Sequence[str]] = None,
) -> Optional[NameCatalog]:
    """Load selected country data, refreshing the cache when the repository changes."""
    selected, use_data, offline_mode = resolve_name_options(
        countries, use_name_datasets, offline
    )
    if not use_data or not selected:
        return None
    for country in selected:
        if not COUNTRY_PATTERN.fullmatch(country):
            raise ValueError(f"Invalid country code: {country!r}")
    exclusions = frozenset(
        DEFAULT_NAME_EXCLUSIONS
        | {_normalize(value) for value in (name_exclusions or ())}
    )

    target_dir = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    forenames_path, surnames_path, metadata_path = _cache_files(target_dir)
    german_enabled = "DE" in selected
    cache_available = _cache_is_complete(target_dir, german=german_enabled)

    try:
        if offline_mode:
            if not cache_available:
                raise NameDatasetUnavailableError(
                    "Name datasets are unavailable offline and no cache exists"
                )
            return _load_cache(
                target_dir,
                selected,
                exclusions=exclusions,
                debug=debug,
                german=german_enabled,
            )

        commit = _fetch_commit()
        german_commit = _fetch_german_commit() if german_enabled else None
        cached_commit = None
        cached_german_commit = None
        if cache_available:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                cached_commit = metadata.get("commit")
                cached_german_commit = metadata.get("german_commit")
            except (OSError, json.JSONDecodeError):
                cached_commit = None
        if (
            cache_available
            and cached_commit == commit
            and cached_german_commit == german_commit
        ):
            return _load_cache(
                target_dir,
                selected,
                exclusions=exclusions,
                debug=debug,
                german=german_enabled,
            )

        forenames = _fetch_text("forenames")
        surnames = _fetch_text("surnames")
        german_contents = None
        if german_enabled:
            german_contents = tuple(
                _fetch_german_text(dataset)
                for dataset in ("nouns", "forenames", "surnames")
            )
        _write_cache(
            target_dir,
            commit,
            forenames,
            surnames,
            german_commit=german_commit,
            german_contents=german_contents,
        )
        if debug:
            LOGGER.debug(
                "Downloaded name datasets commit=%s german_commit=%s",
                commit,
                german_commit,
            )
        return _catalog_from_csv(
            forenames,
            surnames,
            selected,
            exclusions,
            german_contents,
        )
    except (
        OSError,
        URLError,
        TimeoutError,
        UnicodeError,
        json.JSONDecodeError,
        NameDatasetUnavailableError,
    ) as exc:
        if cache_available:
            if debug:
                LOGGER.debug("Using cached name datasets after update failure: %s", exc)
            return _load_cache(
                target_dir,
                selected,
                exclusions=exclusions,
                debug=debug,
                german=german_enabled,
            )
        raise NameDatasetUnavailableError(
            "Configured name datasets could not be loaded and no cache exists"
        ) from exc
