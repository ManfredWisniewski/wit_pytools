# Handoff: PRESORT bowl — INBOX → DOMAINS flow

- Date: 2026-11-03 — Author: Devin — Status: worklist
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

`BOWLS_PRESORT` is a new bowl type, evaluated before all others in
`handlefile` (same "claims every sortable file" semantics as
`BOWLS_INBOX` — alternative first stages, do not combine on one tree).
Markup + JEV classification reuse the existing inbox machinery and the
`[DOCPREP]` / `[JEV]` sections.

## Worklist

- [x] Owner decisions — resolved 2026-11-03, recorded in `intent-presort.md` → "Decisions": deterministic crits first, eval dir below `targetdir` (`INBOX-sort\INBOX-eval`), human placement = ground truth, proposals merged manually
- [ ] `presort_settings(config_object)` — `[PRESORT]` keys: `eval_dir` (default `INBOX-eval`), `domain_question` (default `domain`), `min_confidence`, `proposals`
- [ ] `bowllist_presort` + `bowldir_presort` in `cinderellasort.py` — deterministic pass with `BOWLS_INBOX`-style `filename;content` crits (content crits against existing `.md`); register `BOWLS_PRESORT` in `merge_common_rules` and `prepsort` (create domain bowl dirs)
- [ ] `handle_presort` — pipeline per `intent-presort.md`: (1) deterministic crits → `targetdir/<domain>`; (2) DOCPREP markup for remaining convertible files; (3) JEV `domain_question` answer ≥ `min_confidence` → `targetdir/<domain>`; else move to `<eval_dir>` — with `.md` + sidecars, `maintain_structure`
- [ ] Eval-dir pass in the same run: walk `<eval_dir>`; files under `<eval_dir>/<domain>` whose evaluation now confirms the asserted domain move into the domain bowl; rest stay
- [ ] Proposal writer: `presort-proposals_<targetdir-name>.ini` in `targetdir` — JEV ruleset-format snippets derived from asserted domain + markup; never auto-applied (extend the `sorting-proposals_*.ini` mechanism)
- [ ] `handlefile` priority: insert `handle_presort` before `handle_inbox` (already documented in intent)
- [ ] Tests in `tests/cinderellasort_test.py`, fixtures under `tests/cinderellasort/` (pytest; naming per `.windsurfrules`)
- [ ] Flow diagram for the PRESORT stage in `README_cinderallasort-flow.md`

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
