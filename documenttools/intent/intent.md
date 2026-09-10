# Intent: `documenttools`

## Package purpose

`documenttools` provides modular Python functions for handling document files such as Word, Excel, and PDF documents.

The first concrete capability is the anonymization of string cell values in `.xlsx` workbooks while preserving workbook calculations and structure.

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
- `create_xlsx_mapping(...)`: validate the reviewed candidate CSV and create the mapping CSV.
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

## Non-goals

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
