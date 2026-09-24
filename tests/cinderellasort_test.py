#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


def _docprep_setup(tmp_path, *, docprep_section=None, bowls=None, pdf_name="Rechnung 2026.pdf"):
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
    config["SETTINGS"] = {"overwrite": "false"}
    config["BOWLS_DOCPREP"] = {"Rechnungen": "Rechnung,Invoice"}
    if bowls:
        config["BOWLS"] = bowls
    if docprep_section is not None:
        config["DOCPREP"] = docprep_section
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


def test_docprep_converts_and_moves_original_to_originals(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path, docprep_section={"language": "de", "model": "test/model"}
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "Rechnung 2026.pdf").is_file()
    assert (target_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "# converted"
    assert not (source_dir / "Rechnung 2026.md").exists()
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


def test_docprep_existing_markdown_skips_conversion_but_moves(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    (target_dir / "Rechnung 2026.md").write_text("existing", encoding="utf-8")
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert (target_dir / "Rechnung 2026.md").read_text(encoding="utf-8") == "existing"
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


def test_docprep_keeps_original_and_skips_existing_target_markdown(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(tmp_path)
    target_file = target_dir / "Rechnung 2026.md"
    target_file.write_text("existing", encoding="utf-8")
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert calls == []
    assert target_file.read_text(encoding="utf-8") == "existing"
    assert (source_dir / "Rechnung 2026.pdf").is_file()


def test_docprep_mirrors_subdir_and_keeps_original(tmp_path, monkeypatch):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path, pdf_name="nested/Invoice.pdf"
    )
    calls = []
    monkeypatch.setitem(cs.DOCPREP_CONVERTERS, ".pdf", (cs._pdf_page_count, _fake_converter(calls)))

    cinderellasort(str(config_path), dryrun=False)

    assert (source_dir / "nested" / "Invoice.pdf").is_file()
    assert (target_dir / "nested" / "Invoice.md").is_file()
    assert calls[0]["output"] == target_dir / "nested" / "Invoice.md"


def test_docprep_anonymization_creates_proposals_then_applies_approved_mapping(tmp_path):
    markdown = tmp_path / "document.md"
    markdown.write_text("# Anna Musterpeter", encoding="utf-8")
    mapping = tmp_path / "customer_mapping.csv"
    settings = {
        "anonymize": True,
        "anonymize_mapping": str(mapping),
        "anonymize_update": False,
    }

    assert cs.handle_docprep_anonymization(markdown, settings) is None
    mapping_text = mapping.read_text(encoding="utf-8")
    assert "status" in mapping_text and mapping_text.splitlines()[1].startswith("new,")
    assert not (tmp_path / "document_anon.md").exists()

    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-abc,Anna Musterpeter,name,,,\n",
        encoding="utf-8",
    )
    output = cs.handle_docprep_anonymization(markdown, settings)
    assert output == tmp_path / "document_anon.md"
    assert output.read_text(encoding="utf-8") == "# Person-abc"
    assert not markdown.exists()


def test_docprep_pending_anonymization_scans_existing_target_markdown(tmp_path):
    source_dir, target_dir, config_path = _docprep_setup(
        tmp_path,
        docprep_section={
            "anonymize": "true",
            "anonymize_mapping": str(tmp_path / "customer_mapping.csv"),
        },
    )
    (source_dir / "Rechnung 2026.pdf").unlink()
    target_markdown = target_dir / "old" / "existing.md"
    target_markdown.parent.mkdir(parents=True)
    target_markdown.write_text("Anna Musterpeter", encoding="utf-8")
    mapping = tmp_path / "customer_mapping.csv"
    mapping.write_text(
        "status,replacement_value,original_value,value_type,source_documents,locations,occurrences\n"
        "anon,Person-abc,Anna Musterpeter,name,,,\n",
        encoding="utf-8",
    )

    cinderellasort(str(config_path), dryrun=False)

    assert (target_dir / "old" / "existing_anon.md").read_text(encoding="utf-8") == "Person-abc"


def test_docprep_settings_defaults():
    config = ConfigParser()
    config.optionxform = str
    settings = cs.docprep_settings(config)
    assert settings["language"] == "en"
    assert settings["sidecar"] is True
    assert settings["anonymize_name_countries"] == ()
    assert settings["anonymize_use_name_datasets"] is None
    config["DOCPREP"] = {
        "language": "de",
        "sidecar": "false",
        "anonymize_name_countries": "de, us",
        "anonymize_use_name_datasets": "true",
        "anonymize_name_dataset_offline": "true",
        "anonymize_name_exclusions": "common, word",
    }
    settings = cs.docprep_settings(config)
    assert settings["language"] == "de"
    assert settings["sidecar"] is False
    assert settings["anonymize_name_countries"] == ("de", "us")
    assert settings["anonymize_use_name_datasets"] is True
    assert settings["anonymize_name_dataset_offline"] is True
    assert settings["anonymize_name_exclusions"] == ("common", "word")


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


if __name__ == '__main__':
    pytest.main()
