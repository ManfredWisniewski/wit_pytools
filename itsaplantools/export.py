"""itsaplantools.export - pull Its a Plan instance state into exports/ (target -> Git).

Writes exports/{workspaces,teams,projects}.json and
exports/templates/<name>.project-template.json, then commits and pushes only
when the content changed. Aborts on empty export, dirty tree (outside exports/),
wrong branch or a concurrent run. Doubles as the backup path.

Usage: python -m wit_pytools.itsaplantools.export [--dry-run]
Exit codes: 0 ok/dry-run, 1 error, 2 guard abort, 3 locked.
"""

import argparse
import json
import os
import subprocess
import sys

from .api import (
    Client,
    ItsaplanError,
    list_all,
    load_env,
    parse_ini,
)

EXPORT_BRANCH = "main"
LOCK_FILE = ".itsaplan-export.lock"
EXPORTS_DIR = "exports"


def git(*args, check=True):
    res = subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8"
    )
    if check and res.returncode != 0:
        raise ItsaplanError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res


def git_dirty_outside_exports():
    res = git("status", "--porcelain")
    for line in res.stdout.splitlines():
        path = line[3:].strip().strip('"')
        # porcelain renames show "old -> new"; keep it simple: flag anything
        # that is not inside exports/
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path != EXPORTS_DIR and not path.startswith(EXPORTS_DIR + "/"):
            return path
    return None


def acquire_lock():
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return LOCK_FILE


def release_lock(path):
    try:
        os.remove(path)
    except OSError:
        pass


def resolve_workspace(client, cfg):
    workspaces = _as_list(client.get("/workspaces"))
    if not workspaces:
        raise ItsaplanError("GET /workspaces returned no workspaces")
    wanted = cfg["instance"].get("workspace", "").strip()
    if wanted:
        for ws in workspaces:
            if str(ws.get("id")) == wanted or str(ws.get("name", "")).lower() == wanted.lower():
                return ws
        raise ItsaplanError(f"workspace {wanted!r} not found among {len(workspaces)} visible workspaces")
    return workspaces[0]


def _as_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "workspaces", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ItsaplanError("unexpected list response shape")


def collect(client, workspace_id):
    """Fetch everything the mirror needs. Returns dict with json payloads."""
    ws = client.get("/workspaces")
    teams = list_all(client, "/teams")
    projects = []
    for team in teams:
        tid = team.get("id")
        if tid is None:
            continue
        try:
            projects.extend(list_all(client, f"/teams/{tid}/projects"))
        except ItsaplanError:
            # team may have no project listing permission - skip it
            pass
    templates = {}
    tpl_list = _as_list(client.get(f"/workspaces/{workspace_id}/project-templates"))
    for tpl in tpl_list:
        tid = tpl.get("id")
        name = tpl.get("name") or f"template-{tid}"
        doc = client.get(f"/workspaces/{workspace_id}/project-templates/{tid}/export")
        templates[f"templates/{_safe_name(name)}.project-template.json"] = doc
    return {
        "workspaces.json": ws,
        "teams.json": teams,
        "projects.json": projects,
        "templates": templates,
    }


def _safe_name(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def render(files):
    """files: {relpath: obj} -> {abspath: text}."""
    out = {}
    for rel, obj in files.items():
        path = os.path.join(EXPORTS_DIR, *rel.split("/"))
        out[path] = (
            json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
    return out


def plan_writes(rendered):
    """Compare rendered content to disk; return (changed_paths, all_paths)."""
    changed = []
    for path, text in rendered.items():
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read() != text:
                    changed.append(path)
        except OSError:
            changed.append(path)
    # files on disk that are no longer produced (deleted upstream objects)
    produced = set(rendered)
    for dirpath, _dirs, fnames in os.walk(EXPORTS_DIR):
        for fname in fnames:
            if fname == "README.md" or fname.startswith("."):
                continue
            p = os.path.join(dirpath, fname)
            if p not in produced:
                changed.append(p + " (delete)")
    return changed, sorted(rendered)


def run_export(client, cfg, dry_run):
    workspace = resolve_workspace(client, cfg)
    wid = workspace.get("id")
    collected = collect(client, wid)
    files = {
        "workspaces.json": collected["workspaces.json"],
        "teams.json": collected["teams.json"],
        "projects.json": collected["projects.json"],
    }
    files.update(collected["templates"])

    # empty-export guard
    total = (
        len(_as_list(collected["teams.json"]))
        + len(_as_list(collected["projects.json"]))
        + len(collected["templates"])
    )
    if total == 0:
        raise ItsaplanError("export produced no teams, projects or templates - aborting")

    rendered = render(files)
    changed, _all = plan_writes(rendered)

    if dry_run:
        print(f"workspace: {workspace.get('name', wid)} (id {wid})")
        print(f"would write {len(rendered)} files under {EXPORTS_DIR}/")
        for p in changed:
            print(f"  change: {p}")
        if not changed:
            print("  (no changes)")
        return 0

    for path, text in rendered.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    # remove stale mirror files
    for item in changed:
        if item.endswith(" (delete)"):
            os.remove(item[: -len(" (delete)")])

    if not changed:
        print("exports/ already up to date - nothing to commit")
        return 0

    git("add", EXPORTS_DIR)
    git("commit", "-m", "chore(exports): sync Its a Plan instance state")
    try:
        git("push", "origin", "HEAD")
    except ItsaplanError as exc:
        print(f"warning: commit created but push failed ({exc}) - push manually")
    print(f"exported {len(rendered)} files, committed ({len(changed)} changed)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export Its a Plan state into exports/")
    ap.add_argument("--dry-run", action="store_true", help="show planned writes, no side effects")
    args = ap.parse_args(argv)

    lock = acquire_lock()
    if lock is None:
        print(f"another export is running (lock: {LOCK_FILE})", file=sys.stderr)
        return 3
    try:
        # git guards (checked only when we would commit; dry-run skips them)
        if not args.dry_run:
            inside = git("rev-parse", "--is-inside-work-tree", check=False)
            if inside.returncode != 0 or inside.stdout.strip() != "true":
                raise ItsaplanError("not inside a git work tree")
            branch = git("branch", "--show-current").stdout.strip()
            if branch != EXPORT_BRANCH:
                raise ItsaplanError(f"wrong branch {branch!r} - export commits only on {EXPORT_BRANCH!r}")
            dirty = git_dirty_outside_exports()
            if dirty:
                raise ItsaplanError(f"working tree is dirty outside exports/ ({dirty}) - commit or stash first")

        base_url, api_key = load_env()
        client = Client(base_url, api_key)
        cfg = parse_ini()
        return run_export(client, cfg, args.dry_run)
    except ItsaplanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if any(s in str(exc) for s in ("abort", "dirty", "branch", "work tree", "concurrent")) else 1
    finally:
        release_lock(lock)


if __name__ == "__main__":
    sys.exit(main())
