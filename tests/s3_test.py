import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import s3

# requirements
# pip install pytest


# --- SigV4 known-answer vector (AWS docs, GET IAM ListUsers) -----------------

def test_signature_aws_doc_vector():
    sig, signed = s3.signature(
        "GET", "/",
        [("Action", "ListUsers"), ("Version", "2010-05-08")],
        {
            "content-type": "application/x-www-form-urlencoded; charset=utf-8",
            "host": "iam.amazonaws.com",
            "x-amz-date": "20150830T123600Z",
        },
        s3._EMPTY_SHA256, "20150830T123600Z", "us-east-1",
        "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", service="iam")
    assert signed == "content-type;host;x-amz-date"
    assert sig == "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"


def test_canonical_encodings():
    # '/' preserved in keys, spaces %-encoded (never '+'), query sorted
    assert s3.canonical_uri("/b/mail-archive/a b.md") == "/b/mail-archive/a%20b.md"
    assert s3.canonical_query([("prefix", "a/b"), ("list-type", "2")]) == \
        "list-type=2&prefix=a%2Fb"


def test_client_requires_endpoint():
    with pytest.raises(ValueError):
        s3.S3Client("", "ak", "sk")


# --- fake S3 HTTP server round-trips -----------------------------------------

class _FakeS3(BaseHTTPRequestHandler):
    objects = {}      # (bucket, key) -> body bytes
    requests = []     # (method, path, query)
    headers_log = []  # request headers as sent

    def log_message(self, *a):
        pass

    def _record(self):
        parsed = urlsplit(self.path)
        self.requests.append((self.command, parsed.path, parsed.query))
        self.headers_log.append(dict(self.headers.items()))
        parts = parsed.path.strip("/").split("/", 1)
        return parts[0], parts[1] if len(parts) > 1 else "", parsed.query

    def do_PUT(self):
        bucket, key, _ = self._record()
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.objects[(bucket, key)] = body
        self.send_response(200)
        self.send_header("ETag", '"deadbeef"')
        self.end_headers()

    def do_GET(self):
        bucket, key, query = self._record()
        if key:
            if (bucket, key) not in self.objects:
                return self._xml_error(404, "NoSuchKey", "missing")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown")
            self.end_headers()
            self.wfile.write(self.objects[(bucket, key)])
            return
        prefix = dict(parse_qsl(query)).get("prefix", "")
        keys = [k for (b, k) in sorted(self.objects) if b == bucket and k.startswith(prefix)]
        rows = "".join(
            f"<Contents><Key>{k}</Key><LastModified>2026-11-26T00:00:00Z</LastModified>"
            f"<ETag>\"deadbeef\"</ETag><Size>{len(self.objects[(bucket, k)])}</Size>"
            f"</Contents>" for k in keys)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<Name>{bucket}</Name><Prefix>{prefix}</Prefix><KeyCount>{len(keys)}</KeyCount>"
            f"<IsTruncated>false</IsTruncated>{rows}</ListBucketResult>".encode())

    def do_HEAD(self):
        bucket, key, _ = self._record()
        if (bucket, key) not in self.objects:
            return self._xml_error(404, "NotFound", "missing")
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.objects[(bucket, key)])))
        self.end_headers()

    def do_DELETE(self):
        bucket, key, _ = self._record()
        self.objects.pop((bucket, key), None)
        self.send_response(204)
        self.end_headers()

    def _xml_error(self, status, code, message):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(
            f"<Error><Code>{code}</Code><Message>{message}</Message></Error>".encode())


@pytest.fixture()
def server():
    _FakeS3.objects, _FakeS3.requests, _FakeS3.headers_log = {}, [], []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeS3)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_roundtrip_path_style(server):
    client = s3.S3Client(server, "mail-archive", "s3cr3t")
    etag = client.put_object(
        "inbox-wit", "mail-archive/2026-11-26/doc.md", b"# hi\n",
        "text/markdown; charset=utf-8",
        {"source": "mail-archive", "account": "ec-witconsult-de"})
    assert etag == "deadbeef"

    method, path, _ = _FakeS3.requests[-1]
    assert (method, path) == ("PUT", "/inbox-wit/mail-archive/2026-11-26/doc.md")
    sent = {k.lower(): v for k, v in _FakeS3.headers_log[-1].items()}
    assert sent["x-amz-meta-source"] == "mail-archive"
    assert sent["x-amz-meta-account"] == "ec-witconsult-de"
    assert sent["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=mail-archive/")
    assert "us-east-1/s3/aws4_request" in sent["authorization"]
    assert "x-amz-content-sha256" in sent

    body, headers = client.get_object("inbox-wit", "mail-archive/2026-11-26/doc.md")
    assert body == b"# hi\n"
    assert headers["Content-Type"] == "text/markdown"
    assert client.head_object("inbox-wit", "mail-archive/2026-11-26/doc.md")["Content-Length"] == "5"

    listed = client.list_objects("inbox-wit", prefix="mail-archive/")
    assert [(o["key"], o["size"]) for o in listed] == [("mail-archive/2026-11-26/doc.md", 5)]

    client.delete_object("inbox-wit", "mail-archive/2026-11-26/doc.md")
    with pytest.raises(s3.S3Error) as err:
        client.head_object("inbox-wit", "mail-archive/2026-11-26/doc.md")
    assert err.value.status == 404
    with pytest.raises(s3.S3Error) as err:
        client.get_object("inbox-wit", "mail-archive/2026-11-26/doc.md")
    assert err.value.status == 404 and err.value.code == "NoSuchKey"


def test_list_pagination(server):
    class Paginated(_FakeS3):
        def do_GET(self):
            bucket, key, query = self._record()
            if key:
                return super().do_GET()
            params = dict(parse_qsl(query))
            if "continuation-token" not in params:
                body = ('<ListBucketResult><Name>b</Name><IsTruncated>true</IsTruncated>'
                        '<NextContinuationToken>T</NextContinuationToken>'
                        '<Contents><Key>a</Key><Size>1</Size></Contents></ListBucketResult>')
            else:
                body = ('<ListBucketResult><Name>b</Name><IsTruncated>false</IsTruncated>'
                        '<Contents><Key>b</Key><Size>2</Size></Contents></ListBucketResult>')
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())

    _FakeS3.requests, _FakeS3.headers_log = [], []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Paginated)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        client = s3.S3Client(f"http://127.0.0.1:{httpd.server_address[1]}", "ak", "sk")
        assert [o["key"] for o in client.list_objects("b")] == ["a", "b"]
    finally:
        httpd.shutdown()


def test_bucket_sink_interface(server):
    sink = s3.S3Client(server, "ak", "sk").for_bucket("inbox-wit")
    sink.put("mail-archive/a.md", b"data", "text/markdown", {"source": "mail-archive"})
    assert sink.get("mail-archive/a.md") == b"data"
    assert sink.head("mail-archive/a.md")["Content-Length"] == "4"
    assert sink.list("mail-archive/")[0]["key"] == "mail-archive/a.md"
    sink.delete("mail-archive/a.md")
    with pytest.raises(s3.S3Error):
        sink.get("mail-archive/a.md")
