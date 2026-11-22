#!/usr/bin/env python3
"""Import wallabag entries into karakeep as link bookmarks.

karakeep re-crawls each URL itself (crawlPriority=low for bulk import).
Tags are not imported. Archived wallabag entries are imported as archived.

Required env vars:
  WALLABAG_URL      e.g. https://wallabag.witconsult.de
  WALLABAG_USER     wallabag login name
  WALLABAG_PASS     wallabag password
  KARAKEEP_URL      e.g. https://keep.w1t.org
  KARAKEEP_API_KEY  karakeep API key (Karakeep UI -> Settings -> API Keys)

KARAKEEP_INSECURE=1 skips TLS verification (needed while the Traefik
Let's Encrypt cert is still pending).

Usage:
  WALLABAG_URL=... WALLABAG_USER=... WALLABAG_PASS=... \
  KARAKEEP_URL=... KARAKEEP_API_KEY=... python3 wallabag-to-karakeep.py

Options: --dry-run prints what would be imported, --limit N caps entries.
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

WALLABAG_URL = "https://wallabag.witconsult.de"
WALLABAG_USER = "manfred@wisniewski.family"
WALLABAG_PASS = "!W.armitzwa/5"
WALLABAG_CLIENT_ID = "1_68wiczmesqcco0kwk00cgk440k0wc8w848gc4ks0g4ocowksks"
WALLABAG_CLIENT_SECRET = "1mgd4s7ynrr4wwwwc4gw00kwsss0kggo0gw8048ssc8ckos0c0"
KARAKEEP_URL = "https://keep.w1t.org"
KARAKEEP_API_KEY = "ak2_25d494437cf27ef296ce_f402ea9974ef2e4b1a4dfc513b635338"
KARAKEEP_INSECURE = 1

INSECURE = os.environ.get("KARAKEEP_INSECURE") == "1"
CTX = ssl.create_default_context()
if INSECURE:
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE


def http(url, method="GET", data=None, headers=None, form=None):
    h = {"Accept": "application/json"}
    h.update(headers or {})
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        raw = r.read()
        return r.status, json.loads(raw) if raw else {}


def wallabag_token():
    status, res = http(
        f"{WALLABAG_URL}/oauth/v2/token",
        method="POST",
        form={
            "grant_type": "password",
            "client_id": WALLABAG_CLIENT_ID,
            "client_secret": WALLABAG_CLIENT_SECRET,
            "username": WALLABAG_USER,
            "password": WALLABAG_PASS,
        },
    )
    if status != 200 or "access_token" not in res:
        sys.exit(f"wallabag auth failed: {status} {res}")
    return res["access_token"]


def wallabag_entries(token):
    """Yield full entry dicts (listing endpoint is slim; fetch each detail)."""
    headers = {"Authorization": f"Bearer {token}"}
    page = 1
    ids = []
    while True:
        status, res = http(
            f"{WALLABAG_URL}/api/entries.json?per_page=100&page={page}",
            headers=headers,
        )
        if status != 200:
            sys.exit(f"wallabag entries page {page} failed: {status} {res}")
        items = res.get("_embedded", {}).get("items", [])
        ids.extend(e["id"] for e in items)
        if page >= res.get("pages", 1):
            break
        page += 1
    print(f"wallabag: {len(ids)} entries found", file=sys.stderr)
    for i, eid in enumerate(ids, 1):
        status, entry = http(
            f"{WALLABAG_URL}/api/entries/{eid}.json", headers=headers
        )
        if status != 200:
            print(f"  ! entry {eid} fetch failed ({status}), skipped", file=sys.stderr)
            continue
        yield entry
        if i % 25 == 0:
            print(f"  ...fetched {i}/{len(ids)}", file=sys.stderr)


def karakeep_create(bookmark):
    return http(
        f"{KARAKEEP_URL}/api/v1/bookmarks",
        method="POST",
        data=bookmark,
        headers={"Authorization": f"Bearer {KARAKEEP_API_KEY}"},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.3,
                    help="seconds between karakeep creates")
    args = ap.parse_args()

    token = wallabag_token()
    created = skipped = failed = 0
    for entry in wallabag_entries(token):
        if args.limit and created >= args.limit:
            break
        url = entry.get("url")
        if not url:
            skipped += 1
            continue
        bookmark = {
            "type": "link",
            "url": url,
            "title": entry.get("title") or None,
            "archived": bool(entry.get("is_archived")),
            "crawlPriority": "low",
        }
        if entry.get("created_at"):
            bookmark["createdAt"] = entry["created_at"]
        if args.dry_run:
            print(json.dumps(bookmark, ensure_ascii=False))
            created += 1
            continue
        try:
            status, res = karakeep_create(bookmark)
        except Exception as e:
            print(f"  ! {url}: {e}", file=sys.stderr)
            failed += 1
            continue
        if status in (200, 201):
            created += 1
        else:
            print(f"  ! {url}: HTTP {status} {res}", file=sys.stderr)
            failed += 1
        time.sleep(args.delay)
    print(f"done: {created} sent, {skipped} skipped (no url), {failed} failed",
          file=sys.stderr)


if __name__ == "__main__":
    main()
