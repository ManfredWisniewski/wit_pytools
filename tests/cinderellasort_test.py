#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import os
import sys

# Add parent directory to path so we can import wit_pytools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.cinderellasort import cleanfilename

class TestCleanFilename(unittest.TestCase):
    def test_basic_cleaning(self):
        # Test basic filename cleaning
        result = cleanfilename("test.txt", "", "", {})
        self.assertEqual(result, "test.txt")
        
    def test_clean_with_arabic_numerals(self):
        # Test conversion of Arabic numerals with default convert_numbers=True
        result = cleanfilename("test١٢٣.txt", "", "", {})
        self.assertEqual(result, "test123.txt")
        
        # Test with convert_numbers=False
        result = cleanfilename("test١٢٣.txt", "", "", {}, convert_numbers=False)
        self.assertEqual(result, "test١٢٣.txt")
        
    def test_clean_with_replacements(self):
        # Test with replacement strings
        replacements = {"test": "demo", "old": "new"}
        result = cleanfilename("test_old.txt", "", "", replacements)
        self.assertEqual(result, "demo_new.txt")
        
    def test_clean_with_case_sensitive(self):
        # Test case-sensitive cleaning
        result = cleanfilename("testABCtest.txt", "ABC", "", {})
        self.assertEqual(result, "testtest.txt")
        
    def test_clean_with_case_insensitive(self):
        # Test case-insensitive cleaning
        result = cleanfilename("testABCtest.txt", "", "abc", {})
        self.assertEqual(result, "testtest.txt")
        
    def test_clean_with_invalid_chars(self):
        # Test cleaning invalid filename characters
        result = cleanfilename("test<>:\"/\\|?*.txt", "", "", {})
        self.assertEqual(result, "test.txt")
        
    def test_clean_with_subdirectory(self):
        # Test with subdirectory
        result = cleanfilename("test.txt", "", "", {}, subdir="subdir١٢٣")
        self.assertEqual(result, "subdir123.txt")
        
    def test_clean_with_empty_input(self):
        # Test with empty input
        result = cleanfilename("", "", "", {})
        self.assertEqual(result, "")
        
    def test_clean_with_multiple_extensions(self):
        # Test with multiple extensions
        result = cleanfilename("test.tar.gz", "", "", {})
        self.assertEqual(result, "test.tar.gz")
        
    def test_clean_with_all_features(self):
        # Test combining multiple cleaning features
        replacements = {"test": "demo"}
        result = cleanfilename("test<>:\"/\\|?*١٢٣ABC.txt", "ABC", "", replacements)
        self.assertEqual(result, "demo123.txt")

if __name__ == '__main__':
    unittest.main()
