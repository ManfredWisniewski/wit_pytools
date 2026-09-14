"""Minimal OpenRouter client built on ``requests``."""

import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from eliot import log_message

BASE_URL = "https://openrouter.ai/api/v1"
CHAT_TIMEOUT = 60
IMAGE_TIMEOUT = 120

_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_IMAGE_SIZE_WARNING_BYTES = 5 * 1024 * 1024

Messages = List[Dict[str, Any]]


def _api_key(api_key: Optional[str]) -> str:
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OpenRouter API key missing: set OPENROUTER_API_KEY or pass api_key="
        )
    return key


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {_api_key(api_key)}",
        "Content-Type": "application/json",
    }
    referer = os.environ.get("OPENROUTER_REFERER")
    title = os.environ.get("OPENROUTER_TITLE")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-OpenRouter-Title"] = title
    return headers


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error or body)[:500]


def request(
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    method: str = "POST",
    timeout: int = CHAT_TIMEOUT,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Call an OpenRouter endpoint and return the parsed JSON body."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    log_message(f"OpenRouter {method} {endpoint}", level="INFO")
    response = requests.request(
        method,
        url,
        headers=_headers(api_key),
        json=payload if method != "GET" else None,
        params=payload if method == "GET" else None,
        timeout=timeout,
    )
    if not response.ok:
        message = _error_message(response)
        log_message(f"OpenRouter error {response.status_code}: {message}", level="ERROR")
        raise RuntimeError(f"OpenRouter {response.status_code}: {message}")
    return response.json()


def _resolve_model(model: Optional[str], env_var: str) -> str:
    chosen = model or os.environ.get(env_var, "")
    if not chosen:
        raise RuntimeError(f"No model given: pass model= or set {env_var}")
    return chosen


def chat(
    prompt_or_messages: Union[str, Messages],
    model: Optional[str] = None,
    *,
    system: Optional[str] = None,
    api_key: Optional[str] = None,
    **params: Any,
) -> str:
    """Send a chat completion and return the assistant text."""
    if isinstance(prompt_or_messages, str):
        messages: Messages = [{"role": "user", "content": prompt_or_messages}]
    else:
        messages = list(prompt_or_messages)
    if system:
        messages.insert(0, {"role": "system", "content": system})

    payload = {"model": _resolve_model(model, "OPENROUTER_MODEL"), "messages": messages}
    payload.update({key: value for key, value in params.items() if value is not None})
    body = request("chat/completions", payload, timeout=CHAT_TIMEOUT, api_key=api_key)
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected chat response: {body}") from exc


def list_models(
    output_modality: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return trimmed model entries, optionally filtered by output modality."""
    if output_modality == "image":
        body = request("images/models", method="GET", api_key=api_key)
    else:
        params = {"output_modalities": output_modality} if output_modality else None
        body = request("models", params, method="GET", api_key=api_key)

    models = []
    for entry in body.get("data", []):
        architecture = entry.get("architecture") or {}
        models.append(
            {
                "id": entry.get("id"),
                "name": entry.get("name"),
                "input_modalities": architecture.get("input_modalities", []),
                "output_modalities": architecture.get("output_modalities", []),
                "pricing": entry.get("pricing"),
            }
        )
    return models


def image_part(source: Union[str, Path], detail: Optional[str] = None) -> Dict[str, Any]:
    """Build an ``image_url`` content part from a URL or a local image file."""
    text = str(source)
    if text.startswith(("http://", "https://", "data:")):
        url = text
    else:
        path = Path(source)
        mime = _IMAGE_MIME_TYPES.get(path.suffix.lower())
        if mime is None:
            raise ValueError(
                f"Unsupported image type {path.suffix!r}; "
                f"allowed: {', '.join(sorted(_IMAGE_MIME_TYPES))}"
            )
        data = path.read_bytes()
        if len(data) > _IMAGE_SIZE_WARNING_BYTES:
            log_message(
                f"Image {path} is {len(data) / (1024 * 1024):.1f} MB; "
                "large inline images inflate the request",
                level="WARNING",
            )
        url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    image_url: Dict[str, Any] = {"url": url}
    if detail:
        image_url["detail"] = detail
    return {"type": "image_url", "image_url": image_url}
