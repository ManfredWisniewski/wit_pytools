# Intent: Presort stage — INBOX → DOMAINS (`BOWLS_INBOX` extension)

Companion to `intent.md` — planned INBOX → DOMAINS stage. Implemented as
an extension of Inbox bowls, not a new bowl type: `BOWLS_INBOX` already
owns the "claims every sortable file" pipeline (markup creation, JEV
classification, `filename;content` crits, `!DEFAULT`, proposals).

Presort is the first stage of the INBOX flow: it moves incoming external documents (downloads, scans) out of a flat INBOX into domain bowls below `targetdir` — deterministic criteria first, JEV classification second — with a human triage loop for files that cannot be routed reliably.

Directory-as-state layout (UI-friendly): deterministic *detail* crits are decisions and write directly into `targetdir/<domain>/<detail>`; domain-level matches (JEV or deterministic) land in `targetdir/INBOX-sort/<domain>` staging bowls until the human files them into `<domain>` detail dirs (manual acceptance); the `!DEFAULT` bowl (`INBOX-presort`) is the eval/triage queue.

```text
external documents (Internet, scans) -> INBOX (sourcedir = ...\INBOX)

PRESORT run (BOWLS_INBOX with presort keys):
  1. deterministic crits (match_before_markup)  -> match -> targetdir/<bowl>
                                                     e.g. WIT\Buchhaltung\...
  2. DOCPREP markup for remaining convertible files
  3. JEV classification; routing_question answer
     names a domain                          -> reliable -> INBOX-sort/<domain>
                                              -> else     -> INBOX-presort
                                                             (the !DEFAULT bowl)

human: file INBOX-sort/<domain> into the detail dirs yourself
       (<domain>/<detail...> = accepted); wrong domain ->
       INBOX-presort/<domain>-negative; triage INBOX-presort ->
       INBOX-presort/<domain> (asserted = ground truth)
next runs (eval_rescan): rescan INBOX-presort -> asserted + ruleset confirms
           -> resolved bowl (deterministic -> <domain>/<detail>,
           JEV -> INBOX-sort/<domain>); rejected files return to INBOX
           and can never match that domain again (negative ledger)
           -> write sorting proposals for still-unresolved files
              (human merges them manually)
```

Paths: `sourcedir=...\INBOX`, `targetdir=...\INBOX-sort`, eval queue = `targetdir\INBOX-presort` (the `!DEFAULT` bowl), JEV staging = `targetdir\INBOX-sort\<domain>`, accepted = `targetdir\<domain>[/<detail>]` (deterministic hits + manual filing).

## Configuration

```ini
[TABLE]
sourcedir=P:\sort\INBOX
targetdir=P:\sort\INBOX-sort

[SETTINGS]
match_before_markup=true   ; deterministic crits before conversion (default false)
eval_rescan=true           ; rescan the !DEFAULT bowl each run (default false)

[BOWLS_INBOX]
FAW=FAW                    ; filename crits ; content crits — unchanged syntax
VIM=
WIT=;K1176348023
INBOX-presort=!DEFAULT        ; the eval queue

[JEV]
definitions_file=P:\sort\jev-categories-wit.ini
routing_question=domain    ; JEV question whose answer names the bowl
```

The JEV question named by `routing_question` enumerates the same values as the configured bowl names (domains). JEV ruleset files already exist (e.g. `P:\sort\jev-categories-wit.ini`).

## Behavior per file (sourcedir pass)

1. **Deterministic pass** (`match_before_markup=true`): `bowldir_inbox` crits — filename crits against the cleaned filename, content crits against an `.md` that already exists beside the source. A match that is not the `!DEFAULT` bowl → move to `targetdir/<bowl>` with existing sidecars; no conversion, no JEV call. Detail bowls (`WIT\Buchhaltung\...`) are listed before the domain bowls — first match wins — so strong identifiers file straight into `<domain>/<detail>`.
2. **Markup preparation**: remaining files with a registered `DOCPREP_CONVERTERS` converter get `.md` beside the source (unchanged `handle_inbox` machinery) so JEV can evaluate document content.
3. **JEV routing**: after classification, when `routing_question` is set the answer routes to the `<staging>/<answer>` bowl (`[JEV] staging`, default `review`) — JEV results are probabilistic and stay in `INBOX-sort/<domain>` until the human files them. Without a staging bowl the shallowest bowl naming the domain wins. Otherwise the normal `bowldir_inbox` crit match applies (content crits can still hit `domain: ...` frontmatter).
4. **Eval queue**: no reliable domain — no deterministic match, low confidence (JEV replaces the choice with the fallback), unknown value, no usable markup — the `!DEFAULT` bowl (`INBOX-presort`) catches the file and it lands in `targetdir/INBOX-presort` with its sidecars.
5. **Human triage**: the user moves a file from `INBOX-presort` into `INBOX-presort/<domain>`; the subdirectory name is the asserted domain and is confirmed ground truth.

## Eval rescan (`eval_rescan=true`, run level)

After the sourcedir pass, `process_inbox_eval` walks `<targetdir>/<!DEFAULT bowl>`:

1. For every `ftype_sort` file (sidecars skipped, they travel with the source), the asserted domain is the first path component below the eval root **if it case-insensitively matches the last path component of a configured bowl**; files in the eval root or under a non-bowl subdir carry no assertion.
2. Markup beside the file is re-classified with `force=True` so a ruleset updated since the last run takes effect (eval files are few; the API cost is the point of the loop).
3. The file is re-evaluated: `routing_question` answer, then `bowldir_inbox` crits. A result equal to the `!DEFAULT` bowl or a negatively-ledgered domain counts as unresolved.
4. Confirmed — the resolved bowl's domain equals the asserted domain, or no assertion and any real bowl — the file moves to `targetdir/<resolved bowl>` with its markup and sidecars (`maintain_structure` is not applied inside eval). A deterministic resolution lands directly in `<domain>/<detail>` (decided); a JEV staging resolution lands in `INBOX-sort/<domain>` for human filing.
5. Unresolved files stay in place and are recorded for proposals; an asserted domain seeds the proposal bowl instead of the JEV `category`.
6. **Negative triage**: a file under `<eval>/<domain>-negative` is a human-rejected domain assignment — the rejection is appended to the `inbox-negatives_<targetdir-name>.ini` ledger in `targetdir` and the file returns to `sourcedir` with its sidecars. A recorded negative blocks that bowl in every later evaluation (`handle_inbox` and the rescan): the file can still reach a *different* domain, but never the rejected one, and falls back to the `!DEFAULT` bowl otherwise. A positive assertion in `<eval>/<domain>` overrides a stored rejection for that file.

## Proposals

Unresolved eval files land in the existing `sorting-proposals_<targetdir-name>.ini` (human merges crits into `BOWLS_INBOX` and updates JEV rulesets manually — cinderellasort never edits ruleset files). The proposed bowl is the asserted domain, else the JEV `routing_question` answer; the suggested crits are identifier-like tokens extracted from the markup (≥4 digits — account, customer and invoice numbers), falling back to `;document_type` or the cleaned stem.

## Decisions

- No `BOWLS_PRESORT` bowl type: presort is an evaluation layer on `BOWLS_INBOX`. The two cannot be combined on one tree anyway since inbox claims every sortable file.
- Deterministic sorting comes first, but stays opt-in (`match_before_markup`): skipping conversion means no markup for crit-matched files, which existing users may not want.
- The eval queue is the `!DEFAULT` bowl — no separate `eval_dir` key. `eval_rescan` is opt-in because it re-classifies eval files via JEV on every run (API cost).
- `routing_question` matches the JEV answer to bowl names case-insensitively instead of substring content crits (`domain: fa` prefix pitfalls); crits remain as fallback.
- A human placement under `INBOX-presort/<domain>` is confirmed ground truth: a file only leaves eval when the evaluation confirms the asserted domain, landing in `INBOX-sort/<domain>` like any machine-sorted file — acceptance (filing into `<domain>/<detail>`) is always manual.
- A bowl's **domain** is its first path component, or the component below the staging prefix when it starts with `[JEV] staging` (`INBOX-sort\WIT` → `WIT`; `WIT\Buchhaltung\rechnungen-in` → `WIT`; `3D-print` → `3D-print`). Asserted/rejected dirs and `routing_question` answers name that domain.
- **Deterministic = direct**: detail and domain bowls file straight into `targetdir/<domain>[/<detail>]` — no review step for decided crits. Detail bowls are listed before the domain bowls — first match wins.
- **Per-domain detail rulesets**: after the presort run, `inbox-<domain>.ini` runs per domain — `sourcedir=targetdir/INBOX-sort/<domain>` (staging), `targetdir=targetdir/<domain>`, `BOWLS_INBOX` detail bowls relative to the domain tree; unmatched files stay in staging (no `!DEFAULT`). `inbox.bat` loops `inbox-*.ini` after `inbox.ini`.
- **JEV = staging**: `routing_question` answers route to the `staging/<answer>` bowl (`INBOX-sort\<domain>`, empty-crit bowls in the INI); those files wait for manual filing into the detail dirs.
- At run start `prepsort` creates the configured bowls; `_prepare_inbox_eval_dirs` additionally creates `<domain>`, `INBOX-presort/<domain>` and `INBOX-presort/<domain>-negative` per domain so human triage is a drop-into-existing-folder action.
- Preflight (`structure_root` + `structure_snapshot_dir`): diffs each live domain tree against its snapshot. **New** dirs are harmless — mirrored (dirs only, no files) into `targetdir/<domain>` silently. **Removed or renamed** dirs (a rename shows as `-old/+new`) **stop the run** — `check_domain_structures` returns False and `cinderellasort()` aborts; the human handles the moved dirs, updates the snapshot, then re-runs.
- Preflight change handling (future): distinguish removed dirs *containing filed documents* in the `targetdir` mirror (orphaned filings needing a decision) from empty removals — snapshots record dirs only, so detection keys on filed content in the mirror, not just the path diff.
- A human placement under `INBOX-presort/<domain>-negative` is rejected ground truth, persisted in the `inbox-negatives_*.ini` ledger: the file returns to the INBOX and can never match that domain again. Without it, a wrongly-matched file would ping-pong between the wrong domain and human triage.

## Worklist

`+team/handoff/2026-11-03-presort-inbox-flow_handoff.md`
