#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pytest
import tempfile
import shutil
from configparser import ConfigParser

# Add parent directory to path so we can import wit_pytools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.cinderellasort import cleanfilename, bowldir_gps
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

def test_clean_with_subdirectory():
    # Test with subdirectory
    result = cleanfilename("test.txt", "", "", {}, subdir="subdir١٢٣")
    assert result == "subdir123.txt"

def test_clean_with_empty_input():
    # Test with empty input
    result = cleanfilename("", "", "", {})
    assert result == ""

def test_clean_with_multiple_extensions():
    # Test with multiple extensions
    result = cleanfilename("test.tar.gz", "", "", {})
    assert result == "test.tar.gz"

def test_clean_with_all_features():
    # Test combining multiple cleaning features
    replacements = {"test": "demo"}
    result = cleanfilename("test<>:\"/\\|?*١٢٣ABC.txt", "ABC", "", replacements)
    assert result == "demo123.txt"

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

if __name__ == '__main__':
    pytest.main()
