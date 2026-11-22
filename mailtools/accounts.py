"""Per-account mail configuration: accounts.csv parsing and credential lookup.

All paths come from the caller — the library never resolves repository
layout or loads ``.env`` itself (callers export the variables first).
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path


def account_slug(account: str) -> str:
    """`ec@witconsult.de` -> `ec-witconsult-de`."""
    return re.sub(r"[^a-z0-9]+", "-", account.lower()).strip("-")


def parse_accounts(path: Path) -> list[dict]:
    """Parse an accounts.csv -> account dicts.

    Columns: ``account,host,port,script,rules,prefix`` — only ``account``,
    ``host`` and ``rules`` are required; ``port`` defaults to 4190, ``script``
    to ``mail-sort``, ``prefix`` defaults to ``INBOX.`` when the column is
    absent, while an empty value or ``-`` means no prefix (top-level folders,
    e.g. Stalwart). ``#`` lines are comments.
    """
    accounts = []
    header = None
    for i, row in enumerate(csv.reader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"))), 1):
        row = [c.strip() for c in row]
        if not row or not row[0] or row[0].startswith("#"):
            continue
        if header is None and row[0].lower() == "account":
            header = [c.lower() for c in row]
            continue
        if header is None:
            raise ValueError(f"{Path(path).name}:{i}: expected header 'account,host,port,script,rules,prefix'")
        a = dict(zip(header, row))
        if any("\r" in c or "\n" in c for c in row):
            raise ValueError(f"{Path(path).name}:{i}: CR/LF inside a cell is not allowed")
        for col in ("account", "host", "rules"):
            if not a.get(col):
                raise ValueError(f"{Path(path).name}:{i}: missing '{col}'")
        a["port"] = int(a.get("port") or 4190)
        a["script"] = a.get("script") or "mail-sort"
        p = a.get("prefix")
        a["prefix"] = "INBOX." if p is None else ("" if p in ("", "-") else p)
        a["slug"] = account_slug(a["account"])
        accounts.append(a)
    return accounts


def account_password(acct: dict, env_prefix: str = "SIEVE_PASSWORD") -> str | None:
    """Per-account password from env ``<PREFIX>_<ACCOUNT-SLUG>`` then ``<PREFIX>``."""
    env_key = env_prefix + "_" + re.sub(r"[^A-Z0-9]", "_", acct["account"].upper())
    return os.environ.get(env_key) or os.environ.get(env_prefix)


def allowed_hosts(env_var: str = "SIEVE_HOST") -> set[str]:
    """Hosts allowed to receive mailbox credentials — comma-separated list."""
    return {h.strip().lower() for h in os.environ.get(env_var, "").split(",") if h.strip()}


def check_host(acct: dict, env_var: str = "SIEVE_HOST") -> None:
    """Refuse to send mailbox credentials to a host not pinned in the allowlist."""
    allowed = allowed_hosts(env_var)
    if not allowed:
        raise RuntimeError(f"{env_var} is not set — pin the mail host(s) in .env before connecting")
    if acct["host"].lower() not in allowed:
        raise RuntimeError(f"{acct['account']}: host {acct['host']!r} is not in {env_var} — refusing to connect")
