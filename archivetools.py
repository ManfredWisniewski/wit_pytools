import os
from zipfile import ZipFile
#import rarfile
import py7zr
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from systools import checkfile

def unzip(sourcedir, zipfile, targetdir=None):
    """Extract a zip file to the target directory. If targetdir is None, extract to sourcedir."""
    if not checkfile(sourcedir, zipfile):
        raise FileNotFoundError(f"File not found: {os.path.join(sourcedir, zipfile)}")
    if targetdir is None:
        targetdir = sourcedir
    zip_path = os.path.join(sourcedir, zipfile)
    with ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(targetdir)
    return True

def unrar(sourcedir, rarfile_name, targetdir=None):
    """Extract a rar file to the target directory. If targetdir is None, extract to sourcedir."""
    if not checkfile(sourcedir, rarfile_name):
        raise FileNotFoundError(f"File not found: {os.path.join(sourcedir, rarfile_name)}")
    if targetdir is None:
        targetdir = sourcedir
    rar_path = os.path.join(sourcedir, rarfile_name)
    with rarfile.RarFile(rar_path) as rf:
        rf.extractall(targetdir)
    return True

def un7z(sourcedir, sevenzfile, targetdir=None):
    """Extract a 7z file to the target directory. If targetdir is None, extract to sourcedir."""
    if not checkfile(sourcedir, sevenzfile):
        raise FileNotFoundError(f"File not found: {os.path.join(sourcedir, sevenzfile)}")
    if targetdir is None:
        targetdir = sourcedir
    sevenz_path = os.path.join(sourcedir, sevenzfile)
    with py7zr.SevenZipFile(sevenz_path, mode='r') as archive:
        archive.extractall(path=targetdir)
    return True

