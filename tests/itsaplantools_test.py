#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for wit_pytools.itsaplantools - fake HTTP, no network."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from wit_pytools.itsaplantools import api  # noqa: E402
from wit_pytools.itsaplantools import deploy as dep  # noqa: E402
from wit_pytools.itsaplantools import export as ex  # noqa: E402


class FakeClient:
    """Route-table fake; mutates state for import/create like the real API."""

    def __init__(self, state=None):
        if state is None:
            state = {
                "get": {},
                "post": {},
                "patch": {},
                "delete": {},
            }
        self.state = state
        self.calls = []
        # mutable entity stores for deploy tests
        self.workspaces = [{"id": 1, "name": "Main"}]
        self.teams = []
        self.templates = []
        self.exports = {}
        self.projects = []
        self._next = {"team": 100, "tpl": 200, "proj": 300}

    # -- export-test helpers -------------------------------------------------
    def _route(self, method, path):
        return (method, path.split("?")[0])

    # -- API -----------------------------------------------------------------
    def get(self, path):
        key = self._route("GET", path)
        self.calls.append(("GET", path))
        routes = self.state["get"]
        if key in routes:
            v = routes[key]
            return v() if callable(v) else v
        for (m, p), v in routes.items():
            if m == "GET" and p.endswith("*") and path.split("?")[0].startswith(p[:-1]):
                return v() if callable(v) else v
        # deploy-test stateful routes
        p = path.split("?")[0]
        if p == "/docs/json":
            return {"paths": {"/workspaces": {}, "/teams": {},
                              "/workspaces/{workspaceId}/project-templates": {},
                              "/teams/{teamId}/projects": {}}}
        if p == "/workspaces":
            return list(self.workspaces)
        if p == "/teams":
            return list(self.teams)
        if p == "/workspaces/1/project-templates":
            return [dict(t) for t in self.templates]
        if p.startswith("/workspaces/1/project-templates/") and p.endswith("/export"):
            return self.exports.get(int(p.split("/")[-2]))
        if p.startswith("/teams/") and p.endswith("/projects"):
            tid = int(p.split("/")[2])
            return [x for x in self.projects if x["teamId"] == tid]
        raise api.ApiError(404, "GET", path)

    def post(self, path, body):
        key = self._route("POST", path)
        self.calls.append(("POST", path, body))
        p = path.split("?")[0]
        handler = self.state["post"].get(key)
        if handler is not None:
            return handler(body)
        if p == "/teams":
            tid = self._next["team"]
            self._next["team"] += 1
            team = {"id": tid, "name": body["name"], "slug": body["slug"],
                    "workspaceId": body["workspaceId"]}
            self.teams.append(team)
            return dict(team)
        if p == "/workspaces/1/project-templates/import":
            tid = self._next["tpl"]
            self._next["tpl"] += 1
            tpl = {"id": tid, "name": body["name"],
                   "description": body.get("description", ""),
                   "teamIds": body.get("teamIds")}
            self.templates.append(tpl)
            self.exports[tid] = body["template"]
            return dict(tpl)
        if p.startswith("/teams/") and p.endswith("/projects"):
            tid = int(p.split("/")[2])
            pid = self._next["proj"]
            self._next["proj"] += 1
            proj = {"id": pid, "key": body["key"], "name": body["name"], "teamId": tid}
            self.projects.append(proj)
            return dict(proj)
        raise api.ApiError(404, "POST", path)

    def patch(self, path, body):
        key = self._route("PATCH", path)
        self.calls.append(("PATCH", path, body))
        handler = self.state["patch"].get(key)
        if handler is not None:
            return handler(body)
        p = path.split("?")[0]
        if p.startswith("/workspaces/1/project-templates/"):
            tid = int(p.split("/")[-1])
            for t in self.templates:
                if t["id"] == tid:
                    t.update(body)
                    return dict(t)
        raise api.ApiError(404, "PATCH", path)

    def delete(self, path):
        key = self._route("DELETE", path)
        self.calls.append(("DELETE", path))
        handler = self.state["delete"].get(key)
        if handler is not None:
            return handler()
        p = path.split("?")[0]
        if p.startswith("/workspaces/1/project-templates/"):
            tid = int(p.split("/")[-1])
            self.templates = [t for t in self.templates if t["id"] != tid]
            self.exports.pop(tid, None)
            return None
        raise api.ApiError(404, "DELETE", path)


