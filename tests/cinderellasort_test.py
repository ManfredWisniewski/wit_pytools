#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import sys
import pytest
import tempfile
import shutil
from configparser import ConfigParser
from pathlib import Path

# Add parent directory to path so we can import wit_pytools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.cinderellasort import cleanfilename, bowldir_gps, handlefile, cinderellasort, bowldir
from wit_pytools.imgtools import img_getgps

def test_basic_cleaning():
    # Test basic filename cleaning
    result = cleanfilename("test.txt", "", "", {})
    assert result == "test.txt"

def test_clean_with_arabic_numerals():
    # Test conversion of Arabic numerals with default convert_numbers=True
    result = cleanfilename("test١٢٣.txt", "", "", {})
    assert result == "test123.txt"
    
    # Test with convert_numbers=False
    result = cleanfilename("test١٢٣.txt", "", "", {}, convert_numbers=False)
    assert result == "test١٢٣.txt"

def test_clean_with_replacements():
    # Test with replacement strings
    replacements = {"test": "demo", "old": "new"}
    result = cleanfilename("test_old.txt", "", "", replacements)
    assert result == "demo_new.txt"

def test_clean_with_case_sensitive():
    # Test case-sensitive cleaning
    result = cleanfilename("testABCtest.txt", "ABC", "", {})
    assert result == "testtest.txt"

def test_clean_with_case_insensitive():
    # Test case-insensitive cleaning
    result = cleanfilename("testABCtest.txt", "", "abc", {})
    assert result == "testtest.txt"

def test_clean_with_invalid_chars():
    # Test cleaning invalid filename characters
    result = cleanfilename("test<>:\"/\\|?*.txt", "", "", {})
    assert result == "test.txt"


def test_directory_name_cleaning_collapses_whitespace(tmp_path, monkeypatch):
    config = ConfigParser()
    config.optionxform = str
    config.add_section("BOWLS")
    config.set("BOWLS", "Destination", "!DEFAULT")
    config.add_section("SETTINGS")
    config.set("SETTINGS", "usedirectoryname", "true")

    captured = {}

    def fake_movefile(sourcedir, file, destdir, nfile, filemode, overwrite=False, dryrun=False):
        captured["nfile"] = nfile
        captured["destdir"] = destdir

    monkeypatch.setattr("wit_pytools.cinderellasort.movefile", fake_movefile)

    source_dir = tmp_path / "Foo Bar Baz"
    source_dir.mkdir()
    file_path = source_dir / "sample.txt"
    file_path.write_text("data")

    handlefile(
        file_path,
        str(source_dir),
        str(tmp_path / "dest"),
        ".txt",
        "Bar",
        "NOTdefined",
        config,
        "win",
        {},
        dryrun=False,
        overwrite=False,
        jpg_quality=85,
        gps_moved_unmatched=False,
        gps_compress=False,
        use_directory_name=True,
        dir_file_count=1,
        dirname="Foo Bar Baz",
        skip_unmatched=True,
    )

    assert captured["nfile"] == "Foo Baz.txt"

def test_clean_with_subdirectory():
    # Test with subdirectory
    result = cleanfilename("test.txt", "", "", {}, subdir="subdir١٢٣")
    assert result == "subdir123.txt"

def test_clean_with_empty_input():
    # Test with empty input
    result = cleanfilename("", "", "", {})
    assert result == ""


def test_recursive_false_processes_only_source_root(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    nested = source_dir / "nested"
    nested.mkdir(parents=True)
    target_dir.mkdir()
    (source_dir / "root.txt").write_text("root")
    (nested / "nested.txt").write_text("nested")

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir), "targetdir": str(target_dir),
        "ftype_sort": ".txt", "filemode": "win",
    }
    config["SETTINGS"] = {"recursive": "false", "skipunmatched": "false"}
    config["BOWLS"] = {".": "."}
    config_path = tmp_path / "nonrecursive.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "root.txt").is_file()
    assert (nested / "nested.txt").is_file()


def _write_path_safety_config(tmp_path, source_dir, target_dir, settings=None):
    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ".txt",
        "filemode": "win",
    }
    config["SETTINGS"] = settings or {}
    config_path = tmp_path / "path-safety.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)
    return config_path


