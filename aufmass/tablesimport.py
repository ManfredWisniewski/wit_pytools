"""Import CSV/XLS lists into Nextcloud Tables.

Flow (plan 001-mvp, decision #1): upload the file into the Nextcloud
user storage via WebDAV, then call the Tables import endpoint
``POST /index.php/apps/tables/api/1/import/table/{tableId}`` (or
``.../import/views/{viewId}``) and verify the returned ``ImportState``.

Credentials come from env or .env: NC_URL, NC_USER, NC_PASSWORD
(app password). The endpoint's ``path`` is relative to the user's
files root.

requirements: requests (python-dotenv optional)
"""

import argparse
import csv
import os
import sys
from pathlib import Path, PurePosixPath

import requests

DEFAULT_API_ROOT = "/index.php/apps/tables/api/1"
DEFAULT_REMOTE_DIR = "Aufmass/Import"
DEFAULT_GLOB = "*.csv"


class TablesImportError(RuntimeError):
    """Raised on upload/API failures or a failed ImportState."""


def load_credentials():
    """Return (base_url, user, password) from environment or .env file."""
    try:
        from dotenv import load_dotenv

        # explicit path: implicit discovery could pick up a stray .env on
        # the module-ancestor search path and mix credentials/endpoints
        load_dotenv(Path.cwd() / ".env")
    except ImportError:
        pass
    base_url = os.environ.get("NC_URL", "").rstrip("/")
    user = os.environ.get("NC_USER", "")
    password = os.environ.get("NC_PASSWORD", "")
    if not base_url or not user or not password:
        raise TablesImportError(
            "NC_URL, NC_USER and NC_PASSWORD must be set (env or .env)")
    return base_url, user, password


class NextcloudTablesImporter:
    """WebDAV upload + Tables v1 import API client."""

    def __init__(self, base_url, user, password,
                 api_root=DEFAULT_API_ROOT, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.api_root = self.base_url + api_root
        self.dav_root = f"{self.base_url}/remote.php/dav/files/{user}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({
            "OCS-APIRequest": "true",
            "Accept": "application/json",
        })

    def ensure_remote_dir(self, remote_dir):
        """MKCOL every path segment; existing dirs (405) are fine."""
        path = ""
        for part in PurePosixPath(remote_dir).parts:
            path += "/" + part
            response = self.session.request(
                "MKCOL", self.dav_root + path, timeout=self.timeout)
            if response.status_code not in (201, 405):
                raise TablesImportError(
                    f"MKCOL {path} failed: {response.status_code} "
                    f"{response.text[:200]}")

    def upload_file(self, local_path, remote_dir=DEFAULT_REMOTE_DIR):
        """PUT a local file into the user storage; returns the NC path."""
        local_path = Path(local_path)
        remote_dir = remote_dir.strip("/")
        self.ensure_remote_dir(remote_dir)
        nc_path = f"{remote_dir}/{local_path.name}"
        with local_path.open("rb") as f:
            response = self.session.put(
                f"{self.dav_root}/{nc_path}", data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=self.timeout)
        if response.status_code not in (200, 201, 204):
            raise TablesImportError(
                f"upload {local_path.name} failed: {response.status_code} "
                f"{response.text[:200]}")
        return nc_path

    def import_table(self, table_id, nc_path, create_missing_columns=True):
        """POST /api/1/import/table/{tableId}; returns the ImportState."""
        return self._import("table", table_id, nc_path, create_missing_columns)

    def import_view(self, view_id, nc_path, create_missing_columns=True):
        """POST /api/1/import/views/{viewId}; returns the ImportState."""
        return self._import("views", view_id, nc_path, create_missing_columns)

    def _import(self, kind, target_id, nc_path, create_missing_columns):
        url = f"{self.api_root}/import/{kind}/{target_id}"
        response = self.session.post(
            url, json={"path": nc_path,
                       "createMissingColumns": create_missing_columns},
            timeout=self.timeout)
        if response.status_code != 200:
            raise TablesImportError(
                f"import {kind} {target_id} failed: {response.status_code} "
                f"{response.text[:300]}")
        state = response.json()
        self.verify_import_state(state)
        return state

    @staticmethod
    def verify_import_state(state):
        """Raise on parse/import errors or zero imported rows."""
        errors = state.get("errors_count", 0) \
            + state.get("errors_parsing_count", 0)
        if errors:
            raise TablesImportError(f"ImportState reports {errors} errors")
        rows = state.get("inserted_rows_count", 0) \
            + state.get("updated_rows_count", 0)
        if rows == 0:
            raise TablesImportError("ImportState reports 0 rows imported")


