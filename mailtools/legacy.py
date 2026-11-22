"""Legacy .eml/.msg helpers — the third-party dependencies live here.

Imported lazily via ``mailtools.__init__`` (module ``__getattr__``) so that
``import mailtools`` and the stdlib helpers keep working on hosts without
``eml_parser``/``extract-msg``. Only touching these names pulls the deps:

- ``parse_eml``, ``eml_headers``, ``eml_thread_members``,
  ``eml_thread_to_markdown``, ``parse_msg``

Code moved verbatim from the former flat ``mailtools.py`` (D-refactor):
``eml_to_markdown`` is NOT here — it was merged into the stdlib renderer
in ``mailtools.render``.
"""

from __future__ import annotations

import email
import email.policy
import os
import re
from pathlib import Path

import extract_msg
import eml_parser

from .render import (
    links_to_markdown,
    message_doc_id,
    strip_quoted_text,
    write_attachments,
)

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


def _eml_body(parsed):
    """Extract the text body of a parsed mail (plain preferred, html stripped)."""
    plain, html = [], []
    for part in parsed.get('body') or []:
        content = str(part.get('content') or '').strip()
        if not content:
            continue
        if 'plain' in str(part.get('content_type', '')):
            plain.append(content)
        elif 'html' in str(part.get('content_type', '')):
            html.append(content)
    if plain:
        return '\n\n'.join(plain)
    # strip tags so html-only mails stay searchable, keep link targets
    return re.sub(
        r'[ \t]+', ' ',
        re.sub(r'<[^>]+>', ' ', links_to_markdown('\n\n'.join(html))),
    )


def _eml_id_list(values):
    """Extract all <...> message ids from a header value or list."""
    if isinstance(values, str):
        values = [values]
    ids = []
    for value in values or []:
        ids.extend(re.findall(email_pattern, str(value)))
    return ids


def eml_headers(source):
    """Return threading headers (message_id, references, subject, date, from)."""
    parsed = eml_parser.EmlParser().decode_email_bytes(Path(source).read_bytes())
    header = parsed.get('header', {}) or {}
    raw = header.get('header', {}) or {}

    def first(value, fallback=''):
        if isinstance(value, list):
            value = value[0] if value else ''
        return str(value) if value else fallback

    subject = first(raw.get('subject'), str(header.get('subject') or ''))
    return {
        'message_id': first(_eml_id_list(raw.get('message-id'))),
        'in_reply_to': first(_eml_id_list(raw.get('in-reply-to'))),
        'references': _eml_id_list(raw.get('references')),
        'subject': subject,
        'thread_subject': _eml_base_subject(
            first(raw.get('thread-topic'), subject)
        ),
        'from': first(raw.get('from'), str(header.get('from') or '')),
        'to': first(raw.get('to'), str(header.get('to') or '')),
        'cc': first(raw.get('cc'), str(header.get('cc') or '')),
        'delivered_to': first(
            raw.get('delivered-to') or raw.get('x-original-to'), ''
        ),
        'list_id': first(raw.get('list-id'), ''),
        'list_unsubscribe': first(raw.get('list-unsubscribe'), ''),
        'date': header.get('date'),
    }


_subject_prefix = re.compile(r'^\s*(re|aw|fwd?|wg|antw)\s*[:;-]', re.IGNORECASE)


def _eml_base_subject(subject):
    """Subject without reply/forward prefixes, for header-less threading."""
    while True:
        stripped = _subject_prefix.sub('', subject, count=1).strip()
        if stripped == subject:
            return subject.casefold()
        subject = stripped


def eml_thread_members(directory, source, dropped=None):
    """Return [(path, headers)] of the thread of source in directory, by date.

    Mails are linked transitively by any shared message id (Message-ID,
    In-Reply-To, References) or by the same normalized subject, so partial
    header exports still group. Files duplicating an earlier file's
    Message-ID are skipped and appended to ``dropped`` when a list is given.
    """
    directory, source = Path(directory), Path(source)
    infos = {}
    seen_ids = set()
    for path in sorted(directory.glob('*.eml')):
        try:
            headers = eml_headers(path)
        except Exception:
            continue
        mid = headers['message_id']
        if mid and mid in seen_ids:
            if dropped is not None:
                dropped.append(path)
            continue
        if mid:
            seen_ids.add(mid)
        infos[path] = headers
    if source not in infos:
        try:
            infos[source] = eml_headers(source)
        except Exception:
            infos[source] = {
                'message_id': '', 'in_reply_to': '', 'references': [],
                'subject': source.stem, 'thread_subject': source.stem,
                'from': '', 'to': '', 'cc': '', 'delivered_to': '',
                'list_id': '', 'list_unsubscribe': '', 'date': '',
            }

    # Union-find over shared ids and the normalized subject.
    parent = {p: p for p in infos}

    def find(path):
        while parent[path] != path:
            parent[path] = parent[parent[path]]
            path = parent[path]
        return path

    owners = {}
    for path, headers in infos.items():
        keys = (
            headers['references']
            + [headers['in_reply_to'], headers['message_id']]
            + ['subject:' + headers['thread_subject']]
        )
        for key in keys:
            if not key or key == 'subject:':
                continue
            if key in owners:
                parent[find(owners[key])] = find(path)
            else:
                owners[key] = path

    root = find(source)
    members = [(p, h) for p, h in infos.items() if find(p) == root]
    members.sort(key=lambda member: (str(member[1].get('date') or ''), member[0].name))
    return members


