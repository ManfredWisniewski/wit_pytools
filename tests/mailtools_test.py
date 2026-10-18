import os, pytest
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mailtools import parse_msg

# requirements
# pip install pytest

def test_parse_msg_valid():
   # Adjust path to point to test_files from the tests directory
   sortdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mailtools')
   msgfile = 'testfile.msg'
   test_file_path = os.path.join(sortdir, msgfile)
     
   # Skip test if test file doesn't exist
   if not os.path.isfile(test_file_path):
       pytest.skip(f"Test file {test_file_path} not found. Skipping test.")
       
   try:
       result = parse_msg(test_file_path, True)
       print("Result: ")
       print(result)
       assert result[0] == '2021-05-25'  # index 0 is the date
       assert result[1] == 'F.Germo@haupt-ig.de'  # index 1 is the sender
       assert result[2] == 'Hyparschale'  # index 2 is the subject
       assert len(result) == 3  # Should have date, sender, and subject
       print("Test parse_msg: PASSED")
   except Exception as e:
       print(f"Error: {e}")
       assert False, "Test parse_msg: FAILED"

def test_parse_msg_invalid():
    """Test that parse_msg returns an empty list for non-existent files"""
    # Use a non-existent file
    result = parse_msg(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mailtools'), 'nonexistent_file.msg')
    
    # Check that the result is an empty list
    assert isinstance(result, list)
    assert len(result) == 0
    print("Test parse_msg_invalid: PASSED")

# Run the tests using pytest
if __name__ == "__main__":
    pytest.main(['-v', __file__])


from mailtools import (
    eml_thread_members,
    eml_thread_to_markdown,
    strip_quoted_text,
)


_MAIL_A = (
    "From: a@x.de\n"
    "To: b@y.de\n"
    "Subject: Rechnung 123\n"
    "Date: Mon, 20 Oct 2025 10:00:00 +0200\n"
    "Message-ID: <m1@x.de>\n"
    "Content-Type: text/plain; charset=utf-8\n"
    "\n"
    "Sehr geehrte Kunden, anbei die Rechnung 123.\n"
)

_MAIL_B = (
    "From: b@y.de\n"
    "To: a@x.de\n"
    "Subject: AW: Rechnung 123\n"
    "Date: Tue, 21 Oct 2025 09:00:00 +0200\n"
    "Message-ID: <m2@y.de>\n"
    "In-Reply-To: <m1@x.de>\n"
    "References: <m1@x.de>\n"
    "Content-Type: text/plain; charset=utf-8\n"
    "\n"
    "Danke, Zahlung veranlasst.\n"
    "\n"
    "-----Ursprüngliche Nachricht-----\n"
    "Von: a@x.de\n"
    "Sehr geehrte Kunden, anbei die Rechnung 123.\n"
)

_MAIL_C = (
    "From: c@z.de\n"
    "To: d@z.de\n"
    "Subject: Termin\n"
    "Date: Wed, 22 Oct 2025 08:00:00 +0200\n"
    "Message-ID: <m3@z.de>\n"
    "Content-Type: text/plain; charset=utf-8\n"
    "\n"
    "Hallo.\n"
)


def test_strip_quoted_text():
    text = "Neuer Text\n\n-----Ursprüngliche Nachricht-----\nVon: a@x.de\nalter Text"
    assert strip_quoted_text(text) == "Neuer Text"
    text = "Antwort\n> zitierte Zeile\n> noch mehr\nEnde"
    assert strip_quoted_text(text) == "Antwort\nEnde"


def test_eml_thread_members_groups_thread(tmp_path):
    (tmp_path / "mail_a.eml").write_text(_MAIL_A, encoding="utf-8")
    (tmp_path / "mail_b.eml").write_text(_MAIL_B, encoding="utf-8")
    (tmp_path / "mail_c.eml").write_text(_MAIL_C, encoding="utf-8")

    members = eml_thread_members(tmp_path, tmp_path / "mail_b.eml")
    assert [p.name for p, _ in members] == ["mail_a.eml", "mail_b.eml"]

    alone = eml_thread_members(tmp_path, tmp_path / "mail_c.eml")
    assert [p.name for p, _ in alone] == ["mail_c.eml"]


def test_eml_thread_to_markdown_combines_and_strips(tmp_path):
    a = tmp_path / "mail_a.eml"
    b = tmp_path / "mail_b.eml"
    a.write_text(_MAIL_A, encoding="utf-8")
    b.write_text(_MAIL_B, encoding="utf-8")
    members = eml_thread_members(tmp_path, b)
    out = eml_thread_to_markdown(members, tmp_path / "mail_a.md")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Rechnung 123")
    assert "Sehr geehrte Kunden" in text
    assert "Zahlung veranlasst" in text
    assert "Ursprüngliche Nachricht" not in text
    assert text.count("Sehr geehrte Kunden") == 1
