"""AWS Signature V4 S3 client — Python stdlib only (no boto3).

Path-style addressing ``{endpoint}/{bucket}/{key}`` as required by the
single-host MinIO endpoint (spec: ``+wit/specs/iac-n8n/staging-inbox-s3``).
Region is fixed ``us-east-1`` — MinIO/Silo accepts any. Endpoint,
credentials and bucket are parameters; ``.env`` wiring stays in the CLI
layer (no env or repo knowledge here).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

log = logging.getLogger("s3")

SERVICE = "s3"
DEFAULT_REGION = "us-east-1"
DEFAULT_TIMEOUT = 30

_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class S3Error(RuntimeError):
    """S3 API failure carrying the parsed status/Code/Message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"S3 {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date: str, region: str, service: str = SERVICE) -> bytes:
    key = _hmac(b"AWS4" + secret.encode("utf-8"), date)
    key = _hmac(key, region)
    key = _hmac(key, service)
    return _hmac(key, "aws4_request")


def _quote(value: str, safe: str = "") -> str:
    return urllib.parse.quote(str(value), safe=safe)


def canonical_query(params: list[tuple[str, str]]) -> str:
    """Sorted, RFC3986-encoded canonical query string."""
    return "&".join(
        f"{_quote(k)}={_quote(v)}" for k, v in sorted(params, key=lambda p: (p[0], p[1]))
    )


def canonical_uri(path: str) -> str:
    """Encode each path segment; ``/`` stays literal (S3 keys contain them)."""
    return _quote(path, safe="/~")


