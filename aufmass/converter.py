"""KLIMAX-XLS -> CSV converter for the digital Aufmass (NC-independent).

Reads the KLIMAX export layouts and merges all source lists into one CSV
table per type: ``bauelemente.csv`` (Bauelemente/Bauteile), ``kanal.csv``
(Eckig/Formteile) and ``rohr.csv`` (Rund/Runde). List sums (Laengensummen,
Oberflaechen-/Isolierungssummen, Gesamtsummen) go into a companion
``<type>.summen.csv``.

Target format = export columns (``PosNr`` normalised to ``Pos.Nr.``,
``LV-Nummer`` ensured) + ``Raum`` + ``Verbaut``.
"""

import re
from pathlib import Path

import pandas as pd

from wit_pytools.xlstools import (
    clean_frame,
    clean_value,
    find_header_row,
    first_content_sheet,
    formula_guard,
    is_number,
    load_replacements,
    read_raw,
)

REPLACESTR = "-"
DEFAULT_INI = Path(__file__).with_name("aufmass.ini")
AUX_SHEETS = {"legende", "gesamtsummen"}
CATEGORY_ALIASES = {
    "rund": "Rohr",
    "eckig": "Kanal",
    "bauelemente": "Bauelemente",
    "bauteile": "Bauelemente",
}
SHEET_CATEGORY = {
    "runde": "Rohr",
    "formteile": "Kanal",
    "bauelemente": "Bauelemente",
}
TABLE_TYPES = ("Bauelemente", "Kanal", "Rohr")
SUM_COLUMNS = ["Raum", "Liste", "Summenart", "Bezug", "Wert", "Einheit"]
# columns where the replacement table is applied to any substring
REPLACE_ANYWHERE = ("Kbez", "Beschreibung")
# columns where only a leading abbreviation token is replaced
REPLACE_PREFIX = ("Bezeichnung",)


def category_from_filename(path):
    """Normalised list category from '<Raum> - <Kategorie>.xls' (also '_'/'Bauteile')."""
    parts = re.split(r"\s[-_]\s", Path(path).stem)
    return CATEGORY_ALIASES.get(parts[-1].strip().lower())


def _room_from_raw(raw):
    """Room label '<Ebene>.<Nr> <Name>' from the 'Projekt' row."""
    for idx in range(min(4, len(raw))):
        cells = raw.iloc[idx]
        found_label = False
        for value in cells:
            text = "" if pd.isna(value) else str(value).strip()
            if text == "Projekt":
                found_label = True
            elif found_label and text:
                # accept only '<Ebene>.…' — skips table titles in empty rows
                if re.match(r"^[A-Za-zÄÖÜäöü]+\.", text):
                    # normalise 'UG. 69 …' -> 'UG.69 …'
                    return re.sub(r"^([A-Za-zÄÖÜäöü]+\.)\s+", r"\1", text)
        if found_label:
            break
    return None


def _normalise_columns(names):
    out = []
    for name in names:
        text = str(name).strip()
        if re.fullmatch(r"(?i)pos[.\s_-]*nr\.?", text):
            text = "Pos.Nr."
        elif re.fullmatch(r"(?i)lv[.\s_-]*nummer", text):
            text = "LV-Nummer"
        out.append(text)
    return out


def _apply_replacements(df, replacements):
    for column in REPLACE_ANYWHERE:
        if column in df.columns:
            for old, new in replacements.items():
                df[column] = df[column].str.replace(old, new, regex=True)
    for column in REPLACE_PREFIX:
        if column in df.columns:
            for old, new in replacements.items():
                # only a leading abbreviation token is resolved
                df[column] = df[column].str.replace(
                    rf"^{re.escape(old)}(?=\s|$)", new, regex=True
                )
    return df