def test_same_source_and_target_directory_fails(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "sample.txt"
    source_file.write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(tmp_path, source_dir, source_dir)

    with pytest.raises(ValueError, match="must not be the same directory"):
        cinderellasort(str(config_path), dryrun=False)

    assert source_file.is_file()


def test_target_inside_source_directory_fails(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = source_dir / "target"
    target_dir.mkdir(parents=True)
    source_file = source_dir / "sample.txt"
    source_file.write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(tmp_path, source_dir, target_dir)

    with pytest.raises(ValueError, match="must not be inside sourcedir"):
        cinderellasort(str(config_path), dryrun=False)

    assert source_file.is_file()


def test_clear_empty_directories_defaults_true_for_standard_bowls(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    empty_dir = source_dir / "empty"
    empty_dir.mkdir(parents=True)
    target_dir.mkdir()
    (source_dir / "sample.txt").write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(tmp_path, source_dir, target_dir)

    cinderellasort(str(config_path), dryrun=False)

    assert not empty_dir.exists()


def test_clear_empty_directories_false_keeps_standard_directories(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    empty_dir = source_dir / "empty"
    empty_dir.mkdir(parents=True)
    target_dir.mkdir()
    (source_dir / "sample.txt").write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(
        tmp_path,
        source_dir,
        target_dir,
        settings={"clear-empty-directories": "false"},
    )

    cinderellasort(str(config_path), dryrun=False)

    assert empty_dir.is_dir()


def test_clear_empty_directories_keeps_non_empty_directories(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    empty_dir = source_dir / "empty"
    non_empty_dir = source_dir / "non-empty"
    empty_dir.mkdir(parents=True)
    non_empty_dir.mkdir()
    (non_empty_dir / "sample.bin").write_text("unmatched", encoding="utf-8")
    target_dir.mkdir()
    (source_dir / "sample.txt").write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(tmp_path, source_dir, target_dir)

    cinderellasort(str(config_path), dryrun=False)

    assert not empty_dir.exists()
    assert (non_empty_dir / "sample.bin").is_file()


def test_clear_empty_directories_dryrun_keeps_empty_directories(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    empty_dir = source_dir / "empty"
    empty_dir.mkdir(parents=True)
    target_dir.mkdir()
    (source_dir / "sample.txt").write_text("data", encoding="utf-8")
    config_path = _write_path_safety_config(
        tmp_path,
        source_dir,
        target_dir,
        settings={"clear-empty-directories": "true"},
    )

    cinderellasort(str(config_path), dryrun=True)

    assert empty_dir.is_dir()


def test_ftype_delete_applies_in_nested_directories(tmp_path):
    sourcedir = tmp_path / "source"
    sourcedir.mkdir()
    nested = sourcedir / "nested"
    nested.mkdir()
    targetdir = tmp_path / "target"
    targetdir.mkdir()

    (sourcedir / "valid.keep").write_text("keep")
    delete_path = nested / "remove.tmp"
    delete_path.write_text("delete")

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(sourcedir),
        "targetdir": str(targetdir),
        "ftype_sort": ".keep",
        "ftype_delete": ".tmp",
    }
    config["SETTINGS"] = {}

    config_path = tmp_path / "config.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)

    cinderellasort(str(config_path), dryrun=False)

    assert not delete_path.exists()


def test_ftype_delete_is_case_insensitive(tmp_path):
    sourcedir = tmp_path / "source"
    sourcedir.mkdir()
    nested = sourcedir / "nested"
    nested.mkdir()
    targetdir = tmp_path / "target"
    targetdir.mkdir()

    (sourcedir / "valid.keep").write_text("keep")
    delete_path = nested / "example.PNG"
    delete_path.write_text("delete")

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(sourcedir),
        "targetdir": str(targetdir),
        "ftype_sort": ".keep",
        "ftype_delete": ".png",
    }
    config["SETTINGS"] = {}

    config_path = tmp_path / "config.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)

    cinderellasort(str(config_path), dryrun=False)

    assert not delete_path.exists()


def test_clean_with_multiple_extensions():
    # Test with multiple extensions
    result = cleanfilename("test.tar.gz", "", "", {})
    assert result == "test.tar.gz"

def test_clean_with_all_features():
    # Test combining multiple cleaning features
    replacements = {"test": "demo"}
    result = cleanfilename("test<>:\"/\\|?*١٢٣ABC.txt", "ABC", "", replacements)
    assert result == "demo123.txt"

def test_clean_collapses_whitespace():
    result = cleanfilename("   Foo   Bar   .txt", "", "", {})
    assert result == "Foo Bar.txt"

def test_gpsbowl_functionality():
    """Test the GPSBOWL functionality with the cronmode option"""
    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup test directories
        source_dir = os.path.join(temp_dir, 'source')
        target_dir = os.path.join(temp_dir, 'target')
        os.makedirs(source_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(os.path.join(target_dir, 'TestBowl'), exist_ok=True)
        os.makedirs(os.path.join(target_dir, 'DefaultBowl'), exist_ok=True)
        
        # Copy test images to the source directory
        test_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'imgtools')
        shutil.copy(os.path.join(test_img_dir, 'testimage.jpg'), os.path.join(source_dir, 'testimage.jpg'))
        shutil.copy(os.path.join(test_img_dir, 'testimage_0gps.jpg'), os.path.join(source_dir, 'testimage_0gps.jpg'))
        shutil.copy(os.path.join(test_img_dir, 'testimage_noexif.jpg'), os.path.join(source_dir, 'testimage_noexif.jpg'))
        
        # Create a config file for the test
        config = ConfigParser()
        config.optionxform = str  # Preserve case for keys
        
        # Add sections and options
        config.add_section('TABLE')
        config['TABLE']['sourcedir'] = source_dir
        config['TABLE']['targetdir'] = target_dir
        config['TABLE']['ftype_sort'] = '.jpg,.jpeg'
        config['TABLE']['filemode'] = 'win'
        
        config.add_section('SETTINGS')
        config['SETTINGS']['overwrite'] = 'false'
        config['SETTINGS']['jpg_quality'] = '85'
        config['SETTINGS']['gps_moved_unmatched'] = 'true'
        config['SETTINGS']['gps_compress'] = 'false'
        
        config.add_section('BOWLS_GPS')
        # Get the GPS coordinates from the test image
        image_coords = img_getgps(test_img_dir, 'testimage.jpg')
        assert image_coords is not None, "Test image should have GPS coordinates"
        
        # Create a bowl that matches the test image coordinates (within 5km)
        lat, lon = image_coords
        config['BOWLS_GPS']['TestBowl;5'] = f"{lat},{lon}"
        
        # Create a default bowl for images without GPS data
        config['BOWLS_GPS']['DefaultBowl'] = "!DEFAULT"
        
        # Write the config to a file
        config_path = os.path.join(temp_dir, 'gps-sort-ini.txt')
        with open(config_path, 'w') as configfile:
            config.write(configfile)
        
        # Test the bowldir_gps function directly
        # Test with image that has GPS data
        bowl = bowldir_gps('testimage.jpg', config, image_coords)
        assert bowl == '/TestBowl', f"Expected /TestBowl but got {bowl}"
        
        # Test with image that has no GPS data
        bowl = bowldir_gps('testimage_noexif.jpg', config, None)
        # When image_coords is None, bowldir_gps returns empty string, so we'll handle this in the test
        # In the actual cinderellasort function, files with no GPS are handled separately
        assert bowl == '' or bowl == '/DefaultBowl', f"Expected empty string or /DefaultBowl but got {bowl}"
        
        # Test with image that has zero GPS data
        bowl = bowldir_gps('testimage_0gps.jpg', config, (0, 0))
        assert bowl == '/DefaultBowl', f"Expected /DefaultBowl but got {bowl}"
        
        # Now test the full cinderellasort functionality
        from wit_pytools.cinderellasort import cinderellasort
        
        # Run cinderellasort with the config file
        cinderellasort(config_path, filemode='win', dryrun=False)
        
        # Check that the images were sorted correctly
        # testimage.jpg should be in the TestBowl directory
        assert os.path.exists(os.path.join(target_dir, 'TestBowl', 'testimage.jpg')), \
            "testimage.jpg should be in the TestBowl directory"
            
        # testimage_noexif.jpg should be renamed with _nogps and stay in source directory
        assert os.path.exists(os.path.join(source_dir, 'testimage_noexif_nogps.jpg')), \
            "testimage_noexif.jpg should be renamed with _nogps and stay in source directory"
            
        # testimage_0gps.jpg should be renamed with _nogps and stay in source directory
        assert os.path.exists(os.path.join(source_dir, 'testimage_0gps_nogps.jpg')), \
            "testimage_0gps.jpg should be renamed with _nogps and stay in source directory"


def test_trash_nocase_removes_sample_files(tmp_path):
    source_dir = tmp_path / 'source'
    target_dir = tmp_path / 'target'
    source_dir.mkdir()
    target_dir.mkdir()

    sample_files = ['Sample.mkv', 'Sample#2.mkv', 'sample_lower.mkv']
    keep_file = 'KeepThis.mkv'

    for filename in sample_files + [keep_file]:
        (source_dir / filename).write_text('dummy')

    config = ConfigParser()
    config.optionxform = str
    config.add_section('TABLE')
    config['TABLE']['sourcedir'] = str(source_dir)
    config['TABLE']['targetdir'] = str(target_dir)
    config['TABLE']['ftype_sort'] = '.mkv'
    config['TABLE']['ftype_delete'] = 'notdefined'
    config['TABLE']['clean'] = ''
    config['TABLE']['clean_nocase'] = ''
    config['TABLE']['trash'] = 'notdefined'
    config['TABLE']['trash_nocase'] = 'sample'
    config['TABLE']['filemode'] = 'win'

    config.add_section('SETTINGS')
    config['SETTINGS']['overwrite'] = 'false'
    config['SETTINGS']['jpg_quality'] = '85'
    config['SETTINGS']['gps_moved_unmatched'] = 'false'
    config['SETTINGS']['gps_compress'] = 'false'
    config['SETTINGS']['set_tags'] = 'false'
    config['SETTINGS']['usedirectoryname'] = 'false'
    config['SETTINGS']['skipunmatched'] = 'true'

    config_path = tmp_path / 'trash-sort.ini'
    with config_path.open('w') as configfile:
        config.write(configfile)

    from wit_pytools.cinderellasort import cinderellasort

    cinderellasort(str(config_path), dryrun=False)

    for filename in sample_files:
        assert not (source_dir / filename).exists(), f"Expected {filename} to be deleted"

    assert (source_dir / keep_file).exists(), "Non-matching files should remain"


# --- Doc_prep bowls --------------------------------------------------------

import wit_pytools.cinderellasort as cs

TEST_PDF = os.path.join(os.path.dirname(__file__), "documenttools", "testdocument.pdf")


def _docprep_setup(
    tmp_path,
    *,
    docprep_section=None,
    bowls=None,
    pdf_name="Rechnung 2026.pdf",
    settings_section=None,
    anonymize_bowls=None,
    anonymize_section=None,
):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / pdf_name
    source_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEST_PDF, source_file)

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ".pdf",
        "filemode": "win",
    }
    config["SETTINGS"] = {"overwrite": "false", **(settings_section or {})}
    config["BOWLS_DOCPREP"] = {"Rechnungen": "Rechnung,Invoice"}
    if bowls:
        config["BOWLS"] = bowls
    if docprep_section is not None:
        config["DOCPREP"] = docprep_section
    if anonymize_bowls:
        config["BOWLS_ANONYMIZE"] = anonymize_bowls
    if anonymize_section is not None:
        config["ANONYMIZE"] = anonymize_section
    config_path = tmp_path / "docprep.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)
    return source_dir, target_dir, config_path


def _fake_converter(calls, fail=False):
    def convert(source, output_path, settings):
        calls.append({"source": source, "output": output_path, "settings": settings})
        if fail:
            raise RuntimeError("model unavailable")
        output_path.write_text("# converted", encoding="utf-8")
        return output_path
    return convert


def test_mirrored_target_dir_does_not_duplicate_root():
    relative_parent = Path("DOCDIR") / "files"

    assert cs._mirrored_target_dir(
        Path("target") / "DOCDIR",
        relative_parent,
    ) == Path("target") / "DOCDIR" / "files"


def test_docprep_converts_beside_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path, docprep_section={"language": "de", "model": "test/model"}
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "Rechnung 2026.pdf").is_file()
    assert (source_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "# converted"
    assert not (target_dir / "Rechnung 2026.md").exists()
    assert calls[0]["settings"]["model"] == "test/model"
    assert calls[0]["settings"]["language"] == "de"
    assert calls[0]["settings"]["max_pages"] == 50


def test_docprep_failure_leaves_pdf_in_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter([], fail=True)))

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "Rechnung 2026.pdf").is_file()
    assert not (target_dir / "Rechnung 2026.pdf").exists()
    assert not list(source_dir.glob("*.md"))


