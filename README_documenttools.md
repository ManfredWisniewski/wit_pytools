# documenttools

`documenttools` provides Python functions for handling document files. The current XLSX functionality identifies, reviews, and applies anonymization mappings while preserving workbook formulas and structure.

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
Lia
Barfuss
Lia Barfuss
Herr Barfuss
Frau Barfuss
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

## Requirements

Install the project dependencies, including `openpyxl`:

```text
openpyxl>=3.1.5
```
