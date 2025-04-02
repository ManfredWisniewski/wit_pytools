import os
import subprocess
from eliot import start_action, to_file, log_message

from wit_pytools.witpytools import dryprint

#def ncdelfile(subdir, file, dryrun):
#    if dryrun:
#        print(' -  del: ' + file)
#    else:
#        os.remove((os.path.join(subdir, file)))

def ncmovefile(subdir, file, destdir, nfile, dryrun):
    dryprint(dryrun, 'occ move: ' + os.path.join(subdir, file))
    dryprint(dryrun, 'to: ' + destdir + "\\" + nfile)
    if not dryrun:
        with start_action(action_type=f"occ moving file {os.path.join(subdir, file)} to {destdir + '\\' + nfile}"):
            try:
                #TODO variable nextcloudpath
                subprocess.run(
                    f'php /var/www/nextcloud/occ files:move "{subdir}/{file}" "{destdir}/{file}"',
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
#         print('     to: ' + destdir + "\\" + nfile)
#     else:
#         try:
#             #os.rename((os.path.join(subdir, file)), (destdir + "/" + nfile))
#             shutil.copy(os.path.join(subdir, file), destdir + "/" + nfile)
#         except:
#             #ignore directory already exists error TODO: make more elegant
#             True

# def ncmoveallfiles(sourcedir, destdir, dryrun):
#     if os.path.isdir(sourcedir):
#         if dryrun:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 print(' - move: ' + os.path.join(sourcedir, file))
#                 print('     to: ' + destdir + "\\" + file)
#         else:
#             files = os.listdir(sourcedir)
#             for file in files:
#                 try:
#                     print(' - moving: ' + os.path.join(sourcedir, file))
#                     print('       to: ' + destdir + "\\" + file)
#                     shutil.move(os.path.join(sourcedir, file), destdir)
#                 except:
#                     #ignore directory already exists error TODO: make more elegant
#                     True
#     else:
#         print('Source not found - skipped: ' + sourcedir)
