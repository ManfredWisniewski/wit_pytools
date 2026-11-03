# INBOX presort — flow diagram

Directories are the workflow states: `P:\INBOX` is intake, everything
below `P:\INBOX-sort` is machine or human placement. A file's location
tells you its state.

```text
                        external documents (Internet, scans)
                                       |
                                       v
+--------------------------------------------------------------------+
| P:\INBOX                        new — unprocessed intake           |
+--------------------------------------------------------------------+
                                       |
                     cinderellasort run (inbox.bat)
                                       |
          +----------------------------+----------------------------+
          |                                                         |
          v                                                         v
  0. PREFLIGHT                                            1. deterministic crits
     diff live H:\<domain> tree vs                           match_before_markup
     domain-structure snapshot;                              (filename ; existing .md)
     mirror the live dir tree                                deep detail bowls first
     into <domain>\ (filing targets)                               |
          |                                                         |
          |                                            +------------+------------+
          |                                            |                         |
          |                                            v                         v
          |                               2. DOCPREP markup            3. JEV classification
          |                                  for remaining                routing_question ->
          |                                  convertible files            INBOX-sort\<answer> bowl
          |                                            |                (confidence >= min)
          +--------------------------------------------+------------+------------+
                                                                   |
              +----------------------------------------------------+--------------------+
              |                        |                                         |
              v                        v                                         v
   +----------------------+   +----------------------+   +---------------------------+
   | <domain>[\<detail>]  |   | INBOX-sort\<domain>       |   | INBOX-presort                | <-+
   | deterministic        |   | domain match — JEV or |   | needs a human decision    |   |
   | detail hit — direct  |   | deterministic,        |   |                           |   |
   | decided, direct      |   | probabilistic,        |   |                           |   |
   |                      |   | pending check         |   |                           |   |
   +----------------------+   +----------------------+   +---------------------------+   |
                                              |                             |            |
                                              |  HUMAN                      |  HUMAN       |
                                              v                             v            |
                       file into <domain>\<detail>           <domain>\        asserted     |
                       (accept — manual only;                <domain>-negative\ rejected   |
                        dirs mirrored by preflight)          (dirs auto-created)           |
                                              ^                             |            |
                                              |              eval_rescan every run       |
                                              |                             |            |
                                              |      +----------------------+-------+    |
                                              |      |                              |    |
                                              |      v                              v    |
                                              |  confirmed: asserted        rejected:   |
                                              |  -> resolved bowl           ledger +    |
                                              |  (deterministic ->          return to   |
                                              |   <domain>\<detail>,        INBOX ------+
                                              |   JEV -> INBOX-sort\<domain>)  unresolved:  |
                                              |  unasserted + bowl match   stay +       |
                                              |  -> resolved bowl          proposal     |
                                              |                            (domain +    |
                                              |                             id crits)   |
                                              |                             |
                                              +-----------------------------+
                                              |
   generated state files:
     INBOX-sort\sorting-proposals_INBOX-sort.ini  -> merge manually into
                                                    BOWLS_INBOX / jev-domains.ini
     INBOX-sort\inbox-negatives_INBOX-sort.ini    -> recorded rejections
                                                    (file can never match
                                                    that domain again)
```

## States at a glance

| Location | Meaning | Who puts it there |
|---|---|---|
| `P:\INBOX` | new, unprocessed | you / download |
| `<domain>[\<detail>]` | deterministic match — decided, final | run |
| `INBOX-sort\<domain>` | domain match — JEV/deterministic, pending filing | run |
| `INBOX-presort` | couldn't be routed | run |
| `INBOX-presort\<domain>` | asserted domain | you |
| `INBOX-presort\<domain>-negative` | rejected domain | you |
| `<domain>\<detail>` | accepted — your final filing | you (manual only) |

Notes:

- Deterministic crits are decisions: a hit goes **directly** into
  `<domain>[\<detail>]` — no review step. Bowl order decides; detail
  bowls (`<domain>\<detail>`) are listed before the `<domain>` bowls in
  `inbox.ini`, first match wins.
- JEV is probabilistic: a `domain` answer routes to the `INBOX-sort\<domain>`
  staging bowl (`[JEV] staging=INBOX-sort`) and stays there until you file it.
  Domain-level deterministic crits land there too — only *detail* crits
  go straight to `<domain>\<detail>`.
- `INBOX-sort\` is not rescanned; files stay until you act.
- `INBOX-presort\<domain>` files are re-evaluated every run and leave only
  when the ruleset confirms that domain — landing in the resolved bowl
  (a detail hit goes straight to `<domain>\<detail>`, a JEV hit to
  `INBOX-sort\<domain>`).
- Negative entries block the domain permanently per file; a later
  positive assertion in `INBOX-presort\<domain>` wins.
- Proposals suggest the asserted/JEV domain + identifier crits
  (account/customer/invoice numbers found in the markup), not document
  types.
