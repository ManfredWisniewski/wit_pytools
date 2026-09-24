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

## Configuration

Candidate detection accepts these options:

- `countries`: explicit ISO 3166-1 alpha-2 codes. When omitted, the
  `ANONYMIZATION_NAME_COUNTRIES` comma-separated environment variable is used.
- `use_name_datasets`: explicitly enable or disable dataset use. The default is
  enabled only when countries are configured.
- `cache_dir`: optional cache directory override. Otherwise the user cache
  directory is used.
- `offline`: use cache only and prohibit network access.
- `debug`: emit cache, repository, and matching diagnostics. The default is
  `False`.
- `name_exclusions`: optional additional words excluded from single-token name
  matching. Built-in common-word exclusions always apply.
- `presidio_entities`: optional entity allow-list for Presidio mode. The default
  excludes `DATE_TIME` and `URL`; `all` uses the configured recognizer registry.

Explicit function arguments take precedence over environment variables.
The runner exposes country, opt-out, offline, and debug options.

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

Candidate detection supports two modes. `custom` uses the local text lists and
is the default. `presidio` uses the locally installed `presidio-analyzer`
package and the configured language model, then returns the same generic
candidate model. Presidio errors are not silently replaced with custom mode.

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
- `load_name_catalog(...)` — load configured country-aware forename and surname data.

`CandidateValidationError`, `MappingValidationError`, and
`NameDatasetUnavailableError` identify invalid or unavailable input.
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
- Candidate detection uses deterministic regular-expression-based
  classification and optional country-aware datasets.
- URL-shaped values in Markdown are protected by the Markdown adapter rather
  than treated as editable candidates.
- Candidate detection does not provide statistical confidence scores.
- Geographic presets are not implemented; configure explicit country codes.

## Name dataset support

Candidate detection can optionally use the latest data from the
`sigpwned/popular-names-by-country-dataset` Git repository. It reads the
repository's `common-forenames-by-country.csv` and
`common-surnames-by-country.csv` files. When country `DE` is configured, it
also reads `noun.txt`, `noun-proper-first-name.txt`, and
`noun-proper-surname.txt` from the `ynsrc/german-categorized-wordlist`
repository. German noun matches exclude single-token name candidates; the
German proper-name files add positive first-name and surname evidence.

The popular-name data is CC0-licensed. The German wordlist is CC BY 4.0.
Source repositories and commits are recorded in cache metadata.

Countries are configured with lowercase ISO 3166-1 alpha-2 codes. No country
is enabled by default, and no geographic presets are provided initially. The
explicit function argument takes precedence over the
`ANONYMIZATION_NAME_COUNTRIES` environment variable.

When countries are configured, each run checks the repository's current `main`
commit. Cached data is reused when the commit is unchanged. Changed data is
downloaded and cached in the user cache directory. If the connection fails,
existing cached data is used. If no cache exists, candidate detection raises
`NameDatasetUnavailableError` unless `use_name_datasets=False` is supplied.
`offline=True` prohibits network access and uses only the cache.

The refresh/cache status is logged only with `debug=True`. Candidate CSV output
keeps the existing schema and does not include country or confidence columns.
Dataset matching is Unicode-normalized and case-insensitive for comparison;
original source text is preserved.

## Open items

See `todo.md` for planned support for popular-name dataset enhancements and
country-specific configuration improvements.
