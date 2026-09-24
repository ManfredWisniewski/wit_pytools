import os
import sys
import re
import shutil
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path
from wit_pytools.witpytools import dryprint
from wit_pytools.sanitizers import prepregex, cleanfilestring, convert_numerals_arabic_western, normalize_spaces
from wit_pytools.validators import valid_email_address
from wit_pytools.systools import walklevel, rmemptydir, movefile, copyfile, delfile
from wit_pytools.documenttools import (
    anonymize_text,
    document_find_regex,
    mapping_matches_text,
    update_text_mapping,
)
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
    if not matchtable:
        return False
    for token in matchtable.split(','):
        token = token.strip()
        if not token:
            continue
        if token in file:
            return True
    return False

def merge_common_rules(config_object, common_configfile):
    """Merge common BOWLS rules into a project configuration."""
    if not common_configfile or not os.path.isfile(common_configfile):
        return

    common_config = ConfigParser()
    common_config.optionxform = str
    common_config.read(common_configfile, encoding='utf-8')

    for section in ('BOWLS', 'BOWLS_EMAIL', 'BOWLS_DOCPREP', 'BOWLS_GEN_IMG'):
        if not common_config.has_section(section):
            continue

        merged_rules = {}
        for source_config in (common_config, config_object):
            if not source_config.has_section(section):
                continue
            for bowl, criteria in source_config.items(section, raw=True):
                values = [
                    value.strip()
                    for value in criteria.split(',')
                    if value.strip()
                ]
                if bowl in merged_rules:
                    existing = merged_rules[bowl].split(',')
                    values = existing + [
                        value for value in values if value not in existing
                    ]
                merged_rules[bowl] = ','.join(values)

        if config_object.has_section(section):
            config_object.remove_section(section)
        config_object.add_section(section)
        for bowl, criteria in merged_rules.items():
            config_object.set(section, bowl, criteria)

        log_message(
            f'Merged common {section} rules from {common_configfile}',
            level='INFO',
        )


def parse_bowl_tags(tags_str):
    """Parse a string containing tags with access levels in format 'tag1[level1] tag2[level2]'
    Returns a dictionary mapping tag names to their access levels.
    Example input: 'Photos[p] Private[i]' returns {'Photos': 'p', 'Private': 'i'}"""
    tags = {}
    if tags_str:
        for tag_item in tags_str.split():
            if '[' in tag_item and ']' in tag_item:
                tag_name, level = tag_item.split('[', 1)
                level = level.rstrip(']')
                tags[tag_name] = level
    return tags

