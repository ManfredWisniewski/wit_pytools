# cinderellasort — open items

## General

- Add a user-facing runner/config example for the `recursive=false` option.

- move the cinderellasort script to the package directory
- make the cinderella sort function case-insensitive like the cleanup
- replace the legacy subdirectory pass in `cinderellasort()` with `handlefile()`

## GEN_IMG bowls

- Per-prompt parameter files: allow an optional `<slug>.ini` (or similar) beside
  `<slug>_prompt.txt` that overrides `[GEN_IMG]` values for that job only — at least
  `aspect_ratio`, `resolution`, `quality`; probably also `n`, `model`,
  `output_format`. Precedence: per-prompt file > `[GEN_IMG]` > environment.
  Decide the file format (INI section vs. key=value lines) and whether the
  sidecar records which values came from the per-prompt file.
