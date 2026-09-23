# documenttools

`documenttools` provides Python functions for handling document files. The XLSX functionality identifies, reviews, and applies anonymization mappings while preserving workbook formulas and structure. The PDF functionality converts PDF documents to Markdown.

## XLSX workflow

The workflow uses three steps:

```text
source.xlsx
    |
    +-- source_candidates.csv
            |
            +-- source_mapping.csv
                    |
                    +-- source_anonymized.xlsx
```

### 1. Create candidates

Run `identify_xlsx_strings` or the XLSX runner. The function creates a candidates CSV beside the workbook:

```text
<input-stem>_candidates.csv
```

The candidate file contains:

- `original_value`
- `replacement_value`
- `value_type`
- `worksheet`
- `cell`
- `occurrences`

Only unique, non-empty string values from non-formula cells are included. Dates, numbers, booleans, blanks, errors, and formulas are excluded.

### 2. Human review

Review the candidates CSV manually:

- Edit `replacement_value` when necessary.
- Delete rows that must not be anonymized.
- Keep the remaining rows as the approved candidate list.

No status column is required. A remaining row is considered approved.

### 3. Create the mapping and anonymize

Run the process again after reviewing the candidates CSV. The reviewed candidates create:

```text
<input-stem>_mapping.csv
```

The mapping is then applied to create:

```text
<input-stem>_anonymized.xlsx
```

The source workbook is never overwritten unless an explicit output path points elsewhere and overwrite behavior is enabled.

If the mapping CSV already exists, the runner reuses it and does not regenerate it. This preserves human-approved mapping decisions.

## Public functions

### `identify_xlsx_strings`

```python
identify_xlsx_strings(
    file_path,
    output_path=None,
    *,
    overwrite=False,
)
```

Identifies candidate string values in an `.xlsx` workbook and writes the candidates CSV.

- `file_path`: source `.xlsx` workbook.
- `output_path`: optional candidates CSV path. By default, the file is created beside the workbook.
- `overwrite`: permits replacing an existing candidates CSV.
- Returns: the output `Path`.

### `create_xlsx_mapping`

```python
create_xlsx_mapping(
    candidate_path,
    output_path=None,
    *,
    overwrite=False,
    group_contained_values=False,
)
```

Validates a reviewed candidates CSV and creates the mapping CSV.

The mapping CSV has one row per replacement value and these columns, in this order:

- `replacement_value`
- `original_value` — semicolon-separated original strings
- `value_type`

For example:

```csv
replacement_value,original_value,value_type
Person-54b,Lia Barfuss;Barfuss;Doreen Barfuss,name
```

- `candidate_path`: reviewed candidates CSV.
- `output_path`: optional mapping CSV path. By default, it is created beside the candidates CSV.
- `overwrite`: permits replacing an existing mapping CSV.
- `group_contained_values`: when enabled, groups original values that contain one another as whole values and assigns them the same replacement.
- Returns: the output `Path`.

For example, with containment grouping enabled, values such as these can share one replacement:

```text
Anna
Musterpeter
Anna Musterpeter
Herr Musterpeter
Frau Musterpeter
```

This supports formulas that search for a short value inside a longer transaction description. Grouping is based on the reviewed candidates and is not tied to a particular worksheet name or position.

### `anonymize_xlsx`

```python
anonymize_xlsx(
    file_path,
    mapping_path,
    output_path=None,
    *,
    overwrite=False,
)
```

Applies a mapping CSV to an `.xlsx` workbook.

- `file_path`: source `.xlsx` workbook.
- `mapping_path`: approved mapping CSV.
- `output_path`: optional anonymized workbook path. By default, it is created beside the mapping CSV.
- `overwrite`: permits replacing an existing anonymized workbook.
- Returns: the output `Path`.

Formulas are not changed. String replacements preserve formula matching when related original values have been grouped to the same replacement.

## XLSX runner

The runner files are:

- `runners/xlsx_anonymize_runner.bat`
- `runners/xlsx_anonymize_runner.py`

The batch runner processes the configured XLSX filename in the root directory and its immediate subdirectories. It also processes a workbook located directly in the root directory. `__pycache__` directories are skipped.

Configuration variables:

```bat
set ROOT_DIR=.
set XLSX_FILE=anonymize_xlsx.xlsx
set PYTHON_PATH=python
set OVERWRITE_OUTPUTS=1
set GROUP_CONTAINED_VALUES=1
```

