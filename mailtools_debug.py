"""Debug utility for mailtools - helps diagnose email parsing issues."""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wit_pytools.mailtools import parse_msg


def parse_msg_debug(file):
    """
    Run parse_msg on a file and output all extracted information.
    
    Args:
        file: Path to the .msg file to parse
    """
    print(f"\n{'='*60}")
    print(f"DEBUG: Parsing file: {file}")
    print(f"{'='*60}")
    
    maildata = parse_msg(file, dryrun=True)
    
    print(f"\n{'='*60}")
    print("RESULT:")
    print(f"{'='*60}")
    if maildata and len(maildata) >= 3:
        print(f"Date:    {maildata[0]}")
        print(f"Sender:  {maildata[1]}")
        print(f"Subject: {maildata[2]}")
    else:
        print("No mail data or incomplete data returned!")
        print(f"Raw result: {maildata}")
    print(f"{'='*60}\n")
    
    return maildata


def explore_msg_properties(file):
    """Explore all available properties in the MSG file."""
    import extract_msg
    import re
    
    print(f"\n{'='*60}")
    print(f"EXPLORING MSG PROPERTIES: {file}")
    print(f"{'='*60}\n")
    
    msg = extract_msg.Message(file)
    
    print(f"msg.sender: {msg.sender}")
    print(f"msg.sender_email: {getattr(msg, 'sender_email', 'NOT AVAILABLE')}")
    print(f"msg.headers: {getattr(msg, 'headers', 'NOT AVAILABLE')}")
    
    # Search body for email addresses
    body_text = getattr(msg, 'body', '') or ''
    email_pattern = r'[\w\.-]+@[\w\.-]+\.[\w]{2,}'
    found_emails = re.findall(email_pattern, body_text)
    print(f"\nEmails found in body: {found_emails[:5]}")  # Show first 5
    
    msg.close()
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Hardcoded path for testing
    msg_file = r"C:\maildata\testfile.msg"
    
    if not os.path.isfile(msg_file):
        print(f"Error: File not found: {msg_file}")
        sys.exit(1)
    
    parse_msg_debug(msg_file)
    explore_msg_properties(msg_file)
