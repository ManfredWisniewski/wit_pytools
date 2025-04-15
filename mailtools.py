import os, re, sys, shutil
import extract_msg
import eml_parser

date_format = "%Y-%m-%d"
email_pattern = r'<(.*?)>'  # Matches anything inside < >

# Email EML
# https://pypi.org/project/eml-parser/
# pip install eml-parser
def parse_eml(file, dryrun=False):
    #dryprint(dryrun, 'parsing eml', file)
    with open(file, 'rb') as fhdl:
        raw_email = fhdl.read()
    ep = eml_parser.EmlParser()
    parsed_eml = ep.decode_email_bytes(raw_email)
    mailinfo = []
    mailinfo.append(parsed_eml['header']['date'])
    mailinfo.append(parsed_eml['header']['from'])
    mailinfo.append(parsed_eml['header']['subject'])
    return mailinfo

# Parse Outlook MSG file
# https://pypi.org/project/extract-msg/
# pip install extract-msg
def parse_msg(file, dryrun=False):
    #dryprint(dryrun, 'parsing msg', file)
    if not os.path.isfile(file):
        print(f"File not found: {file}")
        return []
    else:
        try:
            msg = extract_msg.Message(os.path.join(file)) #sys.argv[1]
            msg_sender = msg.sender if msg.sender is not None else ""
            msg_date = msg.date
            msg_subj = msg.subject if msg.subject is not None else ""

            match = re.search(email_pattern, msg_sender)
            if match:
                formatted_sender = match.group(1)  # Get the email address
            else:
                formatted_sender = msg_sender  # Fallback to the original sender if no match

            mailinfo = []
            # Ensure date is not None
            if msg_date is not None:
                mailinfo.append(format(msg_date.strftime(date_format)))
            else:
                mailinfo.append("")
                
            mailinfo.append(format(formatted_sender))
            mailinfo.append(format(msg_subj))
            
            msg.close()
            
            return mailinfo
        except Exception as e:
            print(f"Error parsing MSG file: {e}")
            # Return empty strings for all fields in case of error
            return ["", "", ""]

#structure mailinfo:
# date, sender, subject

#sortdir = 'P:\git\mail-sort\test_files'
#msgfile = 'testfile.msg'
#print(parse_msg(sortdir, msgfile, True))

#emlfile = 'test.eml'
#print(parse_eml(sortdir, emlfile, True))
