import os
from pathlib import Path

import pandas as pd
import pytest

from wit_pytools.aufmass import (
    DEFAULT_INI,
    REPLACESTR,
    category_from_filename,
    convert_all,
    parse_xls_to_csv,
)
from wit_pytools.xlstools import load_replacements


AUFMASS_DATA = Path(os.environ.get("AUFMASS_DATA", r"P:\tmp\aufmass-data"))
DATA_OK = AUFMASS_DATA.is_dir()
needs_data = pytest.mark.skipif(
    not DATA_OK, reason="external sample data not available")


def _write_sheet(path, rows, sheet="Runde", extra_sheets=None):
    """Write a raw (header=None) xlsx fixture."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(
            writer, sheet_name=sheet, header=False, index=False)
        for name, extra in (extra_sheets or {}).items():
            pd.DataFrame(extra).to_excel(
                writer, sheet_name=name, header=False, index=False)


def _rund_fixture(path):
    rows = [
        ["Projekt", "", "UG.99 Testraum"],
        ["", "", ""],
        ["Formteile mit rundem Querschnitt", "", ""],
        ["", "", ""],
        ["", "", ""],
        ["Anz", "Kbez", "Pos.Nr.", "d1", "d2", "d3",
         "l1", "l2", "l3", "l4", "e", "r", "alpha(°)"],
        [2, "BGE", "", 125, "", "", "", 40, "", "", "", 125, 90],
        ["Summe der Länge aller     BGE    mit Durchmesser      125mm =        0mm"],
        ["::"],
        [1, "WFR", "", 125, "", "", 100, 40, "", "", "", "", ""],
        [1, "WFR", "", 125, "", "", 300, 40, "", "", "", "", ""],
        ["Summe der Länge aller     WFR    mit Durchmesser      125mm =      400mm"],
        ["::"],
    ]
    _write_sheet(path, rows)


def test_load_replacements():
    replacements = load_replacements(DEFAULT_INI)
    assert replacements["WFR"] == "Wickelfalzrohr"
    assert len(replacements) > 50
    assert "L" not in replacements  # commented out in the ini


def test_category_from_filename():
    assert category_from_filename("UG.00A Flur - Bauteile.xls") == "Bauelemente"
    assert category_from_filename("UG.66 X _ Bauelemente.xls") == "Bauelemente"
    assert category_from_filename("a - Rund.xls") == "Rohr"
    assert category_from_filename("a - Eckig.xls") == "Kanal"
    assert category_from_filename("x.xls") is None


def test_rund_conversion(tmp_path):
    src = tmp_path / "UG.99 Testraum - Rund.xlsx"
    _rund_fixture(src)
    result = parse_xls_to_csv(src)
    assert result["rows"] == 2
    assert result["sums"] == 2

    df = pd.read_csv(result["csv"], dtype=str)
    assert set(["Pos.Nr.", "LV-Nummer", "Raum", "Verbaut"]
               ) <= set(df.columns)
    assert "Kategorie" not in df.columns
    assert df["Raum"].iloc[0] == "UG.99 Testraum"
    assert (df["Verbaut"] == "0").all()
    # WFR duplicate (Kbez+d1) aggregated: l1 = 100+300, Anz = 1
    wfr = df[df["Kbez"] == "Wickelfalzrohr"]
    assert len(wfr) == 1
    assert wfr["l1"].iloc[0] == "400"
    assert wfr["Anz"].iloc[0] == "1"
    bge = df[df["Kbez"] == "Bogen glatt"]
    assert bge["Anz"].iloc[0] == "2"
    # sum rows and '::' separators never become positions
    assert not df["Anz"].str.contains("Summe").any()

    sums = pd.read_csv(result["sums_csv"], dtype=str)
    wfr_sum = sums[sums["Bezug"].str.contains("WFR")]
    assert wfr_sum["Wert"].iloc[0] == "400"
    assert wfr_sum["Einheit"].iloc[0] == "mm"


def test_missing_number_columns_filled(tmp_path):
    src = tmp_path / "UG.99 Testraum - Rund.xlsx"
    _rund_fixture(src)
    result = parse_xls_to_csv(src)
    df = pd.read_csv(result["csv"], dtype=str)
    assert (df["Pos.Nr."] == REPLACESTR).all()
    assert (df["LV-Nummer"] == REPLACESTR).all()


def test_bauelemente_layout(tmp_path):
    src = tmp_path / "r - Bauteile.xlsx"
    rows = [
        ["Projekt", "", "EG.01 Bad"],
        ["Bauelemente"],
        ["Anz", "Bezeichnung", "Pos.Nr.", "Nennweite", "a", "b"],
        [1, "BSK Typ X", "", "", 400, 200],
    ]
    _write_sheet(src, rows, sheet="Bauelemente")
    result = parse_xls_to_csv(src)
    df = pd.read_csv(result["csv"], dtype=str)
    assert result["rows"] == 1
    assert df["Bezeichnung"].iloc[0].startswith("Brandschutzklappe")
    assert "Kategorie" not in df.columns


@needs_data
def test_all_ug_files_convert(tmp_path):
    """SC-007: all source lists merge into one table per type."""
    results = convert_all(AUFMASS_DATA, tmp_path)
    errors = [r for r in results if "error" in r]
    assert not errors, errors
    names = {r["csv"].name for r in results if "csv" in r}
    assert names == {"bauelemente.csv", "kanal.csv", "rohr.csv"}
    assert sum(r["rows"] for r in results) > 0


@needs_data
def test_optional_categories_and_bauteile(tmp_path):
    """Missing types and the 'Bauteile' naming variant are tolerated."""
    results = convert_all(AUFMASS_DATA, tmp_path)
    raeume = set()
    for r in results:
        if "csv" not in r:
            continue
        df = pd.read_csv(r["csv"], dtype=str)
        assert "Kategorie" not in df.columns
        raeume |= set(df["Raum"])
    assert len(raeume) == 27
    # Bauteile rooms (e.g. UG.00A Flur) are merged into bauelemente.csv
    df = pd.read_csv(tmp_path / "bauelemente.csv", dtype=str)
    assert "UG.00A Flur" in set(df["Raum"])
    assert (tmp_path / "kanal.csv").is_file()
    assert len(df) > 0


@needs_data
def test_known_sum_values(tmp_path):
    """Aggregated l1 matches the exported 'Summe der Länge' (4740mm)."""
    src = AUFMASS_DATA / "UG" / "UG.50 Antriebsraum" / "UG.50 Antriebsraum - Rund.xls"
    result = parse_xls_to_csv(src, tmp_path / "rund.csv")
    df = pd.read_csv(result["csv"], dtype=str)
    wfr = df[df["Kbez"] == "Wickelfalzrohr"]
    assert wfr["l1"].iloc[0] == "4740"
    sums = pd.read_csv(result["sums_csv"], dtype=str)
    wfr_sum = sums[sums["Bezug"].str.contains("WFR")]
    assert wfr_sum["Wert"].iloc[0] == "4740"


@needs_data
def test_detail_layout_keeps_lv_nummer(tmp_path):
    """test.xls detail layout: LV-Nummer and Fabrikat/Bez. pass through."""
    src = Path(__file__).parent / "aufmass" / "test.xls"
    if not src.is_file():
        pytest.skip("test.xls fixture missing")
    result = parse_xls_to_csv(src, tmp_path / "detail.csv")
    df = pd.read_csv(result["csv"], dtype=str)
    assert "LV-Nummer" in df.columns
    assert (df["LV-Nummer"] != REPLACESTR).any()
    assert df["LV-Nummer"].str.contains(r"2\.12\.70").any()
