# INBOX presort flow — how it works

External documents (downloads, scans) arrive in `P:\INBOX`. Each
cinderellasort run sorts them into domains. Everything the machine can't
place reliably waits for a human decision. Directories are the workflow
states — a file's location says where it is in the flow.

```text
P:\INBOX                        new — unprocessed intake (drop files here)
P:\INBOX-sort\
  INBOX-sort\<domain>\              domain-sorted — JEV or deterministic,
                                pending your filing
  INBOX-presort\                   needs a human decision
    <domain>\                   you say: "belongs to this domain"
    <domain>-negative\          you say: "does NOT belong to this domain"
  <domain>\<detail dirs>\       decided — deterministic detail hits
                                land here directly; the rest via you
  3D-print\                     .stl files (deterministic, direct)
```

Domains: `FAW` (private), `VIM` (music school), `WIT` (company).

Deterministic crits are decisions: a hit goes straight into
`<domain>[\<detail>]` — nothing to review. JEV is probabilistic: it
lands in `INBOX-sort\<domain>` and waits for you to file it into the matching
detail directory (e.g. `INBOX-sort\WIT\rechnung.pdf` →
`WIT\Buchhaltung\rechnungen-in\`).

## What a run does

Run `inbox.bat` (add `--dryrun` to preview without moving).

0. **Preflight** — diffs the live `H:\<domain>` tree against its
   structure snapshot and mirrors the directory tree (dirs only) into
   `INBOX-sort\<domain>\` so filing targets exist.
1. **Deterministic match** — filename and existing-markup criteria
   (deep detail bowls first). A hit moves the file straight to
   `<domain>[\<detail>]` — decided, no review, no API cost.
2. **Markup** — remaining documents get a `.md` next to the source
   (DOCPREP conversion) so content can be evaluated.
3. **JEV classification** — the markup is classified; the `domain`
   answer routes the file to the `INBOX-sort\<domain>` staging bowl.
4. **Eval queue** — anything still unresolved lands in `INBOX-presort`.
5. **Eval rescan** — `INBOX-presort` is re-checked every run: asserted
   files move to the resolved bowl (deterministic → `<domain>\<detail>`,
   JEV → `INBOX-sort\<domain>`) when the ruleset confirms them, rejected
   files return to `P:\INBOX` and can never match that domain again.
6. **Proposals** — unresolved files are listed in
   `INBOX-sort\sorting-proposals_INBOX-sort.ini` with suggested criteria.

## What you do

1. **File from `INBOX-sort\<domain>`** — domain-sorted, pending you:
   - correct domain → move into the detail dir
     (`WIT\Buchhaltung\...`) — that's accepting it
   - leave it → stays in `INBOX-sort\` until a rule change moves it again
   - wrong domain → move to `INBOX-presort\<domain>-negative`
   - wrong domain, right one known → move to `INBOX-presort\<domain>`
2. **Triage `INBOX-presort`** — couldn't be routed:
   - you know the domain → move to `INBOX-presort\<domain>`; the rescan
     evaluates it against the ruleset every run and moves it to
     `INBOX-sort\<domain>` once confirmed — plus it feeds the proposals
3. **Merge proposals** — copy useful criteria from
   `sorting-proposals_INBOX-sort.ini` into `inbox.ini`
   (`[BOWLS_INBOX]`) and/or `jev-domains.ini` (`[DOMAIN]`), manually.
4. **Re-run** — repeat until `INBOX-sort\` and `INBOX-presort\` only hold
   true rejects.

## The files that keep state

| File | Meaning |
|---|---|
| `INBOX-sort\sorting-proposals_INBOX-sort.ini` | suggested domain + identifier crits per unresolved file |
| `INBOX-sort\inbox-negatives_INBOX-sort.ini` | recorded rejections (`file = domain`) |
| `inbox.ini` | config: bowls, deterministic crits, settings |
| `jev-domains.ini` | JEV `domain` question (routing ruleset) |

## Rules of thumb

- `<domain>-negative` is permanent: a file recorded there can never be
  matched to that domain again — it only moves via a different domain.
- An asserted dir (`INBOX-presort\<domain>`) overrides a stored rejection
  for the same file — last human decision wins.
- The machine never edits the rulesets; proposals are merged by hand.
- Sidecars (`.md`, `*_pdf2md.json`) always travel with their document.
