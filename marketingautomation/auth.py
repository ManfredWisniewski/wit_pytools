"""Google API authentication (OAuth refresh token or service account).

Google client libraries are imported lazily so pure helper functions stay
usable without the google-api-python-client dependency installed.
"""

from .config import MarketingConfigError, load_google_settings

GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/siteverification",
    "https://www.googleapis.com/auth/analytics.edit",
)

_TOKEN_URI = "https://oauth2.googleapis.com/token"


def google_credentials(settings=None, scopes=GOOGLE_SCOPES):
    """Build google.auth credentials from settings or environment."""
    settings = settings or load_google_settings()

    if settings.get("service_account_file"):
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            settings["service_account_file"], scopes=list(scopes)
        )

    missing = [
        key
        for key in ("client_id", "client_secret", "refresh_token")
        if not settings.get(key)
    ]
    if missing:
        raise MarketingConfigError(
            f"Google OAuth settings incomplete: {', '.join(missing)}"
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=settings["refresh_token"],
        token_uri=_TOKEN_URI,
        client_id=settings["client_id"],
        client_secret=settings["client_secret"],
        scopes=list(scopes),
    )
    creds.refresh(Request())
    return creds


def build_service(api, version, settings=None, scopes=GOOGLE_SCOPES):
    """Build a googleapiclient discovery service for the given API."""
    from googleapiclient.discovery import build

    creds = google_credentials(settings, scopes=scopes)
    return build(api, version, credentials=creds, cache_discovery=False)


def search_console_service(settings=None):
    return build_service("searchconsole", "v1", settings=settings)


def site_verification_service(settings=None):
    return build_service("siteVerification", "v1", settings=settings)


def analytics_admin_service(settings=None):
    return build_service("analyticsadmin", "v1beta", settings=settings)
