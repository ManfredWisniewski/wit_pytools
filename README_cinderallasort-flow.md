# cinderellasort — DOCPREP + ANONYMIZE flow

Flow of the `[DOCPREP]` conversion and the separate `[BOWLS_ANONYMIZE]` /
`[ANONYMIZE]` anonymization pipeline in `cinderellasort.py`, including all
decision options.

## Run-level flow

```mermaid
flowchart TD
    A["cinderellasort run"] --> B["docprep_settings() → [DOCPREP]<br/>anonymize_settings() → [ANONYMIZE]"]
    B --> C{"anonymize enabled<br/>(BOWLS_ANONYMIZE non-empty)<br/>+ ignore_save + mapping file?"}
    C -- yes --> D["_prepare_anonymize_ignore_save()<br/>reset sibling *-ignore-save.csv"]
    C -- no --> E
    D --> E{"anonymize enabled<br/>+ mapping file<br/>and not dryrun?"}
    E -- yes --> F["_prepare_anonymize_directories()<br/>update_directory_mapping() on source dir names"]
    F --> G{"recursive?"}
    G -- yes --> H["rename/merge target directories<br/>to anonymized names"]
    G -- no --> I
    H --> I
    E -- no --> I
    I{"BOWLS_DOCPREP bowls exist<br/>and sync-deletes=true?"}
    I -- yes --> J["_sync_docprep_deletes()<br/>delete source-side .md / _pdf2md.json<br/>whose source document is gone"]
    I -- no --> K
    J --> K["per source file: handlefile()"]
    K --> L{"extension in DOCPREP_CONVERTERS<br/>(.pdf) and bowldir_docprep() matches?"}
    L -- yes --> M["handle_docprep()<br/>see per-document flow"]
    L -- no --> N["other bowls: GEN_IMG, PDF, email,<br/>GPS, BOWLS move"]
    M --> O["process_pending_anonymization()"]
    N --> O
    N2{"file not moved by any earlier bowl<br/>and bowldir_anonymize() matches?"} -.->|"queued marker only"| O
    O --> P["_write_anonymize_lastmap()<br/>rewrite *-anon_lastmap.csv"]
```

Note: a file that is moved by a regular bowl (or any earlier bowl type) is
never seen by `process_pending_anonymization` — it is gone from `sourcedir`.
Which bowl wins is decided by the fixed bowl evaluation order in
`handlefile`; this is intended.

## Per-document flow: `handle_docprep()`

```mermaid
flowchart TD
    A["handle_docprep(source.pdf)"] --> B["output = source.with_suffix('.md')<br/>sidecar = &lt;stem&gt;_pdf2md.json<br/>both beside the source"]
    B --> C{"output .md exists<br/>next to source?"}
    C -- no --> D{"_find_existing_docprep_markup()<br/>found &lt;stem&gt;.md in targetdir?"}
    D -- yes --> E["move markup next to source"]
    E --> Z["return"]
    D -- no --> J{"dryrun?"}
    J -- yes --> Z
    C -- yes --> K["'found existing markup,<br/>skipping conversion'"]
    K --> Z
    J -- no --> N{"pages &gt; max_pages (50)?"}
    N -- yes --> N2["skip document"]
    N2 --> Z
    N -- no --> Q["convert: pdf_to_markdown()<br/>mode=text | mode=vision<br/>model, language, dpi, retry_times,<br/>continue_on_error, sidecar<br/>output beside source"]
    Q --> Z
```

DOCPREP never anonymizes. Its `.md` output becomes a normal source file that
`BOWLS_ANONYMIZE` criteria can match on the same run.

## Anonymization pass: `process_pending_anonymization()`

```mermaid
flowchart TD
    A["process_pending_anonymization()"] --> B{"BOWLS_ANONYMIZE bowls exist?"}
    B -- no --> Z["return"]
    B -- yes --> C{"[ANONYMIZE] mapping_file set?"}
    C -- no --> C2["warning + return"]
    C -- yes --> D["walk sourcedir"]
    D --> E{"per file: bowldir_anonymize()<br/>matches cleaned name?"}
    E -- no --> D
    E -- yes --> F{"suffix supported?"}
    F -- "xls/xlsx" --> F2["warn once: not supported yet"]
    F -- "unknown" --> F3["warn once: not supported"]
    F -- "md/txt/json/csv/log" --> G["skip *_anon.*, *_pdf2md.json,<br/>mapping-family files"]
    G --> H["handle_anonymization()"]
    F2 --> D
    F3 --> D
    H --> D
    D -- done --> I{"sync-deletes=true?"}
    I -- yes --> J2["delete target _anon.*<br/>with no source and no<br/>plaintext sibling"]
    I -- no --> Z2
    J2 --> Z2["done"]
```

## Per-file flow: `handle_anonymization()`