def test_docprep_existing_markup_moves_to_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    (target_dir / "Rechnung 2026.md").write_text("existing", encoding="utf-8")
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (source_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "existing"
    assert not (target_dir / "Rechnung 2026.md").exists()
    assert (source_dir / "Rechnung 2026.pdf").is_file()


def test_docprep_max_pages_skips_large_documents(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path, docprep_section={"max_pages": "1"})
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (source_dir / "Rechnung 2026.pdf").is_file()


def test_docprep_non_matching_pdf_uses_standard_bowls(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path, bowls={"Sonstiges": "Bericht"}, pdf_name="Bericht.pdf"
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (target_dir / "Sonstiges" / "Bericht.pdf").is_file()


def test_docprep_moves_stray_target_markdown_to_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    target_file = target_dir / "Rechnung 2026.md"
    target_file.write_text("existing", encoding="utf-8")
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (source_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "existing"
    assert not target_file.exists()
    assert (source_dir / "Rechnung 2026.pdf").is_file()


def test_docprep_writes_markup_beside_nested_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path, pdf_name="nested/Invoice.pdf"
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "nested" / "Invoice.pdf").is_file()
    assert (source_dir / "nested" / "Invoice.md").is_file()
    assert calls[0]["output"] == source_dir / "nested" / "Invoice.md"


def test_docprep_clear_empty_directories_defaults_false(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    empty_dir = source_dir / "empty"
    empty_dir.mkdir()
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter([])),
    )

    cinderellasort(str(config_path), dryrun=False)

    assert empty_dir.is_dir()
    assert (source_dir / "Rechnung 2026.md").is_file()


def test_docprep_clear_empty_directories_true_removes_directories(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        settings_section={"clear-empty-directories": "true"},
    )
    empty_dir = source_dir / "empty"
    empty_dir.mkdir()
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter([])),
    )

    cinderellasort(str(config_path), dryrun=False)

    assert not empty_dir.exists()
    assert (source_dir / "Rechnung 2026.md").is_file()


def test_anonymize_source_directories_create_anonymization_proposals(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={},
        pdf_name="Anna Muster/Rechnung 2026.pdf",
    )
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter([])),
    )

    cinderellasort(str(config_path), dryrun=False)

    mapping = source_dir / "source-anon-mapping.csv"
    rows = list(csv.DictReader(mapping.open(encoding="utf-8", newline="")))
    directory_rows = [
        row for row in rows
        if row["source_documents"].startswith("directory:")
    ]
    assert [row["original_value"] for row in directory_rows] == [
        "Anna Muster"
    ]
    assert directory_rows[0]["source_documents"] == "directory:Anna Muster"
    assert (source_dir / "Anna Muster" / "Rechnung 2026.md").is_file()


def test_anonymize_source_directories_rename_target_directories(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={},
        pdf_name="Anna Muster/Sub Name/Rechnung 2026.pdf",
    )
    old_target_dir = target_dir / "Anna Muster" / "Sub Name"
    old_target_dir.mkdir(parents=True)
    old_target_dir.joinpath("existing.md").write_text(
        "existing", encoding="utf-8"
    )
    mapping = source_dir / "source-anon-mapping.csv"
    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-abcd,Anna Muster,name,,,\n"
        "anon,value-ef12,Sub Name,string,,,\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter([])),
    )

    cinderellasort(str(config_path), dryrun=False)

    new_target_dir = target_dir / "Person-abcd" / "value-ef12"
    assert not (target_dir / "Anna Muster").exists()
    assert (new_target_dir / "existing.md").read_text(
        encoding="utf-8"
    ) == "existing"
    assert (source_dir / "Anna Muster" / "Sub Name" / "Rechnung 2026.md").is_file()


def test_anonymization_creates_proposals_then_applies_approved_mapping(tmp_path):
    markdown = tmp_path / "document.md"
    markdown.write_text("# Anna Musterpeter", encoding="utf-8")
    mapping = tmp_path / "customer_mapping.csv"
    settings = {
        "enabled": True,
        "mapping_file": str(mapping),
        "force_update": False,
    }

    assert cs.handle_anonymization(markdown, settings) is None
    mapping_text = mapping.read_text(encoding="utf-8")
    assert "status" in mapping_text and mapping_text.splitlines()[1].startswith("new,")
    assert not (tmp_path / "document_anon.md").exists()

    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-abc,Anna Musterpeter,name,,,\n",
        encoding="utf-8",
    )
    output = cs.handle_anonymization(markdown, settings)
    assert output == tmp_path / "document_anon.md"
    assert output.read_text(encoding="utf-8") == "# Person-e3a2"
    assert markdown.is_file()