`ROOT_DIR` defaults to the current working directory. `XLSX_FILE` defaults to `anonymize_xlsx.xlsx`. `GROUP_CONTAINED_VALUES=1` enables containment grouping when a new mapping CSV is created; set it to `0` to disable grouping.

The runner behavior is:

1. If the workbook has no candidates CSV, create the candidates CSV and stop.
2. If the candidates CSV exists but the mapping CSV does not, create the mapping CSV using the reviewed candidates.
3. If the mapping CSV exists, reuse it without regenerating it.
4. Create or replace the anonymized workbook according to `OVERWRITE_OUTPUTS`.

## Preservation rules

The anonymization process:

- preserves formulas exactly as stored;
- preserves formula references and calculations;
- preserves formatting and workbook structure;
- preserves merged cells, hidden states, data validation, and conditional formatting;
- leaves dates unchanged;
- replaces only mapped string values in non-formula cells;
- keeps replacement values as strings;
- supports `.xlsx` files only in the initial implementation.

The mapping CSV is reversible by default. Destroying the mapping file makes the anonymization practically irreversible.

## Generic text and Markdown anonymization

Markdown anonymization uses the same reviewed mapping CSV format as XLSX but
keeps the workbook-specific functions separate.

```python
from wit_pytools.documenttools import (
    identify_text_strings,
    anonymize_text,
    anonymize_text_content,
)

candidates = identify_text_strings("document.md")
output = anonymize_text("document.md", "document_mapping.csv")
```

Outputs use:

```text
document_candidates.csv
document_mapping.csv
document_anon.md
```

Candidate detection identifies names and e-mail addresses, but not URLs. It
records `worksheet=Markdown`, line locations in `cell`, and occurrence counts.
Fenced code blocks, inline code, link destinations, raw URLs, dates, numbers
and blank content are excluded. Visible link labels remain eligible for
replacement while their destinations stay unchanged.

`anonymize_text_content()` returns transformed text without writing files.
`anonymize_text()` never overwrites the source unless an explicit output path
and `overwrite=True` are supplied. PDF conversion and anonymization are
separate explicit steps.

## PDF to Markdown

