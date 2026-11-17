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


# --- package refactor coverage (spec: +wit/specs/wit_pytools/mailtools) ---

import base64
import csv
from pathlib import Path

from mailtools import (
    account_slug,
    compile_sieve,
    folder_relpath,
    init_dirs,
    mail_to_markdown,
    parse_accounts,
    parse_list_names,
    rule_folders,
    sent_folder,
    staging_folder,
    utf7_decode,
)
from mailtools.archive import archive_account, delete_sent, purge_staging
from mailtools import archive as _archive
import mailtools


def test_parse_accounts_and_slug(tmp_path):
    csv_path = tmp_path / "accounts.csv"
    csv_path.write_text(
        "# comment\n"
        "account,host,port,script,rules,prefix\n"
        "ec@witconsult.de,mail.witconsult.de,4190,mail-sort,rules.csv,INBOX.\n"
        "u@stalwart.de,stalwart.de,,,rules.csv,-\n",
        encoding="utf-8",
    )
    accounts = parse_accounts(csv_path)
    assert [a["slug"] for a in accounts] == ["ec-witconsult-de", "u-stalwart-de"]
    assert accounts[0]["prefix"] == "INBOX."
    assert accounts[1]["prefix"] == ""      # '-' -> no namespace prefix
    assert accounts[1]["port"] == 4190      # defaults
    assert account_slug("EC@WitConsult.de") == "ec-witconsult-de"


def test_compile_sieve_stages_and_stops():
    script = compile_sieve([("*@hetzner.com", "Archiv.Rechnungen", "")],
                           "mail-sort.csv", "INBOX.")
    assert 'fileinto :copy :create "INBOX.Incoming";' in script
    assert 'address :matches "From" "*@hetzner.com"' in script
    assert 'fileinto :create "INBOX.Archiv.Rechnungen"; stop;' in script
    # no-prefix account (Stalwart): top-level folders, no INBOX. prefix
    flat = compile_sieve([("*", "INBOX", "")], "r.csv", "")
    assert 'fileinto :copy :create "Incoming";' in flat


def test_utf7_and_list_names():
    assert utf7_decode("Gel&APY-schte Elemente") == "Gelöschte Elemente"
    names = parse_list_names([
        b'(\HasNoChildren) "." INBOX',
        b'(\HasChildren) "." "INBOX.FAW.Shopping"',
    ])
    assert names == ["INBOX", "INBOX.FAW.Shopping"]
    assert staging_folder("INBOX.") == "INBOX.Incoming"
    assert sent_folder("") == "Sent"


_MAIL = (
    b"From: Alice <alice@example.com>\r\n"
    b"To: ec@example.de\r\n"
    b"Subject: Test mail\r\n"
    b"Date: Sat, 11 Oct 2026 10:00:00 +0200\r\n"
    b"Message-ID: <m1@x>\r\n"
    b"\r\nHello body\r\n"
)


def test_mail_to_markdown_frontmatter_and_simple(tmp_path):
    doc = tmp_path / "arch" / "doc.md"
    out, _ = mail_to_markdown(
        _MAIL, doc, frontmatter={"subject": "Test mail", "folder": "INBOX.Sent"})
    text = out.read_text(encoding="utf-8")
    assert text.startswith('---\nsubject: "Test mail"')
    assert 'folder: "INBOX.Sent"' in text
    assert "Hello body" in text

    simple = tmp_path / "simple.md"
    mail_to_markdown(_MAIL, simple)
    text = simple.read_text(encoding="utf-8")
    assert text.startswith("# Test mail")
    assert "- From: Alice <alice@example.com>" in text


def test_folder_relpath():
    assert folder_relpath("INBOX.FAW.Shopping", "INBOX.") == "FAW/Shopping"
    assert folder_relpath("INBOX", "INBOX.") == "INBOX"
    assert folder_relpath("A.B", "") == "A/B"


class _FakeImap:
    def __init__(self, messages=None):
        self._messages = messages or {}
        self._selected = None
        self.untagged_responses = {"UIDVALIDITY": [b"1"]}
        self.stored = []
        self.expunged = False

    def select(self, box, readonly=False):
        self._selected = box.strip('"')
        return ("OK", [b"1"])

    def uid(self, cmd, *args):
        if cmd == "search" and args[1] == "UID":
            uids = [str(u) for (b, u) in sorted(self._messages) if b == self._selected]
            return ("OK", [" ".join(uids).encode()])
        if cmd == "search":
            return ("OK", [b"1 2"])
        if cmd == "fetch":
            raw = self._messages.get((self._selected, int(args[0])))
            return ("OK", [(b"h", raw)] if raw else [b""])
        if cmd == "store":
            self.stored.append(args)
            return ("OK", [])
        return ("NO", [])

    def expunge(self):
        self.expunged = True
        return ("OK", [])


def test_archive_account_drains_sent(tmp_path):
    acct = {"account": "e@x.de", "host": "h", "slug": "e-x-de", "prefix": "INBOX."}
    fake = _FakeImap({("INBOX.Sent", 5): _MAIL, ("INBOX.A", 9): _MAIL})
    captured = archive_account(acct, tmp_path, "pw", imap_client=fake)
    assert captured == [5]
    docs = list((tmp_path / "+INBOX" / "emails" / "e-x-de" / "Sent").glob("*.md"))
    assert len(docs) == 1 and "Hello body" in docs[0].read_text(encoding="utf-8")


def test_delete_and_purge(tmp_path):
    acct = {"account": "e@x.de", "host": "h", "slug": "e-x-de", "prefix": "INBOX."}
    fake = _FakeImap()
    assert delete_sent(acct, [5, 6], "pw", imap_client=fake) == 2
    assert b"5,6" == fake.stored[0][0] and fake.expunged

    fake2 = _FakeImap()
    assert purge_staging(acct, 30, "pw", imap_client=fake2) == 2
    assert fake2.expunged


def test_init_dirs_and_rule_folders(tmp_path):
    rules = tmp_path / "rules.csv"
    rules.write_text("Archiv.Rechnungen,,*@x.de\n", encoding="utf-8")
    assert rule_folders(rules) == ["Archiv.Rechnungen"]
    acct = {"account": "e@x.de", "slug": "e-x-de", "prefix": "INBOX."}
    init_dirs([acct], tmp_path, rules)
    base = tmp_path / "+INBOX" / "emails" / "e-x-de"
    for rel in ("Archiv/Rechnungen", "INBOX", "Sent", "attachments", "proposals"):
        assert (base / rel).is_dir(), rel


def test_legacy_names_resolve_lazily():
    # import itself must not require the optional deps path eagerly
    assert callable(mailtools.eml_thread_members)
    assert callable(mailtools.parse_msg)
