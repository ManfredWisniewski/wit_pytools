# Intent: `mailtools`

## Package purpose

`mailtools` provides modular Python functions for interacting with e-mail servers

The general goal of this package is to interact with E-Mail servers, starting with imap. 
goals:
- read the list of emails in the current folder of an imap account.
- classify the emails using the JEV AI
- move emails to folders corresponding to their classification
- create a set of sieve rules to automate that process

## Package layout (implemented — spec: `+wit/specs/wit_pytools/mailtools`)

| Module | Contents | Deps |
|---|---|---|
| `accounts.py` | `parse_accounts`, `account_slug`, `account_password`, `allowed_hosts`, `check_host` | stdlib |
| `imap.py` | `connect`, `examine`, `search_uids`, `fetch_raw`, `list_folders`, `parse_list_names`, `utf7_decode`, `staging_folder`, `sent_folder`, `imap_before_date`, `hierarchy_sep` | stdlib |
| `sieve.py` | `compile_sieve`, `ManageSieve`, `ensure_folders` | stdlib |
| `render.py` | `mail_to_markdown` (merged renderer), `eml_to_markdown`, `strip_quoted_text`, `slugify`, header/date/attachment helpers | stdlib |
| `archive.py` | `archive_account` (Sent drain), `delete_sent`, `purge_staging`, `init_dirs`, `rule_folders`, `folder_relpath` | stdlib |
| `legacy.py` | `parse_eml`, `eml_headers`, `eml_thread_members`, `eml_thread_to_markdown`, `parse_msg` | `eml_parser`, `extract-msg` |

`legacy` names are re-exported lazily via `__init__.__getattr__` — importing
`mailtools` never pulls the optional third-party packages, so host-side
tools (which must be stdlib-only, iac-n8n D09) work unmodified.
Git helpers live outside the package in top-level `wit_pytools/gittools.py`.
