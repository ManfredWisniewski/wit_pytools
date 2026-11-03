# Intent: Presort bowls (`BOWLS_PRESORT`)

Companion to `intent.md` — planned INBOX → DOMAINS stage. `BOWLS_PRESORT`
is not implemented yet; terms, shared machinery and the `handlefile`
priority are defined in `intent.md`.

Presort is the first stage of the INBOX flow: it moves incoming external documents (downloads, scans) out of a flat INBOX into per-domain subtrees below `targetdir` — deterministic criteria first, JEV classification second — with a human triage loop for files that cannot be routed reliably.

```text
external documents (Internet, scans) -> INBOX (sourcedir = ...\INBOX)

PRESORT run:
  1. deterministic crits ([BOWLS_PRESORT])   -> match -> targetdir/<domain>
  2. DOCPREP markup for remaining convertible files
  3. JEV domain classification             -> reliable -> targetdir/<domain>
                                           -> else     -> targetdir/INBOX-eval

human: moves file into INBOX-eval/<domain>     (asserted domain = ground truth)
next runs: rescan INBOX-eval -> move when the ruleset confirms the domain
           -> write JEV ruleset proposals for still-unresolved files
              (human merges them into the ruleset manually)
```

Paths: `sourcedir=...\INBOX`, `targetdir=...\INBOX-sort`, eval queue = `targetdir\INBOX-eval`.

## Configuration

```ini
[TABLE]
sourcedir=P:\sort\INBOX
targetdir=P:\sort\INBOX-sort

[BOWLS_PRESORT]
FAW=FAW                  ; filename crits ; content crits — BOWLS_INBOX syntax
VIM=
WIT=;K1176348023

[PRESORT]
eval_dir=INBOX-eval          ; below targetdir: unmatched queue + human triage tree
domain_question=domain       ; JEV question id carrying the domain answer
min_confidence=0.0           ; below this the file goes to <eval_dir>
proposals=true               ; write ruleset proposals for unresolved eval files

[JEV]
definitions_file=P:\sort\jev-categories-wit.ini
```

`[PRESORT]` requires `[JEV]` with `definitions_file`; the JEV question named by `domain_question` enumerates the same values as the configured bowl names (domains). JEV ruleset files already exist (e.g. `P:\sort\jev-categories-wit.ini`).

## Behavior per file

1. **Deterministic pass**: `[BOWLS_PRESORT]` criteria in `BOWLS_INBOX` syntax — filename crits against the cleaned filename, content crits against an existing `.md` beside the source. First match wins → move to `targetdir/<domain>` with markup and sidecars.
2. **Markup preparation**: remaining files with a registered `DOCPREP_CONVERTERS` converter get `.md` beside the source (same conversion machinery and `[DOCPREP]` settings as `handle_docprep`) so JEV can evaluate document content.
3. **JEV pass**: the markup is classified per `[JEV]` (skip-if-`category`-present reuse); a `domain_question` answer naming a configured bowl at ≥ `min_confidence` → move to `targetdir/<domain>` with `.md` and `*_pdf2md.json` sidecars (`maintain_structure` applies).
4. **Eval queue**: no reliable domain — no deterministic match, low confidence, unknown value, no usable markup — the file moves to `<eval_dir>` below `targetdir` instead of staying in the INBOX.
5. **Human triage**: the user moves a file from `<eval_dir>` into `<eval_dir>/<domain>`; the subdirectory name is the asserted domain and is confirmed ground truth.
6. **Eval rescan**: each run also walks `<eval_dir>` — a file under `<eval_dir>/<domain>` whose evaluation (deterministic crits or JEV) now resolves reliably to the asserted domain moves into that domain's bowl; files that stay unresolved remain in place.
7. **Proposals**: after the run, every unresolved eval file produces proposal snippets in JEV ruleset format — suggested criteria/values derived from the asserted domain and the file's markup — so a future run can sort it. Proposals are written to `presort-proposals_<targetdir-name>.ini` in `targetdir` and are **never applied automatically**: a human merges them into `definitions_file` and `[BOWLS_PRESORT]` crits.
8. `[BOWLS_PRESORT]` claims every sortable file like `[BOWLS_INBOX]`; the two are alternative first stages and should not be combined on the same source tree.

## Decisions

- Deterministic sorting comes first — `BOWLS_PRESORT` entries take `filename;content` criteria like `BOWLS_INBOX`; JEV only sees what the crits could not route.
- `<eval_dir>` lives below `targetdir` (`INBOX-sort\INBOX-eval`), not inside `sourcedir`; eval scanning is an explicit tree walk in the same run.
- A human placement under `<eval_dir>/<domain>` is confirmed ground truth: it seeds proposals and constrains the rescan — a file only leaves eval when the ruleset confirms the asserted domain.
- Proposals are human-merged; cinderellasort never edits ruleset files.

## Planned functions

- `presort_settings(config_object)` — `[PRESORT]` with defaults.
- `bowllist_presort` — bowl listing.
- `bowldir_presort(file, config_object, markup_path=None)` — deterministic pass; criteria like `bowldir_inbox`.
- `handle_presort` — handler; runs before all other bowl types in `handlefile`.
- Eval-dir walk + proposal writer for `presort-proposals_<targetdir-name>.ini` (extending the `sorting-proposals_*.ini` mechanism).

## Worklist

`+team/handoff/2026-11-03-presort-inbox-flow_handoff.md`
