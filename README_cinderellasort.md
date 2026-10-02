# CinderellaSort

CinderellaSort is the shared file-sorting engine used by Mail-Sort and other
sorting tools.

## Common sorting rules

In Nextcloud mode, CinderellaSort loads common `[BOWLS]`, `[BOWLS_EMAIL]`,
`[BOWLS_DOCPREP]`, `[BOWLS_ANONYMIZE]`, and `[BOWLS_GEN_IMG]` rules from the
central configuration file:

```text
/etc/nctools/nctools.ini
```

The project configuration is loaded first. The central `[BOWLS]` and
`[BOWLS_EMAIL]` rules are merged into the effective configuration at runtime.
Neither configuration file is modified.

Example central configuration:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings
Archive=archive
```

A project configuration can contain additional local rules:

```ini
[BOWLS]
Project=project
Plans=project-plans
```

The effective rules are equivalent to:

```ini
[BOWLS]
Documents=documents
Plans=plans,drawings,project-plans
Archive=archive
Project=project
```

If the same bowl is defined in both configurations, its comma-separated
criteria are combined and duplicate criteria are removed. Central rules are
kept before project-specific rules when matching files.

The central file may contain other sections used by the server, but only its
`[BOWLS]` and `[BOWLS_EMAIL]` sections are merged as common rule sets.

Example for shared email rules:

```ini
[BOWLS_EMAIL]
Eingang/Trox=@troxgroup.com
Eingang=!DEFAULT
```

The same merge and precedence rules apply to `[BOWLS_EMAIL]`.

## Project configuration

Project configurations continue to define their own paths and settings:

```ini
[TABLE]
sourcedir=/path/to/source
targetdir=/path/to/originals
filemode=nc

[BOWLS]
Project=project

[SETTINGS]
clear-empty-directories=true
```

`clear-empty-directories` controls removal of empty source directories after
sorting. It defaults to `true` for standard Cinderella bowls and `false` when
`[BOWLS_DOCPREP]` is configured. An explicit `true` or `false` overrides either
default.

For Nextcloud mode, the project configuration is normally named
`mailsort-ini.txt`. Standalone configurations can use `mailsort.ini`.

The common rule merge is enabled automatically when the effective
configuration uses `filemode=nc`. Existing configurations without central
`[BOWLS]`, `[BOWLS_EMAIL]`, `[BOWLS_DOCPREP]`, `[BOWLS_ANONYMIZE]`, or
`[BOWLS_GEN_IMG]` sections continue to work unchanged.

## Doc_prep bowls

Doc_prep bowls convert documents to Markdown **next to the source document**.
Nothing is moved and nothing is anonymized — the produced `.md` (and the
`_pdf2md.json` sidecar) are plain source files. To have them anonymized or
published, select them with a `[BOWLS_ANONYMIZE]` criterion; to sort them,
select them with a `[BOWLS]` criterion.

```ini
[BOWLS_DOCPREP]
Rechnungen=Rechnung,Invoice

[DOCPREP]
mode=vision
model=
language=de
dpi=150
max_pages=50
retry_times=3
continue_on_error=false
sidecar=true
# Remove Markdown/sidecar files whose source document no longer exists.
sync-deletes=false
```

For a source tree:

```text
source/Project/Rechnung 2026.pdf
```

the result is:

```text
source/Project/Rechnung 2026.pdf
source/Project/Rechnung 2026.md
source/Project/Rechnung 2026_pdf2md.json
```

The `[BOWLS_DOCPREP]` bowl selects files; it does not create a `Doc_prep`
subdirectory. A `.md` already next to the source (or found in `targetdir`)
short-circuits conversion — targetdir copies are moved next to the source.

## Anonymize bowls

Anonymize bowls select source files for the anonymization pipeline — both
markup produced by Doc_prep and files that need no pre-processing
(`.md`, `.txt`, `.json`, `.csv`, `.log`). Matched files stay in `sourcedir`;
the anonymized copy `<stem>_anon.<ext>` is written below `targetdir`,
mirroring the source-relative path (with approved mappings applied to
directory names).

Anonymize bowls only *select*; they never move files and never create
subdirectories. A file moved by a regular bowl (or any earlier bowl type)
is gone before the anonymization pass runs and is not anonymized — bowl
order decides.

```ini
[BOWLS_ANONYMIZE]
Anonymized=.md,.json

