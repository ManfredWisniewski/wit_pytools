"""Sieve script compilation + a minimal RFC 5804 ManageSieve client.

Compiles ``(pattern, folder, subject)`` glob rules into a Sieve script with
a staging-copy prologue (``fileinto :copy :create <prefix>Incoming``) and
deploys it via ManageSieve; ``ensure_folders`` creates+subscribes the rule
targets over IMAP. Stdlib only.
"""

from __future__ import annotations

import base64
import imaplib
import socket
import ssl

from .imap import hierarchy_sep


def _sieve_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def compile_sieve(rules: list[tuple[str, str, str]], source_name: str = "mail-sort.csv",
                  folder_prefix: str = "INBOX.") -> str:
    """Turn (pattern, folder, subject) rules into a Sieve script.

    Globs map 1:1 to Sieve ``:matches`` (* = any run, ? = one char,
    case-insensitive). Each match ends with ``stop`` — first match wins.
    ``fileinto :create`` creates a missing target folder. ``folder_prefix``
    is the account's personal namespace prefix (``INBOX.`` on Dovecot —
    fileinto without it fails and the mail falls back to INBOX).

    Before the rules, every message is additionally staged via
    ``fileinto :copy :create "<prefix>Incoming"`` — the archive workflow
    polls that folder. The copy never affects sorting: the rules file the
    real message as before.
    """
    lines = [
        'require ["fileinto", "mailbox", "copy"];',
        "",
        f"# generated from {source_name} - edit that file, not this script",
        "",
        f"fileinto :copy :create {_sieve_string(folder_prefix + 'Incoming')};",
        "",
    ]
    for pattern, folder, subject in rules:
        tests = []
        if pattern != "*":
            tests.append(f'address :matches "From" {_sieve_string(pattern)}')
        if subject:
            tests.append(f'header :matches "Subject" {_sieve_string(subject)}')
        cond = f"allof({', '.join(tests)})" if len(tests) > 1 else (tests[0] if tests else "true")
        target = "INBOX" if folder.upper() == "INBOX" else folder_prefix + folder
        lines.append(f"if {cond} {{ fileinto :create {_sieve_string(target)}; stop; }}")
    return "\n".join(lines) + "\n"


