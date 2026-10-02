# cinderellasort — DOCPREP flow

Flow of the `[DOCPREP]` pipeline in `cinderellasort.py`, including the
anonymization path and all decision options.

## Run-level flow

```mermaid
flowchart TD
    A["cinderellasort run"] --> B["docprep_settings()<br/>read [DOCPREP] section"]
    B --> C{"anonymize=true<br/>and anonymize_ignore_save=true<br/>and mapping file set?"}
    C -- yes --> D["_prepare_docprep_ignore_save()<br/>reset sibling *-ignore.csv"]
    C -- no --> E
    D --> E{"anonymize=true<br/>and mapping file set<br/>and not dryrun?"}
    E -- yes --> F["_prepare_docprep_directories()<br/>update_directory_mapping() on source dir names"]
    F --> G{"recursive?"}
    G -- yes --> H["rename/merge target directories<br/>to anonymized names"]
    G -- no --> I
    H --> I
    E -- no --> I
    I{"BOWLS_DOCPREP bowls exist<br/>and (sync-deletes=true<br/>or anonymize-sync-deletes=true)?"}
    I -- yes --> J["_sync_docprep_deletes()<br/>delete .md / _anon.md whose<br/>source document is gone"]
    I -- no --> K
    J --> K["per source file: handlefile()"]
    K --> L{"extension in DOCPREP_CONVERTERS<br/>(.pdf) and bowldir_docprep() matches?"}
    L -- yes --> M["handle_docprep()<br/>see per-document flow"]
    L -- no --> N["other bowls (PDF, email, GPS, sort, ...)"]
    M --> O["process_pending_docprep_anonymization()<br/>scan targetdir for *.md without _anon.md<br/>scan sourcedir for *.md → anonymize to computed<br/>target path; if no anon/new mapping row matches,<br/>publish plaintext copy instead<br/>(anonymize_publish_without_review=true also<br/>publishes files with unapproved candidates)<br/>(or all .md if anonymize_update=true)"]
    N --> O
```

## Per-document flow: `handle_docprep()`

```mermaid
flowchart TD
    A["handle_docprep(source)"] --> B["paired_markup = source.with_suffix('.md')"]
    B --> C{"paired_markup exists<br/>next to source?"}
    C -- no --> D{"_find_existing_docprep_markup()<br/>found &lt;stem&gt;.md in targetdir?"}
    D -- yes --> E{"anonymize-keep-originals=true?"}
    E -- yes --> F["move markup next to source<br/>(becomes paired_markup)"]
    F --> Z["return"]
    E -- no --> G["move markup to output_path"]
    G --> H{"anonymize=true?"}
    H -- yes --> I["handle_docprep_anonymization()<br/>remove_source=True"]
    H -- no --> Z
    I --> Z
    D -- no --> J{"dryrun?"}
    J -- yes --> Z
    C -- yes --> K["'found existing markup,<br/>skipping conversion'"]
    K --> L{"anonymize=true?"}
    L -- yes --> M{"anonymize-keep-originals=true<br/>and output_path exists?"}
    M -- yes --> M2["delete stale target .md"]
    M -- no --> M3
    M2 --> M3["handle_docprep_anonymization()<br/>remove_source = not keep_originals"]
    L -- no --> Z
    M3 --> Z
    J -- no --> N{"pages &gt; max_pages (50)?"}
    N -- yes --> N2["skip document"]
    N2 --> Z
    N -- no --> O{"output_path .md exists?"}
    O -- yes --> P["'exists, skipping conversion'"]
    O -- no --> Q["convert: pdf_to_markdown()<br/>mode=text | mode=vision<br/>model, language, dpi, retry_times,<br/>continue_on_error, sidecar"]
    P --> R{"anonymize=true?"}
    Q --> R
    R -- no --> Z
    R -- yes --> S{"anonymize-keep-originals=true?"}
    S -- yes --> T["copy target .md next to source"]
    S -- no --> U
    T --> U["handle_docprep_anonymization()<br/>remove_source = keep_originals"]
    U --> Z
```

## Anonymization flow: `handle_docprep_anonymization()`

```mermaid
flowchart TD
    A["handle_docprep_anonymization(markdown_path)"] --> B{"anonymize=true?"}
    B -- no --> Z["return None"]
    B -- yes --> C{"anonymize_mapping_file set?"}
    C -- no --> C2["error: requires anonymize_mapping_file"]
    C -- yes --> D["output_path = &lt;stem&gt;_anon.md"]
    D --> E{"_anon.md already exists?"}
    E -- yes --> F["candidate_source = _anon.md<br/>(scan anonymized output)"]
    E -- no --> G["candidate_source = markdown_path"]
    F --> H["update_text_mapping(candidate_source)<br/>append status=new candidates<br/>anonymize-mode: custom | presidio | all"]
    G --> H
    H --> I{"mapping_matches_text(new .md)?<br/>approved status=anon rows<br/>as substring of editable parts"}
    I -- no --> I2["'no approved mapping matches'<br/>return None — nothing changes"]
    I -- yes --> J{"_anon.md exists<br/>and anonymize_update=false?"}
    J -- yes --> K["'exists, skipping'<br/>keep existing _anon.md"]
    J -- no --> L["anonymize_text(.md → _anon.md,<br/>overwrite=True)"]
    K --> M{"remove_source?"}
    L --> M
    M -- yes --> N["delete markdown_path (.md)"]
    M -- no --> Z2["return _anon.md"]
    N --> Z2
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
| `sync-deletes` | `false` | delete `.md` when source document is gone |
| `anonymize` | `false` | enable the anonymization pipeline |
| `anonymize-mode` | `custom` | `custom` | `presidio` | `all` candidate detection |
| `anonymize_mapping_file` | `<sourcedir>/<dirname>-anon-mapping.csv` | mapping CSV |
| `anonymize_update` | `false` | regenerate existing `_anon.md` (still requires a mapping match) |
| `anonymize-sync-deletes` | `true` | delete `_anon.md` when source document is gone |
| `anonymize-keep-originals` | `false` | keep unanonymized `.md` next to the source PDF |
| `anonymize_publish_without_review` | `false` | publish source `.md` even when unapproved candidates match |
| `anonymize_presidio_model` | `de_core_news_sm` | spaCy model for presidio mode |
| `anonymize_presidio_score_threshold` | `0.5` | presidio confidence cutoff |
| `anonymize_presidio_entities` | built-in list (`all` = registry) | entity allow-list |
| `anonymize_token_length` | `4` | deterministic replacement token length |
| `anonymize_ignore_dictionary` | `false` | ignore dictionary words |
| `anonymize_ignore_numbers` | `false` | ignore values containing digits |
| `anonymize_ignore_emails` | `false` | ignore e-mail candidates |
| `anonymize_ignore_dates` | `false` | ignore date-like candidates |
| `anonymize_ignore_save` | `false` | write filtered proposals to `*-ignore.csv` |
| `anonymize_name_countries` | — | ISO alpha-2 codes for name datasets |
| `anonymize_use_name_datasets` | on when countries set | enable/disable name datasets |
| `anonymize_name_cache_dir` | user cache dir | dataset cache override |
| `anonymize_name_dataset_offline` | — | cache-only, no network |
| `anonymize_name_dataset_debug` | `false` | dataset diagnostics |
| `anonymize_name_exclusions` | — | extra single-token name exclusions |

Note: a change of `mode` does not trigger re-conversion — any existing `.md`
(paired, in targetdir, or at `output_path`) short-circuits conversion.
An existing `_anon.md` is only regenerated when `anonymize_update=true`
**and** `mapping_matches_text` finds an approved value in the current `.md`.
