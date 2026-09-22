# Intent: `cinderellasort`

## Package purpose

`cinderellasort` provides modular Python functions for sorting files based on multiple factors and moving them to target directories ("bowls"). It is the shared sorting engine behind Mail-Sort, GPS-Sort, and other `witnctools` scripts.

The implementation currently lives in `wit_pytools/cinderellasort.py`; this directory holds only the intent. Moving the code into the package directory is an open item (see `todo.md`).

## Concepts

- **Source directory** (`sourcedir`): files are read from here and its subdirectories.
- **Target directory** (`targetdir`): normally the root below which bowls are created; for Doc_prep it is the separate root for moved originals.
- **Bowl**: a target subdirectory plus the criteria that route files into it. Bowl name = key, criteria = comma-separated values. Bowl names may contain `/` to address nested directories.
- **Bowl type**: a configuration section that defines how criteria are evaluated (`BOWLS`, `BOWLS_EMAIL`, `BOWLS_GPS`, `BOWLS_GPS_TAGS`, `BOWLS_DOCPREP`, `BOWLS_GEN_IMG`).
- **Special tokens** in criteria: `!DEFAULT` marks the fallback bowl of a section; `!MALFORMED` (`BOWLS_EMAIL` only) receives files whose generated name has no valid e-mail address.
- **File modes**: `win` moves with `os.rename`; `nc` moves through Nextcloud (`occ files:move`) and rescans directories so Nextcloud indexes the changes.
- **Run modes**: all-files mode walks `sourcedir`; `single` mode handles one file passed by a Nextcloud Flow.

## Configuration

One INI file per project. Keys and bowl names are case-preserving.

### `[TABLE]`

- `sourcedir`, `targetdir` — paths; separators are normalized.
- `ftype_sort` — extensions to sort, e.g. `.pdf,.msg`.
- `ftype_delete` — extensions deleted inside valid sort directories.
- `clean` / `clean_nocase` — strings removed from filenames (case-sensitive / case-insensitive).
- `trash` / `trash_nocase` — files whose names contain these strings are deleted.
- `filemode` — `win` (default) or `nc`.

### `[SETTINGS]`

- `overwrite` — overwrite existing targets; otherwise `#2`, `#3`, ... is appended.
- `jpg_quality`, `gps_compress`, `gps_moved_unmatched`, `set_tags` — GPS/image options.
- `usedirectoryname` — name a file after its directory when it is the only sortable file there.
- `skipunmatched` (default `true`) — leave files without a matching bowl in place instead of moving them to `targetdir`.
- `check_content` — for PDFs, also search the document text for `[BOWLS]` criteria (`document_find_regex`).
- `recursive` (default `true`) — process subdirectories; set `false` to process only files directly in `sourcedir`.

### `[REPLACEMENTS]`

`old=new` pairs applied to filenames after cleaning.

### `[BOWLS]`

Filename criteria; optionally content criteria for PDFs. Supports `!DEFAULT`.

### `[BOWLS_EMAIL]`

Criteria are matched against the generated mail filename `YYYY-MM-DD_sender_project_subject.msg`. Supports `!DEFAULT` and `!MALFORMED`.

### `[BOWLS_GPS]` and `[BOWLS_GPS_TAGS]`

Key format `Bowl name;distance_km`, value `lat,lon[;lat,lon...]`. Images whose EXIF position lies within the distance are routed to the bowl (`BOWLS_GPS`) or tagged in Nextcloud (`BOWLS_GPS_TAGS`, tags with access levels `Tag[p]`). Default distance from `[ITEMS] gps_default_distancekm` (fallback 2 km). Supports `!DEFAULT`.

### `[BOWLS_DOCPREP]` and `[DOCPREP]`

See "Doc_prep bowls" below.

### `[BOWLS_GEN_IMG]` and `[GEN_IMG]`

See "GEN_IMG bowls" below.

### Common rules

In `nc` mode the sections `BOWLS`, `BOWLS_EMAIL`, `BOWLS_DOCPREP`, and `BOWLS_GEN_IMG` of the central `/etc/nctools/nctools.ini` are merged into the project configuration at runtime (`merge_common_rules`). Criteria of bowls present in both files are combined and deduplicated; the project file is never modified. `[DOCPREP]` and `[GEN_IMG]` are project-specific and not merged.

