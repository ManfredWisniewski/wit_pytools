#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

#   prepare strings to be used correctly in regex expressions (escape special characters)
def prepregex(ostring):
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    nstring = ostring.translate(mapping)
    return nstring

#   clean a file string to remove any characters that might cause invalid file names
def cleanfilestring(file):
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

    return nfile + file_extension
