"""Shared stdlib helpers for the Its a Plan IaC tools.

Provides: .env loading, a minimal JSON HTTP client (x-api-key auth),
ini/template loading and canonical comparison. No third-party dependencies.
"""

import json
import os
import urllib.error
import urllib.request

from wit_pytools.jsontools import load_json

ENV_FILE = ".env"
INI_FILE = "instance/itsaplan.ini"
TEMPLATES_DIR = "src/templates"
TEMPLATE_FORMAT = "itsaplan.project-template"
TEMPLATE_VERSION = 1


class ItsaplanError(Exception):
    """API or configuration failure. Message is safe to show to the user."""


class ApiError(ItsaplanError):
    def __init__(self, status, method, path, detail=""):
        self.status = status
        hint = ""
        if status == 401:
            hint = " - API key invalid or expired; rotate it (Account -> API keys)"
        elif status == 403:
            hint = " - the API key owner lacks permission for this call"
        super().__init__(f"HTTP {status} {method} {path}{hint}" + (f": {detail}" if detail else ""))


def load_env(path=ENV_FILE):
    """Read KEY=VALUE pairs from .env; real environment wins over the file."""
    values = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    values = {k: os.environ.get(k, v) for k, v in values.items()}
    for key in ("ITSAPLAN_API_URL", "ITSAPLAN_API_KEY"):
        if key not in values or not values[key]:
            raise ItsaplanError(f"{key} is not set - copy .env.example to .env and fill it in")
    return values["ITSAPLAN_API_URL"].rstrip("/"), values["ITSAPLAN_API_KEY"]


class Client:
    """Minimal JSON client for the Its a Plan REST API."""

    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def request(self, method, path, body=None):
        url = self.base_url + path
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("x-api-key", self.api_key)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.status == 204 or not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise ApiError(exc.code, method, path, detail) from exc
        except urllib.error.URLError as exc:
            raise ItsaplanError(f"cannot reach {url}: {exc.reason}") from exc

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body):
        return self.request("POST", path, body)

    def patch(self, path, body):
        return self.request("PATCH", path, body)

    def delete(self, path):
        return self.request("DELETE", path)


def canonical(obj):
    """Stable JSON string for deep comparison (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def parse_ini(path=INI_FILE):
    """Parse instance/itsaplan.ini into plain dicts.

    Returns {"instance": {...}, "templates": [...], "teams": [...], "projects": [...]}.
    Section forms: [instance], [template "name"], [team "name"],
    [project "name"], [project "name".template].
    """
    import configparser
    import re

    if not os.path.exists(path):
        raise ItsaplanError(f"{path} not found")
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # preserve case of keys
    cp.read(path, encoding="utf-8")

    cfg = {"instance": {}, "templates": [], "teams": [], "projects": []}
    if cp.has_section("instance"):
        cfg["instance"] = dict(cp["instance"])

    for section in cp.sections():
        m = re.fullmatch(r'template "(.+)"', section)
        if m:
            entry = dict(cp[section])
            entry["name"] = m.group(1)
            cfg["templates"].append(entry)
            continue
        m = re.fullmatch(r'team "(.+)"', section)
        if m:
            entry = dict(cp[section])
            entry["name"] = m.group(1)
            cfg["teams"].append(entry)
            continue
        m = re.fullmatch(r'project "(.+)"(?:\.template)?', section)
        if m:
            is_tpl = section.endswith(".template")
            pname = m.group(1)
            if is_tpl:
                target = next((p for p in cfg["projects"] if p["name"] == pname), None)
                if target is None:
                    target = {"name": pname}
                    cfg["projects"].append(target)
                target.setdefault("template", {}).update(dict(cp[section]))
            else:
                if not any(p["name"] == pname for p in cfg["projects"]):
                    cfg["projects"].append({"name": pname})
                target = next(p for p in cfg["projects"] if p["name"] == pname)
                target.update({k: v for k, v in cp[section].items() if k != "template"})
            continue
    # flatten the template sub-dict collected from [project "X".template]
    for p in cfg["projects"]:
        if "template" in p:
            p["template_name"] = p["template"].get("name")
            del p["template"]
    return cfg


def load_templates(cfg, templates_dir=TEMPLATES_DIR):
    """Load and validate src/templates/*.project-template.json files.

    Returns {template_name: document}. Validates format/version and that the
    ini [template] file reference (when present) matches the JSON `name`.
    """
    docs = {}
    if not os.path.isdir(templates_dir):
        return docs
    for fname in sorted(os.listdir(templates_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(templates_dir, fname)
        doc = load_json(path)
        if doc.get("format") != TEMPLATE_FORMAT:
            raise ItsaplanError(f"{path}: format must be {TEMPLATE_FORMAT!r}")
        if doc.get("version") != TEMPLATE_VERSION:
            raise ItsaplanError(f"{path}: unsupported version {doc.get('version')!r}")
        name = doc.get("name")
        if not name:
            raise ItsaplanError(f"{path}: missing name")
        if name in docs:
            raise ItsaplanError(f"duplicate template name {name!r} ({path})")
        docs[name] = doc
    # cross-check ini references
    for t in cfg["templates"]:
        name = t["name"]
        if name not in docs:
            raise ItsaplanError(f"ini template {name!r} has no matching file in {templates_dir}/")
        expected = t.get("file", f"templates/{name}.project-template.json")
        if expected not in (f"templates/{name}.project-template.json", f"{name}.project-template.json"):
            raise ItsaplanError(f"ini template {name!r}: unexpected file {expected!r}")
    return docs


def list_all(client, path, page_size=100):
    """Fetch a possibly-paginated list endpoint; tolerates array or {items|data|...}.

    Tries ?page=&pageSize= first; on 400/404/422 (strict query validation) or an
    unrecognized shape, falls back to a single plain GET.
    """
    try:
        out = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            chunk = client.get(f"{path}{sep}page={page}&pageSize={page_size}")
            items = _extract_items(chunk)
            if items is None:
                raise ItsaplanError(f"cannot parse list response from {path}")
            out.extend(items)
            if len(items) < page_size:
                return out
            page += 1
            if page > 100:
                raise ItsaplanError(f"pagination runaway on {path}")
    except ApiError as exc:
        if exc.status not in (400, 404, 422):
            raise
    # fallback: plain GET, single page
    chunk = client.get(path)
    items = _extract_items(chunk)
    if items is None:
        raise ItsaplanError(f"cannot parse list response from {path}")
    return items


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "projects", "teams", "templates", "results", "edges"):
            if key in payload and isinstance(payload[key], list):
                if key == "edges" and payload[key] and isinstance(payload[key][0], dict) and "node" in payload[key][0]:
                    return [e["node"] for e in payload[key]]
                return payload[key]
    return None