def export_state():
    return {
        "get": {
            ("GET", "/workspaces"): [{"id": 1, "name": "Main"}],
            ("GET", "/teams"): [{"id": 5, "name": "Backend", "slug": "backend", "workspaceId": 1}],
            ("GET", "/teams/5/projects"): [
                {"id": 50, "key": "API", "name": "API", "teamId": 5}
            ],
            ("GET", "/workspaces/1/project-templates"): [
                {"id": 7, "name": "scrum", "description": "", "teamIds": None}
            ],
            ("GET", "/workspaces/1/project-templates/7/export"): {
                "format": "itsaplan.project-template",
                "version": 1,
                "name": "scrum",
                "description": "",
                "snapshot": {"columns": [{"id": 1}]},
            },
        },
        "post": {},
        "patch": {},
        "delete": {},
    }


class ExportCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("exports", exist_ok=True)
        with open("exports/README.md", "w") as fh:
            fh.write("# mirror\n")
        self.cfg = {"instance": {}, "templates": [], "teams": [], "projects": []}

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_dry_run_writes_nothing(self):
        client = FakeClient(export_state())
        with mock.patch.object(ex, "load_env", return_value=("http://x", "k")), \
             mock.patch.object(ex, "parse_ini", return_value=self.cfg), \
             mock.patch.object(ex, "Client", return_value=client):
            rc = ex.main(["--dry-run"])
        self.assertEqual(rc, 0)
        files = [f for f in os.listdir("exports") if f != "README.md"]
        self.assertEqual(files, [])

    def test_collect_render_layout(self):
        client = FakeClient(export_state())
        collected = ex.collect(client, 1)
        rendered = ex.render({
            "workspaces.json": collected["workspaces.json"],
            "teams.json": collected["teams.json"],
            "projects.json": collected["projects.json"],
            **collected["templates"],
        })
        self.assertIn(os.path.join("exports", "workspaces.json"), rendered)
        self.assertIn(os.path.join("exports", "templates", "scrum.project-template.json"), rendered)
        data = json.loads(rendered[os.path.join("exports", "templates", "scrum.project-template.json")])
        self.assertEqual(data["format"], "itsaplan.project-template")

    def test_empty_export_aborts(self):
        state = export_state()
        state["get"][("GET", "/teams")] = []
        state["get"][("GET", "/teams/5/projects")] = []
        state["get"][("GET", "/workspaces/1/project-templates")] = []
        client = FakeClient(state)
        with self.assertRaises(api.ItsaplanError) as ctx:
            ex.run_export(client, self.cfg, dry_run=True)
        self.assertIn("no teams", str(ctx.exception))

    def test_lock_prevents_concurrent_run(self):
        self.assertIsNotNone(ex.acquire_lock())
        self.assertIsNone(ex.acquire_lock())
        ex.release_lock(ex.LOCK_FILE)
        self.assertIsNotNone(ex.acquire_lock())
        ex.release_lock(ex.LOCK_FILE)

    def test_401_surfaces_rotation_hint(self):
        class Deny(FakeClient):
            def get(self, path):
                raise api.ApiError(401, "GET", path)
        client = Deny(export_state())
        with self.assertRaises(api.ApiError) as ctx:
            client.get("/workspaces")
        self.assertIn("rotate", str(ctx.exception))


TEMPLATE_DOC = {
    "format": "itsaplan.project-template",
    "version": 1,
    "name": "scrum",
    "description": "Scrum board",
    "snapshot": {"columns": [{"id": 1, "name": "Todo"}]},
}

CFG = {
    "instance": {},
    "templates": [{"name": "scrum", "teams": "*"}],
    "teams": [{"name": "Backend", "slug": "backend"}],
    "projects": [{"name": "API", "team": "Backend", "key": "API",
                  "template_name": "scrum"}],
}
DOCS = {"scrum": TEMPLATE_DOC}


def run_deploy(client, argv, cfg=CFG, docs=DOCS):
    with mock.patch.object(dep, "load_env", return_value=("http://x", "k")), \
         mock.patch.object(dep, "parse_ini", return_value=cfg), \
         mock.patch.object(dep, "load_templates", return_value=docs), \
         mock.patch.object(dep, "Client", return_value=client):
        return dep.main(argv)


