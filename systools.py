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

def checkfile(sourcedir, file):
    if not os.path.exists(os.path.join(sourcedir, file)):
        #TODO: add logging
        raise FileNotFoundError(f"File not found: {os.path.join(sourcedir, file)}")
    else:
        return True

# delete empty subdirectories
def rmemptydir(rootdir, dryrun = (False)):

    walk = list(os.walk(rootdir))
    for path, _, _ in walk[::-1]:
        if not (path == rootdir ):
            if len(os.listdir(path)) == 0:
                if dryrun:
                    print('  delete:   ' + path)
                else:
                    try:
                        os.rmdir(path)
                    except OSError as e:
                        True
                        print('  can\'t remove directory: ' + subdir)
            else:
                print(' - skipping: ' + path + ' (not empty)')

def delfile(subdir, file, dryrun):
    #TODO: (low) known problems handling 0 byte files on smb network shares
    if dryrun:
        print(' -  del: ' + file)
    else:
        os.remove((os.path.join(subdir, file)))

def movefile(subdir, file, destdir, nfile, dryrun):
    #TODO: add rights handeling before attempt (gets stuck sometimes when copy but no write access
    dryprint(dryrun, 'Moving file', f'{str(subdir)}/{str(file)}')
    dryprint(dryrun, 'to', f'{str(destdir)}/{str(nfile)}')
    if not dryrun:
        source_path = os.path.join(subdir, file)
        target_path = os.path.join(destdir, nfile)
        
        # Create target directory if it doesn't exist
        os.makedirs(destdir, exist_ok=True)
        
        try:
            os.rename(source_path, target_path)
            print(f"Successfully moved file to {target_path}")
        except FileNotFoundError:
            print(f"ERROR: Source file not found: {source_path}")
        except PermissionError:
            print(f"ERROR: Permission denied. Check file permissions for {source_path} or {destdir}")
            # Try fallback to copy and delete
            try:
                print(f"Attempting copy and delete instead...")
                shutil.copy2(source_path, target_path)
                os.remove(source_path)
                print(f"Successfully copied file to {target_path} and removed original")
            except Exception as e:
                print(f"ERROR: Fallback copy failed: {str(e)}")
        except OSError as e:
            if e.errno == 13:  # Permission denied
                print(f"ERROR: Permission denied. Check file permissions.")
            elif e.errno == 2:  # No such file or directory
                print(f"ERROR: Source or destination path does not exist.")
            elif e.errno == 17:  # File exists
                print(f"ERROR: Target file already exists: {target_path}")
                # Try with a numbered suffix
                try:
                    i = 1
                    base, ext = os.path.splitext(target_path)
                    while os.path.exists(f"{base}_{i}{ext}"):
                        i += 1
                    new_target = f"{base}_{i}{ext}"
                    os.rename(source_path, new_target)
                    print(f"Moved file to {new_target} instead")
                except Exception as e2:
                    print(f"ERROR: Could not create alternative filename: {str(e2)}")
            else:
                print(f"ERROR: Failed to move file: {str(e)}")
        except Exception as e:
            print(f"ERROR: Unexpected error: {str(e)}")

def copyfile(subdir, file, destdir, nfile, dryrun):
    if dryrun:
        print(' - copy: ' + os.path.join(subdir, file))
        print('     to: ' + destdir + "\\" + nfile)
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
                print(' - move: ' + os.path.join(sourcedir, file))
                print('     to: ' + destdir + "\\" + file)
        else:
            files = os.listdir(sourcedir)
            for file in files:
                try:
                    print(' - moving: ' + os.path.join(sourcedir, file))
                    print('       to: ' + destdir + "\\" + file)
                    shutil.move(os.path.join(sourcedir, file), destdir)
                except:
                    #ignore directory already exists error TODO: make more elegant
                    True
    else:
        print('Source not found - skipped: ' + sourcedir)