def read_table_map(map_file):
    """Map file -> (table_id, view_id) from a CSV with columns
    file,table_id[,view_id]. 'file' matches basename or src-relative path."""
    table_map = {}
    with Path(map_file).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            table_map[row["file"].strip().lstrip("/")] = (
                int(row["table_id"]) if row.get("table_id") else None,
                int(row["view_id"]) if row.get("view_id") else None,
            )
    return table_map


def _resolve_target(entry, table_map):
    for key in (entry.name, entry.as_posix()):
        if key in table_map:
            return table_map[key]
    return None


def run_import(importer, files, remote_dir, table_map=None, base_dir=None,
               table_id=None, view_id=None, create_missing_columns=True,
               dry_run=False):
    """Upload + import each file; returns one result dict per file."""
    results = []
    for local_path in files:
        target_table, target_view = table_id, view_id
        if table_map is not None:
            key = local_path if base_dir is None \
                else local_path.relative_to(base_dir)
            resolved = _resolve_target(key, table_map)
            if resolved is None:
                results.append({"file": local_path,
                                "error": "no table_id in map"})
                continue
            target_table, target_view = resolved
        if target_table is None and target_view is None:
            results.append({"file": local_path,
                            "error": "no table_id/view_id"})
            continue
        if dry_run:
            results.append({"file": local_path, "table_id": target_table,
                            "view_id": target_view, "dry": True})
            continue
        try:
            nc_path = importer.upload_file(local_path, remote_dir)
            state = (importer.import_view if target_view
                     else importer.import_table)(
                         target_view or target_table, nc_path,
                         create_missing_columns)
            results.append({"file": local_path, "nc_path": nc_path,
                            "state": state})
        except TablesImportError as error:
            results.append({"file": local_path, "error": str(error)})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Upload lists via WebDAV and import into Nextcloud Tables")
    parser.add_argument("src", help="file or directory (recursive)")
    parser.add_argument("--glob", default=DEFAULT_GLOB,
                        help=f"file glob for directory mode (default {DEFAULT_GLOB})")
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR,
                        help=f"WebDAV target dir (default {DEFAULT_REMOTE_DIR})")
    parser.add_argument("--table-id", type=int, default=None,
                        help="target table id (single file or all files)")
    parser.add_argument("--view-id", type=int, default=None,
                        help="import into a view instead of a table")
    parser.add_argument("--map", dest="map_file", default=None,
                        help="CSV with file,table_id[,view_id] for batch import")
    parser.add_argument("--api-root", default=DEFAULT_API_ROOT,
                        help="Tables API root (default index.php path)")
    parser.add_argument("--no-create-columns", action="store_true",
                        help="fail instead of creating missing columns")
    parser.add_argument("--dry-run", action="store_true",
                        help="print planned uploads/imports only")
    args = parser.parse_args(argv)

    src = Path(args.src)
    base_dir = src if src.is_dir() else src.parent
    files = sorted(src.rglob(args.glob)) if src.is_dir() else [src]
    files = [f for f in files if f.is_file() and not f.name.startswith("~$")]
    if not files:
        print(f"no files matching {args.glob} under {src}", file=sys.stderr)
        return 1

    table_map = read_table_map(args.map_file) if args.map_file else None
    if table_map is None and args.table_id is None and args.view_id is None:
        print("need --table-id, --view-id or --map", file=sys.stderr)
        return 1

    importer = None
    if not args.dry_run:
        base_url, user, password = load_credentials()
        importer = NextcloudTablesImporter(
            base_url, user, password, api_root=args.api_root)

    results = run_import(
        importer, files, args.remote_dir, table_map, base_dir,
        table_id=args.table_id, view_id=args.view_id,
        create_missing_columns=not args.no_create_columns,
        dry_run=args.dry_run)

    errors = 0
    for result in results:
        name = result["file"].name
        if "error" in result:
            errors += 1
            print(f"ERROR {name}: {result['error']}", file=sys.stderr)
        elif result.get("dry"):
            print(f"DRY {name} -> table {result.get('table_id')} "
                  f"view {result.get('view_id')}")
        else:
            state = result["state"]
            print(f"{name}: +{state['inserted_rows_count']} "
                  f"~{state['updated_rows_count']} rows, "
                  f"{state['created_columns_count']} cols created "
                  f"({result['nc_path']})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
