"""Shared git helpers: run a command, commit+push a subtree on change.

Stdlib only. The caller passes the repo checkout; nothing here reads
repository layout or environment.
"""

from __future__ import annotations

import datetime as dt
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("gittools")


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    log.debug("$ %s", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def commit_changes(repo: Path, subdir: str, push: bool = True, dry_run: bool = False,
                   count: int = 0, message_prefix: str = "chore(archive)") -> None:
    """Stage ``repo/subdir``, commit on change, optionally push.

    ``count`` only feeds the commit message. On dry-run the staged changes
    are reset instead of committed. When pushing, the branch is rebased on
    the remote first — other writers push to the same repo and a bare
    commit+push would be rejected non-fast-forward.
    """
    if push and not dry_run:
        run(["git", "pull", "--rebase"], cwd=repo)
    run(["git", "add", "-A", subdir], cwd=repo)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode == 0:
        log.info("no changes to commit")
        return
    if dry_run:
        log.info("dry run: would commit %d new item(s)", count)
        run(["git", "reset", "--quiet", subdir], cwd=repo)
        return
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run(["git", "commit", "-m", f"{message_prefix}: {count} item(s) {stamp}"], cwd=repo)
    if push:
        run(["git", "push"], cwd=repo)
    log.info("committed%s", " and pushed" if push else "")
