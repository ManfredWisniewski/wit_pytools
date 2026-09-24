# Intent: `anonymization`

## Package purpose

`anonymization` provides format-independent candidate detection, deterministic
replacement generation, reviewed mapping validation, containment grouping, and
mapping application.

The package is used by document-specific adapters in `wit_pytools.documenttools`.
The adapters retain XLSX traversal and preservation, Markdown parsing, protected
regions, and output reconstruction. The anonymization package does not depend on
`openpyxl`, `pdfplumber`, or model/API clients.

## Concepts

- **Candidate**: a unique source value proposed for replacement, including its
  value type, replacement proposal, locations, and occurrence count.
- **Protected span**: a character range supplied by a format adapter that must
  not be inspected or changed.
- **Candidate CSV**: a human-reviewable list of proposed replacements.
- **Mapping CSV**: a validated, reusable set of approved replacements.
- **Containment grouping**: grouping whole values where one value occurs inside
  another, so related values can share a replacement.

## Processing order

1. Validate candidate or mapping input.
2. Detect eligible values while excluding adapter-provided protected spans.
3. Classify candidates as names, e-mail addresses, URLs, or general strings.
4. Generate deterministic replacement proposals.
5. Review candidate replacements externally.
6. Validate the reviewed mapping before output is written.
7. Optionally group contained values.
8. Apply approved mappings to editable text or format-adapter values.

## Main workflows

### Candidate detection

`detect_text_candidates(...)` receives text, a source identifier, and optional
protected character spans. It returns generic `Candidate` objects. The detector
handles candidate classification and locations; markup parsing remains in the
calling adapter.

### Mapping creation

`create_mapping(...)` validates a reviewed candidate CSV and writes a reusable
mapping CSV. It rejects missing required columns, empty originals or
replacements, unsupported value types, and duplicate originals.

### Mapping application

The package applies replacements to generic editable text parts and provides
mapping lookup and containment-aware replacement helpers. Format adapters decide
how editable and protected parts are identified and how output is written.

## Public functions

- `detect_text_candidates(...)` — detect generic text candidates outside protected spans.
- `create_mapping(...)` — validate candidate rows and create a mapping CSV.
- `mapping_path_rows(...)` — read and validate approved mapping rows.
- `related_mapping_values(...)` — find containment-related mapping values.
- `replace_related_values(...)` — apply containment-aware replacements.
- `replace_text_part(...)` — replace mapped values in one editable text part.
- `replace_text_parts(...)` — replace editable parts while preserving protected parts.
- `mapping_matches_parts(...)` — check whether approved mappings match editable parts.
- `is_date_string(...)` — identify supported date strings excluded from anonymization.
- `replacement_for(...)` — generate a deterministic replacement proposal.

`CandidateValidationError` and `MappingValidationError` identify invalid input.
The package does not modify source files implicitly.

## Data and file formats

### Candidate CSV

Candidate CSV files use UTF-8 encoding, comma delimiters, standard CSV quoting,
and these columns:

```text
original_value,replacement_value,value_type,worksheet,cell,occurrences
```

The `worksheet` and `cell` names are retained for compatibility. Adapters may
use them for generic source and location information.

### Mapping CSV

Mapping CSV files use UTF-8 encoding, comma delimiters, standard CSV quoting,
and these columns:

```text
replacement_value,original_value,value_type
```

`original_value` may contain semicolon-separated related originals. Status-aware
mapping files may additionally contain `status`, `source_documents`,
`locations`, and `occurrences`. Supported statuses are `keep`, `anon`, and
`new`; rows without a status are treated as `anon`.

## Safety and preservation

- Source files are never overwritten implicitly.
- Existing output files require an explicit overwrite option.
- Mapping validation completes before anonymized output is written.
- The mapping remains separate from source documents and is reusable.
- Protected spans supplied by adapters are preserved exactly.
- The package does not handle workbook structure, formulas, Markdown syntax, or
  PDF layout; those remain adapter responsibilities.

## Tests and verification

Core tests are in:

```text
tests/anonymization/test_core.py
```

Document adapter tests are in:

```text
tests/documenttools/documenttools_test.py
```

The full test runner is:

```text
python tests/runtests.py
```

The current implementation has been verified through the full runner with all
anonymization and document adapter tests passing. The package has no external
service tests.

## Non-goals and limitations

- No direct XLSX, PDF, or Markdown parsing is performed here.
- No model or external service is required for candidate detection.
- Candidate detection currently uses deterministic regular-expression-based
  classification.
- URL-shaped values in Markdown are protected by the Markdown adapter rather
  than treated as editable candidates.
- Candidate detection for country-specific names is not implemented yet.

## Open items

See `todo.md` for planned support for configurable country-aware name datasets.
