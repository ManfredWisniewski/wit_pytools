# Handoff: PRESORT bowl — INBOX → DOMAINS flow

- Date: 2026-11-03 — Author: Devin — Status: implemented
- Repo: `witnctools/wit_pytools` — module: `cinderellasort.py`
- Intent: `cinderellasort/+intent/intent-presort.md` (marker in `intent.md` → "Presort bowls")
- Open items tracked in: `cinderellasort/+intent/todo.md`

## Goal

Implement the PRESORT stage of the INBOX flow:

```text
external documents (Internet, scans) -> INBOX (sourcedir = ...\INBOX)
  -> cinderellasort PRESORT run (targetdir = ...\INBOX-sort)
       1. deterministic [BOWLS_PRESORT] crits -> targetdir/<domain>  (FAW, VIM, WIT)
       2. DOCPREP markup for remaining convertible files
       3. JEV domain classification -> reliable: targetdir/<domain>
                                    -> else:     targetdir/INBOX-eval
  human: moves file from INBOX-eval into INBOX-eval/<domain>  (ground truth)
  next runs: re-evaluate eval files (move when ruleset confirms the domain)
             + write JEV ruleset proposals for files still unresolved
               (human merges them manually — never auto-applied)
```

Implemented as an extension of `BOWLS_INBOX` — no new bowl type:
`BOWLS_INBOX` already owns the "claims every sortable file" pipeline
(markup creation, JEV classification, `filename;content` crits,
`!DEFAULT`, sorting proposals). The presort layer adds three keys:
`[SETTINGS] match_before_markup`, `[SETTINGS] eval_rescan`, and
`[JEV] routing_question`. The eval queue is the `!DEFAULT` bowl.

## Worklist

- [x] Owner decisions — resolved 2026-11-03, recorded in `intent-presort.md` → "Decisions": INBOX extension (no new bowl type), deterministic crits first, eval = `!DEFAULT` bowl below `targetdir`, human placement = ground truth, proposals merged manually
- [x] `jev_settings` — add `routing_question` (default empty); `_jev_tag_markup(..., force=False)` — `force` re-classifies despite existing `category` frontmatter
- [x] `_inbox_jev_bowl(markup, config_object)` — `routing_question` frontmatter answer → configured bowl (case-insensitive), else `''`
- [x] `handle_inbox` — `match_before_markup` param: `bowldir_inbox` (with existing `.md`, no conversion) before markup creation; non-`!DEFAULT` match → move directly, skip conversion + JEV
- [x] `handle_inbox` — after `_jev_tag_markup`: `bowl = _inbox_jev_bowl(...)` before the normal crit match
- [x] `process_inbox_eval(...)` — run-level pass: walk `<targetdir>/<!DEFAULT bowl>`; asserted domain = first path component matching a bowl name; re-classify `force=True`; move only when result confirms the asserted domain (or unasserted file resolves any bowl); else `_inbox_record_proposal(nfile, markup, proposed_bowl=asserted)`
- [x] `_inbox_record_proposal(nfile, markup, proposed_bowl=None)` — asserted bowl overrides JEV `category`
- [x] Wire-up: `[SETTINGS]` keys `match_before_markup` + `eval_rescan` in `cinderellasort()`; `match_before_markup` through `handlefile` → `handle_inbox`; `process_inbox_eval` before `_write_inbox_proposals` (not in single mode)
- [x] Tests in `tests/cinderellasort_test.py`, fixtures under `tests/cinderellasort/` (pytest; naming per `.windsurfrules`)
- [x] Flow diagram for the PRESORT stage in `README_cinderallasort-flow.md`

## Context

- Inbox bowls (`[BOWLS_INBOX]`) already implement markup creation, JEV
  classification, content-criteria matching and `sorting-proposals_*.ini`
  output — `handle_inbox` is the implementation template.
- `[JEV]` config: `definitions_file`, `model`, `max_chars`,
  `min_confidence`; domain routing needs a `domain` question in the JEV
  definitions INI whose choice values equal the bowl names.
- Rules: relative paths only, pytest tests in `tests/`, reuse
  `wit_pytools` helpers before writing new ones, PEP8, short comments.
- Pseudonymise real persons/values in tests and docs.

## Suggested skills

None of the installed plugin skills apply to this task; follow the repo
conventions in `AGENTS.md` / `.windsurfrules` and the cinderellasort
`+intent/` docs.
