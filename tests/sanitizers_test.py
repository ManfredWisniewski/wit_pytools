#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from wit_pytools.sanitizers import convert_numerals_arabic_western, cleanfilestring, prepregex

class TestSanitizers(unittest.TestCase):
    def test_prepregex(self):
        # Test escaping dots
        self.assertEqual(prepregex("file.txt"), "file\.txt")
        
        # Test escaping square brackets
        self.assertEqual(prepregex("[test]"), "\[test\]")
        
        # Test escaping multiple special characters
        self.assertEqual(prepregex("[file.name].txt"), "\[file\.name\]\.txt")
        
        # Test with no special characters
        self.assertEqual(prepregex("simple"), "simple")
        
        # Test empty string
        self.assertEqual(prepregex(""), "")
    
    def test_cleanfilestring(self):
        # Test removing invalid characters
        self.assertEqual(cleanfilestring("file<>:\"/\\|?*name.txt"), "filename.txt")
        
        # Test multiple spaces
        self.assertEqual(cleanfilestring("file   name.txt"), "file name.txt")
        
        # Test trailing period
        self.assertEqual(cleanfilestring("filename."), "filename")
        
        # Test leading/trailing spaces
        self.assertEqual(cleanfilestring("  filename  .txt  "), "filename.txt")
        
        # Test file without extension
        self.assertEqual(cleanfilestring("filename"), "filename")
        
        # Test empty string
        self.assertEqual(cleanfilestring(""), "")
        
        # Test multiple dots in filename
        self.assertEqual(cleanfilestring("my.file.name.txt"), "my.file.name.txt")
    
    def test_convert_numerals_arabic_western(self):
        # Test basic conversion
        self.assertEqual(convert_numerals_arabic_western("٢٠٢٥٠٥٠٥_١٠٠١٣٧"), "20250505_100137")
        
        # Test mixed text
        self.assertEqual(convert_numerals_arabic_western("IMG_٢٠٢٥.jpg"), "IMG_2025.jpg")
        
        # Test all digits
        self.assertEqual(convert_numerals_arabic_western("٠١٢٣٤٥٦٧٨٩"), "0123456789")
        
        # Test with no Arabic numerals
        self.assertEqual(convert_numerals_arabic_western("test123"), "test123")
        
        # Test empty string
        self.assertEqual(convert_numerals_arabic_western(""), "")
        
        # Test None input
        self.assertIsNone(convert_numerals_arabic_western(None))

if __name__ == '__main__':
    unittest.main()