## Processing order

`cinderellasort(configfile, single=None, filemode='win', dryrun=False, common_configfile=None)`:

1. Read the configuration, merge common rules, read settings.
2. `prepsort`: create bowl directories for `BOWLS`, `BOWLS_EMAIL`, `BOWLS_GEN_IMG`.
3. Single mode: `handlefile` for the given file. All-files mode:
   - first pass: delete `ftype_delete` files in directories that contain sortable files;
   - second pass: delete `trash`/`trash_nocase` matches, then `handlefile` for every remaining file;
   - legacy pass over subdirectories (to be replaced by `handlefile`).
4. Remove empty source directories.

`handlefile` evaluates bowl types in this fixed priority and stops at the first that handles the file:

1. File extension not in `ftype_sort` → skip.
2. **Doc_prep**: extension has a registered converter and the cleaned filename matches a `[BOWLS_DOCPREP]` criterion → `handle_docprep`.
3. **GEN_IMG**: `<slug>_prompt.txt` matching a `[BOWLS_GEN_IMG]` criterion → `handle_gen_img`.
4. `.pdf` → `handle_pdf` (uses `[BOWLS]`, optional content check).
5. `[BOWLS_EMAIL]` configured → `handle_emails`.
6. `[BOWLS_GPS_TAGS]` configured and `set_tags=true` → `handle_gps_tags` (does not stop processing).
7. `[BOWLS_GPS]` configured → `handle_gps`; files without GPS data are renamed `*_nogps`.
8. `[BOWLS]` → `bowldir`; unmatched files are skipped (`skipunmatched`) or moved to `targetdir`.

## Doc_prep bowls

Doc_prep is a bowl type that **transforms** documents before sorting them. Its purpose is to turn documents into Markdown (or, later, CSV) so that their content becomes searchable, diffable, and usable by other tools, while keeping the original.

### Configuration

```ini
[BOWLS_DOCPREP]
Rechnungen=Rechnung,Invoice

[DOCPREP]
mode=vision            ; vision | text   (pdf_to_markdown mode)
model=                 ; empty: OPENROUTER_PDF_MODEL, then OPENROUTER_MODEL
language=de            ; en | de: markers and illegibility token
dpi=150
max_pages=50           ; larger documents are skipped
retry_times=3
continue_on_error=false
sidecar=true           ; keep <stem>_pdf2md.json beside the original
```

### Behavior per file

1. Clean the filename as for every bowl; the Markdown gets the cleaned stem.
2. Mirror the source file's relative path below `targetdir`.
3. Page count above `max_pages` → warning, file stays in the source directory.
4. An existing Markdown in the mirrored target skips conversion, no API cost.
5. Otherwise convert to the mirrored target (`documenttools.pdf_to_markdown` with `yes=True`, no interactive cost prompt).
6. The original PDF stays in the source directory. Its `_pdf2md.json` sidecar is written beside the original. Conversion errors leave the PDF untouched; in `nc` mode the mirrored target directory is rescanned.

Example:

```text
source/Project/Document.pdf
source/Project/Document_pdf2md.json
originals/Project/Document.md
```

### Converters

`DOCPREP_CONVERTERS` maps an extension to `(page_counter, converter)`. Only `.pdf` is registered. Additional formats (for example `docx` → Markdown, `xlsx` → CSV) are added by registering an entry; the dispatch and move logic stay unchanged.

### Non-goals

- No conversion of files that match no `[BOWLS_DOCPREP]` criterion; such PDFs take the standard `[BOWLS]` path.
- No re-conversion of existing Markdown (use `overwrite` handling outside cinderellasort if needed).
- No interactive cost confirmation; `max_pages` is the only cost guard.

## GEN_IMG bowls

GEN_IMG is a bowl type that **generates** content: each prompt file produces one or more images through `aitools.generate_image`. Prompt files are the durable input and stay in `sourcedir`; images and sidecars are the output in the bowl below `targetdir`.

### Configuration

