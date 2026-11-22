## anonymization layer

### Completed

- Added generic text/Markdown candidate identification with the same candidate CSV format as XLSX.
- Added `anonymize_text_content()` and `anonymize_text()` using the existing mapping validation and containment behavior.
- Markdown protection excludes fenced code blocks, inline code, link destinations and raw URLs; visible link labels remain replaceable.
- Markdown outputs default to `<stem>_anon.<suffix>` and never overwrite the source implicitly.
- PDF-to-Markdown conversion remains a separate explicit step.

### Remaining

- Generalize candidate identification and mapping application to future supported document types without changing the mapping format.

## mailtools.py

Integrate the functions from `mailtools.py` into `documenttools` as the only handlers for mail document types.
