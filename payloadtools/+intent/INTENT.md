# Intent: `payloadtools`

## Package purpose

`witcontent` synchronizes markdown webtexts, media, and site theme CSS from a
content repository to a Payload CMS 3.x instance via its
REST API. The content repository is the single source of truth; the Payload
database is a derived read model.

All synced content is written as **drafts**. A human reviews and publishes in
the Payload admin panel — this is the D04 review gate. The tool never publishes,
never deletes, and never modifies source files.

Design context: `wit-obs-strategy-trurl/team/trurl/plan-payload-website.md` and
`+wit-wiki/research/cms/payload/2026-09-28-llm-content-to-payload.md`.

## Concepts

- **Webtext**: a publishable markdown file matching `*_webtext*.md` in the
  content repository. Companion `SEO_*`/`SEOP_*` files in the same directory are
  briefings, not publishable content.
- **Status suffix**: the part of the filename after `_webtext`. Observed values:
  `entwurf` (draft — excluded), `locked`, `locked-online`, `online-locked`
  (publishable). Eligibility rule lives in the config file, not in code.
- **Route**: the public URL path, derived from the directory structure plus the
  filename slug. Derivation rules are configurable (see Configuration).
- **`sourcePath`**: repository-relative path of the source file; stored on the
  Payload document and used as the idempotency key for upserts.
- **`sourceHash`**: SHA-256 of an uploaded media file; stored on the Media
  document and used to deduplicate uploads via API query (no local state file).
- **Media placeholder**: after upload, image references in markdown are
  rewritten to `![media:<docId>]()` — Payload's `convertMarkdownToLexical`
  (run server-side in a `beforeValidate` hook) turns them into upload nodes.
- **Theme global**: a Payload global (`theme`) holding compiled CSS variables
  (`cssLight`, `cssDark`) injected by the frontend on `:root`. Pushed via API
  like content; site styling is data, not code.
- **Structure document**: a YAML file under `<site>/structure/` (e.g.
  `structure/navigation.yml`) synced into the generic `structures`
  collection: filename stem → `name`, parsed YAML → `data` (JSON),
  `sourcePath`/`sourceRepo` as with pages. Generic by design — `menu`,
  `navigation`, `footer`, `header`, … all work by filename convention without
  schema changes. Frontend consumers interpret `data` per `name`.

## Payload API contract (server side, already agreed)

- Base URL e.g. `https://payload.witconsult.de`. Auth:
  `Authorization: users API-Key <key>` on a dedicated `content-bot` user.
- Collection `pages` fields used: `title`, `slug`, `path`, `markdownRaw`
  (textarea — we send plain markdown; conversion to Lexical happens
  server-side), `sourcePath`, `sourceRepo`, `template` (renderer name, empty
  = default), `meta.title`, `meta.description`.
- Collection `media` fields used: `file` (upload), `alt`, `caption`,
  `sourceHash`, `sourcePath`.
- Endpoints:
  - `GET  /api/pages?where[sourcePath][equals]=<path>&limit=1` — find existing
  - `POST /api/pages?draft=true` / `PATCH /api/pages/<id>?draft=true` — upsert
  - `GET  /api/media?where[sourceHash][equals]=<sha256>&limit=1` — dedup check
  - `POST /api/media` — `multipart/form-data`: field `file` plus field
    `_payload` containing a JSON string with `alt`, `caption`, `sourceHash`,
    `sourcePath`
  - `PATCH /api/globals/theme` — theme CSS push
  - `GET  /api/structures?where[sourcePath][equals]=<path>&limit=1` — find
  - `POST /api/structures?draft=true` / `PATCH /api/structures/<id>?draft=true`
    — structure upsert (same draft-only rules as pages)
- The `content-bot` API key must not be able to publish or delete. Treat any
  server response indicating otherwise as a configuration error and report it.

## Configuration

Two layers; nothing secret in files.

Environment (or `.env` next to the working directory):

```text
PAYLOAD_BASE_URL=https://payload.witconsult.de
PAYLOAD_API_KEY=<key>
```

`.arrcontent.yml` at the content repository root (all paths relative to it):

