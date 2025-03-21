import os, pytest
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mailtools import parse_msg

# requirements
# pip install pytest

def test_parse_msg_valid():
   # Adjust path to point to test_files from the tests directory
   sortdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests', 'mailtools')
   msgfile = 'testfile.msg'
    
   try:
       result = parse_msg(sortdir,msgfile, True)
       print("Result: ")
       print(result)
       assert result[0] == '2021-05-25'  # index 0 is the date
       assert result[1] == 'F.Germo@haupt-ig.de'  # index 1 is the sender
       assert result[2] == 'Hyparschale'  # index 2 is the subject
       assert len(result) == 3  # Should have date, sender, and subject
       return "Test parse_msg: PASSED"
   except Exception as e:
       print(f"Error: {e}")
       return "Test parse_msg: FAILED"

def test_parse_msg_invalid():
    """Test that parse_msg returns an empty list for non-existent files"""
    # Use a non-existent file
    result = parse_msg(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests', 'mailtools'), 'nonexistent_file.msg', True)
    
    # Check that the result is an empty list
    assert isinstance(result, list)
    assert len(result) == 0
    return "Test parse_msg_invalid: PASSED"

# Run the tests and print the result messages
result_valid = test_parse_msg_valid()
print(result_valid)

result_invalid = test_parse_msg_invalid()
print(result_invalid)