def test_anonymization_mapping_updates_from_existing_anonymized_file(tmp_path):
    source = tmp_path / "document.md"
    output = tmp_path / "document_anon.md"
    source.write_text("Sample Person; New Person", encoding="utf-8")
    output.write_text("Person-001; New Person", encoding="utf-8")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-001,Sample Person,name,source.md,line 1,1\n",
        encoding="utf-8",
    )
    settings = {
        "enabled": True,
        "mapping_file": str(mapping),
        "force_update": True,
        "mode": "custom",
    }

    cs.handle_anonymization(source, settings, output_path=output)

    rows = list(csv.DictReader(mapping.open(encoding="utf-8", newline="")))
    anon_path = tmp_path / "mapping-anon.csv"
    anon_rows = list(
        csv.DictReader(anon_path.open(encoding="utf-8", newline=""))
    )
    assert [row["original_value"] for row in rows] == ["New Person"]
    assert [row["original_value"] for row in anon_rows] == ["Sample Person"]


def test_anonymize_uses_paired_markup_and_keeps_source(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={"mapping_file": str(tmp_path / "mapping.csv")},
    )
    markup = source_dir / "Rechnung 2026.md"
    markup.write_text("# Sample Person", encoding="utf-8")
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-001,Sample Person,name,, ,1\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (lambda source: 99, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert markup.read_text(encoding="utf-8") == "# Sample Person"
    assert (target_dir / "Rechnung 2026_anon.md").read_text(encoding="utf-8") == "# Person-16ad"


def test_anonymize_moves_target_markup_to_source_before_anonymizing(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={"mapping_file": str(tmp_path / "mapping.csv")},
    )
    target_original = target_dir / "Rechnung 2026.md"
    target_original.write_text("# Sample Person", encoding="utf-8")
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-001,Sample Person,name,,,1\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (lambda source: 99, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (source_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "# Sample Person"
    assert not target_original.exists()
    assert (target_dir / "Rechnung 2026_anon.md").read_text(encoding="utf-8") == "# Person-16ad"


def test_anonymize_generated_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={"mapping_file": str(tmp_path / "mapping.csv")},
    )
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-001,converted,string,,,1\n",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter(calls)),
    )

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "# converted"
    assert (target_dir / "Rechnung 2026_anon.md").read_text(encoding="utf-8") == "# Person-001"


def test_docprep_sync_deletes_removes_orphan_markdown(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        docprep_section={"sync-deletes": "true"},
    )
    orphan_source = source_dir / "Orphan.md"
    orphan_sidecar = source_dir / "Orphan_pdf2md.json"
    orphan_source.write_text("orphan", encoding="utf-8")
    orphan_sidecar.write_text("{}", encoding="utf-8")
    (source_dir / "Rechnung 2026.md").write_text(
        "source markdown", encoding="utf-8"
    )
    (source_dir / "Rechnung 2026_pdf2md.json").write_text(
        "{}", encoding="utf-8"
    )

    cinderellasort(str(config_path), dryrun=False)

    assert not orphan_source.exists()
    assert not orphan_sidecar.exists()
    assert (source_dir / "Rechnung 2026.md").is_file()
    assert (source_dir / "Rechnung 2026_pdf2md.json").is_file()


def test_docprep_sync_deletes_defaults_to_keeping_original_markdown(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    orphan = source_dir / "Orphan.md"
    orphan.write_text("orphan", encoding="utf-8")

    cinderellasort(str(config_path), dryrun=False)

    assert orphan.is_file()


def test_anonymize_sync_deletes_removes_orphan_anon(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={"mapping_file": str(tmp_path / "mapping.csv")},
    )
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type\n"
        "anon,Person-001,Sample Person,name\n",
        encoding="utf-8",
    )
    orphan_anon = target_dir / "Orphan_anon.md"
    orphan_anon.write_text("orphan anon", encoding="utf-8")

    cinderellasort(str(config_path), dryrun=False)

    assert not orphan_anon.exists()


def test_anonymize_sync_deletes_false_keeps_orphan_anon(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={
            "mapping_file": str(tmp_path / "mapping.csv"),
            "sync-deletes": "false",
        },
    )
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type\n"
        "anon,Person-001,Sample Person,name\n",
        encoding="utf-8",
    )
    orphan_anon = target_dir / "Orphan_anon.md"
    orphan_anon.write_text("orphan anon", encoding="utf-8")

    cinderellasort(str(config_path), dryrun=False)

    assert orphan_anon.is_file()


def test_docprep_sync_deletes_supports_registered_extensions(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        docprep_section={"sync-deletes": "true"},
    )
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".docx",
        (lambda source: 1, _fake_converter([])),
    )
    (source_dir / "Original.docx").write_text("document", encoding="utf-8")
    (source_dir / "Original.md").write_text("original", encoding="utf-8")
    (source_dir / "Orphan.md").write_text("orphan", encoding="utf-8")

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "Original.md").is_file()
    assert not (source_dir / "Orphan.md").exists()


def test_docprep_sync_deletes_dryrun_keeps_orphans(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        docprep_section={"sync-deletes": "true"},
    )
    orphan = source_dir / "Orphan.md"
    orphan.write_text("orphan", encoding="utf-8")

    cinderellasort(str(config_path), dryrun=True)

    assert orphan.is_file()


def test_docprep_sync_deletes_inactive_without_docprep_bowls(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "document.txt").write_text("text", encoding="utf-8")
    orphan_anon = target_dir / "Orphan_anon.md"
    orphan_anon.write_text("orphan anon", encoding="utf-8")

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ".txt",
        "filemode": "win",
    }
    config["SETTINGS"] = {"overwrite": "false"}
    config["BOWLS"] = {"Docs": "."}
    config_path = tmp_path / "config.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)

    cinderellasort(str(config_path), dryrun=False)

    assert orphan_anon.is_file()


def test_anonymize_pending_scans_source_markdown(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={},
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    source_markdown = source_dir / "old" / "existing.md"
    source_markdown.parent.mkdir(parents=True)
    source_markdown.write_text("Anna Musterpeter", encoding="utf-8")
    mapping = source_dir / "source-anon-mapping.csv"
    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-abc,Anna Musterpeter,name,,,\n",
        encoding="utf-8",
    )

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "old" / "existing_anon.md").read_text(encoding="utf-8") == "Person-e3a2"
    assert (source_dir / "source-anon.csv").is_file()


def test_anonymize_publishes_non_matching_source_files(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".json"},
        anonymize_section={},
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    (source_dir / "data.json").write_text('{}', encoding="utf-8")

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "data.json").read_text(encoding="utf-8") == '{}'


def test_anonymize_pending_review_blocks_publication(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={"mapping_file": str(tmp_path / "mapping.csv")},
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    (source_dir / "notes.md").write_text("Anna Musterpeter", encoding="utf-8")
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type\n"
        "new,Person-abc,Anna Musterpeter,name\n",
        encoding="utf-8",
    )

    cinderellasort(str(config_path), dryrun=False)

    assert not (target_dir / "notes.md").exists()
    assert not (target_dir / "notes_anon.md").exists()


def test_anonymize_pending_review_publishes_when_enabled(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={
            "mapping_file": str(tmp_path / "mapping.csv"),
            "publish_without_review": "true",
        },
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    (source_dir / "notes.md").write_text("Anna Musterpeter", encoding="utf-8")
    (tmp_path / "mapping.csv").write_text(
        "status,replacement_value,original_value,value_type\n"
        "new,Person-abc,Anna Musterpeter,name\n",
        encoding="utf-8",
    )

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "notes.md").read_text(encoding="utf-8") == "Anna Musterpeter"
    assert not (target_dir / "notes_anon.md").exists()


