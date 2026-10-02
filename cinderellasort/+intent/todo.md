# cinderellasort — open items

## General

- move the cinderellasort script to the package directory
- make the cinderella sort function case-insensitive like the cleanup
- replace the legacy subdirectory pass in `cinderellasort()` with `handlefile`
- Add a user-facing runner/config example for the `recursive=false` option.

## Anonymization

### Implemented design

- Doc_prep and anonymization are separate bowl types: `[BOWLS_DOCPREP]` +
  `[DOCPREP]` only convert documents to `.md` beside the source; `[BOWLS_ANONYMIZE]`
  + `[ANONYMIZE]` anonymize bowl-matched source files to `<stem>_anon.<ext>`
  below `targetdir`.
- Supported anonymize input types are `.md`, `.txt`, `.json`, `.csv`, `.log`;
  `.xls`/`.xlsx` warn until a structured adapter exists.
- Only bowl-matched files are anonymized; a file moved by an earlier bowl is
  never evaluated by the anonymize pass.
- `mapping_file` points to one customer mapping CSV; when unset it defaults to
  `<sourcedir>/<sourcedir-name>-anon-mapping.csv`.
- On the first run, new candidates are added with `status=new`; no anonymized
  output is created yet. Only rows with `status=anon` are applied; `status=keep`
  explicitly rejects replacement.
- On later runs, approved mappings are applied only when they match the source
  file. No `_anon.<ext>` is created when there is no match.
- `force_update=false` preserves an existing anonymized output unless the
  `*-anon_lastmap.csv` diff flags a changed or extended approved row present in
  the source; `force_update=true` refreshes unconditionally.
- `ignore_save=false` is off by default; when true, values filtered
  from proposals are written to `<slug>-anon-ignore-save.csv`, which is rewritten
  on each run. `<slug>-anon-ignore.csv` remains cumulative for `keep` rows.
- `publish_without_review=false` withholds plaintext copies that still contain
  unapproved candidates.
- Source subdirectory names are included in anonymization proposals. Approved
  mappings rename matching mirrored target directories before document output;
  source directories remain unchanged.
- `clear-empty-directories` controls empty-source-directory cleanup. It defaults
  to `false` for Doc_prep configurations and `true` otherwise.
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
