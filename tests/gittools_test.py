"""gittools coverage: commit_changes staging/reset/push behaviour."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wit_pytools import gittools


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    (repo / "+INBOX" / "emails").mkdir(parents=True)
    (repo / "base").write_text("x")
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "init", cwd=repo)
    return repo


def test_commit_on_change(tmp_path):
    repo = _repo(tmp_path)
    sub = repo / "+INBOX" / "emails"
    (sub / "doc.md").parent.mkdir(parents=True, exist_ok=True)
    (sub / "doc.md").write_text("mail")
    gittools.commit_changes(repo, "+INBOX/emails", push=False)
    log = _git("log", "--oneline", cwd=repo).stdout
    assert "chore(archive)" in log


def test_no_changes_no_commit(tmp_path):
    repo = _repo(tmp_path)
    before = _git("rev-parse", "HEAD", cwd=repo).stdout
    gittools.commit_changes(repo, "+INBOX/emails", push=False)
    assert _git("rev-parse", "HEAD", cwd=repo).stdout == before


def test_dry_run_resets_index(tmp_path):
    repo = _repo(tmp_path)
    sub = repo / "+INBOX" / "emails"
    (sub / "doc.md").parent.mkdir(parents=True, exist_ok=True)
    (sub / "doc.md").write_text("mail")
    gittools.commit_changes(repo, "+INBOX/emails", push=False, dry_run=True, count=1)
    status = _git("status", "--porcelain", cwd=repo).stdout
    assert "?? +INBOX/" in status  # staged add was reset, file remains untracked
