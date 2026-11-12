import pandas as pd
import pytest

from wit_pytools.xlstools import (
    clean_value,
    find_header_row,
    first_content_sheet,
    formula_guard,
    is_number,
)


def test_clean_value():
    assert clean_value(None) == "-"
    assert clean_value("  a  b   c ") == "a b c"
    assert clean_value("4.0") == "4"
    assert clean_value("2.65") == "2.65"
    assert clean_value(-1.5) == "-1.5"


def test_is_number():
    assert is_number("125")
    assert is_number("2.70")
    assert not is_number("-")
    assert not is_number("51UGER0014")


def test_formula_guard():
    assert formula_guard("=SUM(1)") == "'=SUM(1)"
    assert formula_guard("-") == "-"  # placeholder stays
    assert formula_guard("-20") == "-20"  # numbers stay
    assert formula_guard("+foo") == "'+foo"


def test_find_header_row():
    raw = pd.DataFrame([["x"], ["Anz"], ["1"]])
    assert find_header_row(raw, "Anz") == 1
    with pytest.raises(ValueError):
        find_header_row(pd.DataFrame([["x"]]), "Anz")


def test_first_content_sheet(tmp_path):
    path = tmp_path / "f.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([[1]]).to_excel(
            writer, sheet_name="Legende", header=False, index=False)
        pd.DataFrame([[2]]).to_excel(
            writer, sheet_name="Runde", header=False, index=False)
    assert first_content_sheet(path, {"legende"}) == "Runde"
    with pytest.raises(ValueError):
        first_content_sheet(path, {"legende", "runde"})
