# Decisions

## Anonymization architecture

- **D01 Generic anonymization is a separate `wit_pytools.anonymization` package** (alternatives: keep all anonymization in `documenttools`; create format-specific anonymization packages). Reason: candidate detection, replacement generation, mapping validation, containment grouping, and generic text replacement are shared across XLSX, Markdown, and future formats.
- **D02 Document adapters remain in `documenttools`** (alternatives: move all anonymization adapters into `anonymization`; duplicate format logic). Reason: XLSX workbook preservation and Markdown protected-region handling are format-specific.
- **D03 Candidate detection accepts generic text and protected spans** (alternatives: make the detector Markdown-aware; make each adapter implement its own detector). Reason: adapters own markup parsing while the candidate rules remain reusable.
- **D04 The migration switches callers immediately and removes obsolete implementations** (alternatives: retain compatibility wrappers; deprecate wrappers over time). Reason: this code is not used in a live environment.
- **D05 Generic anonymization tests live under `tests/anonymization/` and adapter tests remain under `tests/documenttools/`** (alternatives: keep all tests in one file; organize tests only by workflow). Reason: tests should follow the package boundary.
- **D06 Existing candidate and mapping CSV schemas remain the interchange format** (alternatives: replace CSV with a new format; expose only Python objects). Reason: reviewed mapping files are a human-editable workflow boundary.
- **D07 Safe output handling remains mandatory** (alternatives: allow implicit overwrite; let adapters decide). Reason: anonymization must validate before writing and must not overwrite source files by default.

Decision date: 2026-09-24
