# Test strategy

## Acceptance criteria

Spec: `+wit/specs/wit_pytools/mailtools/spec.md`.

- **A01** Every moved capability is callable as a `wit_pytools.mailtools` function (IMAP helpers, account config, Sieve compile/deploy, markdown render, archive ops) — SC-001; verified by `tests/mailtools_test.py` using a fake IMAP.
- **A02** `iac-n8n` CLIs keep identical flags/output/side effects — SC-002/SC-004; verified by `pytest wit_pytools/tests` + `python -m unittest discover -s tools` (in iac-n8n) both green.
- **A03** No `.env` access or repo-relative constants inside `mailtools` — SC-003; grep inspection of the package.
- **A04** Legacy flat-module imports (`from mailtools import eml_to_markdown` etc.) keep working via package re-exports — NFR-004; import check.
- **A05** The git commit/push helper lives in `wit_pytools/gittools.py`, not in mailtools — FR-009; import check.

## Test files

```text
tests/mailtools_test.py     pytest — ported function coverage (FakeImap, render, sieve, accounts, archive)
tests/gittools_test.py      pytest — git helper coverage
tests/mailtools/            test data (if needed)
iac-n8n:tools/test_*.py     unittest — CLI/import smoke coverage only
```
