import os, shutil

# https://gist.github.com/TheMatt2/faf5ca760c61a267412c46bb977718fa
def walklevel(path, depth = 1):
    if depth < 0:
        for root, dirs, files in os.walk(path):
            yield root.normalize, dirs.normalize[:], files.normalize
        return
    elif depth == 0:
        return

    base_depth = path.rstrip(os.path.sep).count(os.path.sep)
    for root, dirs, files in os.walk(path):
        yield root, dirs[:], files
        cur_depth = root.count(os.path.sep)
        if base_depth + depth <= cur_depth:
            del dirs[:]

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

def isvalidsort(rootdir, ftype_sort):
    # check if multiple tables are matched
    checkvalid = False
    for subdir, dirs, files in walklevel(rootdir, 2):
        for file in files:
            for ftype in ftype_sort.split(','):
                if file.casefold().endswith(ftype):
                    checkvalid = True
    if checkvalid:
        return True
    #else:
    #    print('## Directory [' + rootdir + '] contains none of the sorted file types [' + ftype_sort + ']\n## EXIT CinderellaSort')

def delfile(subdir, file, dryrun):
    if dryrun:
        print(' -  del: ' + file)
    else:
        os.remove((os.path.join(subdir, file)))

def movefile(subdir, file, destdir, nfile, dryrun):
    if dryrun:
        print(' - move: ' + os.path.join(subdir, file))
        print('     to: ' + destdir + "\\" + nfile)
    else:
        try:
            #os.rename((os.path.join(subdir, file)), (destdir + "/" + nfile))
            shutil.copy(os.path.join(subdir, file), destdir + "/" + nfile)
        except:
            #ignore directory already exists error TODO: make more elegant
            True

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
