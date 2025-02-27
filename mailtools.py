import os, re, sys, shutil
import extract_msg
import eml_parser


date_format = "%Y-%m-%d"
email_pattern = r'<(.*?)>'  # Matches anything inside < >

# Email EML
# https://pypi.org/project/eml-parser/
# pip install eml-parser
def parse_eml(directory,file, debug=False):
    if debug:
        print(' -  parsing: ' + directory + file)

    with open(os.path.join(directory,file), 'rb') as fhdl:
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
def parse_msg(directory,file, debug=False):
    if debug:
        print(' -  parsing: ' + directory + file)

    file_path = os.path.join(directory, file)
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return []
    else:
        print(f"Parsing msg file: {file_path}")

        msg = extract_msg.Message(os.path.join(directory,file)) #sys.argv[1]
        msg_sender = msg.sender
        msg_date = msg.date
        msg_subj = msg.subject

        match = re.search(email_pattern, msg_sender)
        if match:
            formatted_sender = match.group(1)  # Get the email address
        else:
            formatted_sender = msg_sender  # Fallback to the original sender if no match

        mailinfo = []
        mailinfo.append(format(msg_date.strftime(date_format)))
        mailinfo.append(format(formatted_sender))
        mailinfo.append(format(msg_subj))
        return mailinfo
        #YYYY-MM-DD_ABSENDER_PROJEKTNAME_BETREFF-GEFILTERT

        #for k, v in msg.header.items():
        #    print("{}: {}".format(k, v))

        #print(msg.body)

#structure mailinfo:
# date, sender, subject

#sortdir = 'P:\git\mail-sort\test_files'
#msgfile = 'testfile.msg'
#print(parse_msg(sortdir, msgfile, True))

#emlfile = 'test.eml'
#print(parse_eml(sortdir, emlfile, True))
