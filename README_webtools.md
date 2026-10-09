# webtools

`webtools` automates interactive websites (login, navigation, downloads)
using Playwright. For static scraping of server-rendered pages use
`scrapetools` instead.

## Setup

```text
pip install playwright python-dotenv
playwright install chromium
```

## Credentials

Per-site credentials come from environment variables or a `.env` file,
named `<SITE>_USERNAME` / `<SITE>_PASSWORD`:

```text
AMEX_USERNAME=...
AMEX_PASSWORD=...
```

## CLI

```text
python -m wit_pytools.webtools amex-statements [--out DIR] [--profile DIR]
    [--headless] [--count N] [--format pdf|csv|excel] [--mfa-timeout SEC]
```

Downloads recent American Express (US) statements as PDF (default), CSV
or Excel into `--out` (default `P:/Downloads/`).

## Python

```python
from wit_pytools.webtools.sites import amex

saved = amex.run("P:/Downloads", count=3, fmt="pdf")
```

Generic helpers for new site automations:

```python
from wit_pytools.webtools import browser_session, load_credentials, wait_for

with browser_session(".webtools/profile", headless=False) as (ctx, page):
    page.goto("https://example.com/login")
    ...
```

## Notes

- `browser_session` uses a persistent browser profile
  (`.webtools/profile/` by default) so cookies and login sessions survive
  across runs.
- Amex enforces MFA/captcha on unfamiliar sessions: run headed (default)
  and complete the verification manually in the opened browser; later
  runs usually reuse the persisted session.
- Selectors target the Amex US site; other regions differ.