[ANONYMIZE]
# Optional; defaults to <sourcedir>/<sourcedir-name>-anon-mapping.csv.
mapping_file=P:\\customers\\customer-anon-mapping.csv
# custom uses the local text-list detector; presidio uses presidio-analyzer.
mode=custom
presidio_model=de_core_news_sm
presidio_score_threshold=0.5
# DATE_TIME and URL are excluded by default.
presidio_entities=PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,ORGANIZATION,IP_ADDRESS,CREDIT_CARD,CRYPTO,IBAN_CODE,NRP,MEDICAL_LICENSE
# Replacement token length; the default is 4.
token_length=4
ignore_dictionary=true
ignore_numbers=true
ignore_emails=true
ignore_dates=true
# Rewrite <slug>-anon-ignore-save.csv with values filtered in the current run.
ignore_save=false
# Rewrite existing _anon.<ext> even when no mapping change is detected.
force_update=false
# Remove orphaned _anon.<ext> files from targetdir.
sync-deletes=true
# Copy matched source files to target even when unapproved candidates match.
publish_without_review=false
language=de
# Optional country-aware name detection.
name_countries=de,us
use_name_datasets=true
name_dataset_offline=false
name_dataset_debug=false
name_cache_dir=
name_exclusions=
```

`.xls` and `.xlsx` matched by a bowl produce a "not supported yet" warning;
other unmatched-by-handler extensions are skipped with a warning.

## Anonymization modes

`mode=custom` (in `[ANONYMIZE]`) is the default and preserves the existing
candidate and reviewed-mapping workflow. `mode=presidio` uses the locally
installed `presidio-analyzer` package to detect entities, then uses the same
reviewed mapping workflow. Presidio mode fails if the package or configured
language model is unavailable; it does not fall back to custom detection.

`mode=all` runs both custom detection and Presidio, merging duplicate
values with custom detection taking precedence. This mode is useful when the
goal is to find as many possible names as possible, but it produces significantly
more false-positive recommendations than either mode alone and requires more
manual review.

`presidio_entities` is a comma-separated allow-list. Use `all` to
request all entities available in the configured Presidio recognizer registry.
The supported entity names include:

```text
CREDIT_CARD, CRYPTO, DATE_TIME, EMAIL_ADDRESS, IBAN_CODE, IP_ADDRESS,
MAC_ADDRESS, NRP, LOCATION, PERSON, PHONE_NUMBER, MEDICAL_LICENSE, URL, UUID,
US_BANK_NUMBER, US_DRIVER_LICENSE, US_ITIN, US_CLAIM_NUMBER,
US_HEALTH_INSURANCE_MEMBER_ID, US_MBI, US_NPI, US_PASSPORT,
US_PRESCRIPTION_NUMBER, US_PRIOR_AUTHORIZATION_NUMBER, US_PROVIDER_TAX_ID,
US_REFERRAL_NUMBER, US_SSN,
UK_DRIVING_LICENCE, UK_NHS, UK_NINO, UK_PASSPORT, UK_POSTCODE,
UK_VEHICLE_REGISTRATION,
ES_NIF, ES_NIE, ES_PASSPORT,
IT_FISCAL_CODE, IT_DRIVER_LICENSE, IT_VAT_CODE, IT_PASSPORT,
IT_IDENTITY_CARD,
PL_PESEL, SG_NRIC_FIN, SG_UEN, AU_ABN, AU_ACN, AU_TFN, AU_MEDICARE,
IN_PAN, IN_AADHAAR, IN_VEHICLE_REGISTRATION, IN_VOTER, IN_PASSPORT,
IN_GSTIN, CA_SIN, CA_POSTAL_CODE
```

Entity availability depends on the installed Presidio version, language, and
recognizer/model configuration. `DATE_TIME` and `URL` are intentionally absent
from the default allow-list.

Presidio recommendations can also be filtered before they enter the mapping:

- `ignore_dictionary=true` ignores values containing configured-language dictionary words. With `name_countries=de`, this includes German nouns, plurals, articles, pronouns, adjectives, adverbs, conjunctions, subjunctions, prepositions, particles, verbs, numbers, comparatives, superlatives, contractions, interjections, and abbreviations. Dictionary substrings must contain at least five characters; candidate tokens containing entries from `anonymization/assets/de/word-exclusions.txt` are skipped.
- `ignore_numbers=true` ignores any recommendation containing a digit.
- `ignore_emails=true` ignores e-mail addresses.
- `ignore_dates=true` ignores date-like and `DATE_TIME` recommendations.
- `ignore_save=true` writes values removed by the filters to the sibling report file, such as `Wisniewski-anon-ignore-save.csv`, and replaces that file's contents on each run. The report is informational and is not read as an ignore list.

These filters default to `false`; `ignore_save` also defaults to `false`.

When a mapping row has `status=keep`, its `original_value` is moved to a
sibling ignore file such as `Wisniewski-anon-ignore.csv`. The ignore file has
`original_value` and `value_type` columns, retains existing entries, and prevents
those values from being added as new candidates on later runs. Rows with `status=anon` are moved to the
sibling approved mapping file, such as `Wisniewski-anon.csv`; anonymization
functions read that file automatically. Approved rows retain replacement,
original, type, and `vip` fields.

When anonymize bowls are configured, source subdirectory names are also
checked for recommendations. Approved mappings are applied to the mirrored
target directory path before anonymized output is written. If a matching
unanonymized target directory already exists, it is renamed; an existing
anonymized directory is merged without overwriting files. Source directories
remain unchanged.

For German Presidio detection, install a German spaCy model in addition to the
Python dependency, for example:

```text
pip install -r requirements.txt
python -m spacy download de_core_news_sm
```

`[DOCPREP]` keys:

| Key                 | Default                          | Meaning                                                          |
| ------------------- | -------------------------------- | ---------------------------------------------------------------- |
| `mode`              | `vision`                         | `vision` (multimodal model) or `text` (text layer, no API cost). |
| `model`             | env `OPENROUTER_PDF_MODEL`       | Vision model id.                                                 |
| `language`          | `en`                             | `en` or `de`: markers and illegibility token.                    |
| `dpi`               | `150`                            | Render resolution for page images.                               |
| `max_pages`         | `50`                             | Larger documents are skipped with a warning and stay in place.   |
| `retry_times`       | `3`                              | Retries per page.                                                |
| `continue_on_error` | `false`                          | Keep going when a page fails after all retries.                  |
| `sidecar`           | `true`                           | Keep the `_pdf2md.json` sidecar with the original.                |
| `sync-deletes`      | `false`                          | Remove `.md`/`_pdf2md.json` files without a registered source document. |
| `recursive`         | `true`                           | Process files in subdirectories; set `false` for the source root only. |

Behavior:

- Doc_prep is evaluated before all other bowl types, but only for extensions
  with a registered converter (`.pdf`). PDFs that match no `[BOWLS_DOCPREP]`
  criterion take the standard `[BOWLS]` path.
- The original PDF remains in the source tree; `.md` output and the
  `_pdf2md.json` sidecar are written beside it.
- An existing Markdown next to the source skips conversion; a `.md` found in
  `targetdir` is moved next to the source instead.
- A failed conversion leaves the PDF in the source directory and logs an error;
  no output is created.
- `sync-deletes=true` removes `.md` and `_pdf2md.json` files in `sourcedir`
  whose registered source document (every extension in `DOCPREP_CONVERTERS`)
  no longer exists.
- The cost confirmation of `pdf_to_markdown` is bypassed (`yes=True`);
  `max_pages` is the cost guard. Set `OPENROUTER_API_KEY` and
  `OPENROUTER_PDF_MODEL` in the environment of the process that runs
  cinderellasort.
- Anonymization is a separate bowl type (`BOWLS_ANONYMIZE` + `[ANONYMIZE]`).
  New candidates are added with `status=new` in the configured mapping CSV.
  Only rows with `status=anon` are applied. Set `status=anon` to approve a
  value or `status=keep` to explicitly preserve it.
- After normal sorting, the anonymization pass scans `sourcedir` for files
  matching a `[BOWLS_ANONYMIZE]` criterion and anonymizes them to their
  computed target path; source files are never removed. A matched source file
  that requires no anonymization (no `anon` or `new` mapping row matches) is
  copied to its target path instead; `publish_without_review=true` also
  copies files with unapproved `new` candidates. With `force_update=true`, existing
  anonymized files are rewritten unconditionally.
- An existing `_anon.<ext>` is preserved with `force_update=false` unless its
  plaintext source contains an original whose approved mapping row changed
  since the `*-anon_lastmap.csv` snapshot — such files are always
  regenerated. No `_anon.<ext>` is created when no approved mapping matches.
  With `sync-deletes=true`, a target `_anon.<ext>` whose source no longer
  exists is removed.
- The customer mapping CSV starts with the `status` column and uses
  `status=anon` for approved replacements, `status=keep` for values that must
  not be replaced, and `status=new` for
  proposals. The `vip` column follows `value_type` and defaults to an empty
  value. Each row carries a stable `uid` so changed `replacement_value`s and
  extended `original_value` lists can be detected; the applied state is
  recorded in a sibling `*-anon_lastmap.csv` after each run. Only `anon` rows
  are applied.
- In `nc` mode the mirrored target directory is rescanned after conversion.
- `[BOWLS_DOCPREP]` and `[BOWLS_ANONYMIZE]` are merged from the central
  configuration like `[BOWLS]`; `[DOCPREP]` and `[ANONYMIZE]` are
  project-specific.

## GEN_IMG bowls

GEN_IMG bowls generate images from prompt files with
`aitools.generate_image`. Prompt files stay in the source tree; images and
their JSON sidecars are written into the bowl below `targetdir`.

```ini
[TABLE]
sourcedir=P:\prompts
targetdir=P:\images
ftype_sort=.txt

