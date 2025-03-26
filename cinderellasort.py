import os, re, sys
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path
from wit_pytools.mailtools import *
from wit_pytools.systools import walklevel, rmemptydir, movefile

dryrun = (True)

time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
config_object = ConfigParser()

# check for valid searches in subdirectories of the target directory
def isvalidsort(sourcedir, ftype_sort):
    # check if multiple tables are matched
    checkvalid = False
    for subdir, dirs, files in walklevel(sourcedir, 2):
        for file in files:
            for ftype in ftype_sort.split(','):
                if file.casefold().endswith(ftype):
                    checkvalid = True
    if checkvalid:
        return True
    #else:
    #    print('## Directory [' + sourcedir + '] contains none of the sorted file types [' + ftype_sort + ']\n## EXIT CinderellaSort')

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


def cmovefile(sourcedir, file, targetdir, nfile, filemode, dryrun):
    if filemode == 'os':
        movefile(sourcedir, file, targetdir, nfile, dryrun)
    elif filemode == 'nc':
        ncmovefile(sourcedir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)


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

def handlefile(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, filemode, dryrun):
    for ftype in ftype_sort.split(','):
        ftype = ftype.strip().casefold()
        if ftype == '.msg':
            # Special handling for .msg files
            if dryrun:
                print(f" - Special handling for MSG file: {file.name}")
            else:
                try:
                    maildata = parse_msg(os.path.join(sourcedir, file.name), True)
                    project_name = "afsaf"
                    if maildata:
                        print(maildata[0]+'_'+maildata[1]+'_'+project_name+'_'+maildata[2])  # Print only the date
                    else:
                        print("No mail information available.")
                    nfile = cleanfilestring(file.name, clean, clean_nocase)
                    cmovefile(sourcedir, file, targetdir + bowldir(nfile, config_object), nfile, filemode, dryrun)
                except Exception as e:
                    print(f"Error handling MSG file {file.name}: {e}")
        else:
            # Default behavior for other file types
            nfile = cleanfilestring(file.name, clean, clean_nocase)
            cmovefile(sourcedir, file.name, targetdir + bowldir(nfile, config_object), nfile, filemode, dryrun)
        
        # File has been handled, so we can break the loop
        break

    # If the loop completes without breaking, the file didn't match any specified type
    else:
        print(f" - Skipping file {file.name}: not a specified type")

def cinderellasort(configfile, dryrun = (False)):
    files = ""
    config_object.read(configfile, encoding='utf-8')
    table = config_object["TABLE"]
    sourcedir = (table["sourcedir"])
    targetdir = (table["targetdir"])
    ftype_sort = (table["ftype_sort"].casefold())
    ftype_delete = (table["ftype_delete"].casefold())
    clean = (table["clean"])
    clean_nocase = (table["clean_nocase"].casefold())
    trash = (table['trash'])
    trash_nocase = (table['trash_nocase'].casefold())
    filemode = (table['filemode'].casefold())

    print('\n###########################################')
    print('## START CinderellaSort ' + time)
    print(' # from: ' + sourcedir)
    print(' # to:   ' + targetdir)
    print(' # mode: ' + filemode)
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

    # Handle files directly in sourcedir
    for item in Path(sourcedir).iterdir():
        if item.is_file():
            handlefile(item, sourcedir, targetdir, ftype_sort, clean, clean_nocase, filemode, dryrun)

    # Process subdirectories in sourcedir
    dirlist = [f for f in Path(sourcedir).resolve().glob('**/*') if f.is_dir()]
    print(dirlist)
    for maindir in dirlist:
        if isvalidsort(str(maindir), ftype_sort):
            print(' #  valid sort found:' + ftype_delete)
            for subdir, dirs, files in walklevel(str(maindir), 2):
                #TODO replace with handlefile()
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
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
                elif len(files) > 1:
                    for file in files:
                        nfile = cleanfilestring(file, clean, clean_nocase)
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
        else:
            print(' #  No valid sort found!') 

#    print(f"\n## Removing empty directories:")
#    rmemptydir(sourcedir,dryrun)