`pdf_to_markdown` converts a PDF into one Markdown file. The approach mirrors the concept of [MarkPDFDown](https://github.com/MarkPDFdown/markpdfdown) (Apache-2.0): each page is rendered to an image and transcribed by a multimodal model. No code from that project is used; rendering relies on `pdfplumber` and the model is reached through `wit_pytools.aitools` (OpenRouter).

```text
document.pdf
    |
    +-- document.md
    +-- document_pdf2md.json      (sidecar: model, pages, cost, per-page status)
    +-- document_pages/           (only with keep_pages: page_0001.png, page_0001.md, ...)
```

### Modes

| Mode     | What it does                                                    | API cost |
| -------- | --------------------------------------------------------------- | -------- |
| `vision` | Renders each page at `dpi` and sends the image to the model.    | yes      |
| `text`   | Uses the PDF text layer via `pdfplumber` (no layout, no tables). | no       |

Image-only PDFs (scans) work in `vision` mode. In `text` mode a page without a text layer produces a marker instead of content.

### Environment variables

| Variable               | Required           | Purpose                                                    |
| ---------------------- | ------------------ | ---------------------------------------------------------- |
| `OPENROUTER_API_KEY`   | vision             | API key.                                                    |
| `OPENROUTER_PDF_MODEL` | vision             | Vision model id; falls back to `OPENROUTER_MODEL`.          |
| `OPENROUTER_MAX_COST`  | no                 | Confirmation threshold in USD (default `0.50`).             |
| `PDF2MD_LANGUAGE`      | no                 | Marker language `en` (default) or `de`.                     |

### Choosing a model

Any OpenRouter model with `image` in its input modalities works. Inexpensive candidates (USD per million tokens, in/out, as of September 2026):

| Model                            | in   | out  | Notes                                                   |
| -------------------------------- | ---- | ---- | ------------------------------------------------------- |
| `google/gemini-2.5-flash-lite`   | 0.10 | 0.40 | Gemini Flash family is strong at document transcription |
| `qwen/qwen3-vl-8b-instruct`      | 0.12 | 0.46 | Vision-specialised model, good on tables and scans      |
| `openai/gpt-4.1-nano`            | 0.10 | 0.40 | Reliable formatting, weaker on dense scans              |
| `openai/gpt-4o-mini`             | 0.15 | 0.60 | Well-known baseline                                     |

A page rendered at 150 DPI costs roughly 1–2k input tokens, so a 50-page document costs a few cents with any of these. Test one representative document and compare models if tables or numbers come out wrong. Avoid `:batch` model variants: they are asynchronous and do not work with the synchronous `chat()` call.

These models publish no per-image price, so the cost estimate is reported as unknown and the confirmation prompt appears on every run unless `yes=True` / `--yes` / `SKIP_COST_CONFIRM=1` is used. The actual cost is recorded in the sidecar. Current prices: `python -c "from wit_pytools.aitools import list_models; [print(m['id'], m['pricing']) for m in list_models() if 'image' in m['input_modalities']]"`.

### Python

```python
from wit_pytools.documenttools import pdf_to_markdown, pdf_to_markdown_text

path = pdf_to_markdown("invoice.pdf", model="openai/gpt-4o", language="de", yes=True)
text = pdf_to_markdown_text("invoice.pdf", mode="text")
```

```python
pdf_to_markdown(
    pdf_path,
    *,
    mode="vision",
    model=None,
    start_page=1,
    end_page=None,
    output_path=None,
    overwrite=False,
    keep_pages=False,
    prompt_file=None,
    dpi=150,
    retry_times=3,
    continue_on_error=False,
    max_cost=None,
    yes=False,
    language=None,
    api_key=None,
)
```

- `output_path`: defaults to `<stem>.md` beside the PDF. Existing outputs raise `FileExistsError` unless `overwrite=True`. The source PDF is never modified.
- `end_page=None` means the last page.
- `keep_pages`: keeps page images and per-page Markdown in `<stem>_pages/`.
- `prompt_file`: UTF-8 file replacing the built-in prompt (`documenttools/pdf2md_prompt.txt`). The placeholders `{illegible}`, `{signature}` and `{logo}` are translated for the selected language.

Prompt slugs are translated with gettext. Translation sources are stored below:

```text
locale/<language>/LC_MESSAGES/pdf2md.po
```

The German slugs are `[unleserlich]`, `[Unterschrift]` and `[Logo]`. Compiled `.mo` files can be generated from the `.po` sources during packaging; fallback values keep the built-in translations available when `.mo` files are not present.
- `retry_times`: failed or empty model responses are retried with a `2 × attempt` second pause. After the last attempt the page gets a failure marker; the run raises `RuntimeError` unless `continue_on_error=True`.
- `max_cost` / `yes`: before any API call the cost is estimated as pages × per-image price of the model. Above the limit, or if the price is unknown, you are asked to confirm; `yes=True` skips the prompt.
- `language`: `en` or `de`; controls the markers below and the illegibility token in the prompt.
- Returns the output `Path`. `pdf_to_markdown_text` has the same parameters without `output_path`, `overwrite`, `keep_pages` and returns the Markdown string without writing files.

### Output format

Pages are separated by a Markdown horizontal rule:

```markdown
# Page one content

---

Page two content
```

Failed pages and pages without a text layer are marked with a blockquote:

```markdown
> **Page 3: conversion failed** — OpenRouter 502: ...
> **Seite 3: keine Textebene** — für diese Seite den Modus vision verwenden
```

### CLI

```bat
python -m wit_pytools.documenttools.pdf2md document.pdf --model openai/gpt-4o --language de
python -m wit_pytools.documenttools.pdf2md document.pdf --mode text --start 2 --end 5 --output notes.md
```

Options: `--mode`, `--model`, `--start`, `--end`, `--output`, `--overwrite`, `--keep-pages`, `--prompt-file`, `--dpi`, `--retry-times`, `--continue-on-error`, `--max-cost`, `--yes`, `--language`, `--log`.

### Runner

`runners/pdf2md_runner.bat` wraps the CLI. Drag a PDF onto it or pass the path as the first argument; otherwise `INPUT_PDF` from the CONFIGURATION block is used. It loads `set_ENV.bat` (copy `set_ENV_template.bat`, which now contains `OPENROUTER_PDF_MODEL`) and appends console output to `pdf2md_runner.log`.

### Not covered (yet)

Direct image input (PNG/JPG), a `hybrid` mode that passes the text layer to the model as a hint, table extraction in `text` mode, and a Nextcloud Flow wrapper.

## Requirements

Install the project dependencies:

```text
openpyxl>=3.1.5
pdfplumber>=0.11
```

`pdfplumber` is required for `document_find_regex` and the PDF to Markdown functions; `openpyxl` for the XLSX functions. Both imports are optional so that either group can be used without the other installed.
