# marketingautomation

`marketingautomation` automates marketing platform setup tasks: Google
Search Console properties and ownership verification, GA4 properties and
web data streams, and Meta Conversions API events.

## Setup

```text
pip install google-api-python-client google-auth requests python-dotenv pyyaml
```

Google client libraries are imported lazily; only the Meta helpers need
`requests`.

## Credentials

All credentials come from environment variables or a `.env` file in the
package root — never from this repository.

Google (OAuth 2.0 refresh token, recommended for first-time property
setup; service accounts cannot create Search Console properties):

```text
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...
# or, alternatively:
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Meta:

```text
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=...        # optional, ad-account scoped calls only
```

Required OAuth scopes are defined in `auth.GOOGLE_SCOPES`
(`webmasters`, `siteverification`, `analytics.edit`).

## CLI

```text
python -m wit_pytools.marketingautomation search-console list
python -m wit_pytools.marketingautomation search-console add --domain example.com
python -m wit_pytools.marketingautomation search-console verification-token --domain example.com
python -m wit_pytools.marketingautomation search-console verify --domain example.com

python -m wit_pytools.marketingautomation analytics accounts
python -m wit_pytools.marketingautomation analytics create-property \
    --account-name "Acme" --display-name "Acme - Production - Main Website"
python -m wit_pytools.marketingautomation analytics create-stream \
    --property properties/123 --display-name "Main Web" --uri https://example.com

python -m wit_pytools.marketingautomation meta test-event \
    --pixel-id 123456789 --test-event-code TEST12345
```

All commands print JSON to stdout so Ansible can register the output.

## Python API

```python
from wit_pytools.marketingautomation import (
    google_search_console, google_analytics, meta_conversions,
)
```

Domain properties are normalized with `util.normalize_domain()` —
`https://www.example.com/path` becomes `example.com` and the Search
Console site URL becomes `sc-domain:example.com`.

## Limitations

- The GA4 <-> Search Console product link has no public API; create it
  manually in the GA4/Searc Console UI.
- Search Console domain verification requires publishing the returned
  DNS TXT token at the domain apex through the DNS provider before
  calling `verify`.
- Meta pixel *creation* is not implemented; only Conversions API event
  submission is covered.
