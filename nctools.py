import os
import subprocess
from eliot import start_action, to_file, log_message

OCC = os.environ.get('WIT_NC_OCC', '/var/www/nextcloud/occ')


def _occ(*args):
    """Run an occ command with argv list (no shell)."""
    return subprocess.run(
        ['php', OCC, *args],
        capture_output=True,
        text=True
    )


def getncroot():
    config = readconfig()
    ncdir = config['WIT PYTOOLS'].get('ncdir')
    return ncdir

def getncfilename(filename):
    return os.path.basename(filename)

# Returns the nextcloud relative file path from an absolute path without leading slash
def getncpath(abspath):
    import re
    ncpath = re.sub(r'^.*?/data', '', abspath)
    ncpath = ncpath.lstrip('/')
    return ncpath

# Returns the nextcloud relative directory path from an absolute path without leading slash
def getncdir(abspath):
    import re
    ncpath = re.sub(r'^.*?/data', '', abspath)
    ncpath = ncpath.lstrip('/')
    return os.path.dirname(ncpath)

def ncdelfile(ncfile):
    with start_action(action_type=f"occ delete file {ncfile}"):
        try:
            _occ('files:delete', ncfile)
        except subprocess.CalledProcessError:
            #ignore directory already exists error TODO: make more elegant
            True

def ncmovefile(ncfile, ncdest):
    with start_action(action_type=f"ncmovefile: moving file {ncfile} to {ncdest}", level="INFO"):
        log_message(f"ncmovefile: moving {ncfile} -> {ncdest}", level="DEBUG")
        result = _occ('files:move', ncfile, ncdest)
        if result.returncode != 0:
            log_message(
                f"ncmovefile ERROR: returncode={result.returncode}, stdout={result.stdout.strip()}, stderr={result.stderr.strip()}",
                level="ERROR"
            )
            raise RuntimeError(f"Nextcloud move failed for {ncfile} -> {ncdest}")
        else:
            log_message(
                f"ncmovefile OK: returncode={result.returncode}, stdout={result.stdout.strip()}",
                level="INFO"
            )

def ncscandir(targetdir):
    scan_result = _occ('files:scan', f'--path={targetdir}', '--quiet')
    if scan_result.returncode != 0:
        log_message(f"Warning: Folder rescan failed: {scan_result.stderr}")

# Assigns a tag to a file or directory in Nextcloud with specified access level (defaults to public)
# nextcloud tag access levels: public, restricted, invisible
def nctagassign(target, tagname, access="public"):
    scan_result = _occ(
        'files:tag:assign',
        f'--path={target}', f'--tag={tagname}', f'--access={access}')
    if scan_result.returncode != 0:
        log_message(f"Warning: Tag assignment failed: {scan_result.stderr}")

# Removes a tag from a file or directory in Nextcloud
def nctagremove(target, tagname):
    scan_result = _occ(
        'files:tag:remove', f'--path={target}', f'--tag={tagname}')
    if scan_result.returncode != 0:
        log_message(f"Warning: Tag removal failed: {scan_result.stderr}")

def nctagedit(target, tagname, newtagname):
    scan_result = _occ(
        'files:tag:edit',
        f'--path={target}', f'--tag={tagname}', f'--new-tag={newtagname}')
    if scan_result.returncode != 0:
        log_message(f"Warning: Tag edit failed: {scan_result.stderr}")