def test_anonymize_save_ignored_as_list_collects_all_pending_documents(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        anonymize_bowls={"Anonymized": ".md"},
        anonymize_section={
            "ignore_emails": "true",
            "save_ignored_as_list": "true",
        },
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    (source_dir / "first.md").write_text("first@example.com", encoding="utf-8")
    (source_dir / "second.md").write_text("second@example.com", encoding="utf-8")
    ignore_path = source_dir / "source-anon-ignore.csv"
    ignore_path.write_text(
        "original_value,value_type\nstale@example.com,email\n",
        encoding="utf-8",
    )

    cinderellasort(str(config_path), dryrun=False)

    ignore_rows = list(
        csv.DictReader(ignore_path.open(encoding="utf-8", newline=""))
    )
    assert ignore_rows == [
        {"original_value": "stale@example.com", "value_type": "email"}
    ]
    saved_ignore_path = source_dir / "source-anon-ignore-save.csv"
    rows = list(csv.DictReader(saved_ignore_path.open(encoding="utf-8", newline="")))
    assert {row["original_value"] for row in rows} == {
        "first@example.com",
        "second@example.com",
    }


def test_docprep_settings_defaults(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    settings = cs.docprep_settings(config)
    assert settings["language"] == "en"
    assert settings["mode"] == "vision"
    assert settings["sidecar"] is True
    assert settings["sync_deletes"] is False
    config["DOCPREP"] = {
        "language": "de",
        "mode": "text",
        "sidecar": "false",
        "sync-deletes": "true",
    }
    settings = cs.docprep_settings(config)
    assert settings["language"] == "de"
    assert settings["mode"] == "text"
    assert settings["sidecar"] is False
    assert settings["sync_deletes"] is True


def test_anonymize_settings(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    settings = cs.anonymize_settings(config)
    assert settings["enabled"] is False
    assert settings["mapping_file"] is None
    assert settings["mode"] == "custom"
    assert settings["use_name_datasets"] is None
    assert settings["sync_deletes"] is True
    assert settings["publish_without_review"] is False
    config["TABLE"] = {"sourcedir": str(tmp_path / "source")}
    config["BOWLS_ANONYMIZE"] = {"Anonymized": ".md"}
    config["ANONYMIZE"] = {
        "name_countries": "de, us",
        "use_name_datasets": "true",
        "name_dataset_offline": "true",
        "name_exclusions": "common, word",
        "mode": "all",
        "save_ignored_as_list": "true",
        "presidio_score_threshold": "0.7",
        "sync-deletes": "false",
        "force_update": "true",
        "publish_without_review": "true",
    }
    settings = cs.anonymize_settings(config)
    assert settings["enabled"] is True
    assert settings["name_countries"] == ("de", "us")
    assert settings["use_name_datasets"] is True
    assert settings["name_dataset_offline"] is True
    assert settings["name_exclusions"] == ("common", "word")
    assert settings["mode"] == "all"
    assert settings["save_ignored_as_list"] is True
    assert settings["presidio_score_threshold"] == 0.7
    assert settings["sync_deletes"] is False
    assert settings["force_update"] is True
    assert settings["publish_without_review"] is True
    assert "DATE_TIME" not in settings["presidio_entities"]
    assert "URL" not in settings["presidio_entities"]
    assert settings["mapping_file"] == str(
        tmp_path / "source" / "source-anon-mapping.csv"
    )
    custom_mapping = tmp_path / "custom-mapping.csv"
    config["ANONYMIZE"]["mapping_file"] = str(custom_mapping)
    config["ANONYMIZE"]["save_ignored_as_list"] = "false"
    settings = cs.anonymize_settings(config)
    assert settings["mapping_file"] == str(custom_mapping)
    assert settings["save_ignored_as_list"] is False


def test_gen_img_ignore_max_cost_setting():
    config = ConfigParser()
    config.optionxform = str
    config["GEN_IMG"] = {"max_cost": "ignore"}
    assert cs.gen_img_settings(config)["max_cost"] == "ignore"


# --- GEN_IMG bowls ---------------------------------------------------------


def _gen_img_setup(tmp_path, prompts, *, gen_img_section=None):
    source_dir = tmp_path / "prompts"
    target_dir = tmp_path / "images"
    source_dir.mkdir()
    target_dir.mkdir()
    for name, text in prompts.items():
        path = source_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")

    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ".txt",
        "filemode": "win",
    }
    config["SETTINGS"] = {"overwrite": "false"}
    config["BOWLS_GEN_IMG"] = {"Renderings": "."}
    if gen_img_section is not None:
        config["GEN_IMG"] = gen_img_section
    config_path = tmp_path / "gen_img.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)
    return source_dir, target_dir, config_path


def _fake_generator(calls, fail_for=()):
    def generate(prompt, settings, out_dir, basename, negative_prompt, reference):
        calls.append({
            "prompt": prompt, "settings": settings, "out_dir": out_dir,
            "basename": basename, "negative": negative_prompt, "reference": reference,
        })
        if basename in fail_for:
            raise RuntimeError("OpenRouter 502")
        image = out_dir / f"{basename}.png"
        image.write_bytes(b"png")
        (out_dir / f"{basename}.json").write_text("{}", encoding="utf-8")
        return [image]
    return generate


def test_gen_img_generates_with_negative_and_reference(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _gen_img_setup(
        tmp_path,
        {
            "villa_prompt.txt": "  Eine Villa am See, Abendlicht  ",
            "villa_negative-prompt.txt": "Text, Wasserzeichen",
            "villa.jpg": b"\xff\xd8ref",
        },
        gen_img_section={"model": "img/model", "n": "1", "aspect_ratio": "16:9", "max_cost": "0.25"},
    )
    calls = []
    monkeypatch.setattr(cs, "GEN_IMG_GENERATOR", _fake_generator(calls))

    cinderellasort(str(config_path), dryrun=False)

    assert len(calls) == 1, "negative and reference files must not be jobs"
    call = calls[0]
    assert call["prompt"] == "Eine Villa am See, Abendlicht"
    assert call["negative"] == "Text, Wasserzeichen"
    assert call["reference"] == source_dir / "villa.jpg"
    assert call["basename"] == "villa"
    assert call["out_dir"] == target_dir / "Renderings"
    assert call["settings"]["model"] == "img/model"
    assert call["settings"]["aspect_ratio"] == "16:9"
    assert call["settings"]["max_cost"] == 0.25
    assert (target_dir / "Renderings" / "villa.png").is_file()
    assert (source_dir / "villa_prompt.txt").is_file(), "prompt files stay in source"
    assert (source_dir / "villa_negative-prompt.txt").is_file()


@pytest.mark.parametrize("sidecar_name", ["villa.json", "villa_1.json", "villa_7.json"])
def test_gen_img_enumerates_when_sidecar_exists(tmp_path, monkeypatch, sidecar_name):
    source_dir, target_dir, config_path = _gen_img_setup(tmp_path, {"villa_prompt.txt": "prompt"})
    (target_dir / "Renderings").mkdir()
    (target_dir / "Renderings" / sidecar_name).write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cs, "GEN_IMG_GENERATOR", _fake_generator(calls))

    cinderellasort(str(config_path), dryrun=False)

    assert len(calls) == 1


def test_gen_img_failure_continues_and_empty_prompt_skipped(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _gen_img_setup(
        tmp_path, {"a_prompt.txt": "first", "b_prompt.txt": "second", "empty_prompt.txt": "   ", "notes.txt": "not a job"}
    )
    calls = []
    monkeypatch.setattr(cs, "GEN_IMG_GENERATOR", _fake_generator(calls, fail_for={"a"}))

    cinderellasort(str(config_path), dryrun=False)

    assert sorted(c["basename"] for c in calls) == ["a", "b"]
    assert not (target_dir / "Renderings" / "a.png").exists()
    assert (target_dir / "Renderings" / "b.png").is_file()
    assert (source_dir / "a_prompt.txt").is_file()


def test_gen_img_max_jobs_limits_run(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _gen_img_setup(
        tmp_path, {"a_prompt.txt": "1", "b_prompt.txt": "2", "c_prompt.txt": "3"}, gen_img_section={"max_jobs": "2"}
    )
    calls = []
    monkeypatch.setattr(cs, "GEN_IMG_GENERATOR", _fake_generator(calls))

    cinderellasort(str(config_path), dryrun=False)
    assert len(calls) == 2

    calls.clear()
    cinderellasort(str(config_path), dryrun=False)
    assert len(calls) == 2, "existing sidecars do not suppress later runs"


def test_gen_img_general_reference_fallback(tmp_path):
    (tmp_path / "reference.png").write_bytes(b"general")
    assert cs.gen_img_reference(tmp_path, "villa") == tmp_path / "reference.png"

    (tmp_path / "villa.jpg").write_bytes(b"own")
    assert cs.gen_img_reference(tmp_path, "villa") == tmp_path / "villa.jpg"

    assert cs.gen_img_reference(tmp_path, "haus") == tmp_path / "reference.png"
    (tmp_path / "reference.png").unlink()
    assert cs.gen_img_reference(tmp_path, "haus") is None


def test_gen_img_prompt_detection_and_slug():
    assert cs.is_gen_img_prompt("villa_prompt.txt")
    assert not cs.is_gen_img_prompt("villa_negative-prompt.txt")
    assert not cs.is_gen_img_prompt("villa.txt")
    assert not cs.is_gen_img_prompt("_prompt.txt")
    assert cs.gen_img_slug("villa_prompt.txt") == "villa"


def test_gen_img_settings_defaults():
    config = ConfigParser()
    config.optionxform = str
    settings = cs.gen_img_settings(config)
    assert settings == {
        "model": None, "n": 1, "aspect_ratio": None, "resolution": None,
        "quality": None, "output_format": None, "max_cost": None, "max_jobs": 20,
    }


# --- Inbox bowls -----------------------------------------------------------


def _inbox_setup(
    tmp_path,
    *,
    inbox_bowls=None,
    pdf_name="scan001.pdf",
    extra_files=None,
    settings_section=None,
    jev_section=None,
    ftype_sort=".pdf",
):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    source_file = source_dir / pdf_name
    source_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEST_PDF, source_file)
    for extra in extra_files or ():
        path = source_dir / extra
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("extra", encoding="utf-8")
    config = ConfigParser()
    config.optionxform = str
    config["TABLE"] = {
        "sourcedir": str(source_dir),
        "targetdir": str(target_dir),
        "ftype_sort": ftype_sort,
        "filemode": "win",
    }
    config["SETTINGS"] = {"overwrite": "false", **(settings_section or {})}
    config["BOWLS_INBOX"] = inbox_bowls or {"Rechnungen": "Rechnung"}
    if jev_section is not None:
        definitions_path = tmp_path / "jev_definitions.ini"
        definitions = ConfigParser()
        definitions.optionxform = str
        definitions["CATEGORY"] = {
            "Rest": "Everything else.",
            "99_Unclassified": "Cannot be assigned.",
        }
        definitions["DOCUMENT_TYPE"] = {"other": "No specific type."}
        with definitions_path.open("w", encoding="utf-8") as fp:
            definitions.write(fp)
        config["JEV"] = {
            "definitions_file": str(definitions_path),
            **jev_section,
        }
    config_path = tmp_path / "inbox.ini"
    with config_path.open("w", encoding="utf-8") as fp:
        config.write(fp)
    return source_dir, target_dir, config_path


def _fake_decide(answers, calls=None, fail=None):
    def decide(state, questions, model=None, **kwargs):
        if calls is not None:
            calls.append({"state": state, "questions": questions, "model": model})
        if fail:
            raise RuntimeError(fail)
        return answers
    return decide


JEV_ANSWERS = {
    "category": {
        "type": "choice",
        "choice": "02_Finance_And_Banking",
        "confidence": 0.9,
    },
    "document_type": {
        "type": "choice",
        "choice": "invoice",
        "confidence": 0.8,
    },
}


def _fake_converter_with_content(content):
    def convert(source, output_path, settings):
        output_path.write_text(content, encoding="utf-8")
        return output_path
    return convert


def _patch_inbox_converter(monkeypatch, content="# converted"):
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter_with_content(content)),
    )


def test_inbox_sorts_pdf_with_markup_and_sidecars(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        pdf_name="Rechnung 2026.pdf",
        extra_files=["Rechnung 2026_pdf2md.json"],
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert (bowl / "Rechnung 2026.pdf").is_file()
    assert (bowl / "Rechnung 2026.md").read_text(encoding="utf-8") == "# converted"
    assert (bowl / "Rechnung 2026_pdf2md.json").is_file()
    assert not (source_dir / "Rechnung 2026.pdf").exists()
    assert not (source_dir / "Rechnung 2026.md").exists()
    assert not (source_dir / "Rechnung 2026_pdf2md.json").exists()


def test_inbox_content_match_uses_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, inbox_bowls={"Rechnungen": ";rechnung"}
    )
    _patch_inbox_converter(monkeypatch, "# Doc\nRECHNUNG 12345")

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "Rechnungen" / "scan001.pdf").is_file()
    assert (target_dir / "Rechnungen" / "scan001.md").is_file()


