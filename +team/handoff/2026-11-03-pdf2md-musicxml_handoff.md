# Handoff: pdf2md score detection + Audiveris OMR in inbox flow

- Date: 2026-11-03 — Author: Devin — Updated: 2026-11-04 — Status: implemented, verified on real PDF
- Repo: `witnctools/wit_pytools` — modules: `documenttools/pdf2md.py`, `cinderellasort.py`, `sanitizers.py`
- Specs: `documenttools/+intent/intent.md` → "PDF to Markdown", `cinderellasort/+intent/intent.md` → "Inbox"

## Config

```ini
[DOCPREP]
transcode_sheetmusic=true   ; false (default): only rename to _sheet-music
audiveris=                  ; install dir (preferred), exe, or empty
                            ; -> PATH, then C:\Program Files\Audiveris
audiveris_timeout=600
soffice=                    ; .rtf/.doc converter (else PATH, then default)
```

Bowl routing example: `[BOWLS_INBOX] Noten=sheet-music` — filename crits
(left of the first `;`) run after rename + OMR, so they always trigger
post-conversion-attempt. They cannot distinguish OMR success vs failure;
if needed, add a sidecar-existence gate.

## Proposals for later evaluation (not yet approved)

Tiered detection to also catch *scanned* sheet music:

1. Vector staff-line analysis via `pdfplumber` `page.lines`/`page.rects` —
   staves = long horizontal lines clustered in groups of 5. Free.
2. Raster staff-line detection (render → binarize → horizontal projection,
   run-length ratios). Works on scans; false-positive risk on tables.
3. One-shot vision check on page 1 ("music notation: yes/no") only if the
   free checks say no. ~$0.001 per document.

## Context

- Rules: relative paths, pytest in `tests/` named `*_test.py`, reuse
  `wit_pytools` helpers, PEP8, short comments.
- `wit_pytools` imports need the repo parent on `PYTHONPATH`
  (`PYTHONPATH=P:\git\witnctools` for one-off scripts).
- LibreOffice ships its own `python.exe` — prepend it to PATH *after* the
  repo python when running soffice-dependent commands.
- Audiveris: call bundled `runtime\bin\java.exe -cp app\* Audiveris`
  (the `.exe` launcher can detach); arg parsing fails on non-ASCII paths —
  always copy to ASCII; GitHub-API warning at startup is the update check,
  harmless.

## Suggested skills

- `intent` — if the tiered-detection proposal is approved, extend
  `documenttools/+intent/intent.md` before coding (WIT stage 3).
- `implementation` — to build it once intent is written (WIT stage 4).

## Alternative approaches

- PDFtoMusic Pro (commercial, ~€30) — vector/font-based, near-perfect on notation-software PDFs. Only remaining alternative if Audiveris quality proves insufficient; not needed at current quality.
