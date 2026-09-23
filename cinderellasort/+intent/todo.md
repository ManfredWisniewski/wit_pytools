# cinderellasort — open items

## General

- move the cinderellasort script to the package directory
- make the cinderella sort function case-insensitive like the cleanup
- replace the legacy subdirectory pass in `cinderellasort()` with `handlefile`
- Add a user-facing runner/config example for the `recursive=false` option.

## Doc_prep anonymization

### Implemented design

- `[DOCPREP] anonymize=false` is off by default.
- `anonymize_mapping` points to one customer mapping CSV.
- On the first run, Markdown is generated and new candidates are added with
  `status=new`; no anonymized output is created yet.
- Only rows with `status=anon` are approved and applied.
- Set `status=anon` to approve a proposal or `status=keep` to explicitly reject
  replacement. Rows with `status=new` are never applied.
- On later runs, approved mappings are applied only when they match the current
  Markdown. No `_anon.md` file is created when there is no match.
- `anonymize_update=false` preserves an existing anonymized output;
  `anonymize_update=true` refreshes it using the current approved mapping.
- JSON mapping support is a future UI-oriented option; CSV remains the current
  manually editable format.

## GEN_IMG bowls

- Per-prompt parameter files: allow an optional `<slug>.ini` (or similar) beside
  `<slug>_prompt.txt` that overrides `[GEN_IMG]` values for that job only — at least
  `aspect_ratio`, `resolution`, `quality`; probably also `n`, `model`,
  `output_format`. Precedence: per-prompt file > `[GEN_IMG]` > environment.
  Decide the file format and whether the sidecar records which values came from
  the per-prompt file.

## mailtools.py

Integrate the functions from `mailtools.py` into `documenttools` as the only
handlers for mail document types.