def test_inbox_unmatched_file_and_markup_stay(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(tmp_path)
    _patch_inbox_converter(monkeypatch, "nothing relevant")

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "scan001.pdf").is_file()
    assert (source_dir / "scan001.md").is_file()
    assert not (target_dir / "Rechnungen" / "scan001.pdf").exists()


def test_inbox_default_bowl_catches_unmatched(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": "Rechnung", "Rest": "!DEFAULT"},
    )
    _patch_inbox_converter(monkeypatch, "nothing relevant")

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "Rest" / "scan001.pdf").is_file()
    assert (target_dir / "Rest" / "scan001.md").is_file()


def test_inbox_sidecar_is_not_sorted_alone(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        pdf_name="Rechnung 2026.pdf",
        extra_files=["Rechnung 2026.md"],
        ftype_sort=".pdf,.md",
    )
    calls = []
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter(calls)),
    )

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert calls == [], "existing markup must not be re-converted"
    assert (bowl / "Rechnung 2026.pdf").is_file()
    assert (bowl / "Rechnung 2026.md").read_text(encoding="utf-8") == "extra"
    assert not (source_dir / "Rechnung 2026.pdf").exists()
    assert not (source_dir / "Rechnung 2026.md").exists()


def test_inbox_dryrun_converts_and_moves_nothing(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf"
    )
    calls = []
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count, _fake_converter(calls)),
    )

    cinderellasort(str(config_path), dryrun=True)

    assert calls == []
    assert (source_dir / "Rechnung 2026.pdf").is_file()
    assert not (source_dir / "Rechnung 2026.md").exists()
    assert not (target_dir / "Rechnungen" / "Rechnung 2026.pdf").exists()


