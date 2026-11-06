"""Credential loading for marketingautomation (env vars or .env).

Secrets are never stored in this repository; provide them via environment
variables (Ansible vault -> environment) or a .env file.
"""

import os
from pathlib import Path


class MarketingConfigError(RuntimeError):
    """Raised when credentials or settings are missing or invalid."""


def _load_env_files():
    try:
        from dotenv import load_dotenv

        # explicit package-root path only: implicit discovery could pick up
        # a stray .env on the search path and select wrong credentials
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass


GOOGLE_ENV_VARS = (
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REFRESH_TOKEN",
)

META_ENV_VARS = ("META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID")


def _require(env, names, hint):
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise MarketingConfigError(
            f"missing {hint} environment variables: {', '.join(missing)}"
        )


def load_google_settings():
    """Return Google OAuth settings from the environment.

    Optional: GOOGLE_APPLICATION_CREDENTIALS pointing to a service-account
    JSON file (used instead of the OAuth refresh token when set).
    """
    _load_env_files()
    service_account = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not service_account:
        _require(os.environ, GOOGLE_ENV_VARS, "Google OAuth")
    return {
        "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", ""),
        "service_account_file": service_account,
    }


def load_meta_settings():
    """Return Meta settings from the environment.

    META_ACCESS_TOKEN is required; META_AD_ACCOUNT_ID is optional and only
    needed for ad-account scoped calls.
    """
    _load_env_files()
    _require(os.environ, ("META_ACCESS_TOKEN",), "Meta")
    return {
        "access_token": os.environ["META_ACCESS_TOKEN"],
        "ad_account_id": os.environ.get("META_AD_ACCOUNT_ID", ""),
    }
