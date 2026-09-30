# payloadtools

`payloadtools` synchronizes markdown webtexts, media files, site structure documents, and site theme CSS from a content repository to a Payload CMS 3.x instance via its REST API. The content repository is the single source of truth; the Payload database is a derived read model.

All synced content is written as **drafts**. A human reviews and publishes in the Payload admin panel. The tool never publishes, never deletes, and never modifies source files.

## Setup

Dependencies (already in `requirements.txt`): `requests`, `PyYAML`, `python-dotenv` (optional, for `.env` files), `eliot`.

Environment variables:

| Variable           | Required | Purpose                                                              |
| ------------------ | -------- | -------------------------------------------------------------------- |
| `PAYLOAD_BASE_URL` | yes      | Payload instance base URL, e.g. `https://payload.witconsult.de`       |
| `PAYLOAD_API_KEY`  | yes      | API key of the dedicated `content-bot` user. Never stored in files.   |
| `ARRCONTENT_REPO`  | no       | Path to the content repository; `--repo` overrides it (default `.`).  |

The `content-bot` API key must not be allowed to publish or delete. A 401/403 response aborts the run.

## Configuration

`.arrcontent.yml` at the content repository root controls eligibility, routing, meta extraction, and transforms:

```yaml
collection: pages
media_collection: media
include_glob: "**/*_webtext*.md"
status_regex: "_webtext(?P<sep>[-_])(?P<status>[a-z-]+)$"
publishable_statuses: [locked, locked-online, online-locked]
slug_prefixes: [SEOP_]
route:
  strip_dir_prefixes: [kategorie_, produkt_, _kategorie_, _produkt_]
  strip_dir_suffixes: [_produkt]
  strip_leading_underscore: true
  overrides:
    home_webtext_locked.md: /
meta:
  briefing_glob: "SEO_*"
transforms:
  - pattern: '\[Button:\s*(.+?)\]'
    replacement: '<button>\1</button>'
```

Filename rules:

- `*_webtext*.md` files are publishable webtexts. The part after `_webtext` is the status; only statuses in `publishable_statuses` are synced. Files with no status suffix (`foo_webtext.md`) are publishable.
- `SEO_*` / `SEOP_*` files are companion briefings (meta fields), not content.
- `slug_prefixes` are stripped from the filename slug.
- Routes are derived from cleaned directory names plus the slug; `overrides` map an exact repo-relative path to a route and win over derivation.

## CLI

```bat
python -m wit_pytools.payloadtools sync  [--repo DIR] [--file PATH] [--dry-run] [-v]
python -m wit_pytools.payloadtools media [--repo DIR] [--dry-run]
python -m wit_pytools.payloadtools theme --css-light FILE [--css-dark FILE]
python -m wit_pytools.payloadtools check [--repo DIR]
```

`--dry-run` (and `check`) perform all reads and transformations but no writes. Exit codes: `0` nothing failed, `1` at least one file failed, `2` configuration/auth error.

Per-file result lines:

```text
created    kategorie_products/prod_webtext_locked.md
unchanged  home_webtext_locked.md
skipped    notes_webtext_entwurf.md  (status=entwurf)
failed     kategorie_products/broken_webtext_locked.md  (missing image img/missing.png)
```

## What sync does per file

1. Scan `include_glob`; parse status from filename; non-publishable files are `skipped`.
2. Derive route and slug.
3. Extract `meta.title`/`meta.description`/`template` (front matter or `key: value` lines, then `SEO_*` briefing; title falls back to the first `#`/`##` heading). `template` names a frontend render variant — empty means default.
4. Rewrite `![alt](relpath)` to `![media:<docId>]()` — the image is sha256-hashed, looked up via `sourceHash`, and uploaded only if absent. The alt text is preserved on the Media document.
5. Rewrite internal `…file.md` links to their derived `/route` via an index of the whole scan set.
6. Apply configured `transforms` regex rules.
7. Upsert: `GET` by `sourcePath`; `PATCH` if changed, `POST` if new, always with `draft=true`. Identical content reports `unchanged`.
8. Emit the per-file result line.

The `media` command runs steps 1 and 4 only (upload/dedup, no page writes).

## Structure documents

`sync` and `check` also process `structure/*.yml` / `structure/*.yaml` under
the site directory (`media` skips them). Each file maps to one document in the
`structures` collection: the filename stem becomes `name`, the parsed YAML
lands verbatim in `data`, and upserts key on `sourcePath` — same draft-only
rules as pages. Example `structure/navigation.yml`:

```yaml
items:
  - {label: Start, path: /}
  - {label: MDM, path: /mdm}
```

The frontend reads `structures` doc `navigation` and renders
`data.items[*].label/path` as the header menu. Future documents (`footer`,
`header`, …) work by filename convention without schema changes. `--file`
accepts structure paths too (`--file structure/navigation.yml`).

## Errors and safety

- Per-file failures (missing image, API error, transform error) are collected and reported; one bad file does not abort the run.
- Idempotent `GET`s are retried with backoff; 401/403 aborts immediately (bad key).
- Re-runs are no-ops: unchanged markdown yields `unchanged`, media dedups via `sourceHash`, upserts key on `sourcePath`.
- The API key is never logged; the source repo is never written.

## Tests

```bat
python -m pytest tests\payloadtools_scan_test.py tests\payloadtools_meta_test.py tests\payloadtools_media_test.py tests\payloadtools_links_test.py tests\payloadtools_sync_test.py tests\payloadtools_cli_test.py
```

Tests use a `FakeClient` (`tests/payloadtools_fakes.py`) and a fixture content repo (`tests/payloadtools/witrepo/`); no network access or API key is needed.

## Not covered (yet)

Publishing, deleting, or schema changes via API; client-side Lexical JSON generation; two-way sync (admin edits on synced fields are overwritten); webhook/n8n integration. The marker transform spec (`[Button:…]`, `[Link:…]`) and the exact `SEO_*` briefing field mapping are still pending — the plumbing is config-driven and ready.