def signature(method: str, path: str, query: list[tuple[str, str]],
              headers: dict[str, str], payload_hash: str,
              amzdate: str, region: str, secret: str,
              service: str = SERVICE) -> tuple[str, str]:
    """Compute the SigV4 signature; returns ``(signature, signed_headers)``."""
    signed = ";".join(sorted(headers))
    canonical = "\n".join([
        method,
        canonical_uri(path),
        canonical_query(query),
        "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers)),
        signed,
        payload_hash,
    ])
    scope = f"{amzdate[:8]}/{region}/{service}/aws4_request"
    to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amzdate, scope, _sha256_hex(canonical.encode("utf-8"))])
    sig = hmac.new(
        _signing_key(secret, amzdate[:8], region, service),
        to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig, signed


class S3Client:
    """SigV4-signed S3 client for one endpoint + credential pair."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str,
                 region: str = DEFAULT_REGION, timeout: int = DEFAULT_TIMEOUT):
        if not endpoint:
            raise ValueError("endpoint is required (e.g. https://inbox.w1t.org)")
        parsed = urllib.parse.urlsplit(
            endpoint if "://" in endpoint else f"https://{endpoint}")
        self._scheme = parsed.scheme
        self._netloc = parsed.netloc
        self._prefix = parsed.path.rstrip("/")
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._timeout = timeout

    def for_bucket(self, bucket: str) -> "BucketSink":
        """Bucket-bound producer view (``put``/``get``/``list``/``delete``)."""
        return BucketSink(self, bucket)

    # -- signing + transport ------------------------------------------------

    def _request(self, method: str, path: str,
                 query: list[tuple[str, str]] | None = None,
                 body: bytes = b"",
                 extra_headers: dict[str, str] | None = None,
                 expect: tuple[int, ...] = (200,)) -> tuple[dict, bytes]:
        query = query or []
        amzdate = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = _sha256_hex(body)
        headers = {
            "host": self._netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amzdate,
        }
        headers.update({k.lower(): str(v) for k, v in (extra_headers or {}).items()})
        sig, signed = signature(
            method, path, query, headers, payload_hash, amzdate,
            self._region, self._secret_key)
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self._access_key}/{amzdate[:8]}/"
            f"{self._region}/{SERVICE}/aws4_request, "
            f"SignedHeaders={signed}, Signature={sig}")
        url = f"{self._scheme}://{self._netloc}{canonical_uri(self._prefix + path)}"
        if query:
            url += "?" + canonical_query(query)
        req = urllib.request.Request(url, data=body or None, method=method)
        for name, value in headers.items():
            req.add_header(name, value)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status, out_headers, out_body = resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as error:
            raise _s3_error(error) from error
        if status not in expect:
            raise S3Error(status, "UnexpectedStatus", f"expected {expect}, got {status}")
        return out_headers, out_body

    # -- object operations --------------------------------------------------

    def put_object(self, bucket: str, key: str, data: bytes,
                   content_type: str = "application/octet-stream",
                   metadata: dict[str, str] | None = None) -> str:
        """PUT ``data`` under ``key``; returns the ETag."""
        headers = {"content-type": content_type}
        for name, value in (metadata or {}).items():
            headers[f"x-amz-meta-{name}"] = _header_safe(value)
        resp_headers, _ = self._request(
            "PUT", f"/{bucket}/{key}", body=data, extra_headers=headers)
        return (resp_headers.get("ETag") or "").strip('"')

    def get_object(self, bucket: str, key: str) -> tuple[bytes, dict]:
        """GET ``key``; returns ``(body, response_headers)``."""
        headers, body = self._request("GET", f"/{bucket}/{key}")
        return body, headers

    def head_object(self, bucket: str, key: str) -> dict:
        """HEAD ``key``; returns response headers (raises S3Error 404)."""
        headers, _ = self._request("HEAD", f"/{bucket}/{key}")
        return headers

    def delete_object(self, bucket: str, key: str) -> None:
        self._request("DELETE", f"/{bucket}/{key}", expect=(200, 204))

    def list_objects(self, bucket: str, prefix: str = "",
                     delimiter: str | None = None,
                     max_keys: int = 1000) -> list[dict]:
        """ListV2 objects under ``prefix`` (paginates via continuation token)."""
        objects = []
        token = ""
        while True:
            query = [("list-type", "2"), ("max-keys", str(max_keys)),
                     ("prefix", prefix)]
            if delimiter:
                query.append(("delimiter", delimiter))
            if token:
                query.append(("continuation-token", token))
            _, body = self._request("GET", f"/{bucket}", query=query)
            page = _parse_list(body)
            objects.extend(page["objects"])
            token = page["next_token"]
            if not token:
                return objects


def _header_safe(value: str) -> str:
    """Header values must be printable ASCII."""
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in str(value))


def _s3_error(error: urllib.error.HTTPError) -> S3Error:
    code, message = "Unknown", error.reason or str(error)
    try:
        root = ET.fromstring(error.read())
        fields = {e.tag.rsplit("}", 1)[-1]: (e.text or "") for e in root}
        code = fields.get("Code", code)
        message = fields.get("Message", message)
    except ET.ParseError:
        pass
    return S3Error(error.code, code, message)


def _parse_list(body: bytes) -> dict:
    """Parse a ListV2 response; namespace-agnostic tag lookup."""
    root = ET.fromstring(body)

    def text(parent, name):
        el = next((e for e in parent if e.tag.rsplit("}", 1)[-1] == name), None)
        return el.text if el is not None and el.text else ""

    objects = []
    for content in root:
        if content.tag.rsplit("}", 1)[-1] != "Contents":
            continue
        objects.append({
            "key": text(content, "Key"),
            "last_modified": text(content, "LastModified"),
            "etag": text(content, "ETag").strip('"'),
            "size": int(text(content, "Size") or 0),
        })
    truncated = text(root, "IsTruncated").lower() == "true"
    return {
        "objects": objects,
        "next_token": text(root, "NextContinuationToken") if truncated else "",
    }


class BucketSink:
    """Bucket-bound producer view — injected into pipelines as the write side."""

    def __init__(self, client: S3Client, bucket: str):
        self._client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes, content_type: str | None = None,
            metadata: dict[str, str] | None = None) -> str:
        return self._client.put_object(
            self.bucket, key, data,
            content_type or "application/octet-stream", metadata)

    def get(self, key: str) -> bytes:
        body, _ = self._client.get_object(self.bucket, key)
        return body

    def head(self, key: str) -> dict:
        return self._client.head_object(self.bucket, key)

    def delete(self, key: str) -> None:
        self._client.delete_object(self.bucket, key)

    def list(self, prefix: str = "", **kwargs) -> list[dict]:
        return self._client.list_objects(self.bucket, prefix=prefix, **kwargs)
