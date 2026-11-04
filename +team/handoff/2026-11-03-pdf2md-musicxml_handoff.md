# Handoff: pdf2md — detect sheet music, embed MusicXML

- Date: 2026-11-03 — Author: Devin — Status: implemented, verified on real PDF
- Repo: `witnctools/wit_pytools` — module: `documenttools/pdf2md.py`
- Spec: `documenttools/+intent/intent.md` → "PDF to Markdown" (updated)
- Docs: `README_documenttools.md` → "PDF to Markdown" (updated)

## What was implemented

1. `_has_music_notation(pdf)` — flags a PDF as a score if any glyph uses a
   known SMuFL music font (`MUSIC_FONT_TOKENS`: bravura, emmentaler, opus,
   maestro, finale, sibelius, dorico, …) or sits in the Unicode private use
   area U+E000–U+F8FF. Detection is document-level and reads the text layer
   only.
2. `vision` mode + notation detected → `pdf2musicxml_prompt.txt` (new),
   `_MUSICXML_SYSTEM_PROMPT`, and each page's transcription is embedded as a
   ` ```musicxml ` fenced block in the `.md` output (user decision: embed in
   Markdown rather than write a separate `.musicxml` file).
3. `text` mode + notation detected → warning log only; no model available.
4. `_FENCE_PATTERN` extended to strip `xml`/`musicxml` fences; sidecar gains
   `music_notation` and records the actual `prompt_file` used.

## Verified

- `P:\INBOX\ЧайковскийП. Танец маленьких лебедей фа диез минор партии.pdf`
  (Sibelius-produced, 4 pages, Opus font family): `_has_music_notation`
  returns True via the `opus` font token.
- `pytest tests/documenttools/documenttools_test.py -k pdf`: 16 passed.
- Pre-existing unrelated failure on clean tree:
  `test_update_text_mapping_ignores_location_and_corporate_names`.

## Findings

- The Sibelius PDF's Opus glyphs are subset-remapped to scrambled codepoints
  (0xb0, 0xa2, 0x70…) — font-level MusicXML reconstruction is infeasible; only
  positions survive. Vision-model transcription is the pragmatic path.
- No Python library does PDF-font→MusicXML. PDFtoMusic Pro (commercial) does;
  Audiveris (open-source OMR, Java) accepts PDFs but rasterizes them.
- Expect approximate MusicXML from the model on dense orchestral scores.
  If quality is insufficient, evaluate Audiveris as an external OMR step.
- JEV was evaluated for detection and rejected: it classifies *text chunks* —
  scans have no text, and subset-remapped music fonts decode to garbage.

## Proposals for later evaluation (not yet approved)

Tiered detection upgrade to also catch scanned sheet music:

1. Vector staff-line analysis via `pdfplumber` `page.lines`/`page.rects` —
   staves = hundreds of thin horizontal lines clustered in groups of 5.
   Free, no API. Catches notation-software PDFs with unknown fonts.
2. Raster staff-line detection (render → binarize → horizontal projection,
   run-length ratios). Works on scans; moderate false-positive risk on
   tables/ruled forms.
3. One-shot vision check on page 1 ("music notation: yes/no") only if the
   free checks say no. ~$0.001 extra per document.

Suggested order: fonts → vector lines → optional vision check. Only run the
paid check when the free checks are negative.

## Context

- Rules: relative paths, pytest in `tests/` named `*_test.py`, reuse
  `wit_pytools` helpers, PEP8, short comments.
- `wit_pytools` imports need the repo parent on `PYTHONPATH`
  (`PYTHONPATH=P:\git\witnctools` when running one-off scripts).
- JEV is already used elsewhere in this repo (`cinderellasort` INBOX flow)
  for *text* classification — the "no text → nothing to classify" limitation
  applies there too.

## Suggested skills

- `intent` — if the tiered-detection proposal is approved, extend
  `documenttools/+intent/intent.md` before coding (WIT stage 3).
- `implementation` — to build it once intent is written (WIT stage 4).

## Alternative approaches

- PDFtoMusic Pro (commercial, ~€30) — reads the vector/font data directly, near-perfect on notation-software PDFs like yours. Best fit by far.
- Audiveris (free OMR) — rasterizes the page but does real symbol recognition; much better duration consistency than a VLM. Needs Java; I could wire it as an optional converter path.
- Stronger vision model — e.g., anthropic/claude-sonnet-4.5 or google/gemini-2.5-pro via OPENROUTER_PDF_MODEL; better than the cheap tiers but same category of errors.