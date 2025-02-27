import os , pytest
from mailtools import parse_msg

# requirements
# pip install pytest

def test_parse_msg_valid():
   sortdir = os.path.abspath('./test_files')
   msgfile = 'testfile.msg'
    
   result = parse_msg(sortdir,msgfile, True)
   print("Result: ")
   print(result)
   assert result['from'] == 'sender@example.com'
   assert result['to'] == 'recipient@example.com'
   assert result['subject'] == 'Test Email'
   assert result['body'] == 'This is a test email.'

def test_parse_msg_invalid():
    # Example of an invalid EML input
    msg_content = "Not a valid MSG format"
    
    with pytest.raises(ValueError):
        parse_msg('./test_files','testfile.msg', True)

test_parse_msg_valid()