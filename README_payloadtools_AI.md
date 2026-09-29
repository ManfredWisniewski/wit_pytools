# payloadtools — agent reference

Compact facts for AI agents working on or with `wit_pytools.payloadtools`. Human documentation: `README_payloadtools.md`. Design decisions and non-goals: `payloadtools/+intent/INTENT.md`.

Before making changes, read the shared WIT development guidance in `+wit-dev/` in this repository. Start with `+wit-dev/README.md` and `+wit-dev/AGENTS.md`, then read the relevant convention or best-practice files. These shared definitions apply independently of which skill or AI agent is performing the work.

## Layout

```text
wit_pytools/payloadtools/
  __init__.py       re-exports Config, FileResult, PayloadClient, errors, scan_repo, sync_repo, ...
  __main__.py       python -m wit_pytools.payloadtools -> cli.main
  cli.py            argparse subcommands sync|media|theme|check; exit 0/1/2; log_setup + eliot
  client.py         PayloadClient, _json helper; PayloadAuthError, PayloadApiError
  config.py         load_config, load_credentials, PayloadConfigError, Config, RouteConfig
  scan.py           ScanEntry, parse_stem, is_publishable, derive_slug, derive_route,
                    scan_repo, build_route_index
  meta.py           extract_meta: front matter -> SEO_* briefing -> heading fallback
  media.py          rewrite_image_refs, sha256_file
  links.py          rewrite_internal_links, split_target, is_external
  transforms.py     apply_transforms (config [{pattern, replacement}])
  sync.py           sync_repo, process_entry, build_payload, _unchanged, FileResult
  +intent/          INTENT.md
wit_pytools/tests/payloadtools_{scan,meta,media,links,sync,cli}_test.py
wit_pytools/tests/payloadtools_fakes.py     FakeClient (no _test suffix -> not collected)
wit_pytools/tests/payloadtools/witrepo/     fixture content repo (.witcontent.yml + webtexts)
```

## Contracts

```python
load_config(repo) -> Config
# reads <repo>/.witcontent.yml; repo resolved to absolute; validates status_regex
# (re.error) and YAML errors -> PayloadConfigError.

load_credentials() -> (base_url, api_key)
# env or .env (python-dotenv optional); missing -> PayloadConfigError.

PayloadClient(base_url, api_key, *, timeout=30, retries=2)
  .get(path, params) -> dict                       # retries+1 attempts, backoff 2**n
  .find_doc(collection, field, value) -> doc|None  # ?where[field][equals]=v&limit=1
  .create_doc(collection, payload) -> dict         # POST ?draft=true
  .update_doc(collection, doc_id, payload) -> dict # PATCH ?draft=true
  .upload_media(path, *, collection, alt, caption, source_hash, source_path) -> str id
  .update_global(slug, payload) -> dict            # PATCH globals/<slug>
  .close()
# 401/403 -> PayloadAuthError; other non-2xx, network, JSON errors -> PayloadApiError.
# GETs retried; writes are not. Upload = multipart: file + _payload JSON string.

parse_stem(stem, pattern_or_str) -> (base, status|None)
# status = suffix after _webtext<sep>; None when absent (publishable per decision).

is_publishable(status, whitelist) -> bool          # status None -> True
derive_slug(base, slug_prefixes) -> str            # strips each matching prefix
derive_route(relpath, slug, route_cfg) -> str      # overrides win; cleaned dirs + "/" + slug
scan_repo(config) -> list[ScanEntry]               # sorted glob of include_glob
build_route_index(entries) -> {relpath: route}     # publishable entries only

extract_meta(text, file_dir, briefing_glob="") -> {"title","description"}

rewrite_image_refs(text, entry, config, client, *, dry_run=False) -> (text, uploads)
# ![alt](rel) -> ![media:<id>](); sha256 dedup via sourceHash lookup, upload if absent.
# dry_run -> ![media:<sha256>](), no upload call. Missing file -> FileNotFoundError.

rewrite_internal_links(text, entry, repo_root, route_index) -> text
# [t](rel.md#frag) -> [t](/route#frag); link titles preserved; images excluded via (?<!!).
# Targets outside repo or not in index are left unchanged.

apply_transforms(text, rules) -> text              # re.sub per {pattern, replacement}

sync_repo(config, client, *, only_file=None, media_only=False, dry_run=False)
    -> list[FileResult]
process_entry(entry, config, client, route_index, *, media_only=False, dry_run=False)
    -> FileResult(relpath, status, detail)
# statuses: created|updated|unchanged|skipped|failed
# unchanged = compare title|slug|path|markdownRaw|sourceRepo + meta.title|description
# PayloadAuthError propagates (run-level, exit 2); other exceptions -> failed (exit 1)
# media_only: scan + image rewrite only; result created (>=1 upload) | unchanged
```

Payload body: `{title, slug, path, markdownRaw, sourcePath, sourceRepo, meta:{title,description}}`. `title` falls back to slug; `sourceRepo` defaults to repo dir name (override: `source_repo` config key). Never send `_status`.

## Payload API surface used

- `GET  /api/<collection>?where[sourcePath][equals]=<rel>&limit=1`
- `POST /api/pages?draft=true` / `PATCH /api/pages/<id>?draft=true`
- `GET  /api/media?where[sourceHash][equals]=<sha256>&limit=1`
- `POST /api/media` — multipart `file` + `_payload` JSON (`alt`, `caption`, `sourceHash`, `sourcePath`)
- `PATCH /api/globals/theme` — `{cssLight, cssDark}`
- Auth header: `Authorization: users API-Key <key>` (dedicated `content-bot` user; no publish/delete permission)

## Conventions to keep

- Draft-only writes; never send `_status`; no publish/delete code path at all.
- Never log the API key; never write to the source repo.
- Per-file failures are collected (`failed`); only auth/config errors abort the run (exit 2).
- `dry_run`/`check` perform all reads + transforms but make zero write calls.
- Deps: `requests`, `PyYAML`, optional `python-dotenv`, `eliot`. No markdown parser, no SDK.
- Logging via `wit_pytools.logger.log_setup` + `eliot.log_message`.
- Relative paths only in code and tests; test data under `tests/payloadtools/`.
- Tests must not hit the network: inject `FakeClient` (`wit_pytools.tests.payloadtools_fakes`) or monkeypatch `cli.PayloadClient`/`cli.load_credentials`.

## Open items / extension points

- Marker transform spec (`[Button:…]`, `[Link:…]`) pending — `transforms` list is already config-driven `{pattern, replacement}` regexes.
- `SEO_*` briefing field mapping pending — extractor pluggable via `meta.briefing_glob` + `_meta_from_text` (front matter or `key: value` lines).
- `home_webtext_locked.md -> /` override semantics pending WP URL structure check.
- Payload media doc response: `body["doc"]["id"]` (falls back to top-level `id`); missing id raises `PayloadApiError`.

## Run

```bat
python -m pytest tests\payloadtools_scan_test.py tests\payloadtools_meta_test.py tests\payloadtools_media_test.py tests\payloadtools_links_test.py tests\payloadtools_sync_test.py tests\payloadtools_cli_test.py
python -m wit_pytools.payloadtools check --repo <content-repo>
python -m wit_pytools.payloadtools sync --repo <content-repo> [--dry-run] [-v]
python -m wit_pytools.payloadtools theme --css-light light.css [--css-dark dark.css]
```

Run from the repository root with `PYTHONPATH` including `P:\git\witnctools`. `log_setup()` writes `pytools.log` to the current working directory.
