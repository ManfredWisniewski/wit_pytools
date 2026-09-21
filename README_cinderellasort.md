# CinderellaSort

CinderellaSort is the shared file-sorting engine used by Mail-Sort and other
sorting tools.

## Common sorting rules

In Nextcloud mode, CinderellaSort loads common `[BOWLS]` and
`[BOWLS_EMAIL]` rules from the central configuration file:

```text
/etc/nctools/nctools.ini
```

The project configuration is loaded first. The central `[BOWLS]` and
`[BOWLS_EMAIL]` rules are merged into the effective configuration at runtime.
Neither configuration file is modified.

Example central configuration:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings
Archive=archive
```

A project configuration can contain additional local rules:

```ini
[BOWLS]
Project=project
Plans=project-plans
```

The effective rules are equivalent to:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings,project-plans
Archive=archive
Project=project
```

If the same bowl is defined in both configurations, its comma-separated
criteria are combined and duplicate criteria are removed. Central rules are
kept before project-specific rules when matching files.

The central file may contain other sections used by the server, but only its
`[BOWLS]` and `[BOWLS_EMAIL]` sections are merged as common rule sets.

Example for shared email rules:

```ini
[BOWLS_EMAIL]
Eingang/Trox=@troxgroup.com
Eingang=!DEFAULT
```

The same merge and precedence rules apply to `[BOWLS_EMAIL]`.

## Project configuration

Project configurations continue to define their own paths and settings:

```ini
[TABLE]
sourcedir=/path/to/source
targetdir=/path/to/originals
filemode=nc

[BOWLS]
Project=project
```

For Nextcloud mode, the project configuration is normally named
`mailsort-ini.txt`. Standalone configurations can use `mailsort.ini`.

The common rule merge is enabled automatically when the effective
configuration uses `filemode=nc`. Existing configurations without central
`[BOWLS]`, `[BOWLS_EMAIL]`, or `[BOWLS_DOCPREP]` sections continue to work
unchanged.

## Doc_prep bowls

Doc_prep bowls convert documents in place. A matching PDF is converted to
Markdown beside the source PDF, while the original PDF and its sidecar are
moved to a separate target root that mirrors the source directory structure.

```ini
[BOWLS_DOCPREP]
Rechnungen=Rechnung,Invoice

[DOCPREP]
mode=vision
model=
language=de
dpi=150
max_pages=50
retry_times=3
continue_on_error=false
sidecar=true
```

For a source tree:

```text
source/Project/Rechnung 2026.pdf
```

with `targetdir=/path/to/originals`, the result is:

```text
source/Project/Rechnung 2026.md
originals/Project/Rechnung 2026.pdf
originals/Project/Rechnung 2026_pdf2md.json
```

The `[BOWLS_DOCPREP]` bowl selects files; it does not create a `Doc_prep`
subdirectory.

| Key                 | Default                          | Meaning                                                          |
| ------------------- | -------------------------------- | ---------------------------------------------------------------- |
| `mode`              | `vision`                         | `vision` (multimodal model) or `text` (text layer, no API cost). |
| `model`             | env `OPENROUTER_PDF_MODEL`       | Vision model id.                                                 |
| `language`          | `en`                             | `en` or `de`: markers and illegibility token.                    |
| `dpi`               | `150`                            | Render resolution for page images.                               |
| `max_pages`         | `50`                             | Larger documents are skipped with a warning and stay in place.   |
| `retry_times`       | `3`                              | Retries per page.                                                |
| `continue_on_error` | `false`                          | Keep going when a page fails after all retries.                  |
| `sidecar`           | `true`                           | Keep the `_pdf2md.json` sidecar with the original.                |

Behavior:

- Doc_prep is evaluated before all other bowl types, but only for extensions
  with a registered converter (`.pdf`). PDFs that match no `[BOWLS_DOCPREP]`
  criterion take the standard `[BOWLS]` path.
- The original PDF remains in the source tree.
- An existing Markdown file in the mirrored target skips conversion; the source
  PDF remains unchanged.
- The sidecar is written once beside the source PDF.
- A failed conversion leaves the PDF in the source directory and logs an error;
  no output is created.
- The source directory is scanned recursively and its relative directory
  structure is mirrored below `targetdir`.
- The cost confirmation of `pdf_to_markdown` is bypassed (`yes=True`);
  `max_pages` is the cost guard. Set `OPENROUTER_API_KEY` and
  `OPENROUTER_PDF_MODEL` in the environment of the process that runs
  cinderellasort.
- In `nc` mode the mirrored target directory is rescanned after the move.
- `[BOWLS_DOCPREP]` is merged from the central configuration like `[BOWLS]`;
  `[DOCPREP]` is project-specific.

## Duplicate keys

Do not define the same bowl more than once within one configuration file.
Combine criteria on one line:

```ini
Plans=plans,drawings,project-plans
```

Duplicate keys within one file are rejected by `ConfigParser`. Duplicate bowl
names across the central and project files are handled by the runtime merge.
