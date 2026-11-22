"""itsaplantools.deploy - apply authored Its a Plan state to the instance (Git -> target).

Reconciles, in order: project templates (import new/changed, delete superseded
same-name copies), teams, projects (create-once from template by project key).
Default is dry-run; --apply executes. Never deletes unmanaged objects.

Usage: python -m wit_pytools.itsaplantools.deploy [--dry-run|--apply] [--keep-old-templates]
Exit codes: 0 ok, 1 error.
"""

import argparse
import re
import sys

from .api import (
    Client,
    ItsaplanError,
    canonical,
    list_all,
    load_env,
    load_templates,
    parse_ini,
)


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    if len(s) < 2:
        s = (s + "-team")[:40]
    return s[:40]


def as_list(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys or ("items", "data", "results", "templates", "teams", "projects", "workspaces"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def check_openapi(client):
    """Warn (never fail) if the deployed API lacks expected paths."""
    try:
        spec = client.get("/docs/json")
    except ItsaplanError as exc:
        print(f"warning: /docs/json unreachable ({exc}) - skipping version check")
        return
    paths = set((spec or {}).get("paths", {}))
    needed = ["/workspaces", "/teams"]
    if not any(p.startswith("/workspaces/") and "project-templates" in p for p in paths):
        needed.append("/workspaces/{id}/project-templates")
    if not any(p.startswith("/teams/") and p.endswith("/projects") for p in paths):
        needed.append("/teams/{id}/projects")
    missing = [n for n in needed if n not in paths]
    if missing:
        print("warning: deployed API may differ from upstream main - check paths:")
        for m in missing:
            print(f"  {m}")


def resolve_workspace(client, cfg):
    workspaces = as_list(client.get("/workspaces"), "items", "data", "workspaces", "results")
    if not workspaces:
        raise ItsaplanError("GET /workspaces returned no workspaces")
    wanted = cfg["instance"].get("workspace", "").strip()
    if wanted:
        for ws in workspaces:
            if str(ws.get("id")) == wanted or str(ws.get("name", "")).lower() == wanted.lower():
                return ws
        raise ItsaplanError(f"workspace {wanted!r} not found among visible workspaces")
    return workspaces[0]


def find_team_id(client, name):
    for t in list_all(client, "/teams"):
        if t.get("name") == name:
            return t.get("id")
    return None


def find_template_id(client, wid, name):
    for t in as_list(client.get(f"/workspaces/{wid}/project-templates"), "items", "data", "templates", "results"):
        if t.get("name") == name:
            return t.get("id")
    return None


def template_meta_drift(doc, remote, team_ids):
    """PATCH body when remote name/description/teamIds drifted; None when clean."""
    body = {}
    if remote.get("name") != doc.get("name"):
        body["name"] = doc.get("name")
    if (remote.get("description") or "") != (doc.get("description") or ""):
        body["description"] = doc.get("description") or ""
    remote_teams = remote.get("teamIds")
    if team_ids is None:
        if remote_teams is not None:
            body["teamIds"] = None
    elif sorted(remote_teams or []) != sorted(team_ids):
        body["teamIds"] = team_ids
    return body or None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deploy Its a Plan desired state (git -> instance)")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="show planned calls only (default)")
    group.add_argument("--apply", action="store_true", help="execute the planned calls")
    ap.add_argument("--keep-old-templates", action="store_true",
                    help="keep superseded same-name templates instead of deleting them")
    args = ap.parse_args(argv)
    apply_mode = args.apply

    try:
        base_url, api_key = load_env()
        client = Client(base_url, api_key)
        cfg = parse_ini()
        docs = load_templates(cfg)

        print(f"target: {base_url}")
        check_openapi(client)
        workspace = resolve_workspace(client, cfg)
        wid = workspace.get("id")
        print(f"workspace: {workspace.get('name', wid)} (id {wid})")

        actions = []  # (label, callable)

        # --- teams -----------------------------------------------------------
        remote_teams = {t.get("name"): t for t in list_all(client, "/teams")}
        for t in cfg["teams"]:
            name = t["name"]
            if name in remote_teams:
                print(f"  [ok] team {name!r} exists (id {remote_teams[name].get('id')})")
                continue
            body = {"name": name, "slug": t.get("slug") or slugify(name), "workspaceId": wid}

            def make_team(b=body):
                return client.post("/teams", b)

            actions.append((f"CREATE team {name!r} (slug {body['slug']}, workspace {wid})", make_team))

        # --- templates -------------------------------------------------------
        remote_tpls = as_list(
            client.get(f"/workspaces/{wid}/project-templates"),
            "items", "data", "templates", "results",
        )
        by_name = {}
        for t in remote_tpls:
            by_name.setdefault(t.get("name"), []).append(t)

        for name, doc in sorted(docs.items()):
            ini_entry = next((t for t in cfg["templates"] if t["name"] == name), {})
            spec = ini_entry.get("teams", "*").strip()
            team_ids = None
            if spec not in ("", "*"):
                ids = []
                for w in [s.strip() for s in spec.split(",") if s.strip()]:
                    tid = remote_teams.get(w, {}).get("id")
                    if tid is None:
                        tid = next((t.get("id") for t in cfg["teams"] if t["name"] == w), None)
                        if tid is None:
                            raise ItsaplanError(
                                f"template {name!r}: team {w!r} is neither remote nor defined in ini"
                            )
                    ids.append(tid)
                team_ids = ids

            candidates = by_name.get(name, [])
            if len(candidates) > 1:
                print(f"  [warn] {len(candidates)} remote templates named {name!r} - using first")
            remote = candidates[0] if candidates else None

            if remote is not None:
                exported = client.get(f"/workspaces/{wid}/project-templates/{remote['id']}/export")
                if canonical(exported.get("snapshot")) == canonical(doc.get("snapshot")):
                    drift = template_meta_drift(doc, remote, team_ids)
                    if drift:
                        def make_patch(rid=remote["id"], body=drift):
                            return client.patch(f"/workspaces/{wid}/project-templates/{rid}", body)
                        actions.append((f"PATCH template {name!r} metadata {drift}", make_patch))
                    else:
                        print(f"  [ok] template {name!r} unchanged (id {remote['id']})")
                    continue

            body = {"template": doc, "name": doc.get("name") or name}
            if doc.get("description"):
                body["description"] = doc["description"]
            if team_ids is not None:
                body["teamIds"] = team_ids

            def make_import(b=body):
                return client.post(f"/workspaces/{wid}/project-templates/import", b)

            actions.append((
                f"IMPORT template {name!r}" + (" (content changed)" if remote else " (new)"),
                make_import,
            ))
            if remote is not None and not args.keep_old_templates:
                old_id = remote["id"]

                def make_delete(oid=old_id):
                    return client.delete(f"/workspaces/{wid}/project-templates/{oid}")

                actions.append((f"DELETE superseded template {name!r} (id {old_id})", make_delete))

        # --- projects --------------------------------------------------------
        # existing projects per team (only for teams that already exist remotely)
        projects_by_team = {}
        for t in cfg["projects"]:
            team_name = t.get("team")
            if not team_name:
                raise ItsaplanError(f"project {t['name']!r}: missing 'team = ...'")
            remote_team = remote_teams.get(team_name)
            if remote_team is not None:
                tid = remote_team.get("id")
                if tid not in projects_by_team:
                    try:
                        projects_by_team[tid] = list_all(client, f"/teams/{tid}/projects")
                    except ItsaplanError:
                        projects_by_team[tid] = []
            else:
                projects_by_team[team_name] = []  # new team -> no projects yet

        for t in cfg["projects"]:
            pname = t["name"]
            team_name = t["team"]
            key = t.get("key") or pname
            existing = projects_by_team.get(team_name) or projects_by_team.get(
                remote_teams.get(team_name, {}).get("id"), []
            )
            match = next(
                (p for p in existing if str(p.get("key")) == str(key)), None
            )
            if match is not None:
                print(f"  [ok] project {pname!r} (key {key}) exists - create-once, untouched")
                continue
            tpl_name = t.get("template_name")
            body = {"key": key, "name": t.get("name") or pname}
            if t.get("description"):
                body["description"] = t["description"]
            desc = f"CREATE project {pname!r} (key {key}, team {team_name}"
            if tpl_name:
                desc += f", template {tpl_name}"
            desc += ")"

            def make_project(b=body, tname=team_name, tpl=tpl_name):
                tid = find_team_id(client, tname)
                if tid is None:
                    raise ItsaplanError(f"team {tname!r} not found - was it created above?")
                payload = dict(b)
                if tpl:
                    tpl_id = find_template_id(client, wid, tpl)
                    if tpl_id is None:
                        raise ItsaplanError(f"template {tpl!r} not found in workspace {wid}")
                    payload["templateId"] = tpl_id
                return client.post(f"/teams/{tid}/projects", payload)

            actions.append((desc, make_project))

        # --- execute ---------------------------------------------------------
        if not apply_mode:
            print(f"\ndry-run: {len(actions)} action(s) planned - rerun with --apply to execute")
            for label, _ in actions:
                print(f"  {label}")
            return 0

        for label, call in actions:
            print(f"  [apply] {label}")
            call()
        print(f"\napplied {len(actions)} action(s)")
        return 0
    except ItsaplanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