class ManageSieve:
    """Minimal RFC 5804 ManageSieve client: STARTTLS + AUTH PLAIN + PUTSCRIPT/SETACTIVE."""

    def __init__(self, host: str, port: int = 4190, timeout: int = 30, sock=None, verbose: bool = False):
        self.host = host
        self.verbose = verbose
        self.sock = sock or socket.create_connection((host, port), timeout=timeout)
        self.buf = b""
        self.capabilities = self._read_capability_block()

    # -- wire helpers -------------------------------------------------------

    def _readline(self) -> bytes:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(8192)
            if not chunk:
                raise ConnectionError("server closed connection")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        if self.verbose:
            print("<<", line.decode(errors="replace"))
        return line.rstrip(b"\r")

    def _read_literal(self, first_line: bytes) -> bytes:
        """Read a {n+} literal continuation from a response line."""
        literal = first_line[first_line.rindex(b"{") + 1 :].rstrip(b"+}")
        want = int(literal)
        if want > 8 * 1024 * 1024:
            raise RuntimeError(f"refusing oversized literal {{{want}}}")
        while len(self.buf) < want + 2:
            chunk = self.sock.recv(8192)
            if not chunk:
                raise ConnectionError("server closed connection inside literal")
            self.buf += chunk
        data, self.buf = self.buf[:want], self.buf[want:]
        self._readline()  # consume CRLF after literal
        return data

    def _read_capability_block(self) -> bytes:
        out = bytearray()
        while True:
            line = self._readline()
            out += line + b"\n"
            if line.startswith((b"OK", b"NO", b"BYE", b"+")):
                return bytes(out)
            if line.startswith(b'"') and line.rstrip().endswith(b"+}"):
                out += self._read_literal(line) + b"\n"

    def _command(self, line: bytes) -> str:
        if self.verbose:
            shown = b'AUTHENTICATE "PLAIN" "<redacted>"' if line.startswith(b"AUTHENTICATE") else line
            print(">>", shown.decode(errors="replace"))
        self.sock.sendall(line + b"\r\n")
        resp = self._read_capability_block()
        if resp.startswith(b"NO") or resp.startswith(b"BYE"):
            raise RuntimeError(f"{line.split()[0].decode()} failed: {resp.decode(errors='replace').strip()}")
        return resp.decode(errors="replace")

    @staticmethod
    def _quoted(value: str) -> bytes:
        if "\r" in value or "\n" in value:
            raise ValueError("CR/LF is not allowed inside a ManageSieve string")
        return b'"' + value.replace("\\", "\\\\").replace('"', '\\"').encode() + b'"'

    # -- protocol ------------------------------------------------------------

    def starttls(self) -> None:
        self._command(b"STARTTLS")
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(self.sock, server_hostname=self.host)
        self.capabilities = self._read_capability_block()

    def authenticate(self, user: str, password: str) -> None:
        blob = base64.b64encode(f"\x00{user}\x00{password}".encode())
        self._command(b'AUTHENTICATE "PLAIN" "' + blob + b'"')

    def put_script(self, name: str, script: str) -> None:
        # This Dovecot managesieve never answers literal ({N}/{N+}) args —
        # send the script as a single-line quoted string instead (Sieve is
        # whitespace-insensitive; '#' comments would eat the line, strip them).
        flat = " ".join(l.strip() for l in script.splitlines() if l.strip() and not l.lstrip().startswith("#"))
        line = b"PUTSCRIPT " + self._quoted(name) + b" " + self._quoted(flat)
        if self.verbose:
            print(">>", line.decode(errors="replace"))
        self.sock.sendall(line + b"\r\n")
        resp = self._read_capability_block()
        if resp.startswith(b"NO") or resp.startswith(b"BYE"):
            raise RuntimeError(f"PUTSCRIPT failed: {resp.decode(errors='replace').strip()}")

    def set_active(self, name: str) -> None:
        self._command(b"SETACTIVE " + self._quoted(name))

    def logout(self) -> None:
        try:
            self.sock.sendall(b"LOGOUT\r\n")
            self.sock.close()
        except OSError:
            pass


def ensure_folders(rules: list[tuple[str, str, str]], host: str, user: str, password: str,
                   prefix: str = "INBOX.", port: int = 993, imap_client=None) -> None:
    """CREATE + SUBSCRIBE every rule's target folder (and its parents) via IMAP.

    ``fileinto :create`` creates mailboxes but does not subscribe them — most
    clients only show subscribed folders, so sieve-filed mail would look lost.
    """
    m = imap_client or imaplib.IMAP4_SSL(host, port)
    if imap_client is None:
        m.login(user, password)
    sep = hierarchy_sep(m)
    done = set()

    def _ignore_no(fn, box):
        try:
            # names with spaces must reach the server as quoted strings
            fn(f'"{box}"' if " " in box else box)
        except Exception:
            pass  # already exists / already subscribed

    staging = prefix + "Incoming"
    done.add(staging)
    _ignore_no(m.create, staging)
    _ignore_no(m.subscribe, staging)
    for _pattern, folder, _subject in rules:
        name = "INBOX" if folder.upper() == "INBOX" else prefix + folder
        parts = name.split(sep)
        for i in range(2, len(parts)):  # intermediate parents
            box = sep.join(parts[:i])
            if box not in done:
                done.add(box)
                _ignore_no(m.create, box)
                _ignore_no(m.subscribe, box)
        if name not in done:
            done.add(name)
            _ignore_no(m.create, name)
            _ignore_no(m.subscribe, name)
    if imap_client is None:
        m.logout()
    print(f"ensured {len(done)} folder(s) exist and targets are subscribed")
