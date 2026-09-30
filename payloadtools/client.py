"""Minimal Payload CMS REST client (draft-only writes, never publishes)."""

import json
import mimetypes
import time
from pathlib import Path

import requests


class PayloadAuthError(RuntimeError):
    """401/403 response — bad or over-privileged API key."""


class PayloadApiError(RuntimeError):
    """Non-auth API failure."""


def _json(response):
    """Parse a JSON response body or raise PayloadApiError."""
    try:
        return response.json()
    except ValueError as error:
        raise PayloadApiError(
            f"Invalid JSON response from {response.url}: {error}"
        ) from error


class PayloadClient:
    """REST client for a Payload CMS instance."""

    def __init__(self, base_url, api_key, *, timeout=30, retries=2):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"users API-Key {api_key}"

    def _request(self, method, path, *, params=None, json_body=None,
                 data=None, files=None, attempts=1):
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method, url, params=params, json=json_body,
                    data=data, files=files, timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise PayloadApiError(f"{method} {url}: {error}") from error
            if response.status_code in (401, 403):
                raise PayloadAuthError(
                    f"{method} {url}: HTTP {response.status_code} "
                    "(check API key permissions)"
                )
            if response.status_code >= 500 and attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue
            if not response.ok:
                raise PayloadApiError(
                    f"{method} {url}: HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            return response
        raise PayloadApiError(f"{method} {url}: attempts exhausted")

    def close(self):
        """Close the underlying HTTP session."""
        self.session.close()

    def get(self, path, params=None):
        """GET with retry/backoff (idempotent reads only)."""
        response = self._request(
            "GET", path, params=params, attempts=self.retries + 1
        )
        return _json(response)

    def find_doc(self, collection, field_name, value):
        """Return the first doc matching field=value, or None."""
        body = self.get(
            collection,
            params={f"where[{field_name}][equals]": value, "limit": 1},
        )
        if not isinstance(body, dict):
            raise PayloadApiError(
                f"Unexpected response shape from {collection}: {body!r}"
            )
        docs = body.get("docs", [])
        return docs[0] if docs else None

    def create_doc(self, collection, payload):
        """POST a new draft document."""
        response = self._request(
            "POST", collection, params={"draft": "true"}, json_body=payload
        )
        return _json(response)

    def update_doc(self, collection, doc_id, payload):
        """PATCH an existing document as draft."""
        response = self._request(
            "PATCH", f"{collection}/{doc_id}",
            params={"draft": "true"}, json_body=payload,
        )
        return _json(response)

    def upload_media(self, image_path, *, collection, alt="",
                     caption="", source_hash="", source_path=""):
        """POST a media file as multipart/form-data; returns the doc id."""
        path = Path(image_path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload_json = json.dumps({
            "alt": alt,
            "caption": caption,
            "sourceHash": source_hash,
            "sourcePath": source_path,
        })
        with path.open("rb") as handle:
            response = self._request(
                "POST", collection,
                files={"file": (path.name, handle, mime)},
                data={"_payload": payload_json},
            )
        body = _json(response)
        doc = body.get("doc", body) if isinstance(body, dict) else {}
        media_id = doc.get("id") if isinstance(doc, dict) else None
        if not media_id:
            raise PayloadApiError(
                f"Media upload response missing id: {body!r}"
            )
        return str(media_id)

    def update_global(self, slug, payload):
        """Update a global (e.g. theme CSS). Globals use POST, not PATCH."""
        return _json(
            self._request("POST", f"globals/{slug}", json_body=payload)
        )
