import os
import shutil
import sys
from configparser import ConfigParser
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.cinderellasort import bowldir, cinderellasort

TEST_PDF = Path(__file__).parent / "documenttools" / "testdocument.pdf"


def test_bowldir_checks_document_content(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config.add_section("BOWLS")
    config.set("BOWLS", "Rechnungen", "manfred@mustermann.de")
    config.set("BOWLS", "Fallback", "!DEFAULT")

    pdf_path = tmp_path / "testdocument.pdf"
    shutil.copy(TEST_PDF, pdf_path)

    result = bowldir("testdocument.pdf", config, file_path=pdf_path, check_content=True)

    assert result == "/Rechnungen"


def test_cinderellasort_moves_pdf_based_on_content(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    pdf_path = source_dir / "testdocument.pdf"
    shutil.copy(TEST_PDF, pdf_path)

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ".pdf",
        "ftype_delete": ".tmp",
    }
    config["SETTINGS"] = {
        "overwrite": "false",
        "jpg_quality": "85",
        "gps_moved_unmatched": "false",
        "gps_compress": "false",
        "set_tags": "false",
        "usedirectoryname": "false",
        "skipunmatched": "true",
        "check_content": "true",
    }
    config["BOWLS"] = {
        "Rechnungen": "manfred@mustermann.de",
        "Default": "!DEFAULT",
    }

    config_path = tmp_path / "config.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)

    cinderellasort(str(config_path), dryrun=False)

    expected_path = target_dir / "Rechnungen" / "testdocument.pdf"
    assert expected_path.exists()
