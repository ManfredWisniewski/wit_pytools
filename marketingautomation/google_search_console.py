"""Google Search Console and Site Verification helpers.

All functions take an already-authenticated service object so they can be
unit-tested with fakes; use auth.search_console_service() /
auth.site_verification_service() to build real ones.
"""

from .util import normalize_domain, site_url_for_domain

_SEARCH_ANALYTICS_ROW_LIMIT = 25000  # API maximum per request


def list_properties(service):
    """Return the list of Search Console site entries."""
    response = service.sites().list().execute(num_retries=8)
    return response.get("siteEntry", [])


def property_exists(service, site_url):
    return any(entry.get("siteUrl") == site_url for entry in list_properties(service))


def add_domain_property(service, domain, property_type="domain"):
    """Add a Search Console property; returns site URL and created flag."""
    domain = normalize_domain(domain)
    site_url = site_url_for_domain(domain, property_type)
    created = not property_exists(service, site_url)
    if created:
        service.sites().add(siteUrl=site_url).execute(num_retries=8)
    return {"site_url": site_url, "created": created}


def delete_property(service, site_url):
    service.sites().delete(siteUrl=site_url).execute(num_retries=8)


def get_verification_token(verification_service, domain):
    """Request a DNS TXT verification token for a domain property.

    Returns the TXT record value (e.g. "google-site-verification=...").
    The record must be published at the domain apex via the DNS provider
    before calling verify_domain().
    """
    domain = normalize_domain(domain)
    response = verification_service.webResource().getToken(
        body={
            "site": {"type": "INET_DOMAIN", "identifier": domain},
            "verificationMethod": "DNS",
        }
    ).execute(num_retries=8)
    return {
        "domain": domain,
        "site_url": site_url_for_domain(domain),
        "token": response.get("token", ""),
    }


def query_search_analytics(service, site_url, start_date, end_date,
                           dimensions=("query",), row_limit=1000,
                           search_type="web"):
    """Query the Search Analytics API; returns rows as plain dicts.

    Each row: {"keys": [...], "clicks", "impressions", "ctr", "position"}.
    Paginates with startRow until row_limit rows are collected or the API
    returns a short page.
    """
    rows = []
    start_row = 0
    while len(rows) < row_limit:
        request_limit = min(_SEARCH_ANALYTICS_ROW_LIMIT, row_limit - len(rows))
        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "searchType": search_type,
                "dimensions": list(dimensions),
                "rowLimit": request_limit,
                "startRow": start_row,
            },
        ).execute(num_retries=8)
        page = response.get("rows", [])
        rows.extend(page)
        if len(page) < request_limit:
            break
        start_row += len(page)
    return rows


def verify_domain(verification_service, domain):
    """Ask Google to verify domain ownership via the DNS TXT record."""
    domain = normalize_domain(domain)
    get_verification_token(verification_service, domain)
    verification_service.webResource().insert(
        verificationMethod="DNS",
        body={"site": {"type": "INET_DOMAIN", "identifier": domain}},
    ).execute(num_retries=8)
    return {
        "domain": domain,
        "site_url": site_url_for_domain(domain),
        "verified": True,
    }
