"""ytdlptools coverage: install check, item resolution, download loop."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wit_pytools import ytdlptools

FIXTURES = Path(__file__).parent / "ytdlptools"


def _proc(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _load_playlist_json():
    return (FIXTURES / "playlist.json").read_text(encoding="utf-8")


def test_is_yt_dlp_installed_true(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: _proc(0, "2026.01.01"))
    assert ytdlptools.is_yt_dlp_installed() is True


def test_is_yt_dlp_installed_false(monkeypatch):
    def _fail(*a, **kw):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", _fail)
    assert ytdlptools.is_yt_dlp_installed() is False


def test_run_yt_dlp_command_missing_raises(monkeypatch):
    def _fail(*a, **kw):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", _fail)
    with pytest.raises(RuntimeError, match="yt-dlp is not installed"):
        ytdlptools.run_yt_dlp_command(["--version"])


def test_run_yt_dlp_command_module_fallback(monkeypatch):
    calls = []

    def _fake(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "yt-dlp":
            raise FileNotFoundError("binary missing")
        return _proc(0, "ok")

    monkeypatch.setattr(subprocess, "run", _fake)
    proc = ytdlptools.run_yt_dlp_command(["--version"])
    assert proc.stdout == "ok"
    assert calls[1][1:4] == ["-m", "yt_dlp", "--version"]


def test_resolve_items_playlist(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: _proc(0, _load_playlist_json()))
    items = ytdlptools.resolve_items("https://youtube.com/playlist?list=X")
    assert len(items) == 3
    assert items[0].url == "https://www.youtube.com/watch?v=v1"
    assert items[1].title == "Song Two"
    assert items[2].video_id == "v3"


def test_resolve_items_single_video(monkeypatch):
    video = json.dumps({"id": "v1", "title": "Song One",
                        "webpage_url": "https://www.youtube.com/watch?v=v1"})
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: _proc(0, video))
    items = ytdlptools.resolve_items("https://www.youtube.com/watch?v=v1")
    assert len(items) == 1
    assert items[0].url == "https://www.youtube.com/watch?v=v1"


def test_resolve_items_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: _proc(1, stderr="ERROR: nope"))
    with pytest.raises(RuntimeError, match="could not resolve"):
        ytdlptools.resolve_items("https://example.invalid/x")


def _fake_download_run(target_dir, failures=None, record=None):
    """subprocess.run fake: --version ok, -J returns playlist, download writes a file."""
    failures = failures or set()

    def _run(cmd, **kw):
        if record is not None:
            record.append(cmd)
        if "--version" in cmd:
            return _proc(0, "2026.01.01")
        if "-J" in cmd:
            return _proc(0, _load_playlist_json())
        item_url = cmd[-1]
        if item_url in failures:
            return _proc(1, stderr=f"ERROR: unavailable {item_url}")
        video_id = item_url.rsplit("=", 1)[-1]
        out = Path(target_dir) / f"Song [{video_id}].mp3"
        out.write_bytes(b"fake")
        return _proc(0, f"[download] done\n{out}\n")
    return _run


def test_download_audio_playlist_creates_one_file_per_video(monkeypatch, tmp_path):
    target = tmp_path / "music"
    monkeypatch.setattr(subprocess, "run", _fake_download_run(target))
    result = ytdlptools.download_audio(
        "https://youtube.com/playlist?list=X", target)
    assert result.ok
    assert len(result.files) == 3
    assert all(Path(f).exists() for f in result.files)
    assert target.exists()


def test_download_audio_default_command_shape(monkeypatch, tmp_path):
    record = []
    monkeypatch.setattr(subprocess, "run",
                        _fake_download_run(tmp_path, record=record))
    ytdlptools.download_audio("https://youtube.com/playlist?list=X", tmp_path)
    cmd = next(c for c in record if "--print" in c)
    assert cmd[0] == "yt-dlp"
    for flag in ["-x", "--audio-format", "mp3", "--audio-quality", "0",
                 "--embed-metadata", "--embed-thumbnail",
                 "%(title)s [%(id)s].%(ext)s", "-P", str(tmp_path),
                 "--no-playlist"]:
        assert flag in cmd


def test_download_audio_caller_options_passed_through(monkeypatch, tmp_path):
    record = []
    monkeypatch.setattr(subprocess, "run",
                        _fake_download_run(tmp_path, record=record))
    ytdlptools.download_audio(
        "https://youtube.com/playlist?list=X", tmp_path,
        audio_format="m4a", embed_metadata=False, embed_thumbnail=False,
        output_template="%(id)s.%(ext)s",
        extra_args=["--limit-rate", "1M"])
    cmd = next(c for c in record if "--print" in c)
    assert "m4a" in cmd
    assert "%(id)s.%(ext)s" in cmd
    assert "--limit-rate" in cmd and "1M" in cmd
    assert "--embed-metadata" not in cmd
    assert "--embed-thumbnail" not in cmd


def test_download_audio_item_failure_continues_and_reports(monkeypatch, tmp_path):
    failing = "https://www.youtube.com/watch?v=v2"
    monkeypatch.setattr(subprocess, "run",
                        _fake_download_run(tmp_path, failures={failing}))
    result = ytdlptools.download_audio(
        "https://youtube.com/playlist?list=X", tmp_path)
    assert not result.ok
    assert len(result.files) == 2
    assert len(result.failures) == 1
    assert result.failures[0].url == failing
    assert "unavailable" in result.failures[0].error


def test_download_audio_creates_missing_target_dir(monkeypatch, tmp_path):
    target = tmp_path / "deep" / "nested"
    monkeypatch.setattr(subprocess, "run", _fake_download_run(target))
    result = ytdlptools.download_audio(
        "https://youtube.com/playlist?list=X", target)
    assert target.exists()
    assert len(result.files) == 3


def test_download_audio_requires_yt_dlp(monkeypatch, tmp_path):
    def _fail(*a, **kw):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", _fail)
    with pytest.raises(RuntimeError, match="yt-dlp is not installed"):
        ytdlptools.download_audio("https://youtube.com/watch?v=v1", tmp_path)
