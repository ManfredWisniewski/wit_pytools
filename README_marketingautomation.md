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

Serper / keyword research:

```text
SERPER_API_KEY=...
GSC_SITE_URL=example.com      # optional — sc-domain:… or https://… verbatim
GA4_PROPERTY_ID=123456789     # optional — bare id or properties/<id>
```

How to obtain them:

- `SERPER_API_KEY` — serper.dev account -> API Key page (same account
  SerpBear uses).
- `GSC_SITE_URL` — the verified Search Console property. Run
  `search-console list` to see the exact `siteUrl` values
  (`sc-domain:example.com` for a domain property, `https://…/` for a
  URL-prefix property); a bare domain is normalized to `sc-domain:…`.
  No new key — the existing Google credentials are used, the identity
  only needs access to the property.
- `GA4_PROPERTY_ID` — numeric, found in the GA4 UI at
  https://analytics.google.com : gear icon *Admin* (bottom left) ->
  *Property* column -> *Property Settings* -> **Property ID** (top
  right). Or run `analytics accounts` and pick the property resource
  name. If no property exists yet: *Admin -> Create Property*, or
  `analytics ensure-property --account-name "…" --display-name "…"`.
  No new key either — but the **GA4 Data API must be enabled** in the
  Cloud project that owns the credentials (see below), and the identity
  needs at least *Viewer* on the property.

### Enabling the Google APIs

Each used API must be enabled once in the Cloud project that owns the
credentials — with a service account that is the SA's own project
(`project_id` inside the JSON), with OAuth it is the OAuth client's
project. *APIs & Services -> Library*, or directly:

```text
https://console.developers.google.com/apis/api/analyticsdata.googleapis.com/overview?project=<PROJECT_NUMBER>
https://console.developers.google.com/apis/api/searchconsole.googleapis.com/overview?project=<PROJECT_NUMBER>
https://console.developers.google.com/apis/api/analyticsadmin.googleapis.com/overview?project=<PROJECT_NUMBER>
https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=<PROJECT_NUMBER>
```

A disabled API fails the call with `403 SERVICE_DISABLED` — the harvest
reports it in `## Warnungen` and continues without that source.

### Service account (alternative to OAuth)

Recommended for scheduled/unattended use — no refresh-token expiry.

1. Cloud Console -> *IAM & Admin -> Service Accounts* -> select or create
   the SA -> *Keys -> Add Key -> Create new key -> JSON*; store the file
   outside the repository (it is a secret — never commit it).
2. Point the environment at it:

   ```text
   GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account.json
   ```

   When set, it takes precedence over `GOOGLE_OAUTH_*`.
3. Grant access per product — the SA is a foreign identity, OAuth grants
   do not carry over:
   - Search Console: *Settings -> Users and permissions -> Add user* with
     the SA email (already done if the SA is on all your GSC properties)
   - GA4: *Admin -> Property Access Management -> Add users* with the SA
     email, role *Viewer*
4. Enable the APIs listed above in the SA's project.

### Google OAuth refresh token

`GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` come from an OAuth client in the
Google Cloud Console (*APIs & Services -> Credentials -> Create
Credentials -> OAuth client ID*, type *Web application*, redirect URI
`https://developers.google.com/oauthplayground`).

`GOOGLE_OAUTH_REFRESH_TOKEN` is minted at
https://developers.google.com/oauthplayground :

1. gear icon -> check *Use your own OAuth credentials* -> paste client
   id + secret
2. step 1: paste the scopes into *Input your own scopes* — one token can
   carry all of them (all four below cover every command in this
   package; `analytics.readonly` + `webmasters.readonly` suffice for
   keyword research):

   ```text
   https://www.googleapis.com/auth/analytics.readonly
   https://www.googleapis.com/auth/webmasters.readonly
   https://www.googleapis.com/auth/analytics.edit
   https://www.googleapis.com/auth/siteverification
   ```

3. *Authorize APIs* -> sign in with the account that owns the GA4
   property / GSC site -> consent past the "unverified app" warning
4. step 2: *Exchange authorization code for tokens* -> copy the refresh
   token

Caveat: an OAuth consent screen in *Testing* status expires refresh
tokens after 7 days — publish the app (internal use needs no review) or
re-mint. The alternative `GOOGLE_APPLICATION_CREDENTIALS` (service
account JSON) never expires but must be added as a user on the GA4
property and the GSC site, and cannot create GSC properties.

Required OAuth scopes are defined in `auth.GOOGLE_SCOPES`
(`webmasters`, `siteverification`, `analytics.edit`, `analytics.readonly`).

The `.env` is read at the repository root — the superproject root when
wit_pytools is checked out as a submodule — with a package-root `.env`
taking precedence for any variable it sets.

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

python -m wit_pytools.marketingautomation keywords harvest SEO_Produkt_x.md --dry-run
python -m wit_pytools.marketingautomation keywords harvest SEO_Produkt_x.md
```

All commands print JSON to stdout so Ansible can register the output.

## Python API

```python
from wit_pytools.marketingautomation import (
    google_search_console, google_analytics, meta_conversions,
    keyword_research,
)
```

`keywords harvest` expands a `SEO_Produkt_*.md` doc via Serper.dev
(autocomplete, related searches, People-Also-Ask, SERP snapshot) and, when
`GSC_SITE_URL`/`GA4_PROPERTY_ID` are set, merges real Search Console query
metrics (clicks/impressions/position, source `search-console`) and a GA4
top-landing-pages section into the report. Output: a
`keywords-research-<date>.md` report and a SerpBear
`keyword,tags` CSV next to the product doc. `--no-google` skips the
enrichment, `--days` sets the lookback window (default 90, ending 3 days
before today).

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
