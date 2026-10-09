"""Minimal Synapse admin and Matrix client helpers built on ``requests``."""

import os
from typing import Any, Dict, Optional

import requests
from eliot import log_message

TIMEOUT = 30


def _resolve(value: Optional[str], env_var: str) -> str:
    # fall back to env var when no argument is given
    chosen = value or os.environ.get(env_var, "")
    if not chosen:
        raise RuntimeError(f"{env_var} missing: pass argument or set {env_var}")
    return chosen


def _request(
    method: str,
    server: Optional[str],
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    admin_token: Optional[str] = None,
) -> Dict[str, Any]:
    base = _resolve(server, "MATRIX_SERVER").rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    headers = {"Content-Type": "application/json"}
    if admin_token:
        headers["Authorization"] = f"Bearer {admin_token}"
    log_message(f"Matrix {method} {url}", level="INFO")
    response = requests.request(
        method, url, headers=headers, json=payload, timeout=TIMEOUT
    )
    if not response.ok:
        log_message(
            f"Matrix error {response.status_code}: {response.text[:500]}",
            level="ERROR",
        )
        raise RuntimeError(f"Matrix {response.status_code}: {response.text[:500]}")
    return response.json()


def create_user(
    user_id: str,
    password: str,
    displayname: Optional[str] = None,
    *,
    server: Optional[str] = None,
    admin_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a Synapse user (PUT /_synapse/admin/v2/users/{user_id}).

    ``user_id`` is the full MXID, e.g. ``@pirx:example.org``.
    ``admin_token`` falls back to env ``MATRIX_ADMIN_TOKEN``,
    ``server`` to env ``MATRIX_SERVER``.
    """
    token = _resolve(admin_token, "MATRIX_ADMIN_TOKEN")
    payload: Dict[str, Any] = {"password": password}
    if displayname:
        payload["displayname"] = displayname
    return _request(
        "PUT",
        server,
        f"/_synapse/admin/v2/users/{user_id}",
        payload,
        admin_token=token,
    )


def login_as_user(
    user_id: str,
    *,
    server: Optional[str] = None,
    admin_token: Optional[str] = None,
) -> str:
    """Return an access token for ``user_id`` via the admin API.

    POST /_synapse/admin/v1/users/{user_id}/login — no password needed,
    so it also works when password login is disabled.
    """
    token = _resolve(admin_token, "MATRIX_ADMIN_TOKEN")
    body = _request(
        "POST",
        server,
        f"/_synapse/admin/v1/users/{user_id}/login",
        admin_token=token,
    )
    try:
        return body["access_token"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected login response: {body}") from exc


def login(
    user: str,
    password: str,
    *,
    server: Optional[str] = None,
) -> str:
    """Log in via /_matrix/client/v3/login and return the access token."""
    payload = {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": user},
        "password": password,
    }
    body = _request("POST", server, "/_matrix/client/v3/login", payload)
    try:
        return body["access_token"]
    except KeyError as exc:
        raise RuntimeError(f"Unexpected login response: {body}") from exc
