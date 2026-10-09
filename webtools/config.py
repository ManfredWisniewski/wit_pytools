"""Credential loading for webtools site automations (env or .env)."""

import os
from pathlib import Path


class WebtoolsConfigError(RuntimeError):
    """Raised when credentials are missing or invalid."""


def _load_env_files():
    try:
        from dotenv import load_dotenv

        load_dotenv()
        # .env next to the package root (wit_pytools/), used when cwd differs
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass


def load_credentials(site):
    """Return (username, password) from <SITE>_USERNAME / <SITE>_PASSWORD."""
    _load_env_files()
    prefix = site.upper().replace("-", "_")
    username = os.environ.get(f"{prefix}_USERNAME", "")
    password = os.environ.get(f"{prefix}_PASSWORD", "")
    if not username or not password:
        raise WebtoolsConfigError(
            f"{prefix}_USERNAME and {prefix}_PASSWORD must be set (env or .env)"
        )
    return username, password


def load_credentials_group(site):
    """Return {TAG: (username, password)} for every <SITE>_<TAG>_USERNAME
    found, e.g. AMEX_FAW_* -> tag 'FAW'. An untagged <SITE>_USERNAME pair
    maps to the empty-string tag."""
    _load_env_files()
    prefix = site.upper().replace("-", "_")
    suffix = "_USERNAME"
    accounts = {}
    for key, username in os.environ.items():
        if not key.endswith(suffix):
            continue
        stem = key[: -len(suffix)]
        if stem != prefix and not stem.startswith(prefix + "_"):
            continue
        tag = stem[len(prefix):].lstrip("_")
        password = os.environ.get(f"{stem}_PASSWORD", "")
        if not username or not password:
            raise WebtoolsConfigError(
                f"{stem}_USERNAME and {stem}_PASSWORD must both be set "
                "(env or .env)"
            )
        accounts[tag] = (username, password)
    if not accounts:
        raise WebtoolsConfigError(
            f"{prefix}_USERNAME and {prefix}_PASSWORD must be set (env or .env)"
        )
    return accounts
