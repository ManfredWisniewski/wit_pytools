"""Marketing platform automation helpers (Google, Meta)."""

from .config import (
    MarketingConfigError,
    load_google_settings,
    load_meta_settings,
    load_serper_settings,
    load_site_settings,
)
from .util import normalize_domain, site_url_for_domain

__all__ = [
    "MarketingConfigError",
    "load_google_settings",
    "load_meta_settings",
    "load_serper_settings",
    "load_site_settings",
    "normalize_domain",
    "site_url_for_domain",
]
