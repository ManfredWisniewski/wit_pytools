# CinderellaSort

CinderellaSort is the shared file-sorting engine used by Mail-Sort and other
sorting tools.

## Common sorting rules

In Nextcloud mode, CinderellaSort loads common `[BOWLS]` and
`[BOWLS_EMAIL]` rules from the central configuration file:

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
```

For Nextcloud mode, the project configuration is normally named
`mailsort-ini.txt`. Standalone configurations can use `mailsort.ini`.

The common rule merge is enabled automatically when the effective
configuration uses `filemode=nc`. Existing configurations without central
`[BOWLS]`, `[BOWLS_EMAIL]`, or `[BOWLS_DOCPREP]` sections continue to work
unchanged.

## Doc_prep bowls

Doc_prep bowls convert documents in place. A matching PDF is converted to
Markdown beside the source PDF, while the original PDF and its sidecar are
moved to a separate target root that mirrors the source directory structure.

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
anonymize=false
# custom uses the local text-list detector; presidio uses presidio-analyzer.
anonymize-mode=custom
anonymize_presidio_model=de_core_news_sm
anonymize_presidio_score_threshold=0.5
# Replacement token length; the default is 4.
anonymize_replacement_length=4
# DATE_TIME and URL are excluded by default.
anonymize_presidio_entities=PERSON,EMAIL_ADDRESS,PHONE_NUMBER,LOCATION,ORGANIZATION,IP_ADDRESS,CREDIT_CARD,CRYPTO,IBAN_CODE,NRP,MEDICAL_LICENSE
anonymize_ignore_dictionary=true
anonymize_ignore_numbers=true
anonymize_ignore_emails=true
anonymize_mapping=P:\\customers\\customer-anon-mapping.csv
anonymize_update=false
anonymize-keep-originals=false
# Optional country-aware name detection.
anonymize_name_countries=de,us
anonymize_use_name_datasets=true
anonymize_name_dataset_offline=false
anonymize_name_dataset_debug=false
anonymize_name_cache_dir=
anonymize_name_exclusions=
```

For a source tree:

```text
source/Project/Rechnung 2026.pdf
```

with `targetdir=/path/to/originals`, the result is:

```text
source/Project/Rechnung 2026.md
originals/Project/Rechnung 2026.pdf
originals/Project/Rechnung 2026_pdf2md.json
```

The `[BOWLS_DOCPREP]` bowl selects files; it does not create a `Doc_prep`
subdirectory.

## Anonymization modes

`anonymize-mode=custom` is the default and preserves the existing candidate
and reviewed-mapping workflow. `anonymize-mode=presidio` uses the locally
installed `presidio-analyzer` package to detect entities, then uses the same
reviewed mapping workflow. Presidio mode fails if the package or configured
language model is unavailable; it does not fall back to custom detection.

`anonymize_presidio_entities` is a comma-separated allow-list. Use `all` to
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

- `anonymize_ignore_dictionary=true` ignores values made entirely of configured-language dictionary words.
- `anonymize_ignore_numbers=true` ignores numeric-only values.
- `anonymize_ignore_emails=true` ignores e-mail addresses.

These filters default to `false`.

When a mapping row has `status=keep`, its `original_value` is moved to a
sibling ignore file such as `Wisniewski-anon-ignore.csv`. The ignore file has
`original_value` and `value_type` columns and prevents those values from being
added as new candidates on later runs. Approved `anon` rows retain only their
replacement, original, and type fields; source document and location metadata
is removed.

For German Presidio detection, install a German spaCy model in addition to the
Python dependency, for example:

```text
pip install -r requirements.txt
python -m spacy download de_core_news_sm
```

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
| `recursive`         | `true`                           | Process files in subdirectories; set `false` for the source root only. |

Behavior:

- Doc_prep is evaluated before all other bowl types, but only for extensions
  with a registered converter (`.pdf`). PDFs that match no `[BOWLS_DOCPREP]`
  criterion take the standard `[BOWLS]` path.
- The original PDF remains in the source tree.
- An existing Markdown file in the mirrored target skips conversion; the source
  PDF remains unchanged.
- The sidecar is written once beside the source PDF.
- A failed conversion leaves the PDF in the source directory and logs an error;
  no output is created.
- The source directory is scanned recursively and its relative directory
  structure is mirrored below `targetdir`.
- The cost confirmation of `pdf_to_markdown` is bypassed (`yes=True`);
  `max_pages` is the cost guard. Set `OPENROUTER_API_KEY` and
  `OPENROUTER_PDF_MODEL` in the environment of the process that runs
  cinderellasort.
- `anonymize=false` is the default. With `anonymize=true`, new candidates are
  added with `status=new` in the configured customer mapping CSV. Only rows
  with `status=anon` are applied. Set `status=anon` to approve a value or
  `status=keep` to explicitly preserve it.
- After normal sorting, the anonymization pass scans all existing Markdown files
  below `targetdir` that do not have an `_anon.md` output yet. With
  `anonymize_update=true`, it also revisits existing anonymized files.
- After a successful anonymization, the original Markdown file is removed and
  only `_anon.md` remains. `anonymize_update=false` preserves an existing
  `_anon.md`; set it to `true` to apply the current approved mapping again. No
  `_anon.md` is created when no approved mapping matches.
- The customer mapping CSV starts with the `status` column and uses
  `status=anon` for approved replacements, `status=keep` for values that must
  not be replaced, and `status=new` for
  proposals. Only `anon` rows are applied.
- In `nc` mode the mirrored target directory is rescanned after conversion.
- `[BOWLS_DOCPREP]` is merged from the central configuration like `[BOWLS]`;
  `[DOCPREP]` is project-specific.

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
