# migrationtools

Tools to help with migration tasks.

## wallabag2karakeep

`wallabag2karakeep.py` imports wallabag entries into [karakeep](https://karakeep.app) as link bookmarks. karakeep re-crawls each URL itself (`crawlPriority=low` for bulk import). Tags are not imported; archived wallabag entries are imported as archived.

Successfully tested with:

- wallabag **2.6.14**
- karakeep **v0.34.1**

### Setup

No extra dependencies — standard library only.

Connection settings are constants at the top of the script: `WALLABAG_URL`, `WALLABAG_USER`, `WALLABAG_PASS`, `WALLABAG_CLIENT_ID`, `WALLABAG_CLIENT_SECRET`, `KARAKEEP_URL`, `KARAKEEP_API_KEY`.

Notes:

- wallabag's OAuth `client_id` is `{id}_{randomId}` — the `id` prefix is required, see `Client::getClientId()` in wallabag's `ApiBundle`.
- `KARAKEEP_INSECURE=1` env var skips TLS verification (needed while the karakeep cert is still pending). Note: the script also defines a `KARAKEEP_INSECURE` constant that is currently unused — the env var is what takes effect.

### Usage

```powershell
python migrationtools/wallabag2karakeep.py --dry-run --limit 5
python migrationtools/wallabag2karakeep.py
```

Options: `--dry-run` prints what would be imported, `--limit N` caps entries, `--delay` sets seconds between karakeep creates (default 0.3).
