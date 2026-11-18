# Intent: `ytdlptools`

## Module purpose

`ytdlptools` wraps the external `yt-dlp` tool to download music (audio)
from YouTube links — single videos or playlists — for WIT consumers.
First consumer: the einring BFF; the same functions serve a future
device-side app transport.

goals:

- one audio file per YouTube video link
- one audio file per video contained in a YouTube playlist
- caller-controlled yt-dlp options (format, naming, embeds) with
  music-oriented defaults (mp3, metadata + thumbnail embedded)
- per-item result reporting: created file paths and per-item failures

## Layout

Flat module `wit_pytools/ytdlptools.py` (owner decision 2026-11-18) —
escalates to a package only when submodules emerge (mailtools precedent).
Intent docs live in this `ytdlptools/+intent/` directory.

Spec: `+wit/specs/wit_pytools/ytdlptools/`