```mermaid
flowchart TD
    A["handle_anonymization(source)"] --> B{"enabled +<br/>mapping_file set?"}
    B -- no --> Z["return None"]
    B -- yes --> C["output = target/&lt;dirs&gt;/&lt;stem&gt;_anon.&lt;ext&gt;<br/>(dirs anonymized via approved mapping)"]
    C --> D{"dryrun?"}
    D -- yes --> Z
    D -- no --> E{"_anon output exists?"}
    E -- yes --> F["candidate_source = _anon output"]
    E -- no --> G["candidate_source = source file"]
    F --> H["update_text_mapping(candidate_source)<br/>append status=new candidates<br/>mode: custom | presidio | all"]
    G --> H
    H --> I{"approved status=anon values<br/>in source content?"}
    I -- no --> I2["_publish_plaintext():<br/>copy source to target"]
    I2 -- no-match --> I3{"only unapproved<br/>status=new matches?"}
    I3 -- "publish_without_review=false" --> I4["withhold / retract<br/>identical plaintext copy"]
    I3 -- "publish_without_review=true" --> I5["copy plaintext to target"]
    I -- yes --> J{"_anon exists<br/>and force_update=false?"}
    J -- no --> L["anonymize_text(source → _anon,&lt;br/&gt;overwrite=True)"]
    J -- yes --> J3{"lastmap diff:<br/>changed/extended anon rows<br/>present in source?"}
    J3 -- yes --> L
    J3 -- no --> K["'exists, skipping'<br/>keep existing _anon"]
    K --> M["retract identical<br/>plaintext copy"]
    L --> M
    M --> Z2["return"]
```

## `[DOCPREP]` options

| Option | Default | Effect |
|---|---|---|
| `mode` | `vision` | `text` = pdfplumber text layer; `vision` = multimodal model |
| `model` | `OPENROUTER_PDF_MODEL` | vision model id |
| `language` | `en` | OCR/prompt language |
| `dpi` | `150` | render resolution (vision) |
| `max_pages` | `50` | skip larger PDFs |
| `retry_times` | `3` | model retries per page |
| `continue_on_error` | `false` | keep converting after page errors |
| `sidecar` | `true` | write `<stem>_pdf2md.json` metadata next to source |
| `sync-deletes` | `false` | delete `.md`/`_pdf2md.json` when source document is gone |

## `[ANONYMIZE]` options

Anonymization is enabled by configuring `[BOWLS_ANONYMIZE]` (criteria select
files; they do not create subdirectories) plus `[ANONYMIZE]` `mapping_file`.
There is no on/off flag.

| Option | Default | Effect |
|---|---|---|
| `mapping_file` | `<sourcedir>/<dirname>-anon-mapping.csv` | proposal mapping CSV |
| `mode` | `custom` | `custom` / `presidio` / `all` candidate detection |
| `force_update` | `false` | always rewrite existing `_anon.<ext>` |
| `sync-deletes` | `true` | delete `_anon.<ext>` when the source file is gone |
| `publish_without_review` | `false` | copy source to target even when unapproved candidates match |
| `language` | `en` | detection language |
| `presidio_model` | `de_core_news_sm` | spaCy model for presidio mode |
| `presidio_score_threshold` | `0.5` | presidio confidence cutoff |
| `presidio_entities` | built-in list (`all` = registry) | entity allow-list |
| `token_length` | `4` | deterministic replacement token length |
| `ignore_dictionary` | `false` | ignore dictionary words |
| `ignore_numbers` | `false` | ignore values containing digits |
| `ignore_emails` | `false` | ignore e-mail candidates |
| `ignore_dates` | `false` | ignore date-like candidates |
| `ignore_save` | `false` | write filtered proposals to `*-ignore-save.csv` |
| `name_countries` | — | ISO alpha-2 codes for name datasets |
| `use_name_datasets` | on when countries set | enable/disable name datasets |
| `name_cache_dir` | user cache dir | dataset cache override |
| `name_dataset_offline` | — | cache-only, no network |
| `name_dataset_debug` | `false` | dataset diagnostics |
| `name_exclusions` | — | extra single-token name exclusions |

Supported file types in ANONYMIZE bowls: `.md` (protected Markdown spans
excluded), `.txt`, `.json`, `.csv`, `.log` (whole content editable). `.xls`
and `.xlsx` log a warning until a structured adapter exists; any other
matched extension is skipped with a warning.

Notes:

- A change of docprep `mode` does not trigger re-conversion — any existing
  `.md` (paired or found in targetdir) short-circuits conversion.
- An existing `_anon.<ext>` is regenerated when `force_update=true`, or when the
  `*-anon_lastmap.csv` diff shows a changed/extended `uid` row (replacement
  or originals) that occurs in the source. `update_anonymization_lastmap`
  refreshes the snapshot after each run and reports removed rows (their
  tokens may remain orphaned in outputs).
- `*_anon.*` outputs, `*_pdf2md.json` sidecars, and the mapping family
  (mapping, `*-anon.csv`, `*-ignore*.csv`, `*_lastmap.csv`) are excluded from
  anonymize bowl processing.
