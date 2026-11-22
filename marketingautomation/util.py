"""Shared helpers for marketingautomation."""

import re
from urllib.parse import urlparse

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def normalize_domain(value):
    """Reduce a URL or host to a bare lowercase domain (no scheme/path/www).

    Raises ValueError when the input cannot be parsed into a domain.
    """
    text = (value or "").strip().lower()
    if not text:
        raise ValueError("empty domain")
    if "://" not in text:
        text = "//" + text
    host = urlparse(text).hostname or ""
    host = host.strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not _DOMAIN_RE.match(host):
        raise ValueError(f"not a valid domain: {value!r}")
    return host


def site_url_for_domain(domain, property_type="domain"):
    """Return the Search Console site URL for a normalized domain."""
    if property_type == "url_prefix":
        return f"https://www.{domain}/"
    return f"sc-domain:{domain}"