def test_bowldir_inbox_filename_and_default():
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {"Rechnungen": "Rechnung", "Rest": "!DEFAULT"}
    assert cs.bowldir_inbox("Rechnung x.pdf", config) == "/Rechnungen"
    assert cs.bowldir_inbox("other.pdf", config) == "/Rest"


def test_bowldir_inbox_markup_content(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {"Rechnungen": ";rechnung", "Rest": "!DEFAULT"}
    markup = tmp_path / "scan.md"
    markup.write_text("Some rechnung text", encoding="utf-8")
    assert cs.bowldir_inbox("scan.pdf", config, markup_path=markup) == "/Rechnungen"
    assert cs.bowldir_inbox("scan.pdf", config, markup_path=None) == "/Rest"


def test_bowldir_inbox_filename_crit_ignores_content(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {"Rechnungen": "Rechnung", "Rest": "!DEFAULT"}
    markup = tmp_path / "vertrag.md"
    markup.write_text("Anschrift und Rechnungsadresse", encoding="utf-8")
    # "Rechnung" appears in the markup but is a filename-only criterion
    assert cs.bowldir_inbox("vertrag.pdf", config, markup_path=markup) == "/Rest"


def test_bowldir_inbox_content_crit_ignores_filename(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {"Kunde": ";12302", "Rest": "!DEFAULT"}
    markup = tmp_path / "doc.md"
    markup.write_text("nothing", encoding="utf-8")
    # "12302" appears in the filename but is a content-only criterion
    assert cs.bowldir_inbox("12302 scan.pdf", config, markup_path=markup) == "/Rest"


def test_bowldir_inbox_content_crit_beats_filename(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {
        "Auxilia": ";3604326300",
        "Rechnungen": "Rechnung",
    }
    markup = tmp_path / "doc.md"
    markup.write_text("Police 3604326300", encoding="utf-8")
    # filename hits the generic bowl, the content identifier must win
    assert cs.bowldir_inbox("Rechnung abc.pdf", config, markup_path=markup) == "/Auxilia"


def test_bowldir_inbox_mixed_crits(tmp_path):
    config = ConfigParser()
    config.optionxform = str
    config["BOWLS_INBOX"] = {"Mixed": "alpha;beta"}
    markup = tmp_path / "scan.md"
    markup.write_text("contains beta only", encoding="utf-8")
    assert cs.bowldir_inbox("alpha file.pdf", config) == "/Mixed"
    assert cs.bowldir_inbox("scan.pdf", config, markup_path=markup) == "/Mixed"
    assert cs.bowldir_inbox("beta file.pdf", config, markup_path=markup) == "/Mixed"
    assert cs.bowldir_inbox("scan.pdf", config) == ""


def test_inbox_jev_tags_markup_before_move(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf", jev_section={}
    )
    calls = []
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS, calls),
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    assert len(calls) == 1
    assert calls[0]["state"]["filename"] == "Rechnung 2026.pdf"
    markup = (target_dir / "Rechnungen" / "Rechnung 2026.md").read_text(encoding="utf-8")
    assert markup.startswith("---")
    assert "category: 02_Finance_And_Banking" in markup
    assert "document_type: invoice" in markup
    assert "category_confidence: 0.90" in markup
    assert "tags:\n- 02_Finance_And_Banking\n- invoice" in markup
    assert "# converted" in markup


def test_inbox_jev_skips_existing_classification(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        pdf_name="Rechnung 2026.pdf",
        extra_files=["Rechnung 2026.md"],
        jev_section={},
    )
    (source_dir / "Rechnung 2026.md").write_text(
        "---\ncategory: 03_Insurance\n---\n\nold", encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS, calls),
    )

    cinderellasort(str(config_path), dryrun=False)

    assert calls == [], "existing category frontmatter must skip JEV"
    markup = (target_dir / "Rechnungen" / "Rechnung 2026.md").read_text(encoding="utf-8")
    assert "category: 03_Insurance" in markup


def test_jev_definitions_rejects_spaced_criteria(tmp_path):
    definitions = ConfigParser()
    definitions.optionxform = str
    definitions["CLASSIFICATION"] = {
        "intern": "Internal.",
        "streng vertraulich": "Strict.",
    }
    path = tmp_path / "defs.ini"
    with path.open("w", encoding="utf-8") as fp:
        definitions.write(fp)

    with pytest.raises(ValueError, match="streng vertraulich"):
        cs.jev_definitions(path)


def test_inbox_jev_tags_replace_spaces(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf", jev_section={}
    )
    answers = {
        **JEV_ANSWERS,
        "classification": {
            "type": "choice",
            "choice": "streng vertraulich",
            "confidence": 0.9,
        },
    }
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(answers),
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    markup = (target_dir / "Rechnungen" / "Rechnung 2026.md").read_text(
        encoding="utf-8"
    )
    assert "classification: streng vertraulich" in markup
    assert "- streng-vertraulich" in markup


def test_inbox_jev_failure_still_sorts(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf", jev_section={}
    )
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide({}, fail="api down"),
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "Rechnungen" / "Rechnung 2026.pdf").is_file()


def test_inbox_jev_min_confidence(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        pdf_name="Rechnung 2026.pdf",
        jev_section={"min_confidence": "0.95"},
    )
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS),
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    markup = (target_dir / "Rechnungen" / "Rechnung 2026.md").read_text(encoding="utf-8")
    assert "category: 99_Unclassified" in markup
    assert "document_type: other" in markup


def test_md_update_frontmatter_insert_and_merge(tmp_path):
    markup = tmp_path / "doc.md"
    markup.write_text("# title\nbody", encoding="utf-8")
    cs._md_update_frontmatter(markup, {"category": "01_X"})
    text = markup.read_text(encoding="utf-8")
    assert text.startswith("---\ncategory: 01_X\n---\n\n# title")

    cs._md_update_frontmatter(
        markup, {"tags": ["a", "b"], "category": "02_Y"}
    )
    text = markup.read_text(encoding="utf-8")
    assert "category: 02_Y" in text
    assert "tags:\n- a\n- b" in text
    assert text.count("---") == 2


def test_md_update_frontmatter_merge_preserves_list(tmp_path):
    markup = tmp_path / "doc.md"
    markup.write_text(
        "---\ncategory: 01_X\ntags:\n- a\n- b\n---\n\nbody",
        encoding="utf-8",
    )
    cs._md_update_frontmatter(markup, {"category": "02_Y"})
    text = markup.read_text(encoding="utf-8")
    assert "category: 02_Y" in text
    assert "tags:\n- a\n- b" in text


def test_inbox_sorts_eml_with_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": ";rechnung"},
        extra_files=["newsletter.eml"],
        ftype_sort=".eml",
        jev_section={},
    )
    (source_dir / "newsletter.eml").write_text(
        "From: shop@example.com\n"
        "To: me@example.com\n"
        "Subject: Rechnung 123\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Sehr geehrte Kunden, anbei die Rechnung.",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS),
    )

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert (bowl / "newsletter.eml").is_file()
    markup = (bowl / "newsletter.md").read_text(encoding="utf-8")
    assert "Rechnung 123" in markup
    assert "shop@example.com" in markup
    assert "Sehr geehrte Kunden" in markup
    assert "category: 02_Finance_And_Banking" in markup


