import os, re, sys
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path

dryrun = (True)
logtofile = (False)

time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
config_object = ConfigParser()

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

def matchstring(file, matchtable=''):
    if len(matchtable) > 0:
        found = False
        for matchstring in matchtable.split(','):
            if matchstring in file:
                #print('Matchstring: ' + matchstring)
                found = True
        return True if found else False

def bowldir(file, config_object=''):
    if len(config_object) > 0:
        if config_object.has_section("BOWLS"):
            found = False
            for (bowl, critlist) in config_object.items("BOWLS"):
                for crit in critlist.split(','):
                    if crit in file and not found:
                        return '\\' + bowl
            return ''

def cmovefile(subdir, file, destdir, nfile, dryrun):
    if osmode == 'os':
        movefile(subdir, file, destdir + bowldir(nfile, config_object), nfile, dryrun)
    elif osmode == 'nc':
        ncmovefile(subdir, file, destdir + bowldir(nfile, config_object), nfile, dryrun)


#   prepare strings to be used correctly in regex expressions (escape special characters)
def prepregex(ostring):
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    nstring = ostring.translate(mapping)
    return nstring

def cleanfilestring(file, clean, clean_nocase, subdir=''):
    filename, file_extension = os.path.splitext(os.path.join(subdir, file))
    if len(subdir) > 0:
        nfile = os.path.basename(subdir)
    else:
        nfile = filename
    #print('filename: ' + nfile)
    # case-sensitive remove strings from removelist
    for rstring in clean.split(','):
        rstring = prepregex(rstring)
        nfile = nfile.replace(rstring, '')
    # ignore case remove strings from removelist
    for rstring in clean_nocase.split(','):
        rstring = prepregex(rstring)
        #print(rstring)
        #print(nfile)
        nfile = re.sub(rstring,'', nfile, flags=re.IGNORECASE)
        #print(nfile)
    nfile = nfile.replace('.', ' ')
    nfile = nfile.replace('_', ' ')
    # replace multiple spaces with single space
    nfile = re.sub(r'\s+', ' ', nfile.rstrip())
    print('### result: ' + nfile)
    return os.path.join(nfile.strip() + file_extension)

def cinderellasort(configfile, dryrun = (False), logtofile = (True)):
    if logtofile:
        sys.stdout = open('nounasort.log', 'a')
    files = ""
    config_object.read(configfile, encoding='utf-8')
    table = config_object["TABLE"]
    rootdir = (table["rootdir"])
    destdir = (table["destdir"])
    ftype_sort = (table["ftype_sort"].casefold())
    ftype_delete = (table["ftype_delete"].casefold())
    clean = (table["clean"])
    clean_nocase = (table["clean_nocase"].casefold())
    trash = (table['trash'])
    trash_nocase = (table['trash_nocase'].casefold())
    osmode = (table['osmode'].casefold())


    print('\n###########################################')
    print('## START CinderellaSort ' + time)
    print(' # from: ' + rootdir)
    print(' # to:   ' + destdir)
    print(' # mode: ' + destdir)
    if dryrun:
        print('\n     ##  DRYRUN  ##\n')
    print('## Settings ' + configfile + ':')
    print(' # sort: ' + ftype_sort)
    print(' #  del: ' + ftype_delete)

    # ADD CHECK SETTINGS (directories etc.)
    # ADD SAFETY CHECK or fix: no empty criteria (comma at end of list or empty list)
    # ADD verify ini file
    # ADD check if subdirectory
    # ADD unzip
    # CHECK _unpack dir
    # CHECK SORT Lists for ,, and < 2

    dirlist = [f for f in Path(rootdir).resolve().glob('**/*') if f.is_dir()]
    print(dirlist)
    for maindir in dirlist:
        if isvalidsort(str(maindir), ftype_sort):
            print(' #  valid sort found:' + ftype_delete)
            for subdir, dirs, files in walklevel(str(maindir), 2):
                for file in files:
                    # print('# remove unwanted filetypes')
                    for ftype in ftype_delete.split(','):
                        if file.casefold().endswith(ftype.strip()):
                            delfile(subdir, file, dryrun)
                    # print('# removing files that match trash')
                    for ftype in ftype_sort.split(','):
                        if matchstring(file, trash) and file.casefold().endswith(ftype.strip()):
                            delfile(subdir, file, dryrun)
                        if matchstring(file.casefold(), trash_nocase) and file.casefold().endswith(ftype.strip()):
                            # print('del: ' + file)
                            delfile(subdir, file, dryrun)

                if len(files) == 1:
                    # add configure option
                    # TEST what if MULTIPLE files in -subdirs-
                    for file in files:
                        nfile = cleanfilestring(file, clean, clean_nocase, subdir)
                        movefile(subdir, file, destdir + bowldir(nfile, config_object), nfile, dryrun)
                elif len(files) > 1:
                    for file in files:
                        nfile = cleanfilestring(file, clean, clean_nocase)
                        movefile(subdir, file, destdir + bowldir(nfile, config_object), nfile, dryrun)
        else:
            print(' #  No valid sort found!') 

#    print(f"\n## Removing empty directories:")
#    rmemptydir(rootdir,dryrun)

    print("\n## END CinderellaSort ##")
    if logtofile:
        sys.stdout.close()
