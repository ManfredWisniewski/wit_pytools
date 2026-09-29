"""Configuration loading for payloadtools (.witcontent.yml + environment)."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAME = ".witcontent.yml"
DEFAULT_STATUS_REGEX = r"_webtext(?P<sep>[-_])(?P<status>[a-z-]+)$"


class PayloadConfigError(RuntimeError):
    """Raised when configuration or credentials are missing/invalid."""


@dataclass
class RouteConfig:
    strip_dir_prefixes: list = field(default_factory=list)
    strip_dir_suffixes: list = field(default_factory=list)
    strip_leading_underscore: bool = False
    overrides: dict = field(default_factory=dict)


@dataclass
class Config:
    repo: Path
    collection: str = "pages"
    media_collection: str = "media"
    include_glob: str = "**/*_webtext*.md"
    status_regex: str = r"_webtext(?P<sep>[-_])(?P<status>[a-z-]+)$"
    publishable_statuses: list = field(default_factory=list)
    slug_prefixes: list = field(default_factory=list)
    route: RouteConfig = field(default_factory=RouteConfig)
    meta: dict = field(default_factory=dict)
    transforms: list = field(default_factory=list)
    source_repo: str = ""


def load_config(repo) -> Config:
    """Load .witcontent.yml from the content repository root."""
    repo = Path(repo).resolve()
    config_path = repo / CONFIG_FILENAME
    if not config_path.is_file():
        raise PayloadConfigError(f"Missing {CONFIG_FILENAME} in {repo}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise PayloadConfigError(
            f"Cannot read {CONFIG_FILENAME}: {error}"
        ) from error
    status_regex = raw.get("status_regex", DEFAULT_STATUS_REGEX)
    try:
        re.compile(status_regex)
    except re.error as error:
        raise PayloadConfigError(
            f"Invalid status_regex in {CONFIG_FILENAME}: {error}"
        ) from error
    route_raw = raw.get("route") or {}
    return Config(
        repo=repo,
        collection=raw.get("collection", "pages"),
        media_collection=raw.get("media_collection", "media"),
        include_glob=raw.get("include_glob", "**/*_webtext*.md"),
        status_regex=status_regex,
        publishable_statuses=list(raw.get("publishable_statuses") or []),
        slug_prefixes=list(raw.get("slug_prefixes") or []),
        route=RouteConfig(
            strip_dir_prefixes=list(route_raw.get("strip_dir_prefixes") or []),
            strip_dir_suffixes=list(route_raw.get("strip_dir_suffixes") or []),
            strip_leading_underscore=bool(
                route_raw.get("strip_leading_underscore", False)
            ),
            overrides=dict(route_raw.get("overrides") or {}),
        ),
        meta=dict(raw.get("meta") or {}),
        transforms=list(raw.get("transforms") or []),
        source_repo=str(raw.get("source_repo") or repo.name),
    )


def load_credentials():
    """Return (base_url, api_key) from environment or .env file."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    base_url = os.environ.get("PAYLOAD_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("PAYLOAD_API_KEY", "")
    if not base_url or not api_key:
        raise PayloadConfigError(
            "PAYLOAD_BASE_URL and PAYLOAD_API_KEY must be set (env or .env)"
        )
    return base_url, api_key
