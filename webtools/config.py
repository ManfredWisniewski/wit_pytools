"""Credential loading for webtools site automations (env or .env)."""

import os
from pathlib import Path


class WebtoolsConfigError(RuntimeError):
    """Raised when credentials are missing or invalid."""


def load_credentials(site):
    """Return (username, password) from <SITE>_USERNAME / <SITE>_PASSWORD."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
        # .env next to the package root (wit_pytools/), used when cwd differs
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    prefix = site.upper().replace("-", "_")
    username = os.environ.get(f"{prefix}_USERNAME", "")
    password = os.environ.get(f"{prefix}_PASSWORD", "")
    if not username or not password:
        raise WebtoolsConfigError(
            f"{prefix}_USERNAME and {prefix}_PASSWORD must be set (env or .env)"
        )
    return username, password
