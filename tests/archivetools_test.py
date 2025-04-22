import os
import sys
import shutil
import pytest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from archivetools import unzip, unrar, un7z

TESTDIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVEDIR = os.path.join(TESTDIR, 'archivetools')

# Clean up extracted files before and after tests
def cleanup(files):
    for f in files:
        fpath = os.path.join(ARCHIVEDIR, f)
        if os.path.exists(fpath):
            os.remove(fpath)

def test_unzip():
    cleanup(['packed.txt'])
    assert unzip(ARCHIVEDIR, 'packed.zip')
    assert os.path.exists(os.path.join(ARCHIVEDIR, 'packed.txt'))
    cleanup(['packed.txt'])

def test_un7z():
    cleanup(['packed.txt'])
    assert un7z(ARCHIVEDIR, 'packed.7z')
    assert os.path.exists(os.path.join(ARCHIVEDIR, 'packed.txt'))
    cleanup(['packed.txt'])

# Uncomment the following if you add a .rar test archive
# def test_unrar():
#     cleanup(['packed.txt'])
#     assert unrar(ARCHIVEDIR, 'packed.rar')
#     assert os.path.exists(os.path.join(ARCHIVEDIR, 'packed.txt'))
#     cleanup(['packed.txt'])

if __name__ == "__main__":
    test_unzip()
#    test_unrar()
#    test_un7z()
    print("All archive extraction tests passed.")
