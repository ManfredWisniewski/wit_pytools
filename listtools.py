# Import prepregex from sanitizers.py
from wit_pytools.sanitizers import prepregex  # noqa: F401

import csv
import os
from typing import Any, Dict, Optional, List
from datetime import datetime
from decimal import Decimal, InvalidOperation
from eliot import log_message
from wit_pytools.systools import checkfile


def read_csv_to_list(
    sourcedir: str,
    filename: str,
    settings: Optional[Dict[str, Any]] = None,
):
    """Read a CSV file into a list of rows (List[List[str]]).

    Settings keys: delimiter, encoding, has_header, strip, skip_header
    - Always returns List[List[str]]
    - If has_header is True and skip_header is True, the first row is skipped
    """
    # Validate file exists
    checkfile(sourcedir, filename)

    path = os.path.join(sourcedir, filename)
    defaults: Dict[str, Any] = {
        "delimiter": ",",
        "encoding": "utf-8",
        "has_header": True,
        "skip_header": True,
        "strip": True,
    }
    cfg = {**defaults, **(settings or {})}
    rows = []
    try:
        with open(path, mode="r", encoding=cfg["encoding"], newline="") as fh:
            reader = csv.reader(fh, delimiter=cfg["delimiter"])
            first = True
            for row in reader:
                if first and cfg["has_header"] and cfg["skip_header"]:
                    first = False
                    continue
                first = False
                if cfg["strip"]:
                    row = [c.strip() if isinstance(c, str) else c for c in row]
                rows.append(row)
        log_message(
            f"read_csv_to_list: loaded {len(rows)} rows from '{path}'",
            level="INFO",
        )
        return rows
    except Exception as e:
        log_message(f"read_csv_to_list: error reading '{path}': {e}", level="ERROR")
        raise


def _parse_amount(value: Optional[str], decimal_sep: Optional[str], thousands_sep: Optional[str]) -> Optional[Decimal]:
    """Parse a monetary string to Decimal based on separators."""
    if value is None:
        return None
    s = str(value).strip()
    if thousands_sep:
        s = s.replace(thousands_sep, "")
    if decimal_sep and decimal_sep != ".":
        s = s.replace(decimal_sep, ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _format_date(value: Optional[str], in_fmt: Optional[str], out_fmt: Optional[str]) -> Optional[str]:
    """Convert date string from in_fmt to out_fmt."""
    if not value:
        return None
    if not in_fmt:
        return value
    try:
        dt = datetime.strptime(value.strip(), in_fmt)
        if out_fmt:
            return dt.strftime(out_fmt)
        return value
    except ValueError:
        return None


def format_finance_rows(rows: List[Any], preset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform rows using formatting rules defined in the preset."""
    out: List[Dict[str, Any]] = []
    field_map = preset.get("field_map") or {}
    # Use the preset's date_format for both parsing and output formatting
    date_in_fmt: Optional[str] = preset.get("date_format")
    date_out_fmt: Optional[str] = date_in_fmt
    date_field_fallback: Optional[str] = preset.get("date_field")
    amount_field_fallback: Optional[str] = preset.get("amount_field")
    date_field_index_fallback: Optional[int] = preset.get("date_field_index")
    amount_field_index_fallback: Optional[int] = preset.get("amount_field_index")
    dec_sep: Optional[str] = preset.get("decimal_separator")
    thou_sep: Optional[str] = preset.get("thousands_separator")
    currency: Optional[str] = preset.get("currency")

    for r in rows:
        if field_map:
            new_row: Dict[str, Any] = {}
            for out_key, in_key in field_map.items():
                # Support mapping by column name (dict rows) or index (list rows)
                if isinstance(in_key, int):
                    val = r[in_key] if isinstance(r, list) and in_key < len(r) else None
                else:
                    val = r.get(in_key) if isinstance(r, dict) else None
                if out_key.lower() in {"date", "booking_date", "transaction_date"}:
                    val = _format_date(str(val) if val is not None else None, date_in_fmt, date_out_fmt)
                elif out_key.lower() in {"amount", "value", "sum", "credit", "debit"}:
                    val = _parse_amount(str(val) if val is not None else None, dec_sep, thou_sep)
                new_row[out_key] = val
        else:
            # Pass-through then normalize optional known fields
            new_row = dict(r) if isinstance(r, dict) else {str(i): v for i, v in enumerate(r)}
            if isinstance(r, dict) and date_field_fallback and date_field_fallback in r:
                new_row[date_field_fallback] = _format_date(str(r.get(date_field_fallback)), date_in_fmt, date_out_fmt)
            if isinstance(r, dict) and amount_field_fallback and amount_field_fallback in r:
                new_row[amount_field_fallback] = _parse_amount(str(r.get(amount_field_fallback)), dec_sep, thou_sep)
            if isinstance(r, list) and date_field_index_fallback is not None and date_field_index_fallback < len(r):
                new_row[str(date_field_index_fallback)] = _format_date(str(r[date_field_index_fallback]), date_in_fmt, date_out_fmt)
            if isinstance(r, list) and amount_field_index_fallback is not None and amount_field_index_fallback < len(r):
                new_row[str(amount_field_index_fallback)] = _parse_amount(str(r[amount_field_index_fallback]), dec_sep, thou_sep)
        if currency and "currency" not in new_row:
            new_row["currency"] = currency
        out.append(new_row)

    return out