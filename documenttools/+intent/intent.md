# Intent: `documenttools`

## Package purpose

`documenttools` provides modular Python functions for handling document files such as Word, Excel, and PDF documents.

The first concrete capability is the anonymization of string cell values in `.xlsx` workbooks while preserving workbook calculations and structure. The second is the conversion of PDF documents to Markdown.

## XLSX anonymization workflow

Anonymization is a three-step workflow:

1. **Identify candidate values**
   - Read an `.xlsx` workbook without modifying it.
   - Identify unique, non-empty string values in non-formula cells.
   - Exclude numeric, date, boolean, blank, error, and formula cells.
   - Aggregate repeated values into one candidate row.
   - Record all worksheet and cell locations and the number of occurrences.
   - Generate deterministic, type-aware replacement proposals.
   - Write the proposals to `<input-stem>_candidates.csv` beside the source workbook.

2. **Review candidates**
   - A human reviews the candidate CSV.
   - The human may edit `replacement_value`.
   - Rows that must not be replaced may be deleted.
   - Remaining rows are considered approved; no status column is required.

3. **Create and apply the mapping**
   - Validate the reviewed candidate CSV.
   - Reject duplicate originals, missing replacements, conflicting rows, and invalid entries before creating output.
   - Write the final reversible mapping to `<input-stem>_mapping.csv` beside the source workbook.
   - Apply the mapping to the source workbook and write `<input-stem>_anonymized.xlsx` beside it.
   - Never modify or overwrite the source workbook by default.

## Public functions

The workflow should expose modular functions equivalent to:

- `identify_xlsx_strings(...)`: create the candidate CSV.
- `create_mapping(...)`: validate the reviewed candidate CSV and create the mapping CSV.
- `anonymize_xlsx(...)`: apply the mapping CSV and create the anonymized workbook.

The replacement step requires the mapping CSV, allowing the same mapping to be reused for additional copies of the source data.

## Candidate CSV

The candidate CSV uses UTF-8 encoding, a header row, comma delimiters, and standard CSV quoting.

Its columns are:

- `original_value`
- `replacement_value`
- `value_type`
- `worksheet`
- `cell`
- `occurrences`

Each unique original string appears once. Locations may be aggregated in the `worksheet` and `cell` fields. Replacement proposals are deterministic and type-aware, for example:

- names become stable pseudonymous names;
- email addresses become stable synthetic addresses;
- URLs become stable synthetic URLs;
- general strings become stable pseudonymous tokens.

The same original value always receives the same proposed replacement throughout the workbook.

## Mapping CSV

The final mapping CSV uses UTF-8 encoding, a header row, comma delimiters, and standard CSV quoting.

Its columns are:

- `replacement_value`
- `original_value` — semicolon-separated original strings
- `value_type`

There is one mapping row per replacement value. For example:

```csv
replacement_value,original_value,value_type
Person-54b,Lia Barfuss;Barfuss;Doreen Barfuss,name
```

The mapping is reversible by default and is saved separately from the workbook. It must not be stored inside the workbook. A user may destroy the mapping file when irreversible anonymization is desired.

Different original values may use the same replacement value, although replacement values should normally remain unique when distinctions between values are important.

Mapping creation supports configurable containment grouping. When enabled, original values that contain one another as whole values are grouped and receive the same replacement. This supports formulas that match a short Personenkonten value against a longer transaction description without depending on a specific worksheet name or position. The runner controls this behavior with `GROUP_CONTAINED_VALUES=1` or `0`.

A mapping row must contain a non-empty replacement. Deleting a candidate row means that the original value is not replaced; an existing row with an empty replacement is invalid.

## Workbook preservation requirements

The anonymization process must:

- preserve formulas exactly as stored;
- preserve formula references and calculations;
- preserve formatting;
- preserve merged cells;
- preserve worksheet order and hidden states;
- preserve data validation;
- preserve conditional formatting;
- preserve charts and images;
- preserve hyperlinks, except that hyperlinks are not anonymized in the initial implementation;
- preserve workbook structure and metadata unchanged;
- replace only selected string values in non-formula cells;
- keep replacements as strings and avoid type coercion;
- leave the source workbook unchanged;
- fail before writing a partial output when the workbook or mapping is unsupported or invalid.

The initial implementation supports `.xlsx` files only. Macro-enabled `.xlsm` files are outside the initial scope.

## Output handling

Candidate, mapping, and anonymized output files are saved alongside the source workbook. Existing output files must not be overwritten unless an explicit overwrite option is supplied. The source workbook must never be overwritten implicitly.

## XLSX non-goals

The initial implementation does not anonymize:

- formulas or formula text;
- numeric, date, boolean, blank, or error cells;
- comments or notes;
- hyperlinks;
- worksheet names;
- defined names;
- workbook properties or other metadata;
- charts or images;
- external links;
- VBA or other macro content;
- `.xlsm` files.

## Generic text/Markdown anonymization

Text-based anonymization uses the same reviewed mapping CSV format as XLSX.
The XLSX functions remain separate because workbook cells, formulas and
metadata require different traversal and preservation logic.

### Public functions

- `identify_text_strings(...) -> Path`: create a candidate CSV for Markdown or plain text.
- `anonymize_text_content(content, mapping_path) -> str`: apply a validated mapping to text content.
- `anonymize_text(file_path, mapping_path, ...) -> Path`: write `<stem>_anon.<suffix>` without overwriting the source by default.

### Candidate rules

