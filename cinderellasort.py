import os
import sys
import re
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path
from wit_pytools.witpytools import dryprint
from wit_pytools.sanitizers import prepregex, cleanfilestring, convert_numerals_arabic_western
from eliot import log_message
import gettext

# Fix import issue by using relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def setup_translations(language='de'):
    translations = gettext.translation('cinderellasort', 
                                    localedir=os.path.join(os.path.dirname(__file__), 'locale'),
                                    languages=[language],
                                    fallback=True)
    translations.install()
    return translations.gettext

# Initialize translations
_ = setup_translations()

# Now import the modules
from wit_pytools.systools import walklevel, rmemptydir, movefile, copyfile

dryrun = (True)

# check for valid searches in subdirectories of the target directory
def isvalidsort(sourcedir, ftype_sort):
    # check if any files match the sort types
    for subdir, dirs, files in walklevel(sourcedir, 2):
        for file in files:
            for ftype in ftype_sort.split(','):
                if file.casefold().endswith(ftype.strip()):
                    print(f' #  valid sort found for file type: {ftype}')
                    return True
    print(f' #  No valid sort found for file types: {ftype_sort}')
    return False

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

# list all gps bowls
def bowllist_gps(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_GPS"):
        # Get bowls from config while preserving case
        for bowl, _ in config_object.items("BOWLS_GPS", raw=True):
            # Extract just the bowl path part before any parameters
            bowl_path = bowl.split(';')[0] if ';' in bowl else bowl
            bowls.append(bowl_path)
    print(f"GPS Bowls found: {bowls}")
    return bowls

# list all email bowls
def bowllist_email(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_EMAIL"):
        # Get bowls from config while preserving case
        for bowl, _ in config_object.items("BOWLS_EMAIL", raw=True):
            bowls.append(bowl)
    return bowls

# check if file matches a criteria for a bowl and return the corresponding bowl
def bowldir(file, config_object=''):
    if config_object and len(config_object) > 0:
        if config_object.has_section("BOWLS"):
            found = False
            default_bowl = ''
            
            # First pass: look for matches and find default bowl if it exists
            for (bowl, critlist) in config_object.items("BOWLS"):
                if "!DEFAULT" in critlist:
                    default_bowl = bowl
                    continue
                    
                for crit in critlist.split(','):
                    crit = crit.strip()
                    if crit and crit in file and not found:
                        return '/' + bowl
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                return '/' + default_bowl
                
            return ''
    return ''

# check if file matches a criteria for an email bowl and return the corresponding bowl
def bowldir_email(file, config_object=''):
    if config_object and len(config_object) > 0:
        if config_object.has_section("BOWLS_EMAIL"):
            found = False
            default_bowl = ''
            
            # First pass: look for matches and find default bowl if it exists
            for (bowl, critlist) in config_object.items("BOWLS_EMAIL"):
                if "!DEFAULT" in critlist:
                    default_bowl = bowl
                    continue
                    
                for crit in critlist.split(','):
                    crit = crit.strip()
                    if crit and crit in file and not found:
                        return '/' + bowl
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                return '/' + default_bowl
                
            return ''
    return ''

# check if file matches a criteria for a gps bowl and return the corresponding bowl
def bowldir_gps(file, config_object='', image_coords=None):
    from wit_pytools.gpstools import is_valid_gps, gps_distance
    log_message(f"bowldir_gps called with file={file}, image_coords={image_coords}", level="DEBUG")
    if config_object and len(config_object) > 0 and image_coords:
        if config_object.has_section("BOWLS_GPS"):
            # fetch fallback distance if exists
            if config_object.has_section('ITEMS') and config_object.has_option('ITEMS', 'gps_default_distancekm'):
                distancekm = float(config_object.get('ITEMS', 'gps_default_distancekm').replace(',', '.'))
                log_message("Using default distance of {} km for GPS bowls".format(distancekm), level="DEBUG")
            else:
                distancekm = 2
                log_message("Setting gps_default_distancekm not found, using  2 km as default for GPS bowls", level="DEBUG")
            
            default_bowl = ''
            found = False
            
            # Check for default bowl
            for (bowl, critlist) in config_object.items("BOWLS_GPS", raw=True):
                if "!DEFAULT" in critlist:
                    default_bowl = bowl.split(';')[0] if ';' in bowl else bowl
                    continue
            log_message("Default bowl: {}".format(default_bowl), level="DEBUG")
            
            # Then check for GPS matches
            for (bowl, critlist) in config_object.items("BOWLS_GPS", raw=True):
                # Extract distance from bowl key if present (format: 'Bowl Name;3=lat,lon')
                if "!DEFAULT" in critlist:
                    continue
                log_message(f"Checking bowl: {bowl} with criteria: {critlist}", level="DEBUG")
                if ';' in bowl:
                    bowl_name, distance_str = bowl.rsplit(';', 1)
                    log_message(f"Parsed bowl name: {bowl_name}, distance string: {distance_str}", level="DEBUG")
                    if '=' in distance_str:
                        distance_val, _ = distance_str.split('=', 1)
                        try:
                            distancekm = float(distance_val.replace(',', '.'))
                            log_message("Distance for bowl {} is {} km".format(bowl_name, distancekm), level="DEBUG")
                        except ValueError:
                            log_message(f"Invalid distance value in bowl key: {bowl}", level="ERROR")
                            continue
                    else:
                        try:
                            distancekm = float(distance_str.replace(',', '.'))
                        except ValueError:
                            log_message(f"Invalid distance value in bowl key: {bowl}", level="ERROR")
                            continue
                else:
                    bowl_name = bowl
                    
                for crit in critlist.split(';'):
                    # Normalize coordinates by removing spaces
                    normalized_crit = crit.replace(' ', '')
                    log_message(f"Checking GPS criterion: {normalized_crit}", level="DEBUG")
                    valid = is_valid_gps(normalized_crit)
                    log_message(f"is_valid_gps returned: {valid}", level="DEBUG")
                    if valid:
                        try:
                            crit_lat, crit_lon = map(float, normalized_crit.split(','))
                            log_message(f"Comparing bowl coordinates {crit_lat},{crit_lon} with image coordinates {image_coords}", level="DEBUG")
                            
                            # Parse coordinates if they're in string format (lat,lon)
                            parsed_image_coords = image_coords
                            if isinstance(image_coords, str) and ',' in image_coords:
                                try:
                                    lat, lon = map(float, image_coords.split(','))
                                    parsed_image_coords = (lat, lon)
                                    log_message(f"Parsed image coordinates from string: {parsed_image_coords}", level="DEBUG")
                                except Exception as e:
                                    log_message(f"Failed to parse image coordinates: {e}", level="ERROR")
                                    continue
                                
                            try:
                                dist = gps_distance(parsed_image_coords, (crit_lat, crit_lon))
                                log_message(f"Distance: {dist} km (max allowed: {distancekm} km)", level="DEBUG")
                                if dist < distancekm:
                                    found = True
                                    log_message(f"Found matching bowl: {bowl_name} with distance {dist} km", level="DEBUG")
                                    return '/' + bowl_name
                            except Exception as e:
                                log_message(f"Error calculating distance: {e}", level="ERROR")
                                continue
                        except Exception as e:
                            continue
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                return '/' + default_bowl
                
            return ''
    return ''

def cleanfilename(file, clean, clean_nocase, replacements, subdir='', convert_numbers=True):
    filename, file_extension = os.path.splitext(os.path.join(subdir, file))
    if len(subdir) > 0:
        nfile = os.path.basename(subdir)
    else:
        nfile = filename
    # Convert Arabic numerals if enabled
    if convert_numbers:
        nfile = convert_numerals_arabic_western(nfile)
        
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
    # Clean the filename part without extension
    nfile = cleanfilestring(nfile)
    # Return with the original extension
    return nfile + file_extension

# Prepare everything for the current sort process
def prepsort(config_object, targetdir, prepfilter = False):
    # Create directories if they don't exist
    # Normalize path separators to OS-specific ones
    targetdir = str(targetdir).replace('\\', '/').replace('//', '/')
    targetdir = Path(targetdir)
    bowls = bowllist(config_object)
    for bowl in bowls:
        # Normalize bowl path separators
        bowl = str(bowl).replace('\\', '/').replace('//', '/')
        directory = targetdir / bowl
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
    if prepfilter:
        print(f"(Scan for all existing directories in the target directory: {targetdir})")
        dirnames = []
        for subdir, dirs, files in walklevel(str(targetdir), -1):
            for d in dirs:
                dirnames.append(os.path.relpath(os.path.join(subdir, d), str(targetdir)))
        dirnames.reverse()
        with open(targetdir / "filter-examples.txt", "w", encoding="utf-8") as f:
            for name in dirnames:
                f.write(f"{name}\n")
    # ADD CHECK SETTINGS (directories etc.)
    # ADD SAFETY CHECK or fix: no empty criteria (comma at end of list or empty list)
    # ADD check if subdirectory
    # CHECK _unpack dir
    # CHECK SORT Lists for ,, and < 2

def handle_emails(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
    from wit_pytools.mailtools import parse_msg
    try:
        log_message(_('Handling MSG: {}').format(os.path.join(sourcedir, file)))
        maildata = parse_msg(os.path.join(sourcedir, file.name), True)
        
        # Extract project name from the last directory in targetdir
        project_name = os.path.basename(os.path.normpath(targetdir))
        
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
            nfile = cleanfilename(nfile, clean, clean_nocase, replacements)
            bowl = bowldir_email(nfile, config_object)
            movefile(sourcedir, file, targetdir + bowl, nfile, filemode)
        else:
            #TODO check
            log_message("No mail information available or incomplete data.")
            nfile = cleanfilename(file.name, clean, clean_nocase, replacements)
            bowl = bowldir_email(nfile, config_object)
            movefile(sourcedir, file, targetdir + bowl, nfile, filemode, dryrun=dryrun)
    except Exception as e:
        print(f"Error handling MSG file {file.name}: {e}")
        # Fallback to using the original filename
        nfile = cleanfilename(file.name, clean, clean_nocase, replacements)
        if not dryrun and filemode == 'win':
            bowl = bowldir_email(nfile, config_object)
            movefile(sourcedir, file, targetdir + bowl, nfile, filemode, dryrun=dryrun)
    return

def handle_gps(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
    # Check if this is a supported image file type (JPEG or JPG) that we should process
    file_ext = os.path.splitext(file.name)[1].lower()
    if file_ext in ['.jpg', '.jpeg'] and '_nogps' not in file.name.lower():
        from wit_pytools.imgtools import img_getgps
        try:
            # Clean the filename if clean parameters are provided
            nfile = cleanfilename(file.name, clean, clean_nocase, replacements) if clean else file.name
            log_message(_('Handling GPS: {}').format(os.path.join(sourcedir, file.name)))
            image_coords = img_getgps(sourcedir, file.name)
            # Handle images without GPS data
            if image_coords is None:
                log_message("Image file does not contain GPS coordinates, renaming", level="WARNING")
                base, ext = os.path.splitext(nfile)
                nfile = base + '_nogps' + ext
                if not dryrun:
                    # Only rename in place and add _nogps
                    movefile(sourcedir, file.name, sourcedir, nfile, filemode, overwrite, dryrun)
                return False  # Return False to indicate no GPS handling was done
            bowl_coords = {}
            # Check for valid GPS bowl configuration
            if config_object.has_section("BOWLS_GPS"):
                for bowl, critlist in config_object.items("BOWLS_GPS", raw=True):
                    if "!DEFAULT" in critlist:
                        continue
                    coords = []
                    for crit in critlist.split(';'):
                        if ',' in crit and len(crit.split(',')) == 2:
                            coords.append(crit)
                    bowl_name = bowl.split(';')[0] if ';' in bowl else bowl
                    bowl_coords[bowl_name] = coords
                log_message("Available GPS bowls with coordinates: {}".format(bowl_coords), level="DEBUG")
                bowl = bowldir_gps(nfile, config_object, image_coords)
                log_message("Selected bowl: {} for coordinates: {}".format(bowl, image_coords), level="DEBUG")
                print("Selected bowl: {} for coordinates: {}".format(bowl, image_coords))
                if not bowl or bowl.strip() == '':
                    log_message("No matching bowl found within for file {} at {}".format(file.name, image_coords), level="WARNING")
                    print("No matching bowl found within for file {} at {}".format(file.name, image_coords))
                    return  # Exit function if no matching bowl found
                # move file if not in dryrun mode
                if not dryrun:
                    print("Moving file {}".format(file.name, targetdir))
                    movefile(sourcedir, file, targetdir + bowl, nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        except Exception as e:
            log_message("Error handling GPS file {}".format(file.name), level="ERROR")
            # Don't move files when there's an error processing GPS data
            return
    return

def handle_oldfiles(file_path, time_diff):
    #TODO FINISH AND TEST
    try:
        os.remove(file_path)
        print(f" - Deleted old file {file.name}: {time_diff.days} days old")
        return
    except Exception as e:
        print(f"Error deleting old file {file.name}: {e}")
        return

def handle_pdf(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
    # Check if this is a PDF file
    if file.name.lower().endswith('.pdf'):
        try:
            log_message(_('Handling PDF: {}').format(os.path.join(sourcedir, file)))
            nfile = cleanfilename(file.name, clean, clean_nocase, replacements)
            bowl = bowldir(nfile, config_object)
            if not dryrun:
                movefile(sourcedir, file, targetdir + bowl, nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        except Exception as e:
            log_message(f"Error handling PDF file {file.name}: {e}", level="ERROR")
    return

def handlefile(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress):
    # First check if the file matches any of the specified file types
    file_matches_type = False
    for ftype in ftype_sort.split(','):
        ftype = ftype.strip().casefold()
        if file.name.lower().endswith(ftype):
            file_matches_type = True
            break

    if not file_matches_type:
        print(f" - Skipping file {file.name}: not a specified type ({ftype_sort})")
        return

    ## Handle PDF Bowls ##
    if file.name.lower().endswith('.pdf'):
        print("Handle PDF Bowls")
        handle_pdf(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite)
        return
    
    ## Handle E-Mail Bowls ##
    if bowllist_email(config_object):
        print("Handle E-Mail Bowls")
        handle_emails(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite)
        return

    ## Handle GPS Bowls##
    if bowllist_gps(config_object):
        print("Handle GPS Bowls")
        # Try GPS handling first
        if handle_gps(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
            # If GPS handling was successful (file was moved), we're done
            return
        # If GPS handling returned False (no GPS data) and gps_moved_unmatched is False, skip further processing
        if not gps_moved_unmatched and file.name.lower().rsplit('.', 1)[0].endswith('_nogps'):
            log_message(f"Skipping file {file.name} as it has no GPS data and gps_moved_unmatched is False", level="INFO")
            return

    ## Default behavior for all other bowls
    print("Handle Default Bowls")
    nfile = cleanfilestring(file.name)
    bowl = bowldir(nfile, config_object)
    movefile(sourcedir, file, targetdir + bowl, nfile, filemode, overwrite=overwrite, dryrun=dryrun)

## MAIN cinderellasort execution ##
def cinderellasort(configfile, single=None, filemode='win', dryrun=False):
    #TODO check configfile for valid ini file
    files = ""
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Fetch configuration from ini
    config_object = ConfigParser()
    config_object.optionxform = str  # preserves case for keys and values
    config_object.read(configfile, encoding='utf-8')
    table = config_object["TABLE"]
    # Normalize path separators in source and target directories
    sourcedir = str(table["sourcedir"]).replace('\\', '/').replace('//', '/')
    targetdir = str(table["targetdir"]).replace('\\', '/').replace('//', '/')
    ftype_sort = (table["ftype_sort"].casefold())
    ftype_delete = (table["ftype_delete"].casefold()) if "ftype_delete" in table else "NOTdefined"
    clean = (table["clean"]) if "clean" in table else "NOTdefined"
    clean_nocase = (table["clean_nocase"].casefold()) if "clean_nocase" in table else "NOTdefined"
    trash = (table['trash']) if "trash" in table else "NOTdefined"
    trash_nocase = (table['trash_nocase'].casefold()) if "trash_nocase" in table else "NOTdefined"
    filemode = (table['filemode'].casefold()) if "filemode" in table else "win"

    settings = config_object["SETTINGS"]
    overwrite = settings.get('overwrite', 'false').strip().lower() == 'true'
    jpg_quality = int(settings.get('jpg_quality', '85').strip())
    gps_moved_unmatched = settings.get('gps_moved_unmatched', 'false').strip().lower() == 'true'
    gps_compress = settings.get('gps_compress', 'false').strip().lower() == 'true'

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
        print('     sort: ' + ftype_sort)
        print('   delete: ' + ftype_delete)
        print('overwrite: ' + str(overwrite))
        print(' jpg qual: ' + str(jpg_quality))
        print(' gps move unmatched: ' + str(gps_moved_unmatched))
        print(' gps comp: ' + str(gps_compress)) 

    # ADD unzip

    # prepare for sort process
    prepsort(config_object, targetdir)

    # Handle single file if specified, otherwise process all files in sourcedir
    if single:
        print("Running cinderellasort in single mode")
        # If single file is specified, only handle that file
        from witnctools import getncabsdir, getncfilename
        file_dir = getncabsdir(single)
        file_name = getncfilename(single)
        file_path = Path(os.path.join(file_dir, file_name))
        
        if file_path.is_file():
            handlefile(file_path, file_dir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress)
    else:
        # Handle all files in sourcedir and all subdirectories
        print("Running cinderellasort in all-files mode")
        print("Sourcedir: " + sourcedir)
        processed_files = 0
        for root, dirs, files in os.walk(sourcedir):
            for filename in files:
                print("Filename: " + filename)
                file_path = Path(os.path.join(root, filename))
                handlefile(file_path, root, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress)
                processed_files += 1
        log_message(f"Processed {processed_files} files in {sourcedir} and subdirectories")
        
    # Get list of all subdirectories for additional processing if needed
    dirlist = [f for f in Path(sourcedir).resolve().glob('**/*') if f.is_dir()]
    print([str(d) for d in dirlist])
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
                        nfile = cleanfilename(file, clean, clean_nocase, replacements, subdir)
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, filemode, overwrite=overwrite, dryrun=dryrun)
                elif len(files) > 1:
                    for file in files:
                        nfile = cleanfilename(file, clean, clean_nocase, replacements)
                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        else:
            print(' #  No valid sort found!') 

#    print(f"\n## Removing empty directories:")
#    rmemptydir(sourcedir,dryrun)
#    rmemptydir(sourcedir,dryrun)