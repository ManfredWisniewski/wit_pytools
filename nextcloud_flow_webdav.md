Summary: Nightly “retag all files in Groupfolders” (no Windmill required)
Goal
Re-apply your existing regex-based tagging rules to all existing files (Groupfolders only) on a nightly schedule, because Nextcloud Flow “file created” triggers don’t retroactively re-run.

Core idea
Keep your current Python scheduler/task runner (OCS-based where useful), and add WebDAV calls specifically for assigning/removing system tags, because that’s the part OCS is often missing/limited for.

What to implement in your Python project
1) Enumerate all files + obtain fileid
For each Groupfolder root that the admin/service account can see, run a recursive WebDAV PROPFIND to list items.
Request the DAV property oc:fileid so you get a stable numeric <fileid> per file.
Also collect the path (href) so you can run your regex matching on filename or full path.
Result per file:

fileid
path (or filename)
2) Evaluate your regex rules
For each file:

Apply your existing regex logic
Produce the desired set of system tags (by name) that should be present (and optionally those that must be absent)
3) Resolve tag names → tag IDs (once per run, then cache)
You need <tagid> to attach/detach. Do one of:

Static config: store a mapping tag_name -> tagid
Dynamic: fetch tags once at start (however you already do it), then cache in-memory
4) Modify system tags via WebDAV (this is the key addition)
Use Nextcloud WebDAV systemtags-relations endpoints:

Assign a tag
PUT /remote.php/dav/systemtags-relations/files/<fileid>/<tagid>
Unassign a tag
DELETE /remote.php/dav/systemtags-relations/files/<fileid>/<tagid>
(Optional) Read current tags
PROPFIND /remote.php/dav/systemtags-relations/files/<fileid>
Use this to compute a delta (to_add, to_remove) and avoid redundant calls.
Authentication:

same as WebDAV: service user + app password (basic auth)
5) Operational notes
Run only over Groupfolders (as you requested).
Do it in batches (avoid one gigantic PROPFIND response).
Add rate limiting / retries to avoid hammering Nextcloud.
Log changes: file path + tags added/removed.
Optional: Where Windmill would fit (if you still want it later)
Windmill wouldn’t “trigger Flow for old files”; it would just:

schedule the nightly job
provide UI/logging/retries
But since you already have a Python system, you can skip Windmill entirely.

Completion status
Design is complete and ready to implement in your separate Python repo.
Start a new process in that codebase and point me at the repo + existing script entrypoint; I’ll apply the minimal changes to add:
PROPFIND file enumeration with oc:fileid
PUT/DELETE system tag relations via DAV