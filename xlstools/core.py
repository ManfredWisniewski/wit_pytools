"""Generic helpers for reading and normalising XLS/XLSX sheets.

Domain-agnostic: sheet/header detection, cell cleaning, formula
injection guard and ini-based replacement tables.

requirements: pandas, xlrd (xls), openpyxl (xlsx)
"""

import configparser
import re
from pathlib import Path

import pandas as pd

DEFAULT_PLACEHOLDER = "-"


def is_number(value):
    if not isinstance(value, str):
        return False
    return re.fullmatch(r"[+-]?\d+([.,]\d+)?", value.strip()) is not None


def clean_value(value, placeholder=DEFAULT_PLACEHOLDER):
    """NaN/empty -> placeholder, collapse whitespace, strip trailing '.0'."""
    if pd.isna(value):
        return placeholder
    text = re.sub(r"\s{2,}", " ", str(value)).strip()
    if text == "":
        return placeholder
    m = re.fullmatch(r"(-?\d+)\.0+", text)
    return m.group(1) if m else text


def clean_frame(df, placeholder=DEFAULT_PLACEHOLDER):
    """Apply clean_value to every cell of a DataFrame."""
    return df.map(lambda v: clean_value(v, placeholder))


def formula_guard(value, placeholder=DEFAULT_PLACEHOLDER):
    """Keep leading formula triggers inert in spreadsheet apps."""
    if isinstance(value, str) and value != placeholder \
            and value[:1] in ("=", "+", "-", "@"):
        if not is_number(value):
            return "'" + value
    return value


def load_replacements(ini_path, section="REPLACEMENTS"):
    """Load a key -> value mapping table from an ini section."""
    ini_path = Path(ini_path)
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str  # keep keys case-sensitive
    with ini_path.open(encoding="utf-8") as f:
        config.read_file(f)
    return dict(config.items(section))


def read_raw(xls_file, sheet):
    """Read a sheet without headers; drop all-empty columns."""
    raw = pd.read_excel(xls_file, sheet_name=sheet, header=None, dtype=object)
    return raw.dropna(axis=1, how="all")


def first_content_sheet(xls_file, skip_names=frozenset()):
    """First sheet whose name is not in skip_names (case-insensitive)."""
    skip = {n.lower() for n in skip_names}
    xls = pd.ExcelFile(xls_file)
    for name in xls.sheet_names:
        if name.strip().lower() not in skip:
            return name
    raise ValueError(f"no content sheet in {xls_file}")


def find_header_row(raw, marker, column=0, max_scan=20):
    """Locate the header row: first row whose cell equals marker."""
    for idx in range(min(max_scan, len(raw))):
        if str(raw.iloc[idx, column]).strip() == marker:
            return idx
    raise ValueError(f"header row '{marker}' not found")
