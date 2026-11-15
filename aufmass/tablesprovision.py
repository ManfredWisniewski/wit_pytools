"""Provision an Aufmass project/floor into Nextcloud Tables.

Implements tasks T006/T024–T027 on top of the verified API flow:
context -> scheme -> CSV import -> column widths -> group views
(_gf/_plan/_monteur/_abrechnung) -> readonly mapping -> hidden
``original`` delete-guard column -> view shares.

Env credentials: NCAUF_USER/NCAUF_TOKEN (Aufmass service account) or
NC_URL/NC_USER/NC_PASSWORD. Host must be ``cloud.wuttke.gmbh`` —
``wuttke.cloud`` redirects and drops auth.

requirements: requests (python-dotenv optional)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

from wit_pytools.aufmass.tablesimport import NextcloudTablesImporter

SCHEME_DIR = Path(__file__).with_name("schemes")
# type -> (scheme file, csv name, view label)
TYPES = {
    "bauelemente": ("scheme_bauelemente.json", "bauelemente.csv",
                    "Bauelemente"),
    "kanal_summen": ("scheme_kanal_summen.json", "kanal.summen.csv",
                     "Kanal"),
    "rohr_summen": ("scheme_rohr_summen.json", "rohr.summen.csv", "Rohr"),
}
VIEW_GROUPS = ("gf", "plan", "monteur", "abrechnung")
ADMIN_GROUP = "admin"
ORIGINAL_COLUMN = {"title": "original", "type": "selection",
                   "subtype": "check", "mandatory": False}
DEFAULT_REMOTE_DIR = "AUF"


class ProvisionError(RuntimeError):
    """Raised on provisioning API failures."""


def load_credentials():
    """Return (base_url, user, password) from env or .env file."""
    try:
        from dotenv import load_dotenv

        # cwd first (wins), then the package-level .env as fallback
        load_dotenv(Path.cwd() / ".env")
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    base_url = (os.environ.get("NCAUF_URL")
                or os.environ.get("NC_URL", "")).rstrip("/")
    user = os.environ.get("NCAUF_USER") or os.environ.get("NC_USER", "")
    password = (os.environ.get("NCAUF_TOKEN")
                or os.environ.get("NC_PASSWORD", ""))
    if not base_url or not user or not password:
        raise ProvisionError(
            "NCAUF_URL/NC_URL, NCAUF_USER/NC_USER and "
            "NCAUF_TOKEN/NC_PASSWORD must be set (env or .env)")
    return base_url, user, password


def table_title(projekt_id, slug, etage, typ):
    """Table title per FR-016 naming convention."""
    return f"AUF_{projekt_id}_{slug}_{etage}_{typ}"


def context_name_default(projekt_id, slug, etage):
    return f"AUF {projekt_id} {slug} {etage}"


class TablesProvisioner:
    """Tables v1/v2 provisioning client (contexts, schemes, views, shares)."""

    def __init__(self, base_url, user, password, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.api1 = f"{self.base_url}/index.php/apps/tables/api/1"
        self.api2 = f"{self.base_url}/ocs/v2.php/apps/tables/api/2"
        self.timeout = timeout
        self.importer = NextcloudTablesImporter(base_url, user, password,
                                                timeout=timeout)
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"OCS-APIRequest": "true"})

    def _request(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=self.timeout,
                                        **kwargs)
        if response.status_code not in (200, 201):
            raise ProvisionError(
                f"{method} {url} failed: {response.status_code} "
                f"{response.text[:300]}")
        return response

    # -- tables / columns -------------------------------------------------

    def list_tables(self):
        """All visible tables as {title: id}."""
        response = self._request("GET", f"{self.api1}/tables")
        return {t["title"]: t["id"] for t in response.json()}

    def create_table_from_scheme(self, scheme_path, title):
        """POST /api/2/tables/scheme; returns the new table id."""
        scheme = json.loads(Path(scheme_path).read_text(encoding="utf-8"))
        scheme["title"] = title
        before = set(self.list_tables().values())
        self._request("POST", f"{self.api2}/tables/scheme", json=scheme)
        new_ids = set(self.list_tables().values()) - before
        if not new_ids:
            raise ProvisionError(f"table '{title}' not found after scheme POST")
        return new_ids.pop()

    def list_columns(self, table_id):
        return self._request(
            "GET", f"{self.api1}/tables/{table_id}/columns").json()

    def ensure_column(self, table_id, coldef):
        """Create a column unless a column with its title exists."""
        existing = {c["title"]: c for c in self.list_columns(table_id)}
        if coldef["title"] in existing:
            return existing[coldef["title"]]["id"]
        response = self._request(
            "POST", f"{self.api1}/tables/{table_id}/columns", json=coldef)
        return response.json()["id"]

    def update_column(self, column_id, fields):
        """Partially update a column (e.g. mandatory, customSettings)."""
        self._request("PUT", f"{self.api1}/columns/{column_id}", json=fields)

    def sync_mandatory(self, table_id, column_defs):
        """Apply `mandatory` from scheme column defs to existing columns."""
        by_title = {c["title"]: c for c in self.list_columns(table_id)}
        for coldef in column_defs:
            col = by_title.get(coldef["title"])
            if col is None or "mandatory" not in coldef:
                continue
            if bool(col.get("mandatory")) != bool(coldef["mandatory"]):
                self.update_column(
                    col["id"], {"mandatory": bool(coldef["mandatory"])})

    def _row_count(self, table_id, page=200):
        count, offset = 0, 0
        while True:
            rows = self._request(
                "GET", f"{self.api1}/tables/{table_id}/rows",
                params={"limit": page, "offset": offset}).json()
            count += len(rows)
            if len(rows) < page:
                return count
            offset += page

    # -- rows --------------------------------------------------------------

    def iter_rows(self, table_id, page=200):
        offset = 0
        while True:
            rows = self._request(
                "GET", f"{self.api1}/tables/{table_id}/rows",
                params={"limit": page, "offset": offset}).json()
            if not rows:
                return
            yield from rows
            if len(rows) < page:
                return
            offset += page

    def mark_rows_original(self, table_id, column_id):
        """Set original=true on every row that is not already set (T027)."""
        marked = 0
        for row in self.iter_rows(table_id):
            data = {c["columnId"]: c["value"] for c in row.get("data", [])}
            if data.get(column_id) in (True, "true", 1, "1"):
                continue
            self._request("PUT", f"{self.api1}/rows/{row['id']}",
                          json={"data": {str(column_id): True}})
            marked += 1
        return marked

    # -- contexts ------------------------------------------------------------

    def ensure_context(self, name, icon="football"):
        """Context id by name; creates it if missing."""
        response = self._request("GET", f"{self.api2}/contexts")
        match = re.search(
            rf"<id>(\d+)</id>\s*<name>{re.escape(name)}</name>", response.text)
        if match:
            return int(match.group(1))
        response = self._request(
            "POST", f"{self.api2}/contexts",
            json={"name": name, "iconName": icon, "description": ""})
        return int(re.search(r"<id>(\d+)</id>", response.text).group(1))

    def context_nodes(self, context_id):
        """Existing context nodes as [{id, type, permissions}]."""
        response = self._request("GET", f"{self.api2}/contexts/{context_id}")
        return [
            {"id": int(nid), "type": int(ntype), "permissions": int(perm)}
            for nid, ntype, perm in re.findall(
                r"<node_id>(\d+)</node_id>\s*<node_type>(\d+)</node_type>"
                r"\s*<permissions>(\d+)</permissions>", response.text)]

    def add_context_node(self, context_id, node_id, node_type=1,
                         permissions=7):
        """Attach a view (type 1) or table (type 0) to a context.

        The nodes PUT replaces the whole list — always resubmit the
        existing nodes plus the new one.
        """
        nodes = self.context_nodes(context_id)
        if any(n["id"] == node_id for n in nodes):
            return
        nodes.append({"id": node_id, "type": node_type,
                      "permissions": permissions})
        self._request("PUT", f"{self.api2}/contexts/{context_id}",
                      json={"nodes": nodes})

    # -- views / shares ------------------------------------------------------

    def list_views(self, table_id):
        return self._request(
            "GET", f"{self.api1}/tables/{table_id}/views").json()

    def ensure_view(self, table_id, title):
        for view in self.list_views(table_id):
            if view["title"] == title:
                return view["id"]
        response = self._request(
            "POST", f"{self.api1}/tables/{table_id}/views",
            json={"title": title})
        return response.json()["id"]

    def configure_view(self, table_id, view_id, view_config):
        """Apply a per-table/view config file (schemes/views/*.json).

        ``view_config["columns"]`` is a list of {title, visible, readonly}
        in display order; a column title missing from the table is skipped.
        An optional ``width`` (px) is applied to the *column* — it is
        table-wide, not per-view (Tables drops width in columnSettings).
        Optional ``metaColumns`` lists meta column ids appended to the
        view (-1 id, -2 created by, -3 last edit by, -4 created at,
        -5 last edit at).
        """
        by_title = {c["title"]: c for c in self.list_columns(table_id)}
        settings, visible = [], []
        for order, spec in enumerate(view_config["columns"]):
            column = by_title.get(spec["title"])
            if column is None:
                continue
            if spec.get("width"):
                merged = dict(column.get("customSettings") or {})
                if merged.get("width") != spec["width"]:
                    merged["width"] = spec["width"]
                    self.update_column(
                        column["id"], {"customSettings": merged})
            if spec.get("visible", True):
                visible.append(column["id"])
                settings.append({"columnId": column["id"], "order": order,
                                 "readonly": spec.get("readonly", True),
                                 "mandatory": spec.get("mandatory", False)})
        for order, meta_id in enumerate(
                view_config.get("metaColumns", []), start=len(visible)):
            visible.append(meta_id)
            settings.append({"columnId": meta_id, "order": order,
                             "readonly": True, "mandatory": False})
        self._request("PUT", f"{self.api1}/views/{view_id}",
                      json={"data": {"columns": visible,
                                     "columnSettings": settings,
                                     "sort": []}})

    def share_view(self, view_id, receiver, receiver_type="group"):
        """Read-share a view to a receiver; skips existing shares."""
        shares = self._request(
            "GET", f"{self.api1}/views/{view_id}/shares").json()
        if any(s["receiver"] == receiver for s in shares):
            return
        self._request("POST", f"{self.api1}/shares",
                      json={"nodeType": "view", "nodeId": view_id,
                            "receiver": receiver,
                            "receiverType": receiver_type,
                            "permissionRead": True})


def provision(projekt_id, slug, etage, src_dir, prov, context_name=None,
              context_id=None, groups=None, remote_dir=DEFAULT_REMOTE_DIR,
              scheme_dir=None):
    """Provision all types of one project/floor; returns a result map."""
    groups = groups or {}
    scheme_dir = Path(scheme_dir) if scheme_dir else SCHEME_DIR
    src_dir = Path(src_dir)
    if context_id is not None:
        context = int(context_id)
    else:
        context = prov.ensure_context(
            context_name or context_name_default(projekt_id, slug, etage))
    result = {"context_id": context, "tables": {}}
    known_tables = prov.list_tables()

    for typ, (scheme_file, csv_name, _label) in TYPES.items():
        title = table_title(projekt_id, slug, etage, typ)
        table_id = known_tables.get(title)
        entry = {"title": title}
        if table_id is None:
            table_id = prov.create_table_from_scheme(
                scheme_dir / scheme_file, title)
            entry["created"] = True
        else:
            scheme = json.loads(
                (scheme_dir / scheme_file).read_text(encoding="utf-8"))
            prov.sync_mandatory(table_id, scheme.get("columns", []))
        entry["table_id"] = table_id

        csv_file = src_dir / csv_name
        if csv_file.is_file() and prov._row_count(table_id) == 0:
            nc_path = prov.importer.upload_file(csv_file, remote_dir)
            entry["import"] = prov.importer.import_table(
                table_id, nc_path, create_missing_columns=False)

        col_id = prov.ensure_column(table_id, ORIGINAL_COLUMN)
        entry["original_marked"] = prov.mark_rows_original(table_id, col_id)

        views = {}
        for group in VIEW_GROUPS:
            config_path = scheme_dir / "views" / f"{typ}_{group}.json"
            view_config = json.loads(
                config_path.read_text(encoding="utf-8"))
            view_id = prov.ensure_view(table_id, view_config["title"])
            prov.configure_view(table_id, view_id, view_config)
            prov.share_view(view_id, ADMIN_GROUP)
            if group in groups:
                prov.share_view(view_id, groups[group])
            prov.add_context_node(context, view_id)
            views[group] = view_id
        entry["views"] = views
        result["tables"][typ] = entry
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Provision an Aufmass project/floor into Nextcloud Tables")
    parser.add_argument("--projekt", default=None,
                        help="Wuttke Projekt-ID (default: PROJEKT_ID/PROJEKT-ID env)")
    parser.add_argument("--slug", required=True, help="project slug, e.g. Stadthalle")
    parser.add_argument("--etage", required=True, help="floor slug, e.g. UG")
    parser.add_argument("--src", required=True,
                        help="directory holding the converter CSVs")
    parser.add_argument("--context-name", default=None,
                        help="existing context name (default 'AUF <id> <slug> <etage>')")
    parser.add_argument("--context-id", type=int, default=None,
                        help="existing context id; skips context lookup/creation")
    parser.add_argument("--group", action="append", default=[],
                        metavar="NAME=UID",
                        help="NC group uid per view group, e.g. gf=<uid>; "
                             "repeatable for gf/plan/monteur/abrechnung")
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR,
                        help="WebDAV upload dir (default AUF)")
    args = parser.parse_args(argv)

    groups = dict(g.split("=", 1) for g in args.group)
    base_url, user, password = load_credentials()
    projekt = (args.projekt or os.environ.get("PROJEKT_ID")
               or os.environ.get("PROJEKT-ID"))
    if not projekt:
        raise ProvisionError(
            "Projekt-ID missing: pass --projekt or set PROJEKT_ID/PROJEKT-ID")
    prov = TablesProvisioner(base_url, user, password)
    result = provision(projekt, args.slug, args.etage, args.src, prov,
                       context_name=args.context_name,
                       context_id=args.context_id, groups=groups,
                       remote_dir=args.remote_dir)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
