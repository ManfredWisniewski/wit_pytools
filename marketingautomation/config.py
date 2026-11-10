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

SERPER_ENV_VARS = ("SERPER_API_KEY",)


def _repo_root():
    """Outermost git worktree root containing this file.

    wit_pytools is often checked out as a submodule — climbing past its .git
    boundary reaches the superproject root where the shared .env lives.
    """
    root = Path(__file__).resolve().parents[1]
    for parent in root.parents:
        if (parent / ".git").exists():
            root = parent
    return root


def _parse_env_file(path):
    """Minimal KEY=VALUE reader — stdlib fallback when python-dotenv is absent.

    Mirrors dotenv basics: ``#`` comments, surrounding whitespace and quotes;
    an unquoted value ends at the first `` #`` (inline comment).
    """
    values = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip()
                if val[:1] in ('"', "'"):
                    val = val[1:].split(val[0], 1)[0]
                else:
                    val = val.split(" #", 1)[0].strip()
                values[key.strip()] = val
    except OSError:
        pass
    return values


def _load_repo_root_env():
    """Load .env at the repository root; never overrides existing env vars."""
    env_path = _repo_root() / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        for key, val in _parse_env_file(env_path).items():
            os.environ.setdefault(key, val)


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
    _load_repo_root_env()
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
    _load_repo_root_env()
    _require(os.environ, ("META_ACCESS_TOKEN",), "Meta")
    return {
        "access_token": os.environ["META_ACCESS_TOKEN"],
        "ad_account_id": os.environ.get("META_AD_ACCOUNT_ID", ""),
    }


def load_serper_settings():
    """Return Serper.dev settings from the environment.

    SERPER_API_KEY is required (same account SerpBear uses). The .env is
    read at the repository root — the superproject root when wit_pytools
    is a submodule.
    """
    _load_env_files()
    _load_repo_root_env()
    _require(os.environ, SERPER_ENV_VARS, "Serper")
    return {"api_key": os.environ["SERPER_API_KEY"]}


def load_site_settings():
    """Return the Google site/property wiring for data pulls.

    GSC_SITE_URL: Search Console site URL — accepts a bare domain
    (normalized to ``sc-domain:<domain>``) or a verbatim value such as
    ``sc-domain:example.com`` / ``https://example.com/``.
    GA4_PROPERTY_ID: GA4 property — accepts the bare numeric id or the
    resource name ``properties/<id>``.

    Both are optional; an empty value means that source is skipped.
    """
    from .util import normalize_domain, site_url_for_domain

    _load_env_files()
    _load_repo_root_env()

    site_url = os.environ.get("GSC_SITE_URL", "").strip()
    if site_url and not site_url.startswith(("sc-", "http")):
        site_url = site_url_for_domain(normalize_domain(site_url))

    prop = os.environ.get("GA4_PROPERTY_ID", "").strip()
    if prop and not prop.startswith("properties/"):
        prop = f"properties/{prop}"

    return {"gsc_site_url": site_url, "ga4_property": prop}
