"""Mail tools: IMAP/Sieve/archive helpers + legacy .eml/.msg parsing.

Package layout (spec: +wit/specs/wit_pytools/mailtools):

- ``accounts``  — accounts.csv parsing, slugs, credential env lookup
- ``imap``      — read-oriented IMAP helpers (EXAMINE/BODY.PEEK)
- ``sieve``     — Sieve compile + ManageSieve client + folder ensuring
- ``render``    — merged RFC822→Markdown renderer (stdlib)
- ``archive``   — Sent drain to staging objects, delete-after-PUT, purge, init_dirs
- ``legacy``    — .eml/.msg parsing; needs ``eml_parser``/``extract-msg``

The ``legacy`` names are re-exported lazily so ``import mailtools`` and all
host-side helpers stay usable on hosts with stdlib only.
"""

from .accounts import (
    account_slug,
    account_password,
    allowed_hosts,
    check_host,
    parse_accounts,
)
from .archive import (
    archive_account,
    delete_sent,
    folder_relpath,
    init_dirs,
    message_objects,
    purge_staging,
    rule_folders,
)
from .imap import (
    connect as imap_connect,
    examine as imap_examine,
    fetch_raw,
    imap_before_date,
    list_folders,
    parse_list_names,
    search_uids,
    sent_folder,
    staging_folder,
    utf7_decode,
)
from .render import (
    decode_header_value,
    eml_to_markdown,
    mail_to_markdown,
    message_date_str,
    message_doc_id,
    message_month_str,
    message_text,
    safe_filename,
    slugify,
    strip_quoted_text,
    yaml_escape,
)
from .sieve import (
    ManageSieve,
    compile_sieve,
    ensure_folders,
)

_LAZY = {
    "parse_eml": "legacy",
    "eml_headers": "legacy",
    "eml_thread_members": "legacy",
    "eml_thread_to_markdown": "legacy",
    "parse_msg": "legacy",
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        module = importlib.import_module(f".{_LAZY[name]}", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
