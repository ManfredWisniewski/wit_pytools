# Decisions

## Name datasets

- **D01 Use `sigpwned/popular-names-by-country-dataset`** (alternatives: no dataset; a bundled dataset; a different provider). Reason: it provides separate country-aware forename and surname CSV files under CC0.
- **D02 Fetch the latest repository data** (alternatives: pin one release; bundle data in the repository). Reason: the configured behavior requires current upstream data while retaining a local cache for resilience.
- **D03 Check the repository commit on every run and download only when it changes** (alternatives: download every call; refresh once per day). Reason: this detects upstream changes on each run without downloading unchanged datasets.
- **D04 Use cached data on connection failure and raise when no cache exists** (alternatives: silently use regex-only detection; fail every time). Reason: configured dataset behavior must not silently disappear, but a temporary outage should not interrupt a previously prepared workflow.
- **D05 Disable dataset use explicitly with `use_name_datasets=False`** (alternatives: implicit fallback; environment-only control). Reason: callers need an explicit opt-out when they want regex-only detection.
- **D06 Configure explicit ISO alpha-2 country codes with no default countries or presets** (alternatives: all countries by default; geographic presets). Reason: explicit configuration keeps matching predictable and avoids unnecessary downloads.
- **D07 Store datasets in the user cache and metadata separately** (alternatives: repository files; temporary-only data). Reason: cached operation must work offline without adding generated or third-party data to the repository.

- **D08 Use German noun and proper-name lists when `DE` is configured** (alternatives: use only the international dataset; use the German list for all countries). Reason: the German categorized wordlist provides language-specific noun exclusions and positive first-name/surname evidence; its scope must remain explicit.
- **D09 Treat German nouns as a single-token filter, not an absolute rejection of compound names** (alternatives: reject any candidate containing a noun; ignore nouns). Reason: legitimate surnames can also be German nouns.

Decision date: 2026-09-24
