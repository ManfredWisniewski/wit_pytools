import os
import subprocess
from eliot import start_action, to_file, log_message

from wit_pytools.witpytools import dryprint

def getncpath():
    config = readconfig()
    ncdir = config['WIT PYTOOLS'].get('ncdir')
    return ncdir

def getncfilename(filename):
    return os.path.basename(filename)

def getncfilepath(filename):
    relative_path = filename.replace(getncpath(), '', 1).lstrip(os.path.sep)
    relative_path = relative_path.replace('data/', '', 1)
    return '/' + relative_path.rsplit('/', 1)[0] if '/' in relative_path else '/' + relative_path

#def getncabspath(filename):
#    ncpath = getncpath()
#    return os.path.join(ncpath, 'data', filename)

#def getncabsdir(filename):
#    ncpath = getncpath()
#    abspath = os.path.join(ncpath, 'data', filename)
#    return os.path.dirname(abspath)

def ncdelfile(ncfile):
    dryprint(dryrun, 'occ delete: ' + ncfile)
    if not dryrun:
        with start_action(action_type=f"occ delete file {ncfile}"):
            try:
                #TODO variable nextcloudpath
                subprocess.run(
                    f'php /var/www/nextcloud/occ files:delete "{ncfile}"',
                    capture_output=True,
                    shell=True,
                    text=True,
                    check=True
                )
            except:
                #ignore directory already exists error TODO: make more elegant
                True
    else:
        pass

def ncmovefile(subdir, file, destdir, nfile, dryrun):
    dryprint(dryrun, 'occ move: ' + os.path.join(subdir, file))
    dryprint(dryrun, 'to: ' + os.path.join(destdir, nfile))
    if not dryrun:
        with start_action(action_type=f"occ moving file {os.path.join(subdir, file)} to {os.path.join(destdir, nfile)}"):
            try:
                #TODO variable nextcloudpath
                subprocess.run(
                    f'php /var/www/nextcloud/occ files:move "{os.path.join(subdir, file)}" "{os.path.join(destdir, nfile)}"',
                    capture_output=True,
                    shell=True,
                    text=True,
                    check=True
                )
            except:
                #ignore directory already exists error TODO: make more elegant
                True
            try:
                #TODO variable nextcloudpath
                subprocess.run(
                    f'php /var/www/nextcloud/occ files:move "{os.path.join(subdir, file)}" "{os.path.join(destdir, nfile)}"',
                    capture_output=True,
                    shell=True,
                    text=True,
                    check=True
                )
            except:
                #ignore directory already exists error TODO: make more elegant
                True
            try:
                #TODO variable nextcloudpath
                subprocess.run(
                    f'php /var/www/nextcloud/occ files:move "{os.path.join(subdir, file)}" "{os.path.join(destdir, nfile)}"',
                    capture_output=True,
                    shell=True,
                    text=True,
                    check=True
                )
            except:
                #ignore directory already exists error TODO: make more elegant
                True

def ncscandir(targetdir):
    scan_result = subprocess.run(
        f'php /var/www/nextcloud/occ files:scan --path="{targetdir}" --quiet',
        capture_output=True,
        shell=True,
        text=True
    )
    if scan_result.returncode != 0:
        log_message(f"Warning: Folder rescan failed: {scan_result.stderr}")

# def nccopyfile(subdir, file, destdir, nfile, dryrun):
#     if dryrun:
#         print(' - copy: ' + os.path.join(subdir, file))
#         print('     to: ' + os.path.join(destdir, nfile))
#     else:
#         try:
#             #os.rename((os.path.join(subdir, file)), (destdir + "/" + nfile))
#             shutil.copy(os.path.join(subdir, file), os.path.join(destdir, nfile))
#         except:
#             #ignore directory already exists error TODO: make more elegant
#             True

# def ncmoveallfiles(sourcedir, destdir, dryrun):
#     if os.path.isdir(sourcedir):
#         if dryrun:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 print(' - move: ' + os.path.join(sourcedir, file))
#                 print('     to: ' + os.path.join(destdir, file))
#         else:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 try:
#                     print(' - moving: ' + os.path.join(sourcedir, file))
#                     print('       to: ' + os.path.join(destdir, file))
#                     shutil.move(os.path.join(sourcedir, file), destdir)
#                 except:
#                     #ignore directory already exists error TODO: make more elegant
#                     True
#     else:
#         print('Source not found - skipped: ' + sourcedir)