def _trimmed_lines(text):
    """Body lines without trailing blanks."""
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _shared_footer_length(lines, other):
    """Longest identical non-blank trailing line run of two bodies."""
    k = 0
    while (k < len(lines) and k < len(other)
           and lines[-1 - k].strip() == other[-1 - k].strip()
           and lines[-1 - k].strip()):
        k += 1
    return k


def _dedupe_shared_footers(bodies):
    """Footers shared by several thread mails: keep only the last instance."""
    line_lists = [_trimmed_lines(body) for body in bodies]
    footers = []
    for i, lines in enumerate(line_lists):
        best = max(
            (_shared_footer_length(lines, other)
             for j, other in enumerate(line_lists) if j != i),
            default=0,
        )
        footers.append(tuple(l.strip() for l in lines[len(lines) - best:]))
    last_of = {}
    for i, footer in enumerate(footers):
        if len(footer) >= 2:
            last_of[footer] = i  # later index wins
    out = []
    for i, (lines, footer) in enumerate(zip(line_lists, footers)):
        if len(footer) >= 2 and last_of.get(footer) != i:
            lines = _trimmed_lines('\n'.join(lines[:len(lines) - len(footer)]))
        out.append('\n'.join(lines))
    return out


def eml_thread_to_markdown(members, output_path, attachments_dir=None):
    """Write one Markdown file for a mail thread, quote-stripped, by date.

    ``attachments_dir`` enables attachment extraction — files are prefixed
    with the mail's message-doc id and listed under ``- Attachments:``.
    """
    output_path = Path(output_path)
    subject = members[0][1].get('subject') or members[0][0].stem
    first_base = members[0][1].get('thread_subject')
    bodies, attachments = [], []
    for i, (path, _headers) in enumerate(members):
        raw = path.read_bytes()
        parsed = eml_parser.EmlParser(include_raw_body=True).decode_email_bytes(raw)
        bodies.append(strip_quoted_text(_eml_body(parsed)))
        names = []
        if attachments_dir is not None:
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            names = write_attachments(
                msg, attachments_dir, prefix=f"{message_doc_id(msg, i)}-"
            )
        attachments.append(names)
    bodies = _dedupe_shared_footers(bodies)
    lines = [f"# {subject}", '']
    for (path, headers), body, names in zip(members, bodies, attachments):
        lines += [
            f"## {headers.get('date') or ''}",
            f"- From: {headers.get('from') or ''}",
            f"- To: {headers.get('to') or ''}",
        ]
        optional = (
            ('Cc', headers.get('cc')),
            ('Subject', headers.get('subject')
             if headers.get('thread_subject') != first_base else ''),
            ('Delivered-To', headers.get('delivered_to')),
            ('List-Id', headers.get('list_id')),
            ('List-Unsubscribe', headers.get('list_unsubscribe')),
        )
        lines += [f"- {label}: {value}" for label, value in optional if value]
        if names:
            lines.append(f"- Attachments: {', '.join(names)}")
        lines += ['', body, '']
    output_path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')
    return output_path


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
            print(f"DEBUG: raw msg_sender = '{msg_sender}'")

            # Try to extract email from msg.sender_email property (SMTP address)
            try:
                if hasattr(msg, 'sender_email') and msg.sender_email:
                    formatted_sender = msg.sender_email
                    print(f"DEBUG: using sender_email = '{formatted_sender}'")
            except Exception:
                pass

            # If still no email (just display name), search for email pattern in the sender string
            if '@' not in formatted_sender:
                try:
                    # Look for email in angle brackets within sender
                    match = re.search(email_pattern, msg_sender)
                    if match and '@' in match.group(1):
                        formatted_sender = match.group(1)
                        print(f"DEBUG: extracted from angle brackets = '{formatted_sender}'")
                except Exception:
                    pass

            # If still no email, try to get from message headers
            if '@' not in formatted_sender:
                try:
                    from_header = msg.header.get('From', '') if hasattr(msg, 'header') else ''
                    print(f"DEBUG: From header = '{from_header}'")
                    if from_header:
                        match = re.search(email_pattern, from_header)
                        if match and '@' in match.group(1):
                            formatted_sender = match.group(1)
                            print(f"DEBUG: extracted from header = '{formatted_sender}'")
                except Exception as e:
                    print(f"DEBUG: header extraction error = {e}")
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
                            extracted_sender = m_angle.group(1)
                        else:
                            # Fallback: bare email somewhere on the line
                            m_bare = re.search(r'[\w\.-]+@[\w\.-]+', from_line)
                            if m_bare:
                                extracted_sender = m_bare.group(0)

                        # Only use extracted sender if it looks like a valid forward
                        # (contains @ and doesn't match the actual sender domain)
                        if extracted_sender and '@' in extracted_sender:
                            # Check if extracted sender domain differs from actual sender domain
                            actual_domain = formatted_sender.split('@')[-1] if '@' in formatted_sender else ''
                            extracted_domain = extracted_sender.split('@')[-1] if '@' in extracted_sender else ''

                            # Only use extracted sender if domains are different
                            # This prevents misidentification of replies (AW) as forwards
                            if actual_domain and extracted_domain and actual_domain != extracted_domain:
                                formatted_sender = extracted_sender
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