def _aggregate_round(df):
    """Rund lists: sum l1*Anz over duplicate (Kbez, d1), set Anz=1."""
    needed = ("l1", "l2", "l3", "Kbez", "d1", "Anz")
    if not all(c in df.columns for c in needed):
        return df
    df = df.copy()
    anz = pd.to_numeric(df["Anz"], errors="coerce")
    l1 = pd.to_numeric(df["l1"], errors="coerce")
    mask = (df["d1"] != REPLACESTR) & (df["d2"] == REPLACESTR) & (df["d3"] == REPLACESTR)
    df["l1"] = l1.where(~mask, l1 * anz)
    df["Anz"] = anz.where(~(mask & l1.notna()), 1)

    group_key = df["Kbez"] + "_" + df["d1"].astype(str)
    valid = df["l1"].notna()
    dup_mask = valid & group_key.duplicated(keep=False)
    singles = df[valid & ~dup_mask].copy()
    rest = df[~valid].copy()

    agg = {col: "first" for col in df.columns}
    agg["l1"] = "sum"
    grouped = (
        df[dup_mask]
        .assign(_key=group_key[dup_mask])
        .groupby("_key", as_index=False, sort=False)
        .agg(agg)
        .drop(columns="_key")
    )
    df = pd.concat([singles, grouped, rest], ignore_index=True)
    df["l1"] = df["l1"].map(clean_value)
    df["Anz"] = df["Anz"].map(clean_value)

    sort_cols = [c for c in ("d1", "d2", "d3") if c in df.columns]
    keys = {"_kbez": df["Kbez"]}
    keys.update({f"_d{i}": pd.to_numeric(df[c], errors="coerce")
                 for i, c in enumerate(sort_cols)})
    sort_keys = list(keys)
    return (df.assign(**keys)
              .sort_values(by=sort_keys, kind="mergesort")
              .drop(columns=sort_keys))


_SUM_PATTERNS = [
    ("laenge", re.compile(
        r"^Summe der Länge aller\s+(\S+)\s+mit Durchmesser\s*([\d.,]+)\s*mm\s*=\s*([\d.,]+)\s*mm")),
    ("material", re.compile(r"^Material:\s*(.+)")),
    ("oberflaeche", re.compile(r"^Oberflächensumme\s+(Kanäle|Formteile):\s*([\d.,]+)\s*m")),
    ("isolierung", re.compile(r"^Isolierung:\s*(.+)")),
    ("kante", re.compile(
        r"^Kantenlänge\s+(bis|über)\s*(\d+)\s*mm\s+([\d.,]+)\s*m")),
    ("summe_iso", re.compile(r"^Summe Isolierung\s+([\d.,]+)\s*m")),
]


def _parse_sum_line(text, isolierung):
    """Map one raw first-column line to a sums row, or None."""
    m = _SUM_PATTERNS[0][1].match(text)
    if m:
        return ("Längensumme", f"{m.group(1)} d={m.group(2)}mm", m.group(3), "mm"), isolierung
    m = _SUM_PATTERNS[1][1].match(text)
    if m:
        return ("Material", m.group(1).strip(), "-", "-"), isolierung
    m = _SUM_PATTERNS[2][1].match(text)
    if m:
        return ("Oberflächensumme", m.group(1), m.group(2), "m²"), isolierung
    m = _SUM_PATTERNS[3][1].match(text)
    if m:
        return None, m.group(1).strip()
    m = _SUM_PATTERNS[4][1].match(text)
    if m:
        bezug = f"{isolierung} / Kantenlänge {m.group(1)} {m.group(2)}mm" if isolierung \
            else f"Kantenlänge {m.group(1)} {m.group(2)}mm"
        return ("Isolierungssumme", bezug, m.group(3), "m²"), isolierung
    m = _SUM_PATTERNS[5][1].match(text)
    if m:
        bezug = f"{isolierung} / Summe" if isolierung else "Summe"
        return ("Isolierungssumme", bezug, m.group(1), "m²"), isolierung
    return None, isolierung


def _extract_gesamtsummen(xls_file, raum, liste):
    """Structured rows from the 'Gesamtsummen' sheet (Eckig layout)."""
    xls = pd.ExcelFile(xls_file)
    if not any(n.strip().lower() == "gesamtsummen" for n in xls.sheet_names):
        return []
    sheet = next(n for n in xls.sheet_names if n.strip().lower() == "gesamtsummen")
    raw = read_raw(xls_file, sheet)
    rows = []
    for _, line in raw.iterrows():
        label = clean_value(line.iloc[0])
        if not (label.startswith("Kantenlänge") or label == "Gesamtsumme"):
            continue
        for idx, part in ((1, "Kanal"), (2, "Formteil")):
            value = clean_value(line.iloc[idx]) if idx < len(line) else REPLACESTR
            if is_number(value):
                rows.append([raum, liste, "Gesamtsumme Oberfläche",
                             f"{label} / {part}", value, "m²"])
    return rows


