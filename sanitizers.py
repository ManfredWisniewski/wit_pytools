#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import unicodedata
from typing import Optional


INVALID_PATH_CHARS = set('<>:"/\\|?*')


TRANSLITERATION_MAP = {
    'ß': 'ss',
}


def sanitize_path(value: str) -> str:
    """Normalize a string for safe filesystem usage."""

    if value is None:
        return ""

    cleaned = "".join('_' if ch in INVALID_PATH_CHARS else ch for ch in value)
    normalized = unicodedata.normalize("NFKD", cleaned)

    ascii_chars = []
    for ch in normalized:
        if unicodedata.combining(ch):
            continue
        replacement = TRANSLITERATION_MAP.get(ch)
        if replacement is not None:
            ascii_chars.append(replacement)
            continue
        if ch.isascii():
            ascii_chars.append(ch)
        else:
            ascii_chars.append('_')

    cleaned = "".join(ascii_chars)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().strip('.').strip()

# whitespace normalization helper
def normalize_spaces(value: Optional[str]) -> str:
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', value).strip()


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
    nfile = normalize_spaces(nfile.rstrip())
    # Remove last character period
    nfile = nfile.rstrip('.')
    # Remove leading and trailing spaces
    nfile = nfile.strip()
    
    # Only add extension if it's not just a period
    if file_extension and file_extension != '.':
        return normalize_spaces(nfile + file_extension)
    return normalize_spaces(nfile)


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