# list all bowls
def bowllist(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS"):
        # Get bowls from config while preserving case
        for bowl, _ in config_object.items("BOWLS", raw=True):
            bowls.append(bowl)
    return bowls

# check if gps bowls are configured
def bowllist_gps(config_object=''):
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_GPS"):
        # Get bowls from config while preserving case
        bowls = []
        for bowl, _ in config_object.items("BOWLS_GPS", raw=True):
            # Extract just the bowl path part before any parameters
            bowl_path = bowl.split(';')[0] if ';' in bowl else bowl
            bowls.append(bowl_path)
        print(f"GPS Bowls found: {bowls}")
        return bool(bowls)  # Return True only if we found actual bowls
    return False

# list all email bowls
def bowllist_email(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_EMAIL"):
        # Get bowls from config while preserving case
        for bowl, _ in config_object.items("BOWLS_EMAIL", raw=True):
            bowls.append(bowl)
    return bowls

# list all document preparation bowls
def bowllist_docprep(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_DOCPREP"):
        for bowl, _ in config_object.items("BOWLS_DOCPREP", raw=True):
            bowls.append(bowl)
    return bowls

# check if file matches a criteria for a document preparation bowl and return the corresponding bowl
def bowldir_docprep(file, config_object=''):
    if not (config_object and len(config_object) > 0 and config_object.has_section("BOWLS_DOCPREP")):
        return ''
    for (bowl, critlist) in config_object.items("BOWLS_DOCPREP", raw=True):
        for crit in critlist.split(','):
            crit = crit.strip()
            if crit and crit in file:
                return '/' + bowl
    return ''

# list all image generation bowls
def bowllist_gen_img(config_object=''):
    bowls = []
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_GEN_IMG"):
        for bowl, _ in config_object.items("BOWLS_GEN_IMG", raw=True):
            bowls.append(bowl)
    return bowls

# check if a prompt file matches a criteria for an image generation bowl
def bowldir_gen_img(file, config_object=''):
    if not (config_object and len(config_object) > 0 and config_object.has_section("BOWLS_GEN_IMG")):
        return ''
    for (bowl, critlist) in config_object.items("BOWLS_GEN_IMG", raw=True):
        for crit in critlist.split(','):
            crit = crit.strip()
            if crit and crit in file:
                return '/' + bowl
    return ''

# check if file matches a criteria for a bowl and return the corresponding bowl
def bowldir(file, config_object='', file_path=None, check_content=False):
    if not (config_object and len(config_object) > 0 and config_object.has_section("BOWLS")):
        return ''

    default_bowl = ''
    bowls = list(config_object.items("BOWLS"))

    # First pass: filename-based matching
    for (bowl, critlist) in bowls:
        if "!DEFAULT" in critlist:
            default_bowl = bowl
            continue

        for crit in critlist.split(','):
            crit = crit.strip()
            if crit and crit in file:
                return '/' + bowl

    # Second pass: optional content search when filename did not match
    if check_content and file_path:
        file_path_obj = Path(file_path)
        if file_path_obj.suffix.lower() == '.pdf':
            for (bowl, critlist) in bowls:
                if "!DEFAULT" in critlist:
                    continue
                for crit in critlist.split(','):
                    crit = crit.strip()
                    if not crit:
                        continue
                    try:
                        content_matches = document_find_regex(file_path_obj, crit)
                    except RuntimeError:
                        content_matches = []
                    if content_matches:
                        return '/' + bowl

    if default_bowl:
        return '/' + default_bowl
    return ''

# check if gps tag bowls are configured
def bowllist_gps_tags(config_object=''):
    if config_object and len(config_object) > 0 and config_object.has_section("BOWLS_GPS_TAGS"):
        # Get bowls from config while preserving case
        bowls = []
        for bowl, _ in config_object.items("BOWLS_GPS_TAGS", raw=True):
            # Extract just the bowl path part before any parameters
            bowl_path = bowl.split(';')[0] if ';' in bowl else bowl
            bowls.append(bowl_path)
        print(f"GPS Tag Bowls found: {bowls}")
        return bool(bowls)  # Return True only if we found actual bowls
    return False

# check if file matches a criteria for an email bowl and return the corresponding bowl
def bowldir_email(file, config_object=''):
    if config_object and len(config_object) > 0:
        if config_object.has_section("BOWLS_EMAIL"):
            found = False
            default_bowl = ''
            malformed_bowl = ''
            
            # First pass: look for matches and find special bowls if they exist
            for (bowl, critlist) in config_object.items("BOWLS_EMAIL"):
                if "!DEFAULT" in critlist:
                    default_bowl = bowl
                    continue
                if "!MALFORMED" in critlist:
                    malformed_bowl = bowl
                    continue
                    
                for crit in critlist.split(','):
                    crit = crit.strip()
                    if crit and crit in file and not found:
                        return '/' + bowl
            
            # Check if file has a valid email address
            has_valid_email = valid_email_address(file)
            
            # If no email found and we have a malformed bowl, use it
            if not has_valid_email and malformed_bowl:
                return '/' + malformed_bowl
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                return '/' + default_bowl
                
            return ''
    return ''

def gps_fetch_default_distance(config_object):
    if config_object.has_section('ITEMS') and config_object.has_option('ITEMS', 'gps_default_distancekm'):
        distancekm = float(config_object.get('ITEMS', 'gps_default_distancekm').replace(',', '.'))
        log_message("Using default distance of {} km for GPS bowls".format(distancekm), level="DEBUG")
        return distancekm
    log_message("Setting gps_default_distancekm not found, using 2 km as default for GPS bowls", level="DEBUG")
    return 2 # fallback default distance if not found

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
                    parts = bowl.split(';')
                    bowl_name = parts[0]
                    tags_str = parts[1] if len(parts) > 2 else ''
                    distance_str = parts[-1]
                    
                    # Parse tags and their access levels
                    tags = parse_bowl_tags(tags_str)
                    log_message(f"Parsed bowl name: {bowl_name}, tags: {tags}, distance string: {distance_str}", level="DEBUG")
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
                                    # Return normalized bowl path with leading slash, e.g. '/TestBowl'
                                    return '/' + bowl_name
                            except Exception as e:
                                log_message(f"Error calculating distance: {e}", level="ERROR")
                                continue
                        except Exception as e:
                            continue
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                # Return normalized default bowl path with leading slash
                return '/' + default_bowl
                
            return ''
    return ''

# check if file matches a criteria for a gps bowl and return the corresponding bowl
def bowldir_gps_tags(file, config_object='', image_coords=None):
    from wit_pytools.gpstools import is_valid_gps, gps_distance
    log_message(f"bowldir_gps_tags called with file={file}, image_coords={image_coords}", level="DEBUG")
    if config_object and len(config_object) > 0 and image_coords:
        if config_object.has_section("BOWLS_GPS_TAGS"):
            # fetch fallback distance if exists
            distancekm = gps_fetch_default_distance(config_object)
            log_message("Using default distance of {} km for GPS bowls".format(distancekm), level="DEBUG")
            
            default_bowl = ''
            found = False
            
            # Then check for GPS matches
            for (bowl, critlist) in config_object.items("BOWLS_GPS_TAGS", raw=True):
                log_message(f"Checking bowl: {bowl} with criteria: {critlist}", level="DEBUG")
                
                # Split bowl into name, tags, and distance
                if ';' in bowl:
                    parts = bowl.split(';')
                    if len(parts) < 2:
                        log_message(f"Invalid GPS tag bowl format: {bowl}", level="WARNING")
                        continue
                        
                    bowl_name = parts[0]
                    tags_str = parts[1]
                    distance_str = parts[2] if len(parts) > 2 else ''
                    
                    # Parse distance if present
                    if '=' in distance_str:
                        distance_val = distance_str.split('=')[0]
                        try:
                            distancekm = float(distance_val.replace(',', '.'))
                            log_message(f"Using specified distance: {distancekm} km", level="DEBUG")
                        except ValueError:
                            log_message(f"Invalid distance value in bowl key: {bowl}", level="ERROR")
                            continue
                else:
                    bowl_name = bowl
                    tags_str = ''
                    
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
                                    log_message(f"Found matching bowl: {bowl} with distance {dist} km", level="DEBUG")
                                    return bowl
                            except Exception as e:
                                log_message(f"Error calculating distance: {e}", level="ERROR")
                                continue
                        except Exception as e:
                            continue
            
            # If no match was found but we have a default bowl, use it
            if default_bowl and not found:
                return default_bowl
                
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
    return normalize_spaces(nfile + file_extension)

# Prepare everything for the current sort process
def prepsort(config_object, targetdir, prepfilter = False):
    # Create directories if they don't exist
    # Normalize path separators to OS-specific ones
    log_message(f"prepsort called with targetdir: {targetdir}", level="INFO")
    targetdir = str(targetdir).replace('\\', '/').replace('//', '/')
    targetdir = Path(targetdir)
    log_message(f"Normalized targetdir: {targetdir}", level="INFO")
    
    # Create directories from BOWLS section
    log_message("Checking BOWLS section for directories to create", level="INFO")
    bowls = bowllist(config_object)
    log_message(f"Found {len(bowls)} bowls in BOWLS section: {bowls}", level="INFO")
    for bowl in bowls:
        # Normalize bowl path separators
        bowl = str(bowl).replace('\\', '/').replace('//', '/')
        directory = targetdir / bowl
        log_message(f"Checking directory: {directory}", level="INFO")
        if not directory.exists():
            log_message(f"Creating directory: {directory}", level="INFO")
            try:
                directory.mkdir(parents=True, exist_ok=True)
                log_message(f"Successfully created directory: {directory}", level="INFO")
            except Exception as e:
                log_message(f"Error creating directory {directory}: {e}", level="ERROR")
        else:
            log_message(f"Directory already exists: {directory}", level="INFO")
            
    # Create directories from BOWLS_EMAIL section
    log_message("Checking BOWLS_EMAIL section for directories to create", level="INFO")
    email_bowls = bowllist_email(config_object)
    log_message(f"Found {len(email_bowls)} bowls in BOWLS_EMAIL section: {email_bowls}", level="INFO")
    for bowl in email_bowls:
        # Normalize bowl path separators
        bowl = str(bowl).replace('\\', '/').replace('//', '/')
        directory = targetdir / bowl
        log_message(f"Checking directory: {directory}", level="INFO")
        if not directory.exists():
            log_message(f"Creating directory: {directory}", level="INFO")
            try:
                directory.mkdir(parents=True, exist_ok=True)
                log_message(f"Successfully created directory: {directory}", level="INFO")
            except Exception as e:
                log_message(f"Error creating directory {directory}: {e}", level="ERROR")
        else:
            log_message(f"Directory already exists: {directory}", level="INFO")

    # Create directories from BOWLS_GEN_IMG section
    for bowl in bowllist_gen_img(config_object):
        directory = targetdir / str(bowl).replace('\\', '/').replace('//', '/')
        if not directory.exists():
            log_message(f"Creating directory: {directory}", level="INFO")
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log_message(f"Error creating directory {directory}: {e}", level="ERROR")

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

def handle_gps_tags(file, sourcedir, config_object, dryrun=False):
    # Check if this is a supported image file type (JPEG or JPG) that we should process
    file_ext = os.path.splitext(file.name)[1].lower()
    if file_ext in ['.jpg', '.jpeg'] and '_nogps' not in file.name.lower():
        from wit_pytools.imgtools import img_getgps
        from wit_pytools.nctools import nctagassign
        try:
            log_message(_('Handling GPS Tags: {}').format(os.path.join(sourcedir, file.name)))
            image_coords = img_getgps(sourcedir, file.name)
            if not image_coords:
                log_message(f"No GPS coordinates found in {file.name}", level="WARNING")
                return
            
            # Get bowl and tags based on GPS coordinates
            bowl = bowldir_gps_tags(file.name, config_object, image_coords)
            if not bowl or bowl.strip() == '':
                log_message(f"No matching GPS bowl found for {file.name} at {image_coords}", level="WARNING")
                return
            
            # Get the tags for this bowl
            bowl_parts = bowl.split(';')
            if len(bowl_parts) > 1:
                tags_str = bowl_parts[1]
                tags = parse_bowl_tags(tags_str)
                if tags and not dryrun:
                    log_message(f"Setting tags for {file.name}: {tags}", level="DEBUG")
                    file_path = os.path.join(sourcedir, file.name)
                    for tag_name, access_level in tags.items():
                        nctagassign(file_path, tag_name, access_level)
                    
            log_message(f"Successfully processed GPS tags for {file.name}", level="DEBUG")
            return True
        except Exception as e:
            log_message(f"Error handling GPS file {file.name}: {str(e)}", level="ERROR")
            return False
    return False


def handle_oldfiles(file_path, time_diff):
    #TODO FINISH AND TEST
    try:
        os.remove(file_path)
        log_message(f"Deleted old file {file.name}: {time_diff.days} days old")
        return
    except Exception as e:
        print(f"Error deleting old file {file.name}: {e}")
        return

def _pdf_page_count(file_path):
    import pdfplumber
    with pdfplumber.open(str(file_path)) as pdf:
        return len(pdf.pages)


def _docprep_pdf(source, output_path, settings):
    from wit_pytools.documenttools import pdf_to_markdown
    sidecar_path = settings.get('sidecar_path')
    write_sidecar = settings['sidecar']
    if sidecar_path and Path(sidecar_path).exists():
        sidecar_path = None
        write_sidecar = False
    output = pdf_to_markdown(
        source,
        output_path=output_path,
        sidecar_path=sidecar_path,
        write_sidecar=write_sidecar,
        overwrite=False,
        mode=settings['mode'],
        model=settings['model'],
        language=settings['language'],
        dpi=settings['dpi'],
        retry_times=settings['retry_times'],
        continue_on_error=settings['continue_on_error'],
        yes=True,
    )
    if not settings['sidecar']:
        sidecar = output.with_name(f"{output.stem}_pdf2md.json")
        if sidecar.exists():
            sidecar.unlink()
    return output


def process_pending_docprep_anonymization(targetdir, settings):
    """Anonymize existing target Markdown files that still need processing."""
    if not settings['anonymize']:
        return
    if not settings['anonymize_mapping']:
        message = 'Doc_prep anonymization skipped: anonymize_mapping is not configured'
        log_message(message, level='WARNING')
        print(message)
        return
    markdown_files = sorted(Path(targetdir).rglob('*.md'))
    message = f'Doc_prep anonymization: scanning {targetdir}; found {len(markdown_files)} Markdown file(s)'
    log_message(message, level='INFO')
    print(message)
    for markdown_path in markdown_files:
        if markdown_path.name.endswith('_anon.md'):
            continue
        anonymized_path = markdown_path.with_name(f"{markdown_path.stem}_anon.md")
        if anonymized_path.exists() and not settings['anonymize_update']:
            continue
        try:
            handle_docprep_anonymization(markdown_path, settings)
        except Exception as e:
            log_message(
                f"Pending Doc_prep anonymization failed for {markdown_path}: {e}",
                level="ERROR",
            )


def handle_docprep_anonymization(
    markdown_path,
    settings,
    output_path=None,
    remove_source=None,
):
    """Collect proposals and optionally apply approved mappings to Markdown."""
    if not settings['anonymize']:
        return None
    if not settings['anonymize_mapping']:
        raise ValueError('DOCPREP anonymize=true requires anonymize_mapping')

    mapping_path = Path(settings['anonymize_mapping'])
    output_path = (
        Path(output_path)
        if output_path is not None
        else Path(markdown_path).with_name(f"{Path(markdown_path).stem}_anon.md")
    )
    candidate_source = output_path if output_path.exists() else Path(markdown_path)
    update_text_mapping(
        candidate_source,
        mapping_path,
        countries=settings.get('anonymize_name_countries'),
        use_name_datasets=settings.get('anonymize_use_name_datasets'),
        cache_dir=settings.get('anonymize_name_cache_dir'),
        offline=settings.get('anonymize_name_dataset_offline'),
        debug=settings.get('anonymize_name_dataset_debug', False),
        name_exclusions=settings.get('anonymize_name_exclusions'),
        anonymize_mode=settings.get('anonymize_mode', 'custom'),
        language=settings.get('language', 'en'),
        presidio_model=settings.get('anonymize_presidio_model', 'de_core_news_sm'),
        presidio_score_threshold=settings.get('anonymize_presidio_score_threshold', 0.5),
        presidio_entities=settings.get('anonymize_presidio_entities'),
        replacement_length=settings.get('anonymize_token_length', 4),
        ignore_dictionary=settings.get('anonymize_ignore_dictionary', False),
        ignore_numbers=settings.get('anonymize_ignore_numbers', False),
        ignore_emails=settings.get('anonymize_ignore_emails', False),
        ignore_dates=settings.get('anonymize_ignore_dates', False),
    )
    log_message(f"Doc_prep anonymization: updated mapping {mapping_path}", level="INFO")
    print(f"Doc_prep anonymization: updated mapping {mapping_path}")
    content = Path(markdown_path).read_text(encoding='utf-8')
    if not mapping_matches_text(content, mapping_path):
        log_message(f"Doc_prep anonymization: no approved mapping matches {markdown_path.name}", level="INFO")
        return None

    keep_originals = settings.get('anonymize_keep_originals', False)
    if remove_source is None:
        remove_source = not keep_originals
    if output_path.exists() and not settings['anonymize_update']:
        log_message(f"Doc_prep anonymization: {output_path.name} exists, skipping", level="INFO")
        if remove_source and Path(markdown_path).exists():
            Path(markdown_path).unlink()
            log_message(f"Doc_prep anonymization: removed source {markdown_path}", level="INFO")
        return output_path
    result = anonymize_text(markdown_path, mapping_path, output_path, overwrite=True)
    if remove_source:
        Path(markdown_path).unlink()
        log_message(f"Doc_prep anonymization: removed source {markdown_path}", level="INFO")
    return result


# Converter registry: extension -> (page counter, converter). Only PDF for now.
DOCPREP_CONVERTERS = {
    '.pdf': (_pdf_page_count, _docprep_pdf),
}


def docprep_settings(config_object):
    """Read the [DOCPREP] section with defaults."""
    section = config_object['DOCPREP'] if config_object.has_section('DOCPREP') else {}
    language = (section.get('language', 'en') or 'en').strip().lower()

    def optional_bool(key):
        value = section.get(key)
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if normalized not in {'true', 'false'}:
            raise ValueError(f'{key} must be true or false')
        return normalized == 'true'

    def csv_values(key):
        return tuple(
            value.strip()
            for value in (section.get(key, '') or '').split(',')
            if value.strip()
        )

    anonymize_mode = (section.get('anonymize-mode', 'custom') or 'custom').strip().lower()
    if anonymize_mode not in {'custom', 'presidio', 'all'}:
        raise ValueError('anonymize-mode must be custom, presidio, or all')
    presidio_entities = csv_values('anonymize_presidio_entities')
    if presidio_entities == ('all',):
        presidio_entities = None
    elif not presidio_entities:
        presidio_entities = (
            'PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'LOCATION',
            'ORGANIZATION', 'IP_ADDRESS', 'CREDIT_CARD', 'CRYPTO',
            'IBAN_CODE', 'NRP', 'MEDICAL_LICENSE',
        )
    replacement_length = int(
        section.get('anonymize_token_length', '4') or '3'
    )
    if replacement_length < 1:
        raise ValueError('anonymize_token_length must be at least 1')

    return {
        'mode': (section.get('mode', 'vision') or 'vision').strip().lower(),
        'model': (section.get('model', '') or '').strip() or None,
        'language': language,
        'dpi': int(section.get('dpi', '150')),
        'max_pages': int(section.get('max_pages', '50')),
        'retry_times': int(section.get('retry_times', '3')),
        'continue_on_error': (section.get('continue_on_error', 'false') or 'false').strip().lower() == 'true',
        'sidecar': (section.get('sidecar', 'true') or 'true').strip().lower() == 'true',
        'anonymize': (section.get('anonymize', 'false') or 'false').strip().lower() == 'true',
        'anonymize_mode': anonymize_mode,
        'anonymize_presidio_model': (section.get('anonymize_presidio_model', 'de_core_news_sm') or 'de_core_news_sm').strip(),
        'anonymize_presidio_score_threshold': float(section.get('anonymize_presidio_score_threshold', '0.5') or '0.5'),
        'anonymize_presidio_entities': presidio_entities,
        'anonymize_token_length': replacement_length,
        'anonymize_ignore_dictionary': (section.get('anonymize_ignore_dictionary', 'false') or 'false').strip().lower() == 'true',
        'anonymize_ignore_numbers': (section.get('anonymize_ignore_numbers', 'false') or 'false').strip().lower() == 'true',
        'anonymize_ignore_emails': (section.get('anonymize_ignore_emails', 'false') or 'false').strip().lower() == 'true',
        'anonymize_ignore_dates': (section.get('anonymize_ignore_dates', 'false') or 'false').strip().lower() == 'true',
        'anonymize_mapping': (section.get('anonymize_mapping', '') or '').strip() or None,
        'anonymize_update': (section.get('anonymize_update', 'false') or 'false').strip().lower() == 'true',
        'anonymize_keep_originals': (section.get('anonymize-keep-originals', 'false') or 'false').strip().lower() == 'true',
        'anonymize_name_countries': csv_values('anonymize_name_countries'),
        'anonymize_use_name_datasets': optional_bool('anonymize_use_name_datasets'),
        'anonymize_name_cache_dir': (section.get('anonymize_name_cache_dir', '') or '').strip() or None,
        'anonymize_name_dataset_offline': optional_bool('anonymize_name_dataset_offline'),
        'anonymize_name_dataset_debug': (section.get('anonymize_name_dataset_debug', 'false') or 'false').strip().lower() == 'true',
        'anonymize_name_exclusions': csv_values('anonymize_name_exclusions'),
    }


def _docprep_output_path(targetdir, relative_path, cleaned_name, bowl):
    target_root = Path(targetdir)
    relative_parent = relative_path.parent
    bowl_path = Path(str(bowl).replace('\\', '/').strip('/'))
    target_prefix_matches = (
        relative_parent.parts
        and target_root.name.casefold() == relative_parent.parts[0].casefold()
    )
    bowl_prefix_matches = (
        bowl_path != Path('.')
        and target_root.parts[-len(bowl_path.parts):] == bowl_path.parts
        and relative_parent.parts[:len(bowl_path.parts)] == bowl_path.parts
    )
    if target_prefix_matches:
        relative_parent = relative_parent.relative_to(relative_parent.parts[0])
    elif bowl_prefix_matches:
        relative_parent = relative_parent.relative_to(bowl_path)
    return target_root / relative_parent / f"{Path(cleaned_name).stem}.md"


def _find_existing_docprep_markup(targetdir, output_path, relative_path, bowl):
    target_root = Path(targetdir)
    direct_path = target_root / Path(str(bowl).replace('\\', '/')) / relative_path.parent / output_path.name
    candidates = [output_path, direct_path]
    candidates.extend(
        path
        for path in target_root.rglob(output_path.name)
        if path.is_file()
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def handle_docprep(file, sourcedir, targetdir, bowl, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
    """Create Markdown in targetdir while preserving source documents."""
    settings = docprep_settings(config_object)
    source = file if isinstance(file, Path) else Path(os.path.join(sourcedir, str(file)))
    page_count, convert = DOCPREP_CONVERTERS[source.suffix.lower()]
    source_root = Path(config_object['TABLE']['sourcedir']).resolve()
    source = source.resolve()
    relative_path = source.relative_to(source_root)
    cleaned_name = normalize_spaces(cleanfilename(source.name, clean, clean_nocase, replacements))
    output_path = _docprep_output_path(
        targetdir,
        relative_path,
        cleaned_name,
        bowl,
    )
    sidecar_path = source.parent / f"{Path(cleaned_name).stem}_pdf2md.json"
    paired_markup = source.with_suffix('.md')
    log_message(_('Handling Doc_prep: {}').format(source), level="INFO")

    if not paired_markup.is_file():
        existing_markup = _find_existing_docprep_markup(
            targetdir,
            output_path,
            relative_path,
            bowl,
        )
        if existing_markup is not None:
            keep_originals = settings.get('anonymize_keep_originals', False)
            if keep_originals:
                paired_markup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(existing_markup), str(paired_markup))
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if existing_markup != output_path:
                    shutil.move(str(existing_markup), str(output_path))
                if settings['anonymize']:
                    anonymized_output = output_path.with_name(
                        f"{output_path.stem}_anon{output_path.suffix}"
                    )
                    handle_docprep_anonymization(
                        output_path,
                        settings,
                        output_path=anonymized_output,
                        remove_source=True,
                    )
                return True

    if dryrun:
        if paired_markup.is_file():
            print(f"  Doc_prep (dryrun): using existing markup {paired_markup}")
        else:
            print(f"  Doc_prep (dryrun): {source} -> {output_path}")
        return True

    if paired_markup.is_file():
        message = f"Doc_prep: found existing markup {paired_markup.name}, skipping conversion"
        log_message(message, level="INFO")
        print(message)
        if settings['anonymize']:
            try:
                keep_originals = settings.get('anonymize_keep_originals', False)
                if keep_originals and output_path.is_file():
                    output_path.unlink()
                    log_message(
                        f"Doc_prep: moved original markup to {paired_markup}",
                        level="INFO",
                    )
                anonymized_output = output_path.with_name(
                    f"{output_path.stem}_anon{output_path.suffix}"
                )
                handle_docprep_anonymization(
                    paired_markup,
                    settings,
                    output_path=anonymized_output,
                    remove_source=not settings.get('anonymize_keep_originals', False),
                )
            except Exception as e:
                message = f"Doc_prep anonymization failed for {paired_markup.name}: {e}"
                log_message(message, level="ERROR")
                print(message)
                return False
        return True

    try:
        pages = page_count(source)
        if pages > settings['max_pages']:
            message = f"Doc_prep: skipping {source.name}: {pages} pages exceed max_pages={settings['max_pages']}"
            log_message(message, level="WARNING")
            print(message)
            return False
        if output_path.exists():
            message = f"Doc_prep: {output_path.name} exists, skipping conversion"
            log_message(message, level="INFO")
            print(message)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            conversion_settings = dict(settings)
            conversion_settings['sidecar_path'] = str(sidecar_path)
            convert(source, output_path, conversion_settings)
            message = f"Doc_prep: created {output_path}"
            log_message(message, level="INFO")
            print(message)
    except Exception as e:
        message = f"Doc_prep: conversion failed for {source.name}: {e}"
        log_message(message, level="ERROR")
        print(message)
        return False

    if settings['anonymize']:
        try:
            keep_originals = settings.get('anonymize_keep_originals', False)
            if keep_originals:
                original_markup = source.with_suffix('.md')
                if not original_markup.exists():
                    shutil.copy2(output_path, original_markup)
            handle_docprep_anonymization(
                output_path,
                settings,
                remove_source=keep_originals,
            )
        except Exception as e:
            message = f"Doc_prep anonymization failed for {output_path.name}: {e}"
            log_message(message, level="ERROR")
            print(message)
            return False

    if filemode == 'nc':
        from wit_pytools import nctools
        nctools.ncscandir(nctools.getncpath(str(output_path.parent)))
    return True


GEN_IMG_REFERENCE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
GEN_IMG_GENERAL_REFERENCE = 'reference'
GEN_IMG_PROMPT_SUFFIX = '_prompt'
GEN_IMG_NEGATIVE_SUFFIX = '_negative-prompt'


def gen_img_settings(config_object):
    """Read the [GEN_IMG] section with defaults."""
    section = config_object['GEN_IMG'] if config_object.has_section('GEN_IMG') else {}

    def optional(key):
        value = (section.get(key, '') or '').strip()
        return value or None

    max_cost = optional('max_cost')
    if max_cost and max_cost.lower() == 'ignore':
        max_cost_value = 'ignore'
    else:
        max_cost_value = float(max_cost) if max_cost else None
    return {
        'model': optional('model'),
        'n': int(section.get('n', '1') or '1'),
        'aspect_ratio': optional('aspect_ratio'),
        'resolution': optional('resolution'),
        'quality': optional('quality'),
        'output_format': optional('output_format'),
        'max_cost': max_cost_value,
        'max_jobs': int(section.get('max_jobs', '20') or '20'),
    }


def _gen_img_call(prompt, settings, out_dir, basename, negative_prompt, reference):
    from wit_pytools.aitools.generate_image import generate_image
    return generate_image(
        prompt,
        settings['model'],
        negative_prompt=negative_prompt,
        out_dir=out_dir,
        n=settings['n'],
        aspect_ratio=settings['aspect_ratio'],
        resolution=settings['resolution'],
        quality=settings['quality'],
        output_format=settings['output_format'],
        input_references=[reference] if reference else None,
        max_cost=None if settings['max_cost'] == 'ignore' else settings['max_cost'],
        yes=settings['max_cost'] == 'ignore',
        interactive=False,
        basename=basename,
    )


# Indirection so tests can replace the generator without touching aitools.
GEN_IMG_GENERATOR = _gen_img_call

# Jobs already generated in the current run, reset by cinderellasort().
_gen_img_jobs_done = 0


def is_gen_img_prompt(file):
    """True for ``<slug>_prompt.txt`` files; negative prompt files are not jobs."""
    path = Path(file)
    return (
        path.suffix.lower() == '.txt'
        and path.stem.endswith(GEN_IMG_PROMPT_SUFFIX)
        and len(path.stem) > len(GEN_IMG_PROMPT_SUFFIX)
    )


def gen_img_slug(file):
    """Return the job slug of ``<slug>_prompt.txt``."""
    return Path(file).stem[:-len(GEN_IMG_PROMPT_SUFFIX)]


def gen_img_reference(directory, slug):
    """Return ``<slug>.<ext>`` in ``directory``, else the general ``reference.<ext>``, else None."""
    directory = Path(directory)
    for name in (slug, GEN_IMG_GENERAL_REFERENCE):
        for suffix in GEN_IMG_REFERENCE_SUFFIXES:
            candidate = directory / f"{name}{suffix}"
            if candidate.is_file():
                return candidate
    return None


def handle_gen_img(file, sourcedir, targetdir, bowl, config_object, filemode, dryrun):
    """Generate images for a prompt file into its bowl; prompt files stay in place."""
    global _gen_img_jobs_done
    settings = gen_img_settings(config_object)
    source = file if isinstance(file, Path) else Path(os.path.join(sourcedir, str(file)))
    if not is_gen_img_prompt(source):
        return False
    stem = gen_img_slug(source)
    bowl_dir = Path(targetdir + bowl)
    log_message(_('Handling GEN_IMG: {}').format(source), level="INFO")

    if _gen_img_jobs_done >= settings['max_jobs']:
        message = f"GEN_IMG: max_jobs={settings['max_jobs']} reached, leaving {source.name} for the next run"
        log_message(message, level="WARNING")
        print(message)
        return False

    prompt = source.read_text(encoding='utf-8').strip()
    if not prompt:
        message = f"GEN_IMG: empty prompt file {source}, skipping"
        log_message(message, level="WARNING")
        print(message)
        return False
    negative_file = source.with_name(f"{stem}{GEN_IMG_NEGATIVE_SUFFIX}.txt")
    negative_prompt = negative_file.read_text(encoding='utf-8').strip() if negative_file.is_file() else None
    reference = gen_img_reference(source.parent, stem)

    if dryrun:
        print(f"  GEN_IMG (dryrun): {source.name} -> {bowl_dir / stem}")
        return True

    try:
        bowl_dir.mkdir(parents=True, exist_ok=True)
        paths = GEN_IMG_GENERATOR(prompt, settings, bowl_dir, stem, negative_prompt or None, reference)
        _gen_img_jobs_done += 1
        message = f"GEN_IMG: generated {[p.name for p in paths]} for {source.name}"
        log_message(message, level="INFO")
        print(message)
    except Exception as e:
        message = f"GEN_IMG: generation failed for {source.name}: {e}"
        log_message(message, level="ERROR")
        print(message)
        return False

    if filemode == 'nc':
        from wit_pytools import nctools
        nctools.ncscandir(nctools.getncpath(str(bowl_dir)))
    return True


def handle_pdf(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, check_content=False):
    # Check if this is a PDF file
    if file.name.lower().endswith('.pdf'):
        try:
            log_message(_('Handling PDF: {}').format(os.path.join(sourcedir, file)))
            nfile = cleanfilename(file.name, clean, clean_nocase, replacements)
            nfile = normalize_spaces(nfile)
            file_path = file if isinstance(file, Path) else Path(os.path.join(sourcedir, str(file)))
            bowl = bowldir(nfile, config_object, file_path=file_path, check_content=check_content)
            if not dryrun:
                movefile(sourcedir, file, targetdir + bowl, nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        except Exception as e:
            log_message(f"Error handling PDF file {file.name}: {e}", level="ERROR")
    return

def handlefile(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress, use_directory_name=False, dir_file_count=None, dirname=None, skip_unmatched=True, check_content=False):
    # First check if the file matches any of the specified file types
    file_matches_type = False
    file_ext = ''
    for ftype in ftype_sort.split(','):
        ftype = ftype.strip().casefold()
        if file.name.lower().endswith(ftype):
            file_matches_type = True
            file_ext = ftype
            break

    if not file_matches_type:
        print(f" - Skipping file {file.name}: not a specified type ({ftype_sort})")
        return

    ## Handle Doc_prep Bowls (conversion before sorting) ##
    if file_ext in DOCPREP_CONVERTERS and bowllist_docprep(config_object):
        nfile = normalize_spaces(cleanfilename(file.name, clean, clean_nocase, replacements))
        docprep_bowl = bowldir_docprep(nfile, config_object)
        if docprep_bowl:
            print("Handle Doc_prep Bowls")
            handle_docprep(file, sourcedir, targetdir, docprep_bowl, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite)
            return

    ## Handle image generation bowls (prompt files) ##
    if file_ext == '.txt' and bowllist_gen_img(config_object) and is_gen_img_prompt(file):
        gen_img_bowl = bowldir_gen_img(file.name, config_object)
        if gen_img_bowl:
            print("Handle GEN_IMG Bowls")
            handle_gen_img(file, sourcedir, targetdir, gen_img_bowl, config_object, filemode, dryrun)
            return

    ## Handle PDF Bowls ##
    if file.name.lower().endswith('.pdf'):
        print("Handle PDF Bowls")
        handle_pdf(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, check_content=check_content)
        return
    
    ## Handle E-Mail Bowls ##
    if bowllist_email(config_object):
        print("Handle E-Mail Bowls")
        handle_emails(file, sourcedir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite)
        return

    # Handle GPS tags if enabled
    has_gps_tags = bowllist_gps_tags(config_object)
    log_message(f"GPS Tags check - has_gps_tags: {has_gps_tags}, has SETTINGS: {config_object.has_section('SETTINGS')}", level="DEBUG")
    if has_gps_tags:
        if config_object.has_section("SETTINGS"):
            set_tags = config_object.get("SETTINGS", "set_tags", fallback="false").lower() == "true"
            log_message(f"GPS Tags check - set_tags enabled: {set_tags}", level="DEBUG")
            if set_tags:
                print("Handle GPS Tags")
                if handle_gps_tags(file, sourcedir, config_object, dryrun):
                    log_message(f"Successfully handled GPS tags for {file.name}", level="DEBUG")
            else:
                log_message("GPS Tags disabled in SETTINGS (set_tags is not true)", level="DEBUG")
        else:
            log_message("SETTINGS section not found in config", level="DEBUG")
    else:
        log_message("No GPS tag bowls configured", level="DEBUG")

    # Handle GPS bowls separately, only if BOWLS_GPS is configured
    has_gps_bowls = bowllist_gps(config_object)
    if has_gps_bowls:
        print("Handle GPS Bowls")
        if handle_gps(file, sourcedir, targetdir, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite):
            # If GPS handling was successful (file was moved), we're done
            return
        # If GPS handling returned False (no GPS data) and gps_moved_unmatched is False, skip further processing
        if not gps_moved_unmatched and file.name.lower().rsplit('.', 1)[0].endswith('_nogps'):
            log_message(f"Skipping file {file.name} as it has no GPS data and gps_moved_unmatched is False", level="INFO")
            return

    ## Default behavior for standard bowls
    # Only proceed if there are standard bowls configured
    if config_object.has_section("BOWLS") and len(list(config_object.items("BOWLS"))) > 0:
        print("Handle Default Bowls")
        
        # Check if we should use directory name instead of filename
        if use_directory_name and dir_file_count == 1 and dirname:
            # For directory names, don't treat them as filenames with extensions.
            # Apply clean/clean_nocase/replacements to the entire dirname, then add file extension.
            cleaned_dirname = cleanfilestring(dirname)  # Remove invalid chars first
            # Apply clean list (case-sensitive)
            if clean and clean != "NOTdefined":
                for rstring in clean.split(','):
                    if rstring:
                        rstring_escaped = prepregex(rstring)
                        cleaned_dirname = re.sub(rstring_escaped, '', cleaned_dirname)
            # Apply clean_nocase list (case-insensitive)
            if clean_nocase and clean_nocase != "NOTdefined":
                for rstring in clean_nocase.split(','):
                    if rstring:
                        rstring_escaped = prepregex(rstring)
                        cleaned_dirname = re.sub(rstring_escaped, '', cleaned_dirname, flags=re.IGNORECASE)
            # Apply replacements
            if replacements:
                for rstring, nstring in replacements.items():
                    cleaned_dirname = cleaned_dirname.replace(rstring, nstring)
            # Re-clean to collapse whitespace introduced by removals/replacements
            cleaned_dirname = cleanfilestring(cleaned_dirname)
            # Strip trailing whitespace
            cleaned_dirname = cleaned_dirname.strip()
            print(f"  Using directory name: {cleaned_dirname} (count={dir_file_count})")
            nfile = cleaned_dirname + file_ext
        else:
            nfile = cleanfilename(file.name, clean, clean_nocase, replacements)
        
        bowl = bowldir(nfile, config_object, file_path=file, check_content=check_content)
        # Only move if a bowl was found and it's not empty
        if bowl:
            # Make sure we're not moving to the root target directory
            if bowl.strip() == '':
                log_message(f"Empty bowl returned for {file.name}, skipping move", level="DEBUG")
            else:
                movefile(sourcedir, file, targetdir + bowl, nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        else:
            # No matching bowl
            if skip_unmatched:
                print(f"  No bowl match, skipping: {nfile}")
            else:
                print(f"  No bowl match, moving to base target: {nfile}")
                movefile(sourcedir, file, targetdir, nfile, filemode, overwrite=overwrite, dryrun=dryrun)

## MAIN cinderellasort execution ##
def _walk_source(sourcedir, recursive):
    """Yield source directory contents recursively or at one level."""
    if recursive:
        yield from os.walk(sourcedir)
        return
    yield sourcedir, [], os.listdir(sourcedir)


def cinderellasort(
        configfile,
        single=None,
        filemode='win',
        dryrun=False,
        common_configfile=None):
    #TODO check configfile for valid ini file
    global _gen_img_jobs_done
    _gen_img_jobs_done = 0
    files = ""
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Fetch configuration from ini
    config_object = ConfigParser()
    config_object.optionxform = str  # preserves case for keys and values
    config_object.read(configfile, encoding='utf-8')
    table = config_object["TABLE"]
    configured_filemode = table.get('filemode', filemode).casefold()
    if common_configfile is None and configured_filemode == 'nc':
        common_configfile = '/etc/nctools/nctools.ini'
    merge_common_rules(config_object, common_configfile)
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
    has_trash = trash != "NOTdefined"
    has_trash_nocase = trash_nocase != "notdefined"
    
    filemode = (table['filemode'].casefold()) if "filemode" in table else "win"

    settings = config_object["SETTINGS"] if "SETTINGS" in config_object else {}
    overwrite = settings.get('overwrite', 'false').strip().lower() == 'true'
    jpg_quality = int(settings.get('jpg_quality', '85').strip())
    gps_moved_unmatched = settings.get('gps_moved_unmatched', 'false').strip().lower() == 'true'
    gps_compress = settings.get('gps_compress', 'false').strip().lower() == 'true'
    set_tags = settings.get('set_tags', 'false').strip().lower() == 'true'
    use_directory_name = settings.get('usedirectoryname', 'false').strip().lower() == 'true'
    skip_unmatched = settings.get('skipunmatched', 'true').strip().lower() == 'true'
    check_content = settings.get('check_content', 'false').strip().lower() == 'true'
    recursive = settings.get('recursive', 'true').strip().lower() == 'true'

    # Fetch replacements from the REPLACEMENTS section
    replacements = {}
    if "REPLACEMENTS" in config_object:
        replacements_section = config_object["REPLACEMENTS"]
        for key in replacements_section:
            value = replacements_section.get(key, raw=True)
            # Strip quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            replacements[key] = value
    
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
        print(' skip unmatched: ' + str(skip_unmatched)) 

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
            handlefile(file_path, file_dir, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress, skip_unmatched=skip_unmatched, check_content=check_content)
    else:
        # First pass: delete unwanted files in directories with valid sorts
        print("Running cinderellasort in all-files mode")
        print("Sourcedir: " + sourcedir)
        print("\n## First pass: deleting unwanted files")
        valid_sort_dirs = set()
        for root, dirs, files in _walk_source(sourcedir, recursive):
            root_path = Path(root).resolve()
            current_valid = isvalidsort(root, ftype_sort)
            if current_valid:
                print(f'   Valid sort dir: {root}')
                valid_sort_dirs.add(root_path)

            should_delete = current_valid
            if not should_delete:
                for valid_dir in valid_sort_dirs:
                    try:
                        root_path.relative_to(valid_dir)
                        should_delete = True
                        break
                    except ValueError:
                        continue

            if should_delete:
                for file in files:
                    for ftype in ftype_delete.split(','):
                        ftype_clean = ftype.strip().casefold()
                        if ftype_clean and file.casefold().endswith(ftype_clean):
                            print(f'   -> deleting {file} (matches {ftype_clean})')
                            delfile(root, file, dryrun)
        
        # Second pass: process and move files
        print("\n## Second pass: processing files")
        processed_files = 0
        
        # First, count valid sort files per directory
        dir_file_counts = {}
        if use_directory_name:
            print("  Counting valid files per directory...")
            for root, dirs, files in _walk_source(sourcedir, recursive):
                valid_count = 0
                for filename in files:
                    for ftype in ftype_sort.split(','):
                        ftype_clean = ftype.strip().casefold()
                        if filename.lower().endswith(ftype_clean):
                            valid_count += 1
                            break
                if valid_count > 0:
                    dir_file_counts[root] = valid_count
                    print(f"    {root}: {valid_count} valid files")
        
        for root, dirs, files in _walk_source(sourcedir, recursive):
            for filename in files:
                lower_name = filename.casefold()
                if not any(
                    lower_name.endswith(ftype.strip().casefold())
                    for ftype in ftype_sort.split(',')
                    if ftype.strip()
                ):
                    continue
                print("Filename: " + filename)
                delete_candidate = False
                for ftype in ftype_sort.split(','):
                    ftype_clean = ftype.strip().casefold()
                    if not ftype_clean:
                        continue
                    if lower_name.endswith(ftype_clean):
                        if has_trash and matchstring(filename, trash):
                            delfile(root, filename, dryrun)
                            delete_candidate = True
                            break
                        if has_trash_nocase and matchstring(lower_name, trash_nocase):
                            delfile(root, filename, dryrun)
                            delete_candidate = True
                            break
                if delete_candidate:
                    continue
                file_path = Path(os.path.join(root, filename))
                # Get directory name and file count for this file
                dirname = os.path.basename(root) if use_directory_name else None
                dir_count = dir_file_counts.get(root, 0) if use_directory_name else None
                handlefile(file_path, root, targetdir, ftype_sort, clean, clean_nocase, config_object, filemode, replacements, dryrun, overwrite, jpg_quality, gps_moved_unmatched, gps_compress, use_directory_name, dir_count, dirname, skip_unmatched, check_content=check_content)
                processed_files += 1
        log_message(f"Processed {processed_files} files in {sourcedir} and subdirectories")
        
    # Get list of all subdirectories for additional processing if needed
    dirlist = []
    if recursive:
        dirlist = [f for f in Path(sourcedir).resolve().glob('**/*') if f.is_dir()]
    print([str(d) for d in dirlist])
    for maindir in dirlist:
        print(f'Checking dir: {maindir}')
        if isvalidsort(str(maindir), ftype_sort):
            print(' #  valid sort found:' + ftype_delete)
            for subdir, dirs, files in walklevel(str(maindir), 2):
                print(f'   Scanning subdir: {subdir}, files: {files}')
                #TODO replace with handlefile()
                for file in files:
                    # print('# remove unwanted filetypes')
                    for ftype in ftype_delete.split(','):
                        ftype_clean = ftype.strip().casefold()
                        if ftype_clean and file.casefold().endswith(ftype_clean):
                            print(f'   -> deleting {file} (matches {ftype_clean})')
                            delfile(subdir, file, dryrun)
                    # print('# removing files that match trash')
                    for ftype in ftype_sort.split(','):
                        if matchstring(file, trash) and file.casefold().endswith(ftype.strip()):
                            delfile(subdir, file, dryrun)
                        if matchstring(file.casefold(), trash_nocase) and file.casefold().endswith(ftype.strip()):
                            # print('del: ' + file)
                            delfile(subdir, file, dryrun)

#                if len(files) == 1:
#                    # add configure option
#                    # TEST what if MULTIPLE files in -subdirs-
#                    for file in files:
#                        nfile = cleanfilename(file, clean, clean_nocase, replacements, subdir)
#                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, filemode, overwrite=overwrite, dryrun=dryrun)
#                elif len(files) > 1:
#                    for file in files:
#                        nfile = cleanfilename(file, clean, clean_nocase, replacements)
#                        movefile(subdir, file, targetdir + bowldir(nfile, config_object), nfile, filemode, overwrite=overwrite, dryrun=dryrun)
        else:
            print(' #  No valid sort found!') 

    process_pending_docprep_anonymization(targetdir, docprep_settings(config_object))

    print(f"\n## Removing empty directories:")
    rmemptydir(sourcedir,dryrun)