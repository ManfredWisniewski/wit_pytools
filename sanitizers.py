#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from typing import Optional

#   prepare strings to be used correctly in regex expressions (escape special characters)
def prepregex(ostring):
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    nstring = ostring.translate(mapping)
    return nstring

#   clean a file string to remove any characters that might cause invalid file names
def cleanfilestring(file):
    # Handle empty string case
    if not file:
        return file
        
    nfile, file_extension = os.path.splitext(file)
    # Remove invalid characters from filename
    invalid_chars = r'[<>:"/\\|?*]'
    nfile = re.sub(invalid_chars, '', nfile)
    # Replace multiple spaces with single space
    nfile = re.sub(r'\s+', ' ', nfile.rstrip())
    # Remove last character period
    nfile = nfile.rstrip('.')
    # Remove leading and trailing spaces
    nfile = nfile.strip()
    
    # Only add extension if it's not just a period
    if file_extension and file_extension != '.':
        return (nfile + file_extension).strip()
    return nfile.strip()


def convert_numerals_arabic_western(text: str) -> Optional[str]:
    """Convert Arabic numerals to Western numerals.
    
    Args:
        text: String containing Arabic numerals
        
    Returns:
        String with Arabic numerals converted to Western numerals,
        or None if input is None
    """
    if text is None:
        return None
        
    # Mapping of Arabic numerals to Western numerals
    arabic_to_western = {
        '٠': '0',
        '١': '1', 
        '٢': '2',
        '٣': '3',
        '٤': '4',
        '٥': '5',
        '٦': '6',
        '٧': '7',
        '٨': '8',
        '٩': '9'
    }
    
    # Replace each Arabic numeral with its Western equivalent
    result = text
    for arabic, western in arabic_to_western.items():
        result = result.replace(arabic, western)
        
    return result
