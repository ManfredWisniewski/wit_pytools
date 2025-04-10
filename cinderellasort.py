import os, re, sys
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path
from wit_pytools.witpytools import dryprint
from eliot import start_action, to_file, log_message

# Fix import issue by using relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now import the modules
from wit_pytools.mailtools import *
from wit_pytools.systools import walklevel, rmemptydir, movefile

dryrun = (True)

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

# list all bowls
def bowllist(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS"):
        # Get bowls from config while preserving case
        for bowl, _ in config_object.items("BOWLS", raw=True):
            bowls.append(bowl)
    return bowls

# check if file matches a criteria for a bowl and return the corresponding bowl
def bowldir(file, config_object=''):
    if config_object and len(config_object) > 0:
        if config_object.has_section("BOWLS"):
            found = False
            for (bowl, critlist) in config_object.items("BOWLS"):
                for crit in critlist.split(','):
                    if crit in file and not found:
                        return '\\' + bowl
            return ''
    return ''

#   prepare strings to be used correctly in regex expressions (escape special characters)
def prepregex(ostring):
    mapping = str.maketrans({'.': '\\.', '[': '\\[', ']': '\\]'})
    nstring = ostring.translate(mapping)
    return nstring

def cleanfilestring(file, clean, clean_nocase, replacements, subdir=''):
    filename, file_extension = os.path.splitext(os.path.join(subdir, file))
    if len(subdir) > 0:
        nfile = os.path.basename(subdir)
    else:
        nfile = filename
    # case-sensitive remove strings from removelist
    for rstring in clean.split(','):
        rstring = prepregex(rstring)
        nfile = nfile.replace(rstring, '')
    # ignore case remove strings from removelist
    for rstring in clean_nocase.split(','):
        rstring = prepregex(rstring)
        nfile = re.sub(rstring,'', nfile, flags=re.IGNORECASE)
    # replace strings from replacements list
    for rstring, nstring in replacements.items():
        rstring = prepregex(rstring)
        nstring = prepregex(nstring)
        nfile = nfile.replace(rstring, nstring)
    # Remove invalid characters from filename
    invalid_chars = r'[<>:"/\\|?*]'
    nfile = re.sub(invalid_chars, '', nfile)
    # Replace multiple spaces with single space
    nfile = re.sub(r'\s+', ' ', nfile.rstrip())
    # Remove last character period
    nfile = nfile.rstrip('.')

    return os.path.join(nfile.strip() + file_extension)

# Prepare everything for the current sort process
def prepsort(config_object, targetdir):
    # Create directories if they don't exist
    log_message(_s('Prepsort: {}').format(targetdir))
    bowls = bowllist(config_object)
    for bowl in bowls:
        directory = os.path.join(targetdir, bowl)
        if not os.path.exists(directory):
            os.makedirs(directory)
    # ADD CHECK SETTINGS (directories etc.)
    # ADD SAFETY CHECK or fix: no empty criteria (comma at end of list or empty list)
    # ADD check if subdirectory
    # CHECK _unpack dir
    # CHECK SORT Lists for ,, and < 2

def handlefile(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun):
    for ftype in ftype_sort.split(','):
        ftype = ftype.strip().casefold()
        if ftype == '.msg':
            dryprint(dryrun, 'handle MSG', file.name)
            try:
                maildata = parse_msg(os.path.join(sourcedir, file.name), True)
                
                # Extract project name from the last directory in sourcedir
                project_name = os.path.basename(os.path.normpath(sourcedir))
                
                if maildata and len(maildata) >= 3:
                    # Strip leading date in YYYY-MM-DD format from subject if it exists
                    subject = maildata[2] if maildata[2] is not None else ""
                    # Regular expression to match YYYY-MM-DD at the beginning of the string
                    # followed by optional whitespace
                    date_pattern = r'^(\d{4}-\d{2}-\d{2})\s*'
                    subject = re.sub(date_pattern, '', subject).strip()
                    maildata[2] = subject
                    
                    # Ensure all elements in maildata are strings to prevent NoneType concatenation errors
                    for i in range(len(maildata)):
                        if maildata[i] is None:
                            maildata[i] = ""
                    
                    nfile = maildata[0]+'_'+maildata[1]+'_'+project_name+'_'+maildata[2]+'.msg'
                    nfile = cleanfilestring(nfile, clean, clean_nocase, replacements)
                    dryprint(dryrun, 'bowl', bowldir(nfile, config_object))
                    if not dryrun:
                        movefile(sourcedir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
                else:
                    print("No mail information available or incomplete data.")
                    nfile = cleanfilestring(file.name, clean, clean_nocase, replacements)
                    if not dryrun and filemode == 'win':
                        movefile(sourcedir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
                    elif filemode == 'nc':
                        ncmovefile(getncfilepath(file.name), targetdir + bowldir(nfile, config_object), nfile)
            except Exception as e:
                print(f"Error handling MSG file {file.name}: {e}")
                # Fallback to using the original filename
                nfile = cleanfilestring(file.name, clean, clean_nocase, replacements)
                if not dryrun and filemode == 'win':
                    movefile(sourcedir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
        else:
            # Default behavior for other file types
            nfile = cleanfilestring(file.name, clean, clean_nocase, replacements)
            if not dryrun and filemode == 'win':
                movefile(sourcedir, file.name, targetdir + bowldir(nfile, config_object), nfile, dryrun)
        
        # File has been handled, so we can break the loop
        break

    # If the loop completes without breaking, the file didn't match any specified type
    else:
        print(f" - Skipping file {file.name}: not a specified type")

def cinderellasort(configfile, dryrun=False):
    #TODO check configfile for valid ini file
    files = ""
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Initialize ConfigParser to preserve case
    config_object = ConfigParser()
    config_object.optionxform = str  # This preserves case for keys and values
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
    
    # Fetch replacements from the REPLACEMENTS section
    replacements = {}
    if "REPLACEMENTS" in config_object:
        replacements_section = config_object["REPLACEMENTS"]
        for key in replacements_section:
            replacements[key] = replacements_section[key]
    
    if not filemode == 'nc':
        print('\n###########################################')
        print('## START CinderellaSort ' + time)
        print(' Dryrun: ' + str(dryrun))
        print('   from: ' + sourcedir)
        print('   to:   ' + targetdir)
        dryprint(dryrun, 'mode',filemode)
        print('## Settings ' + configfile + ':')
        print('   sort: ' + ftype_sort)
        print('    del: ' + ftype_delete)

    # ADD unzip

    # prepare for sort process
    prepsort(config_object, targetdir)

    # Handle files directly in sourcedir
    for item in Path(sourcedir).iterdir():
        if item.is_file():
            handlefile(item, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun)

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
                        nfile = cleanfilestring(file, clean, clean_nocase, replacements, subdir)
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
                elif len(files) > 1:
                    for file in files:
                        nfile = cleanfilestring(file, clean, clean_nocase, replacements)
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, dryrun)
        else:
            print(' #  No valid sort found!') 

#    print(f"\n## Removing empty directories:")
#    rmemptydir(sourcedir,dryrun)