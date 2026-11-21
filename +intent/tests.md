# Tests and acceptance criteria — `<project>`

*Format per `+wit/development/bestpractices/tests.md`. Criteria are numbered `A01`, `A02`, ... and never renumbered.*

## Commands

```text
test:   <test command, or "manual">
lint:   npx markdownlint-cli2 "**/*.md"
```

## Acceptance criteria

### A01 Repository structure

- `README.md`, `AGENTS.md`, `+team/+tasks/README.md`, `+team/+tasks/backlog.md`, `+intent/{intent,tests}.md`, `knowledge/{README,decisions}.md`, `.gitignore` and `.markdownlint-cli2.jsonc` exist at the root.
- The branches and submodules required by `+wit/common/conventions/repo-setup.md` exist.

### A02 `<feature>`

- `<checkable criterion — by a test or a manual step>`.
- `<negative case for security-relevant paths>`.

## Not tested

- `<what is deliberately not covered yet, and why>`.
