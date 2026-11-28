# Tests and acceptance criteria - `wit_pytools`

*Format per `+wit/development/bestpractices/tests.md`. Criteria are numbered
`A01`, `A02`, ... and never renumbered.*

## Commands

```text
test:   python -m pytest
lint:   npx markdownlint-cli2 "**/*.md"
```

## Acceptance criteria

### A01 Repository structure

- `python scripts/check-repo-structure.py . --remote --skills-check` exits
  successfully.
- The `+wit` submodule pin is present on its upstream and tracks `main`.

### A02 Test suite

- `python -m pytest` discovers and passes the repository's test suites under
  `tests/`.

## Not tested

- Live behavior of external APIs and services is not a root-level acceptance
  criterion; consult each tool's documentation and tests for its coverage.
