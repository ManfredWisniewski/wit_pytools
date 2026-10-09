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
python -m wit_pytools.webtools amex-de-statements [--out DIR] [--profile DIR]
    [--headless] [--count N] [--formats pdf,csv,excel] [--mfa-timeout SEC]
```

Downloads the newest American Express DE statements as PDF and CSV into
`--out` (default `P:/Downloads/`).

Each site lives in its own module under `webtools/sites/` and registers
a CLI subcommand via `COMMAND`, `DESCRIPTION`, `add_arguments(parser)`
and `run(args)`. New sites are picked up automatically.

## Python

```python
from wit_pytools.webtools.sites import amex_de
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
- Selectors target the Amex DE site (global.americanexpress.com).