Text candidates include names and e-mail addresses. URL-shaped values are not
candidates. Candidate CSV columns remain the common schema:
`original_value`, `replacement_value`, `value_type`, `worksheet`, `cell`, and
`occurrences`. Markdown locations use `worksheet=Markdown` and line locations
such as `line 12; line 48`.

Markdown candidate detection excludes fenced code blocks, inline code spans,
link destinations, raw URLs, dates, numbers and blank content. Visible link
labels remain eligible for replacement while their destinations are preserved.

### Replacement rules

Replacement uses the same mapping validation and containment grouping as XLSX.
Markdown replacement protects fenced code, inline code, link destinations and
raw URLs. The source is never modified implicitly. PDF conversion and
anonymization are separate explicit steps; `pdf_to_markdown` does not invoke
anonymization automatically.

## PDF to Markdown

### Purpose

Convert a PDF document into a single Markdown file that reflects the document's text and structure. The concept mirrors MarkPDFDown (Apache-2.0): render each page to an image and let a multimodal model transcribe it. No code from that project is used. Rendering uses `pdfplumber`, already required by `document_find_regex`; the model is reached through `wit_pytools.aitools`. No additional dependencies are introduced.

### Workflow

1. Validate the input (`.pdf` only), the mode, the language, and the page range.
2. In `vision` mode: resolve the model (`model=` → `OPENROUTER_PDF_MODEL` → `OPENROUTER_MODEL`), load the prompt, estimate the cost as pages × per-image price, and ask for confirmation above the limit or when the price is unknown (`yes` skips).
3. For each page in the range:
   - `vision`: render at `dpi` to a temporary PNG, send prompt and image to the model, strip a surrounding Markdown fence, retry on errors or empty responses with a `2 × attempt` second pause.
   - `text`: use the text layer via `pdfplumber`; a page without text yields a marker.
4. Join pages with a Markdown horizontal rule (`---`, surrounded by blank lines, only between pages).
5. Write `<stem>.md` and the sidecar `<stem>_pdf2md.json`; optionally keep page images and per-page Markdown in `<stem>_pages/`.

### Public functions

- `pdf_to_markdown_text(...) -> str`: convert and return the Markdown without touching disk.
- `pdf_to_markdown(...) -> Path`: convert, write the output beside the source (or to `output_path`), write the sidecar, return the output path.

Parameters: `mode`, `model`, `start_page`, `end_page`, `output_path`, `overwrite`, `keep_pages`, `prompt_file`, `dpi`, `retry_times`, `continue_on_error`, `max_cost`, `yes`, `language`, `api_key`.

### Modes

- `vision` (default): multimodal transcription of page images. Handles image-only PDFs.
- `text`: text layer only, no API call, no layout or table reconstruction.

### Prompt

One built-in English prompt (`pdf2md_prompt.txt`): transcribe faithfully in the document's language, keep headings, lists, tables as Markdown tables, formulas as LaTeX, describe images briefly in brackets, mark unreadable passages with the illegibility token, never invent content, output Markdown only. `prompt_file` replaces it; the `{illegible}` placeholder is filled per language in both cases.

### Language

`language` (parameter, `PDF2MD_LANGUAGE`, `--language`, runner `LANGUAGE`) selects the marker texts and the illegibility token. Supported: `en` (default), `de`. Unknown codes raise `ValueError`. The prompt itself stays English; the transcription is always in the document's own language.

### Failure handling

After the retries are exhausted, the page receives a visible blockquote marker (`> **Page N: conversion failed** — reason`) and conversion continues. At the end the run raises `RuntimeError` listing the failed pages unless `continue_on_error` is set. Pages without a text layer in `text` mode receive an analogous marker and a warning log entry; they never fall back to the model automatically.

### Output handling

Outputs are written beside the source PDF. Existing outputs are not overwritten unless `overwrite` is set. The source PDF is never modified. The sidecar records source, mode, model, page range, dpi, language, prompt file, estimated cost, per-page status, and creation time.

### Entry points

- Python functions above.
- CLI: `python -m wit_pytools.documenttools.pdf2md INPUT [options]` with a `--log` tee like `aitools.generate_image`.
- Runner: `runners/pdf2md_runner.bat`, drag-and-drop capable, loads `set_ENV.bat`.

### PDF non-goals

The initial implementation does not provide:

- direct image input (PNG/JPG) — handled by a separate future function;
- a `hybrid` mode passing the text layer to the model as a hint;
- table extraction in `text` mode;
- OCR without a model;
- a Nextcloud Flow wrapper (planned follow-up in `witnctools`);
- automatic fallback from `text` to `vision`.

## Anonymization package boundary

Generic anonymization functionality is provided by `wit_pytools.anonymization`.
It owns candidate models and detection, deterministic replacement proposals,
mapping CSV validation and application, containment grouping, and generic text
replacement. It does not depend on document parsers or external document
providers.

`documenttools` owns format adapters: XLSX traversal and workbook preservation,
and Markdown parsing, protected-region detection, and reconstruction. These
adapters call `anonymization` for candidate detection and replacement logic.
Candidate detection accepts generic text and format-provided protected spans.

The migration switches all callers to the new package immediately. Obsolete
anonymization implementations are removed from `documenttools`; no
compatibility wrappers are retained. Generic anonymization tests live under
`tests/anonymization/`, while format adapter tests remain under
`tests/documenttools/`. The existing candidate and mapping CSV schemas remain
the file interchange format.