[BOWLS_GEN_IMG]
Renderings=.

[GEN_IMG]
model=
n=1
aspect_ratio=
resolution=
quality=
output_format=
max_cost=
max_jobs=20
```

Job files beside each other in the source tree:

| File                        | Role                                                    |
| --------------------------- | ------------------------------------------------------- |
| `villa_prompt.txt`          | prompt (UTF-8, whitespace stripped; empty → skipped)   |
| `villa_negative-prompt.txt` | optional negative prompt; never a job on its own        |
| `villa.png/.jpg/.webp`      | optional single reference image (image-to-image)        |
| `reference.png/.jpg/.webp`  | optional general reference for all prompts in the directory that have no own reference image |

The slug (`villa`) is the part before `_prompt.txt`; other `.txt` files are not
jobs and take the standard `[BOWLS]` path.

Result:

```text
images/Renderings/villa.png
images/Renderings/villa.json
```

Each image has its own sidecar with the same name. With `n=2`, or when
`villa.png`/`villa.json` already exist, the next free index is used for both:

```text
images/Renderings/villa_1.png
images/Renderings/villa_1.json
images/Renderings/villa_2.png
images/Renderings/villa_2.json
```

| Key             | Default                       | Meaning                                                             |
| --------------- | ----------------------------- | ------------------------------------------------------------------- |
| `model`         | env `OPENROUTER_IMAGE_MODEL`  | Image model id.                                                     |
| `n`             | `1`                           | Images per prompt; names become `<stem>_1.png` … `<stem>_n.png`.    |
| `aspect_ratio`, `resolution`, `quality`, `output_format` | unset | Passed through to the model when set.          |
| `max_cost`      | env `OPENROUTER_MAX_COST` / `0.50` | Per-job limit; above it, or if the price is unknown, the job is skipped with a warning. Set `ignore` to bypass the cost guard. |
| `max_jobs`      | `20`                          | Jobs per run; remaining prompts are left for the next run.         |

Behavior:

- Evaluated for `.txt` files after Doc_prep and before the standard bowls;
  prompts matching no `[BOWLS_GEN_IMG]` criterion take the `[BOWLS]` path.
- Existing images or sidecars do not skip a job. Each run generates the next
  free image/sidecar enumeration (`<slug>_1`, `<slug>_2`, ...).
- Failures log an error and the run continues with the next prompt.
- No interactive cost prompt; `max_cost` and `max_jobs` are the guards. Set
  `OPENROUTER_API_KEY` and `OPENROUTER_IMAGE_MODEL` in the runner environment.
- In `nc` mode the bowl directory is rescanned after generation.
- `[BOWLS_GEN_IMG]` is merged from the central configuration; `[GEN_IMG]` is
  project-specific.

Per-prompt parameter files (individual aspect ratio, resolution, quality) are
planned; see `cinderellasort/+intent/todo.md`.

## Duplicate keys

Do not define the same bowl more than once within one configuration file.
Combine criteria on one line:

```ini
Plans=plans,drawings,project-plans
```

Duplicate keys within one file are rejected by `ConfigParser`. Duplicate bowl
names across the central and project files are handled by the runtime merge.
