# Test strategy

## Anonymization acceptance criteria

- **A01 Candidate detection** identifies supported names, e-mail addresses, URLs, and general strings according to the input adapter's eligible text.
- **A02 Protected spans** are excluded from candidate detection and replacement.
- **A03 Replacement proposals** are deterministic for the same original value and value type.
- **A04 Mapping validation** rejects empty replacements, duplicate originals, unsupported value types, and malformed mapping rows before output is written.
- **A05 Containment grouping** can group related original values and reuse one replacement.
- **A06 Mapping application** replaces approved values while preserving unmapped text.
- **A07 XLSX adapter** preserves formulas and non-string cell values while applying the generic mapping.
- **A08 Markdown adapter** preserves code blocks, inline code, link destinations, and raw URLs.
- **A09 Output safety** refuses to overwrite source or existing output files unless explicitly requested.
- **A10 Package isolation** allows the anonymization core to run without document parser dependencies.

## Test levels

Unit tests for `wit_pytools.anonymization` live under `tests/anonymization/`.
XLSX and Markdown adapter integration tests live under `tests/documenttools/`.
The full pytest suite is run through `tests/runtests.py`.
