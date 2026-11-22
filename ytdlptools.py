#!/usr/bin/env python
# requires: yt-dlp (https://github.com/yt-dlp/yt-dlp), ffmpeg
"""
yt-dlp wrapper for music downloads — single YouTube videos and playlists.

Spec: +wit/specs/wit_pytools/ytdlptools/
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

__all__ = [
    "DownloadItemResult",
    "DownloadResult",
    "download_audio",
    "is_yt_dlp_installed",
    "resolve_items",
    "run_yt_dlp_command",
]

DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_AUDIO_QUALITY = "0"
DEFAULT_OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".opus", ".ogg", ".flac", ".wav"}


@dataclass
class DownloadItemResult:
    """Outcome of one video download."""

    url: str
    title: Optional[str] = None
    video_id: Optional[str] = None
    file_path: Optional[str] = None
    ok: bool = False
    error: Optional[str] = None


@dataclass
class DownloadResult:
    """Aggregate result of a download_audio call."""

    items: List[DownloadItemResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.items) and all(item.ok for item in self.items)

    @property
    def files(self) -> List[str]:
        return [i.file_path for i in self.items if i.file_path]

    @property
    def failures(self) -> List[DownloadItemResult]:
        return [i for i in self.items if not i.ok]


def _child_env() -> Dict[str, str]:
    """Minimal env for child processes — no secrets passed through."""
    keys = ["PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR",
            "TMPDIR", "TMP", "TEMP", "HOME", "USERPROFILE",
            "LANG", "LC_ALL", "LC_CTYPE", "NO_COLOR"]
    return {k: os.environ[k] for k in keys if k in os.environ}


def is_yt_dlp_installed() -> bool:
    """Check whether yt-dlp is available as binary or python module."""
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True,
                       check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def run_yt_dlp_command(
    cmd: Sequence[str],
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Run a yt-dlp command (binary first, `python -m yt_dlp` fallback).

    Raises:
        RuntimeError: If yt-dlp is not installed.
        subprocess.SubprocessError: If the command fails and check=True.
    """
    if env is None:
        env_to_use = _child_env()
    else:
        env_to_use = env.copy()
    env_to_use["PYTHONIOENCODING"] = "utf-8"
    env_to_use["PYTHONUTF8"] = "1"
    env_to_use.setdefault("NO_COLOR", "1")

    try:
        return subprocess.run(
            ["yt-dlp"] + list(cmd), check=check,
            capture_output=capture_output, text=text,
            env=env_to_use, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        try:
            return subprocess.run(
                [sys.executable, "-m", "yt_dlp"] + list(cmd), check=check,
                capture_output=capture_output, text=text,
                env=env_to_use, encoding="utf-8", errors="replace",
            )
        except FileNotFoundError as module_e:
            raise RuntimeError(
                "yt-dlp is not installed. "
                "Install it with 'pip install yt-dlp'"
            ) from module_e


def _stderr_tail(proc: subprocess.CompletedProcess) -> str:
    """Last meaningful error line for caller-facing messages."""
    for line in reversed((proc.stderr or proc.stdout or "").splitlines()):
        if line.strip():
            return line.strip()[:200]
    return f"yt-dlp exited with code {proc.returncode}"


def _entry_url(entry: dict) -> str:
    """Best-effort watch URL for a flat-playlist entry."""
    url = entry.get("webpage_url") or entry.get("url") or ""
    if url.startswith("http"):
        return url
    video_id = entry.get("id") or url
    return f"https://www.youtube.com/watch?v={video_id}"


def resolve_items(url: str) -> List[DownloadItemResult]:
    """
    Resolve a YouTube URL to download items.

    A playlist URL yields one item per contained video; a single video URL
    yields one item. Raises RuntimeError when the URL cannot be resolved.
    """
    proc = run_yt_dlp_command(["--flat-playlist", "-J", url], check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp could not resolve {url}: "
                           f"{_stderr_tail(proc)}")
    data = json.loads(proc.stdout)
    entries = data.get("entries") or [data]
    return [
        DownloadItemResult(
            url=_entry_url(entry),
            title=entry.get("title"),
            video_id=entry.get("id"),
        )
        for entry in entries
    ]


def _build_download_cmd(
    item_url: str,
    target_dir: Path,
    audio_format: str,
    audio_quality: str,
    output_template: Optional[str],
    embed_metadata: bool,
    embed_thumbnail: bool,
    extra_args: Optional[Sequence[str]],
) -> List[str]:
    """Assemble the yt-dlp argument list for one item."""
    cmd = [
        "-x", "--audio-format", audio_format,
        "--audio-quality", audio_quality,
        "-o", output_template or DEFAULT_OUTPUT_TEMPLATE,
        "-P", str(target_dir),
        "--no-playlist",
        "--print", "after_move:filepath",
    ]
    if embed_metadata:
        cmd.append("--embed-metadata")
    if embed_thumbnail:
        cmd.append("--embed-thumbnail")
    if extra_args:
        cmd += list(extra_args)
    cmd.append(item_url)
    return cmd


def _printed_filepath(
    proc: subprocess.CompletedProcess,
    target_dir: Path,
) -> Optional[str]:
    """
    Final file path: the --print after_move:filepath line, falling back to
    the newest audio file in target_dir when the print is missing.
    """
    lines = [l.strip() for l in (proc.stdout or "").splitlines() if l.strip()]
    if lines:
        candidate = Path(lines[-1])
        if candidate.exists():
            return str(candidate)
    audio_files = [p for p in target_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
    if audio_files:
        newest = max(audio_files, key=lambda p: p.stat().st_mtime)
        return str(newest)
    return None


def download_audio(
    url: str,
    target_dir: Union[str, Path],
    *,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    audio_quality: str = DEFAULT_AUDIO_QUALITY,
    output_template: Optional[str] = None,
    embed_metadata: bool = True,
    embed_thumbnail: bool = True,
    extra_args: Optional[Sequence[str]] = None,
) -> DownloadResult:
    """
    Download the audio of a YouTube video or playlist into target_dir.

    Creates target_dir when missing, downloads each item separately and
    continues past per-item failures — failures are reported on the item.
    """
    if not is_yt_dlp_installed():
        raise RuntimeError(
            "yt-dlp is not installed. "
            "Install it with 'pip install yt-dlp'"
        )
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    result = DownloadResult(items=resolve_items(url))
    for item in result.items:
        cmd = _build_download_cmd(
            item.url, target, audio_format, audio_quality,
            output_template, embed_metadata, embed_thumbnail, extra_args,
        )
        proc = run_yt_dlp_command(cmd, check=False)
        if proc.returncode != 0:
            item.error = _stderr_tail(proc)
            continue
        item.file_path = _printed_filepath(proc, target)
        item.ok = item.file_path is not None
        if not item.ok:
            item.error = ("yt-dlp reported success but no output file "
                          "was found")
    return result