def test_inbox_eml_thread_shared_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": ";rechnung"},
        extra_files=["mail1.eml", "mail2.eml"],
        ftype_sort=".eml",
        jev_section={},
    )
    (source_dir / "mail1.eml").write_text(
        "From: a@x.de\n"
        "To: b@y.de\n"
        "Subject: Rechnung 123\n"
        "Date: Mon, 20 Oct 2025 10:00:00 +0200\n"
        "Message-ID: <m1@x.de>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Sehr geehrte Kunden, anbei die Rechnung 123.",
        encoding="utf-8",
    )
    (source_dir / "mail2.eml").write_text(
        "From: b@y.de\n"
        "To: a@x.de\n"
        "Subject: AW: Rechnung 123\n"
        "Date: Tue, 21 Oct 2025 09:00:00 +0200\n"
        "Message-ID: <m2@y.de>\n"
        "In-Reply-To: <m1@x.de>\n"
        "References: <m1@x.de>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Danke, Zahlung veranlasst.\n"
        "\n"
        "-----Ursprüngliche Nachricht-----\n"
        "Von: a@x.de\n"
        "Sehr geehrte Kunden, anbei die Rechnung 123.",
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS, calls),
    )

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert (bowl / "mail1.eml").is_file()
    assert (bowl / "mail2.eml").is_file()
    # one shared thread markup, named after the earliest member
    text = (bowl / "mail1.md").read_text(encoding="utf-8")
    assert "Sehr geehrte Kunden" in text
    assert "Zahlung veranlasst" in text
    assert "Ursprüngliche Nachricht" not in text
    assert "category: 02_Finance_And_Banking" in text
    assert not (bowl / "mail2.md").exists()
    # the shared thread file was tagged once and left the inbox
    assert len(calls) == 1
    assert not list(source_dir.glob("*.md"))


def test_inbox_remove_source_deletes_original(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": ";rechnung"},
        extra_files=["newsletter.eml"],
        ftype_sort=".eml",
        settings_section={"remove_source": ".eml"},
    )
    (source_dir / "newsletter.eml").write_text(
        "From: shop@example.com\n"
        "To: me@example.com\n"
        "Subject: Rechnung 123\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Sehr geehrte Kunden, anbei die Rechnung.",
        encoding="utf-8",
    )
    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert not (bowl / "newsletter.eml").exists()
    assert not (source_dir / "newsletter.eml").exists()
    assert (bowl / "newsletter.md").is_file()


def test_inbox_remove_source_keeps_source_without_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": "scan"},
        ftype_sort=".pdf",
        settings_section={"remove_source": ".pdf"},
    )
    monkeypatch.setitem(
        cs.DOCPREP_CONVERTERS,
        ".pdf",
        (cs._pdf_page_count,
         lambda *a: (_ for _ in ()).throw(RuntimeError("fail"))),
    )
    cinderellasort(str(config_path), dryrun=False)

    # conversion failed -> no markup -> source still moved, not deleted
    assert (target_dir / "Rechnungen" / "scan001.pdf").is_file()
    assert not list((target_dir / "Rechnungen").glob("*.md"))


def test_inbox_eml_threads_disabled(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": ";rechnung"},
        extra_files=["mail1.eml", "mail2.eml"],
        ftype_sort=".eml",
        settings_section={"email_threads": "false"},
    )
    (source_dir / "mail1.eml").write_text(
        "From: a@x.de\n"
        "To: b@y.de\n"
        "Subject: Rechnung 123\n"
        "Message-ID: <m1@x.de>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Sehr geehrte Kunden, anbei die Rechnung 123.",
        encoding="utf-8",
    )
    (source_dir / "mail2.eml").write_text(
        "From: b@y.de\n"
        "To: a@x.de\n"
        "Subject: AW: Rechnung 123\n"
        "Message-ID: <m2@y.de>\n"
        "In-Reply-To: <m1@x.de>\n"
        "References: <m1@x.de>\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Danke, Zahlung veranlasst.",
        encoding="utf-8",
    )
    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    m1 = (bowl / "mail1.md").read_text(encoding="utf-8")
    m2 = (bowl / "mail2.md").read_text(encoding="utf-8")
    assert "Zahlung veranlasst" not in m1
    assert "Sehr geehrte Kunden" not in m2


def _write_docx(path, paragraphs):
    """Write a minimal valid .docx containing the given paragraphs."""
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>',
        )
        body = "".join(
            f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs
        )
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>",
        )


def test_inbox_sorts_docx_with_markup(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": ";rechnung"},
        ftype_sort=".docx",
        jev_section={},
    )
    _write_docx(source_dir / "brief.docx", ["Anbei die Rechnung 123"])
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS),
    )

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert (bowl / "brief.docx").is_file()
    markup = (bowl / "brief.md").read_text(encoding="utf-8")
    assert "Rechnung 123" in markup
    assert "category: 02_Finance_And_Banking" in markup


def test_inbox_doc_conversion_failure_still_sorts_by_name(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": "Rechnung"},
        extra_files=["Rechnung alt.doc"],
        ftype_sort=".doc",
    )
    monkeypatch.setattr(
        "wit_pytools.documenttools.doc_to_markdown",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no soffice")),
    )

    cinderellasort(str(config_path), dryrun=False)

    bowl = target_dir / "Rechnungen"
    assert (bowl / "Rechnung alt.doc").is_file()
    assert not (bowl / "Rechnung alt.md").exists()


def test_inbox_proposals_written_for_skipped_file(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(tmp_path)
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    proposals = target_dir / "sorting-proposals_target.ini"
    assert proposals.is_file()
    text = proposals.read_text(encoding="utf-8")
    assert "[99_Unclassified]" in text
    assert "scan001.pdf=scan001" in text


def test_inbox_proposals_written_for_default_bowl(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path,
        inbox_bowls={"Rechnungen": "Rechnung", "Rest": "!DEFAULT"},
        jev_section={},
    )
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS),
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "Rest" / "scan001.pdf").is_file()
    text = (target_dir / "sorting-proposals_target.ini").read_text(
        encoding="utf-8"
    )
    assert "[02_Finance_And_Banking]" in text
    assert "scan001.pdf=;invoice" in text


def test_inbox_no_proposals_when_all_sorted(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf"
    )
    _patch_inbox_converter(monkeypatch)

    cinderellasort(str(config_path), dryrun=False)

    assert not (target_dir / "sorting-proposals_target.ini").exists()


def test_jev_run_prints_default_bowl_reminder(tmp_path, monkeypatch, capsys):
    _inbox_setup(
        tmp_path, pdf_name="Rechnung 2026.pdf", jev_section={}
    )
    monkeypatch.setattr(
        "wit_pytools.aitools.openrouter.decide",
        _fake_decide(JEV_ANSWERS),
    )
    _patch_inbox_converter(monkeypatch)
    config_path = tmp_path / "inbox.ini"

    cinderellasort(str(config_path), dryrun=False)

    out = capsys.readouterr().out
    assert "update your criteria for files sorted to !DEFAULT" in out


def test_run_without_jev_prints_no_reminder(tmp_path, monkeypatch, capsys):
    _inbox_setup(tmp_path, pdf_name="Rechnung 2026.pdf")
    _patch_inbox_converter(monkeypatch)
    config_path = tmp_path / "inbox.ini"

    cinderellasort(str(config_path), dryrun=False)

    out = capsys.readouterr().out
    assert "update your criteria for files sorted to !DEFAULT" not in out


if __name__ == '__main__':
    pytest.main()
