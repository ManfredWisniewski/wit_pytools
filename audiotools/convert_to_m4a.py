#!/usr/bin/env python
"""Utility script to batch-encode audio sources to AAC/M4A in-place."""

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List

# Allow running from repository root without installing wit_pytools
sys.path.append(str(Path(__file__).resolve().parents[2]))

from wit_pytools.audiotools import encode_m4a, is_ffmpeg_available  # noqa: E402


def discover_audio_files(root: Path, extensions: Iterable[str]) -> List[Path]:
    """Return all files under *root* that match the given extensions."""

    exts = {ext.lower().lstrip('.') for ext in extensions}
    files: List[Path] = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix.lower().lstrip('.') in exts:
            files.append(path)
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encode audio files to AAC/M4A alongside the originals"
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        default=os.environ.get(
            "AUDIOBOOK_INPUT_FOLDER",
            r".\",
        ),
        help="Folder containing source audio (defaults to AUDIOBOOK_INPUT_FOLDER env)",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=["mp3"],
        help="File extensions to encode (default: mp3)",
    )
    parser.add_argument(
        "--bitrate",
        default="64k",
        help="Target audio bitrate passed to ffmpeg (default: 64k)",
    )
    parser.add_argument(
        "--codec",
        default="aac",
        help="Audio codec to use (default: aac)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Optional output sample rate in Hz",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=None,
        help="Optional number of audio channels",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing M4A files (default: skip if present)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work that would be done without invoking ffmpeg",
    )

    args = parser.parse_args()

    if args.input_folder is None:
        parser.error("No input folder supplied and AUDIOBOOK_INPUT_FOLDER not set")

    root = Path(args.input_folder)
    if not root.exists():
        parser.error(f"Input folder does not exist: {root}")

    if not is_ffmpeg_available():
        parser.error("FFmpeg is not available on PATH – install it from https://ffmpeg.org/download.html")

    print(f"Scanning '{root}' for {', '.join(args.extensions)} files...")
    audio_files = discover_audio_files(root, args.extensions)

    if not audio_files:
        print("No matching source files found. Nothing to do.")
        return

    print(f"Found {len(audio_files)} file(s) to process. Starting encoding...\n")

    processed = 0
    skipped = 0

    for input_path in audio_files:
        output_path = input_path.with_suffix('.m4a')

        if output_path.exists() and not args.overwrite:
            print(f"Skipping existing file: {output_path}")
            skipped += 1
            continue

        if args.dry_run:
            action = "Overwrite" if output_path.exists() else "Create"
            print(f"[DRY RUN] {action}: {output_path}")
            processed += 1
            continue

        print(f"Encoding '{input_path.name}' -> '{output_path.name}' @ {args.bitrate}")
        try:
            result_path = encode_m4a(
                input_path,
                output_path,
                bitrate=args.bitrate,
                audio_codec=args.codec,
                sample_rate=args.sample_rate,
                channels=args.channels,
                overwrite=True,
            )
            if result_path.stat().st_size == 0:
                print(f"  WARNING: Encoded file is empty, removing: {result_path}")
                result_path.unlink(missing_ok=True)
                raise RuntimeError("Encoded file had zero length")
            processed += 1
        except Exception as exc:  # pylint: disable=broad-except
            print(f"  ERROR: Failed to encode {input_path}: {exc}")

    print("\nEncoding complete.")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")


if __name__ == "__main__":
    main()
