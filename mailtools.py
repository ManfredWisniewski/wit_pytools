import os, re, sys, shutil
import extract_msg
import eml_parser

date_format = "%Y-%m-%d"
email_pattern = r'<(.*?)>'  # Matches anything inside < >
forward_subject_prefix = re.compile(r'^\s*(fwd|fw|wg)\s*:', re.IGNORECASE)  # Common forward prefixes (EN/DE)

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

            # Prefer original sender if this is a forwarded mail
            formatted_sender = msg_sender
            try:
                # Extract plain email if angle brackets are present
                match = re.search(email_pattern, msg_sender)
                if match:
                    formatted_sender = match.group(1)
            except Exception:
                pass

            try:
                # Detect forward by common subject prefixes
                is_forward = bool(forward_subject_prefix.search(msg_subj))
                if is_forward:
                    body_text = getattr(msg, 'body', '') or ''
                    # Search for original From/Von line in the forwarded header block
                    # Example lines:
                    #   From: John Doe <john@example.com>
                    #   Von: Jane Doe <jane@example.com>
                    from_line_match = re.search(r'^(?:From|Von)\s*:\s*(.+)$', body_text, re.IGNORECASE | re.MULTILINE)
                    if from_line_match:
                        from_line = from_line_match.group(1).strip()
                        # Prefer email inside angle brackets
                        m_angle = re.search(email_pattern, from_line)
                        if m_angle and m_angle.group(1):
                            formatted_sender = m_angle.group(1)
                        else:
                            # Fallback: bare email somewhere on the line
                            m_bare = re.search(r'[\w\.-]+@[\w\.-]+', from_line)
                            if m_bare:
                                formatted_sender = m_bare.group(0)
            except Exception:
                # If anything goes wrong, keep the original formatted_sender
                pass

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


# create_msg.py
# Requires: Windows + Outlook installed
# Run: python create_msg.py

import win32com.client as win32
from datetime import datetime

def create_msg(
    path,
    subject="Test Subject",
    sender_name="Alice Sender",
    sender_email="alice@example.com",
    to="bob@example.com",
    cc="",
    bcc="",
    body_html="<p>Hello, this is a test.</p>",
    sent_dt=datetime(2025, 9, 1, 10, 30),
    importance=2,  # 0 Low, 1 Normal, 2 High
    attachments=None
):
    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # olMailItem

    mail.Subject = subject
    mail.HTMLBody = body_html
    mail.To = to
    mail.CC = cc
    mail.BCC = bcc
    mail.Importance = importance

    # Set sender (only works for accounts you can send-as; otherwise it will save with default)
    # For testing metadata, adding "From" as a header-like line in body is often sufficient if send-as isn't available.

    if attachments:
        for fp in attachments:
            mail.Attachments.Add(fp)

    # Set SentOn for saved draft-style item (Outlook may override on send; for saved .msg it’s kept)
    mail.SentOn = sent_dt

    mail.SaveAs(path, 3)  # 3 = olMSG
    print(f"Saved: {path}")

if __name__ == "__main__":
    create_msg(
        path="test_mail.msg",
        subject="Project Update – Sprint 15",
        sender_name="Alice Sender",
        sender_email="alice@example.com",
        to="Bob Receiver <bob@example.com>",
        cc="Team Lead <lead@example.com>",
        bcc="",
        body_html="""
        <html><body>
        <p>Hi Bob,</p>
        <p>Here’s the update for Sprint 15.</p>
        <ul><li>Task A done</li><li>Task B in progress</li></ul>
        <p>Regards,<br>Alice</p>
        </body></html>
        """,
        attachments=[],
    )