```ini
[BOWLS_GEN_IMG]
Renderings=.            ; bowl = output subdirectory; criteria on the prompt filename

[GEN_IMG]
model=                  ; empty: OPENROUTER_IMAGE_MODEL
n=1
aspect_ratio=           ; optional pass-through parameters
resolution=
quality=
output_format=
max_cost=               ; per job; empty: OPENROUTER_MAX_COST / 0.50; ignore: bypass guard
max_jobs=20             ; per run
```

### Job definition

For a prompt `<slug>_prompt.txt` in `sourcedir` (recursive); `<slug>` is the job name:

- `<slug>_negative-prompt.txt` — optional negative prompt; never a job itself.
- `<slug>.png|.jpg|.jpeg|.webp` — optional single reference image.
- `reference.png|.jpg|.jpeg|.webp` — general reference in the same directory, used when the slug has no own reference image.
- Other `.txt` files are not jobs.
- Files are read as UTF-8 and stripped; an empty prompt is skipped with a warning.

### Behavior per job

1. Existing images and sidecars do not skip a job; `generate_image` advances to the next free `_k` enumeration.
2. `max_jobs` reached in this run → leave for the next run (warning).
3. `generate_image(prompt, model, negative_prompt, out_dir=<bowl>, n, ..., input_references=[ref], basename=<slug>, interactive=False, max_cost).
4. Output `<slug>.png` (or `<slug>_1..n.png`); an existing image or sidecar name advances to the next free `_k`. Every image gets its own sidecar with the identical name (`<slug>.json`, `<slug>_k.json`).
5. Cost above `max_cost` or unknown price → `RuntimeError` from `generate_image`, logged, job skipped. API errors likewise; the run continues.
6. `nc` mode → rescan the bowl directory.

### Non-goals (current)

- No per-prompt parameters; all jobs of a run share `[GEN_IMG]` (see `todo.md`).
- No moving or deleting of prompt files.
- Existing sidecars do not prevent regeneration; each run uses the next free enumeration.

## Functions

Configuration and rules:

- `merge_common_rules(config_object, common_configfile)` — merge central bowl sections.
- `parse_bowl_tags(tags_str)` — parse `Tag[level]` lists for GPS tags.
- `gps_fetch_default_distance(config_object)` — default GPS distance.
- `docprep_settings(config_object)` — `[DOCPREP]` with defaults.
- `gen_img_settings(config_object)` — `[GEN_IMG]` with defaults.

Bowl listing:

- `bowllist`, `bowllist_email`, `bowllist_gps`, `bowllist_gps_tags`, `bowllist_docprep`, `bowllist_gen_img`.

Bowl matching (return `'/<bowl>'` or `''`):

- `bowldir(file, config_object, file_path=None, check_content=False)`
- `bowldir_email(file, config_object)`
- `bowldir_gps(file, config_object, image_coords)`
- `bowldir_gps_tags(file, config_object, image_coords)`
- `bowldir_docprep(file, config_object)`
- `bowldir_gen_img(file, config_object)`; `is_gen_img_prompt(file)` accepts only `<slug>_prompt.txt`; `gen_img_slug(file)` returns `<slug>`; `gen_img_reference(directory, slug)` resolves the slug or general reference image.

Filenames:

- `cleanfilename(file, clean, clean_nocase, replacements, subdir='', convert_numbers=True)` — apply clean lists, replacements, sanitizing, Arabic numeral conversion.
- `matchstring(file, matchtable)` — comma-list containment test.
- `isvalidsort(sourcedir, ftype_sort)` — directory contains sortable files.

Preparation and handlers:

- `prepsort(config_object, targetdir, prepfilter=False)` — create bowl directories; optionally write `filter-examples.txt`.
- `handle_docprep`, `handle_gen_img`, `handle_pdf`, `handle_emails`, `handle_gps`, `handle_gps_tags`, `handle_oldfiles` (unfinished).
- `GEN_IMG_GENERATOR` — indirection to `aitools.generate_image`, replaceable in tests.
- `handlefile(...)` — dispatcher described above.
- `cinderellasort(...)` — main entry point.

The `wit_pytools.filetools` package provides general file helpers, including
`compare_file(first, second)` for size-based file comparisons.

Translations are loaded from `locale/` via `gettext` (`setup_translations`).

## Open items

See `todo.md` in this directory.