def extract_sums(xls_file, sheet_name, header_row, raum, liste):
    """Collect sum lines from the position sheet and 'Gesamtsummen'."""
    raw = read_raw(xls_file, sheet_name)
    rows = []
    isolierung = None
    for value in raw.iloc[header_row + 1:, 0]:
        text = clean_value(value)
        if text == REPLACESTR:
            continue
        result, isolierung = _parse_sum_line(text, isolierung)
        if result:
            rows.append([raum, liste, *result])
    rows += _extract_gesamtsummen(xls_file, raum, liste)
    return pd.DataFrame(rows, columns=SUM_COLUMNS)


def parse_xls(xls_file, ini_path=DEFAULT_INI, replacements=None):
    """Parse one KLIMAX XLS into positions df, sums df and table type."""
    xls_file = Path(xls_file)
    replacements = replacements if replacements is not None \
        else load_replacements(ini_path)

    sheet = first_content_sheet(xls_file, AUX_SHEETS)
    raw = read_raw(xls_file, sheet)
    header_row = find_header_row(raw, "Anz")
    raum = _room_from_raw(raw) or re.split(r"\s[-_]\s", xls_file.stem)[0].strip()
    kategorie = category_from_filename(xls_file) \
        or SHEET_CATEGORY.get(sheet.strip().lower(), REPLACESTR)

    df = raw.iloc[header_row + 1:].copy()
    df.columns = _normalise_columns(raw.iloc[header_row])
    df = clean_frame(df)
    df = _apply_replacements(df, replacements)
    # only real positions: numeric Anz drops Summen-/Legende-/:: rows
    df = df[pd.to_numeric(df["Anz"], errors="coerce").notna()]
    df = _aggregate_round(df)

    for column in ("Pos.Nr.", "LV-Nummer"):
        if column not in df.columns:
            df[column] = REPLACESTR
    df["Raum"] = raum
    df["Verbaut"] = "0"
    df = df.map(formula_guard)

    sums = extract_sums(xls_file, sheet, header_row, raum, xls_file.stem)
    return {"df": df, "sums": sums, "kategorie": kategorie, "raum": raum}


def parse_xls_to_csv(xls_file, csv_file=None, ini_path=DEFAULT_INI,
                     replacements=None, write_sums=True):
    """Convert one KLIMAX XLS to the CSV target format (+ .summen.csv)."""
    xls_file = Path(xls_file)
    csv_file = Path(csv_file) if csv_file else xls_file.with_suffix(".csv")
    parsed = parse_xls(xls_file, ini_path, replacements)
    df, sums = parsed["df"], parsed["sums"]

    csv_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_file, index=False)

    sums_file = None
    if write_sums and not sums.empty:
        sums_file = csv_file.with_suffix(".summen.csv")
        sums.to_csv(sums_file, index=False)

    return {
        "csv": csv_file, "rows": len(df),
        "sums_csv": sums_file, "sums": len(sums),
    }


def convert_all(src_dir, out_dir=None, ini_path=DEFAULT_INI):
    """Merge every *.xls under src_dir into one table per type.

    Writes ``bauelemente.csv``, ``kanal.csv`` and ``rohr.csv`` (plus
    ``<type>.summen.csv`` where sums exist) to out_dir (default: src_dir).
    """
    src_dir = Path(src_dir)
    out_dir = Path(out_dir) if out_dir else src_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    replacements = load_replacements(ini_path)

    groups = {table_type: [] for table_type in TABLE_TYPES}
    results = []
    xls_files = sorted(
        f for f in src_dir.rglob("*.xls*") if not f.name.startswith("~$")
    )
    for xls_file in xls_files:
        try:
            parsed = parse_xls(xls_file, replacements=replacements)
            groups.setdefault(parsed["kategorie"], []).append(parsed)
        except Exception as error:
            results.append({"csv": xls_file, "error": str(error)})

    for kategorie, parsed_list in groups.items():
        if not parsed_list:
            continue
        df = pd.concat([p["df"] for p in parsed_list], ignore_index=True)
        sums = pd.concat([p["sums"] for p in parsed_list], ignore_index=True)
        csv_file = out_dir / f"{kategorie.lower()}.csv"
        df.to_csv(csv_file, index=False)
        sums_file = None
        if not sums.empty:
            sums_file = csv_file.with_suffix(".summen.csv")
            sums.to_csv(sums_file, index=False)
        results.append({
            "csv": csv_file, "rows": len(df),
            "sums_csv": sums_file, "sums": len(sums),
        })
    return results
