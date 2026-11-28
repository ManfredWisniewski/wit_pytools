# `wit_pytools`

Reusable Python modules and command-line tools for WIT workflows. Tool behavior
and configuration are documented in the corresponding module README or
package-specific intent file.

## WIT guidance

Before making changes, read the shared WIT development guidance in `+wit/`.
Start with `+wit/development/README.md` and `+wit/development/AGENTS.md`, then
read the relevant convention or best-practice files.

## Getting started

Run the test suite from the repository root:

```bash
python -m pytest
```

## Contents

| Path | Purpose |
|------|---------|
| `+intent/` | Repository purpose and acceptance criteria |
| `+team/` | Team task files and local handoff notes |
| `+wit/` | Shared WIT definitions and templates |
| `.agents/`, `.devin/` | Synced agent skills and session hooks |
| `.github/`, `.vscode/` | CI workflows and editor configuration |
| `aitools/`, `anonymization/`, `audiotools/`, `aufmass/` | AI, anonymization, audio, and measurement tools |
| `cinderellasort/`, `csvtools/`, `davtools/`, `documenttools/` | File sorting, CSV, DAV, and document tools |
| `filetools/`, `imgtools/`, `jsontools/`, `mappingtools/`, `xlstools/` | File, image, JSON, mapping, and spreadsheet tools |
| `itsaplantools/`, `mailtools/`, `matrixtools/`, `migrationtools/` | Platform, mail, Matrix, and migration integrations |
| `marketingautomation/`, `payloadtools/`, `scrapetools/`, `webtools/`, `ytdlptools/` | Marketing, CMS, scraping, browser, and media-download tools |
| `examples/`, `runners/` | Example inputs and command runners |
| `scripts/`, `tests/` | Repository automation and pytest suites/fixtures |
| `knowledge/`, `locale/` | Durable repository knowledge and translations |
| `structure/`, `taxonomies/` | Repository structure guidance and the existing taxonomy template |
| `thraell/` | Thraell initialization files |
| Root `*.py` modules | Shared helpers and legacy tool entry points |

## Repository setup

Branches (`main`, `work`, `wip`, one per persona) and submodules follow
`+wit/common/conventions/repo-setup.md`.
