"""Google Analytics 4 Admin API helpers.

GA4 property creation, web data streams and measurement IDs.
The GA4 <-> Search Console product link has no public API and must be
created manually in the GA4/Searc Console UI.
"""


def list_accounts(service):
    """Return GA4 account summaries (account + property listing)."""
    accounts = []
    page_token = None
    while True:
        kwargs = {"pageToken": page_token} if page_token else {}
        response = service.accountSummaries().list(**kwargs).execute(num_retries=8)
        accounts.extend(response.get("accountSummaries", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return accounts


def find_account_by_name(service, account_name):
    """Find an account resource name (accounts/123) by display name."""
    for account in list_accounts(service):
        account_info = account.get("account", {})
        if account_info.get("displayName") == account_name:
            return account_info.get("name")
    return None


def create_property(service, account_name, display_name,
                    timezone="Europe/Berlin", currency="EUR"):
    """Create a GA4 property under the named account; returns property name."""
    account = find_account_by_name(service, account_name)
    if not account:
        raise LookupError(f"GA4 account not found: {account_name}")
    response = service.properties().create(
        parent=account,
        body={
            "displayName": display_name,
            "timeZone": timezone,
            "currencyCode": currency,
        },
    ).execute(num_retries=8)
    return response.get("name", "")


def find_property_by_display_name(service, account_name, display_name):
    """Find a GA4 property resource name under an account by display name."""
    for account in list_accounts(service):
        account_info = account.get("account", {})
        if account_info.get("displayName") != account_name:
            continue
        for prop in account.get("propertySummaries", []):
            if prop.get("displayName") == display_name:
                return prop.get("property")
    return None


def ensure_property(service, account_name, display_name,
                    timezone="Europe/Berlin", currency="EUR"):
    """Return existing or newly created GA4 property (idempotent)."""
    existing = find_property_by_display_name(
        service, account_name, display_name
    )
    if existing:
        return {"property": existing, "created": False}
    return {
        "property": create_property(
            service, account_name, display_name,
            timezone=timezone, currency=currency,
        ),
        "created": True,
    }


def list_data_streams(service, property_name):
    """Return web data streams of a GA4 property."""
    streams = []
    page_token = None
    while True:
        kwargs = {"pageToken": page_token} if page_token else {}
        response = (
            service.properties()
            .dataStreams()
            .list(parent=property_name, **kwargs)
            .execute(num_retries=8)
        )
        streams.extend(response.get("dataStreams", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return streams


def find_web_stream(service, property_name, display_name=None, uri=None):
    """Find an existing WEB_DATA_STREAM by name or default URI."""
    for stream in list_data_streams(service, property_name):
        if stream.get("type") != "WEB_DATA_STREAM":
            continue
        if display_name and stream.get("displayName") == display_name:
            return stream
        web_data = stream.get("webStreamData", {})
        if uri and web_data.get("defaultUri") == uri:
            return stream
    return None


def create_web_data_stream(service, property_name, display_name, uri):
    """Create a GA4 web data stream; returns the stream resource."""
    response = (
        service.properties()
        .dataStreams()
        .create(
            parent=property_name,
            body={
                "type": "WEB_DATA_STREAM",
                "displayName": display_name,
                "webStreamData": {"defaultUri": uri},
            },
        )
        .execute(num_retries=8)
    )
    return response


def ensure_web_data_stream(service, property_name, display_name, uri):
    """Return existing or newly created web data stream (idempotent)."""
    stream = find_web_stream(
        service, property_name, display_name=display_name, uri=uri
    )
    if stream:
        return stream
    return create_web_data_stream(
        service, property_name, display_name, uri
    )
