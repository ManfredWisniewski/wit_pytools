# Decisions

## Name datasets

- **D01 Use `sigpwned/popular-names-by-country-dataset`** (alternatives: no dataset; a bundled dataset; a different provider). Reason: it provides separate country-aware forename and surname CSV files under CC0.
- **D02 Fetch the latest repository data** (alternatives: pin one release; bundle data in the repository). Reason: the configured behavior requires current upstream data while retaining a local cache for resilience.
- **D03 Check the repository commit on every run and download only when it changes** (alternatives: download every call; refresh once per day). Reason: this detects upstream changes on each run without downloading unchanged datasets.
- **D04 Use cached data on connection failure and raise when no cache exists** (alternatives: silently use regex-only detection; fail every time). Reason: configured dataset behavior must not silently disappear, but a temporary outage should not interrupt a previously prepared workflow.
- **D05 Disable dataset use explicitly with `use_name_datasets=False`** (alternatives: implicit fallback; environment-only control). Reason: callers need an explicit opt-out when they want regex-only detection.
- **D06 Configure explicit ISO alpha-2 country codes with no default countries or presets** (alternatives: all countries by default; geographic presets). Reason: explicit configuration keeps matching predictable and avoids unnecessary downloads.
- **D07 Store datasets in the user cache and metadata separately** (alternatives: repository files; temporary-only data). Reason: cached operation must work offline without adding generated or third-party data to the repository.

Decision date: 2026-09-24
