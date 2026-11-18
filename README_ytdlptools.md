# ytdlptools — yt-dlp music download wrapper

Wraps the external `yt-dlp` tool to download music (audio) from YouTube
links — a single video or every video of a playlist. Spec:
`+wit/specs/wit_pytools/ytdlptools/`.

## Requirements

- `yt-dlp` on PATH (or importable as `python -m yt_dlp`):
  `pip install yt-dlp`
- `ffmpeg` on PATH — required for the default mp3 transcode and thumbnail
  embedding.

## Usage

```python
from wit_pytools import ytdlptools

result = ytdlptools.download_audio(
    "https://www.youtube.com/playlist?list=PL...",
    "downloads/music",
)

for item in result.failures:
    print(item.url, item.error)
print(result.files)   # list of created audio file paths
```

`download_audio(url, target_dir, ...)` accepts a video or playlist URL,
creates `target_dir` when missing and returns a `DownloadResult` with one
`DownloadItemResult` per video (`ok`, `file_path`, `error`). A failed
playlist item does not abort the rest.

## Options

| Parameter | Default | Effect |
|---|---|---|
| `audio_format` | `"mp3"` | `--audio-format` value (needs ffmpeg when transcoding) |
| `audio_quality` | `"0"` | best VBR quality |
| `output_template` | `"%(title)s [%(id)s].%(ext)s"` | yt-dlp `-o` template; the id suffix keeps duplicate titles unique |
| `embed_metadata` | `True` | `--embed-metadata` |
| `embed_thumbnail` | `True` | `--embed-thumbnail` (cover art) |
| `extra_args` | `None` | additional yt-dlp flags appended verbatim |

Lower-level helpers: `is_yt_dlp_installed()`, `resolve_items(url)`
(playlist → item list), `run_yt_dlp_command(cmd)` (binary or
`python -m yt_dlp`, minimal child env without secret-bearing variables).

## Notes

- Filenames are sanitised by yt-dlp itself (per-OS invalid-character
  handling); callers control naming via `output_template`.
- The module is stdlib-only and holds no CLI — callers keep their own
  entry points.