class DeployCase(unittest.TestCase):
    def test_dry_run_default_plans_without_mutating(self):
        client = FakeClient()
        rc = run_deploy(client, [])
        self.assertEqual(rc, 0)
        posts = [c for c in client.calls if c[0] == "POST"]
        self.assertEqual(posts, [])
        self.assertTrue(any(c[0] == "GET" for c in client.calls))

    def test_apply_creates_team_template_project_in_order(self):
        client = FakeClient()
        rc = run_deploy(client, ["--apply"])
        self.assertEqual(rc, 0)
        posts = [(c[1], c[2]) for c in client.calls if c[0] == "POST"]
        paths = [p for p, _ in posts]
        self.assertEqual(paths[0], "/teams")
        self.assertEqual(paths[1], "/workspaces/1/project-templates/import")
        self.assertTrue(paths[2].startswith("/teams/") and paths[2].endswith("/projects"))
        proj_body = posts[2][1]
        self.assertEqual(proj_body["key"], "API")
        self.assertEqual(proj_body["templateId"], 200)  # freshly imported template id
        self.assertEqual(len(client.projects), 1)
        self.assertEqual(len(client.templates), 1)

    def test_idempotent_second_run(self):
        client = FakeClient()
        run_deploy(client, ["--apply"])
        calls_before = len(client.calls)
        rc = run_deploy(client, ["--apply"])
        self.assertEqual(rc, 0)
        new_posts = [c for c in client.calls[calls_before:] if c[0] == "POST"]
        self.assertEqual(new_posts, [])

    def test_changed_template_reimports_and_deletes_old(self):
        client = FakeClient()
        client.teams = [{"id": 5, "name": "Backend", "slug": "backend", "workspaceId": 1}]
        client.templates = [{"id": 7, "name": "scrum", "description": "Scrum board",
                             "teamIds": None}]
        client.exports[7] = {**TEMPLATE_DOC, "snapshot": {"columns": [{"id": 1, "name": "Old"}]}}
        rc = run_deploy(client, ["--apply"])
        self.assertEqual(rc, 0)
        kinds = [(c[0], c[1]) for c in client.calls]
        self.assertTrue(any(k == "POST" and "import" in p for k, p in kinds))
        self.assertTrue(any(k == "DELETE" and p.endswith("/7") for k, p in kinds))
        self.assertEqual([t["name"] for t in client.templates], ["scrum"])
        self.assertNotIn(7, client.exports)

    def test_existing_project_not_recreated(self):
        client = FakeClient()
        client.teams = [{"id": 5, "name": "Backend", "slug": "backend", "workspaceId": 1}]
        client.templates = [{"id": 7, "name": "scrum", "description": "Scrum board",
                             "teamIds": None}]
        client.exports[7] = TEMPLATE_DOC
        client.projects = [{"id": 50, "key": "API", "name": "API", "teamId": 5}]
        rc = run_deploy(client, ["--apply"])
        self.assertEqual(rc, 0)
        project_posts = [c for c in client.calls
                         if c[0] == "POST" and c[1].endswith("/projects")]
        self.assertEqual(project_posts, [])

    def test_team_restriction_maps_to_teamIds(self):
        client = FakeClient()
        client.teams = [{"id": 5, "name": "Backend", "slug": "backend", "workspaceId": 1}]
        cfg = dict(CFG)
        cfg["templates"] = [{"name": "scrum", "teams": "Backend"}]
        rc = run_deploy(client, ["--apply"], cfg=cfg)
        self.assertEqual(rc, 0)
        import_call = next(c for c in client.calls
                           if c[0] == "POST" and "import" in c[1])
        self.assertEqual(import_call[2]["teamIds"], [5])

    def test_unknown_team_in_template_spec_fails(self):
        client = FakeClient()
        cfg = dict(CFG)
        cfg["templates"] = [{"name": "scrum", "teams": "Nope"}]
        rc = run_deploy(client, ["--apply"], cfg=cfg)
        self.assertEqual(rc, 1)  # main catches ItsaplanError -> exit 1


if __name__ == "__main__":
    unittest.main()
