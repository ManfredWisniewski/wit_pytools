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
        log_message(f"checkfile: File not found: {filepath}", level="INFO")
        raise FileNotFoundError(f"File not found: {filepath}")
    else:
        log_message(f"checkfile: File exists: {filepath}", level="INFO")
        return True

# delete empty subdirectories
def rmemptydir(rootdir, dryrun = (False)):
    walk = list(os.walk(rootdir))
    for path, _, _ in walk[::-1]:
        if not (path == rootdir ):
            if len(os.listdir(path)) == 0:
                if dryrun:
                    print('  delete:   ' + path)
                    log_message(f"Would delete empty directory: {path}", level="INFO")
                else:
                    try:
                        os.rmdir(path)
                        log_message(f"Deleted empty directory: {path}", level="INFO")
                    except OSError as e:
                        log_message(f"Can't remove directory: {path}, error: {str(e)}", level="ERROR")
            else:
                log_message(f"Skipping non-empty directory: {path}", level="INFO")

def delfile(subdir, file, dryrun=False):
    #TODO: (low) known problems handling 0 byte files on smb network shares
    if dryrun:
        print(' -  del: ' + file)
    else:
        os.remove((os.path.join(subdir, file)))

def movefile(subdir, file, destdir, nfile, overwrite=False, dryrun=False):
    #TODO: add rights handeling before attempt (gets stuck sometimes when copy but no write access
    print('OVERWRITE: ' + str(overwrite))
    if not dryrun:
        # Check for null bytes in arguments and remove them if found
        args = [subdir, file, destdir, nfile]
        cleaned_args = []
        for arg in args:
            if '\x00' in str(arg):
                log_message(f"ERROR: Null byte detected and removed in argument: {arg!r}", level="INFO")
                arg = str(arg).replace('\x00', '')
            arg = str(arg).rstrip()
            cleaned_args.append(arg)
        subdir, file, destdir, nfile = cleaned_args
        
        source_path = os.path.join(subdir, file)
        target_path = os.path.join(destdir, nfile)
        log_message(f"movefile: source_path={source_path}, target_path={target_path}", level="INFO")

        # Create target directory if it doesn't exist
        os.makedirs(destdir, exist_ok=True)

        try:
            # Check if target file already exists
            #TODO add test for this case
            if not overwrite and os.path.exists(target_path):
                # Add enumerator and move file
                i = 2
                base, ext = os.path.splitext(target_path)
                while os.path.exists(f"{base}#{i}{ext}"):
                    i += 1
                new_target = f"{base}#{i}{ext}"
                try:
                    shutil.copy2(source_path, new_target)
                    os.remove(source_path)
                    log_message(f"Copied file to {new_target} and removed original", level="INFO")
                except Exception as e2:
                    log_message(f"ERROR: Could not copy to enumerated filename: {str(e2)}", level="ERROR")
            else:
                if overwrite and os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(source_path, target_path)
                log_message(f"Successfully moved file to {target_path}", level="INFO")
        except FileNotFoundError:
            log_message(f"ERROR: Source file not found: {source_path}", level="ERROR")
        except PermissionError:
            log_message(f"ERROR: Permission denied. Check file permissions for {source_path} or {destdir}", level="ERROR")
            # Try fallback to copy and delete
            try:
                log_message(f"Attempting copy and delete instead...", level="INFO")
                shutil.copy2(source_path, target_path)
                os.remove(source_path)
                log_message(f"Successfully copied file to {target_path} and removed original", level="INFO")
            except Exception as e:
                log_message(f"ERROR: Fallback copy failed: {str(e)}", level="ERROR")
        except OSError as e:
            if e.errno == 13:  # Permission denied
                log_message(f"ERROR: Permission denied. Check file permissions.", level="ERROR")
            elif e.errno == 2:  # No such file or directory
                log_message(f"ERROR: Source or destination path does not exist.", level="ERROR")
            elif e.errno == 17:  # File exists
                log_message(f"ERROR: Target file already exists: {target_path}", level="WARNING")
            else:
                log_message(f"ERROR: Failed to move file: {str(e)}", level="ERROR")
        except Exception as e:
            log_message(f"ERROR: Unexpected error: {str(e)}", level="ERROR")

def copyfile(subdir, file, destdir, nfile, overwrite=False, dryrun=False):
    """
    Copy a file from subdir/file to destdir/nfile with error handling and overwrite option.
    Does not remove the original file.
    """
    if dryrun:
        log_message(f"Would copy file: {os.path.join(subdir, file)} to {os.path.join(destdir, nfile)}", level="INFO")
        return
    # Clean null bytes and whitespace from arguments
    args = [subdir, file, destdir, nfile]
    cleaned_args = []
    for arg in args:
        if '\x00' in str(arg):
            log_message(f"ERROR: Null byte detected and removed in argument: {arg!r}", level="INFO")
            arg = str(arg).replace('\x00', '')
        arg = str(arg).rstrip()
        cleaned_args.append(arg)
    subdir, file, destdir, nfile = cleaned_args
    source_path = os.path.join(subdir, file)
    target_path = os.path.join(destdir, nfile)
    log_message(f"copyfile: source_path={source_path}, target_path={target_path}", level="INFO")
    os.makedirs(destdir, exist_ok=True)
    try:
        if not overwrite and os.path.exists(target_path):
            # Add enumerator to filename
            i = 2
            base, ext = os.path.splitext(target_path)
            while os.path.exists(f"{base}#{i}{ext}"):
                i += 1
            new_target = f"{base}#{i}{ext}"
            try:
                shutil.copy2(source_path, new_target)
                log_message(f"Copied file to {new_target}", level="INFO")
            except Exception as e2:
                log_message(f"ERROR: Could not copy to enumerated filename: {str(e2)}", level="ERROR")
        else:
            if overwrite and os.path.exists(target_path):
                os.remove(target_path)
            shutil.copy2(source_path, target_path)
            log_message(f"Successfully copied file to {target_path}", level="INFO")
    except FileNotFoundError:
        log_message(f"ERROR: Source file not found: {source_path}", level="ERROR")
    except PermissionError:
        log_message(f"ERROR: Permission denied. Check file permissions for {source_path} or {destdir}", level="ERROR")
    except OSError as e:
        if e.errno == 13:
            log_message(f"ERROR: Permission denied. Check file permissions.", level="ERROR")
        elif e.errno == 2:
            log_message(f"ERROR: Source or destination path does not exist.", level="ERROR")
        elif e.errno == 17:
            log_message(f"ERROR: Target file already exists: {target_path}", level="WARNING")
        else:
            log_message(f"ERROR: Failed to copy file: {str(e)}", level="ERROR")
    except Exception as e:
        log_message(f"ERROR: Unexpected error: {str(e)}", level="ERROR")


# Pathlib: https://stackoverflow.com/questions/41826868/moving-all-files-from-one-directory-to-another-using-python
def moveallfiles(sourcedir, destdir, dryrun):
    if os.path.isdir(sourcedir):
        if dryrun:
            files = os.listdir(sourcedir)
            for file in files:
                log_message(f"Would move file: {os.path.join(sourcedir, file)} to {os.path.join(destdir, file)}", level="INFO")
        else:
            files = os.listdir(sourcedir)
            for file in files:
                try:
                    log_message(f"Moving file: {os.path.join(sourcedir, file)} to {os.path.join(destdir, file)}", level="INFO")
                    shutil.move(os.path.join(sourcedir, file), destdir)
                except:
                    #ignore directory already exists error TODO: make more elegant
                    True
    else:
        log_message(f"Source not found - skipped: {sourcedir}")
