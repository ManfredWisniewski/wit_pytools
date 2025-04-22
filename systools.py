import os, shutil

# Helper function for dry run printing
def dryprint(dryrun, *args):
    if dryrun:
        print(*args)

# https://gist.github.com/TheMatt2/faf5ca760c61a267412c46bb977718fa
def walklevel(path, depth = 1):
    if depth < 0:
        for root, dirs, files in os.walk(path):
            yield root, dirs[:], files
        return
    elif depth == 0:
        return

    base_depth = path.rstrip(os.path.sep).count(os.path.sep)
    for root, dirs, files in os.walk(path):
        yield root, dirs[:], files
        cur_depth = root.count(os.path.sep)
        if base_depth + depth <= cur_depth:
            del dirs[:]

from eliot import log_message

def checkfile(sourcedir, file):
    filepath = os.path.join(sourcedir, file)
    if not os.path.exists(filepath):
        log_message(f"File not found: {filepath}")
        raise FileNotFoundError(f"File not found: {filepath}")
    else:
        log_message(f"File exists: {filepath}")
        return True

# delete empty subdirectories
def rmemptydir(rootdir, dryrun = (False)):
    walk = list(os.walk(rootdir))
    for path, _, _ in walk[::-1]:
        if not (path == rootdir ):
            if len(os.listdir(path)) == 0:
                if dryrun:
                    print('  delete:   ' + path)
                    log_message(f"Would delete empty directory: {path}")
                else:
                    try:
                        os.rmdir(path)
                        log_message(f"Deleted empty directory: {path}")
                    except OSError as e:
                        log_message(f"Can't remove directory: {path}, error: {str(e)}")
                        print('  can\'t remove directory: ' + path)
            else:
                print(' - skipping: ' + path + ' (not empty)')
                log_message(f"Skipping non-empty directory: {path}")

def delfile(subdir, file, dryrun=False):
    #TODO: (low) known problems handling 0 byte files on smb network shares
    if dryrun:
        print(' -  del: ' + file)
    else:
        os.remove((os.path.join(subdir, file)))

def movefile(subdir, file, destdir, nfile, dryrun=False):
    #TODO: add rights handeling before attempt (gets stuck sometimes when copy but no write access
    if not dryrun:
        # Check for null bytes in arguments and remove them if found
        args = [subdir, file, destdir, nfile]
        cleaned_args = []
        for arg in args:
            if '\x00' in str(arg):
                log_message(f"ERROR: Null byte detected and removed in argument: {arg!r}")
                arg = str(arg).replace('\x00', '')
            cleaned_args.append(arg)
        subdir, file, destdir, nfile = cleaned_args
        
        source_path = os.path.join(subdir, file)
        target_path = os.path.join(destdir, nfile)
        log_message(f"movefile: source_path={source_path}, target_path={target_path}")
        
        # Create target directory if it doesn't exist
        os.makedirs(destdir, exist_ok=True)
        
        try:
            os.rename(source_path, target_path)
            log_message(f"Successfully moved file to {target_path}")
        except FileNotFoundError:
            log_message(f"ERROR: Source file not found: {source_path}")
        except PermissionError:
            log_message(f"ERROR: Permission denied. Check file permissions for {source_path} or {destdir}")
            # Try fallback to copy and delete
            try:
                log_message(f"Attempting copy and delete instead...")
                shutil.copy2(source_path, target_path)
                os.remove(source_path)
                log_message(f"Successfully copied file to {target_path} and removed original")
            except Exception as e:
                log_message(f"ERROR: Fallback copy failed: {str(e)}")
        except OSError as e:
            if e.errno == 13:  # Permission denied
                log_message(f"ERROR: Permission denied. Check file permissions.")
            elif e.errno == 2:  # No such file or directory
                log_message(f"ERROR: Source or destination path does not exist.")
            elif e.errno == 17:  # File exists
                log_message(f"ERROR: Target file already exists: {target_path}")
                # Try with a numbered suffix
                try:
                    i = 1
                    base, ext = os.path.splitext(target_path)
                    while os.path.exists(f"{base}_{i}{ext}"):
                        i += 1
                    new_target = f"{base}_{i}{ext}"
                    os.rename(source_path, new_target)
                    log_message(f"Moved file to {new_target} instead")
                except Exception as e2:
                    log_message(f"ERROR: Could not create alternative filename: {str(e2)}")
            else:
                log_message(f"ERROR: Failed to move file: {str(e)}")
        except Exception as e:
            log_message(f"ERROR: Unexpected error: {str(e)}")

def copyfile(subdir, file, destdir, nfile, dryrun):
    if dryrun:
        log_message(f"Would copy file: {os.path.join(subdir, file)} to {os.path.join(destdir, nfile)}")
    else:
        try:
            #os.rename((os.path.join(subdir, file)), (destdir + "/" + nfile))
            shutil.copy(os.path.join(subdir, file), destdir + "/" + nfile)
        except:
            #ignore directory already exists error TODO: make more elegant
            True

# Pathlib: https://stackoverflow.com/questions/41826868/moving-all-files-from-one-directory-to-another-using-python
def moveallfiles(sourcedir, destdir, dryrun):
    if os.path.isdir(sourcedir):
        if dryrun:
            files = os.listdir(sourcedir)
            for file in files:
                log_message(f"Would move file: {os.path.join(sourcedir, file)} to {os.path.join(destdir, file)}")
        else:
            files = os.listdir(sourcedir)
            for file in files:
                try:
                    log_message(f"Moving file: {os.path.join(sourcedir, file)} to {os.path.join(destdir, file)}")
                    shutil.move(os.path.join(sourcedir, file), destdir)
                except:
                    #ignore directory already exists error TODO: make more elegant
                    True
    else:
        log_message(f"Source not found - skipped: {sourcedir}")