```yaml
collection: pages
media_collection: media
include_glob: "**/*_webtext*.md"
status_regex: "_webtext(?P<sep>[-_])(?P<status>[a-z-]+)$"   # matched against stem suffix
publishable_statuses: [locked, locked-online, online-locked]
slug_prefixes: [SEOP_]            # stripped from filename slug
route:
  strip_dir_prefixes: [kategorie_, produkt_, _kategorie_, _produkt_]
  strip_dir_suffixes: [_produkt]
  strip_leading_underscore: true
  overrides:                    # exact relpath -> route wins over derivation
    home_webtext_locked.md: /
meta:
  briefing_glob: "SEO_*"          # companion docs consulted for meta fields
  # field mapping TBD with Leon — keep the extractor pluggable
transforms:
  # marker rules like [Button: X], [Link: Y] — spec pending; config-driven
```

## Processing order (per file)

1. Scan `include_glob`; parse slug + status from filename; skip non-publishable
   statuses with an explicit `skipped` result.
2. Derive `route` from directory rules or `overrides`; derive `slug`.
3. Extract `meta` + `template` (front matter or `key: value` lines, else
   companion briefing per config; title fallback = first `#`/`##` heading,
   template has no fallback).
4. Rewrite image refs: for each `![alt](relpath)`, resolve against the file's
   directory, sha256 the file, `GET` media by `sourceHash`, upload if absent,
   replace with `![media:<id>]()` preserving the alt text.
5. Rewrite internal markdown links `…file.md` → their derived `/route` using a
   `sourcePath → route` index built for the whole scan set.
6. Apply configured `transforms` (marker replacements, Obsidian leftovers).
7. Upsert: `GET` by `sourcePath` → `PATCH` existing or `POST` new with
   `draft=true`; never send `_status`.
8. Emit a per-file result line: `created|updated|unchanged|skipped|failed`.

After the webtext pass, `structure/*.yml` files get the same upsert treatment
into `structures` (steps 7–8 semantics; no status/route/media/link handling).
Skipped entirely in the `media` pass; `--file` applies to both.

## CLI

```text
witcontent sync   [--repo DIR] [--file PATH] [--dry-run] [-v]
witcontent media  [--repo DIR]                      # media pass only
witcontent theme  --css-light FILE [--css-dark FILE] # PATCH /api/globals/theme
witcontent check  [--repo DIR]                      # dry validation, no writes
```

`--dry-run` performs all reads and transformations but no writes. Exit code `0`
when nothing failed, `1` if any file failed, `2` on configuration/auth errors.

## Error handling and safety

- Per-file failures (missing image, 4xx/5xx, transform error) are collected and
  reported; one bad file must not abort the run.
- Network: retry idempotent GETs with backoff; fail fast on 401/403 (bad key).
- Never log the API key; never write to the source repo implicitly.
- Re-runs are no-ops: unchanged markdown produces `unchanged`, media dedup via
  `sourceHash`, upsert via `sourcePath`.
- The bot cannot publish; do not implement a publish path at all in v1.

## Code style and dependencies

- Python 3 (latest stable), PEP8, modular package `wit_pytools/witcontent/`.
- Reuse existing `wit_pytools` helpers before adding new ones (`logger.py`,
  `filetools`, etc. — check what exists first).
- Relative paths only in code and tests.
- Minimal dependencies: `requests` or `httpx` for HTTP, `PyYAML` for config,
  `python-dotenv` optional for `.env`. No heavy markdown parser needed for the
  documented transforms — regex/lightweight processing only; markdown→Lexical
  conversion is the server's job.

## Tests and verification

pytest; tests named `witcontent_<module>_test.py` in `tests/`, fixtures in
`tests/witcontent/` (sample webtext tree mirroring the real naming: a
`kategorie_x` dir, a `produkt_x` dir, a `_entwurf` file, a file with image refs,
a file with `[Button:…]`/`[Link:…]` markers, a companion `SEO_*` briefing).

Cover at least:

- filename/status parsing incl. hyphenated status combos and no-status files
- route derivation for each observed directory style + override table
- image ref rewrite incl. sha256 dedup path (mocked API)
- internal link rewrite via the `sourcePath → route` index
- upsert decision logic (find→patch vs create) against a mocked REST server
- no writes occur under `--dry-run`; exit codes per spec

## Non-goals

- No publishing, deleting, or schema changes via API.
- No client-side Lexical JSON generation.
- No two-way sync; edits made in admin on synced fields are overwritten.
- No webhook/n8n integration (v1 is a manually-run CLI).
- No frontend/rendering concerns — that lives in the `docker-payload` repo.

## Open items

- Marker transform spec (`[Button:…]`, `[Link:…]`) — pending owner/Leon.
- Exact `SEO_*` briefing field names to map into `meta` — pending Leon.
- Whether `home_webtext_locked.md` maps to `/` or a `home` page — confirm with
  the existing WordPress URL structure.
