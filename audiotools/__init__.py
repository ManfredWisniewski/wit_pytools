#!/usr/bin/env python
# requires: m4b-util
"""
Audio handling and conversion tools.
"""

import os
import re
import subprocess
import sys
import shutil
import json

from pathlib import Path
from typing import List, Optional, Union, Tuple, Dict, Sequence, Any
import tempfile
from os import PathLike
import importlib.util

from wit_pytools.sanitizers import sanitize_path


def is_m4b_util_installed() -> bool:
    """Check if m4b-util is installed."""
    # First check if the package is installed
    try:
        if importlib.util.find_spec("m4b_util") is not None:
            return True
    except ImportError:
        pass
    
    # Then check if the command-line tool is available
    try:
        subprocess.run(['m4b-util', '--version'], 
                      capture_output=True, 
                      check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    # If we get here, it's not installed or not accessible
    return False


def run_m4b_util_command(
    cmd: List[str], 
    check: bool = True, 
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    """
    Run a m4b-util command.
    
    Args:
        cmd: Command to run (without the 'm4b-util' prefix)
        check: Whether to check the return code
        capture_output: Whether to capture stdout and stderr
        text: Whether to decode stdout and stderr as text
        env: Environment variables to set for the command
        
    Returns:
        CompletedProcess instance
        
    Raises:
        RuntimeError: If m4b-util is not installed
        subprocess.SubprocessError: If the command fails
    """
    if not is_m4b_util_installed():
        raise RuntimeError(
            "m4b-util is not installed. Install it with 'pip install m4b-util'"
        )
    
    # First try to run as command line tool
    try:
        return subprocess.run(
            ['m4b-util'] + cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            # If command line tool not found, try as module
            try:
                return subprocess.run(
                    [sys.executable, '-m', 'm4b_util'] + cmd,
                    check=check,
                    capture_output=capture_output,
                    text=text,
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.SubprocessError as module_e:
                raise module_e
        else:
            raise e


def get_directory_audio_size(
    directory: Union[str, Path], 
    extensions: Optional[List[str]] = None
) -> int:
    """
    Calculate the total size of audio files in a directory.
    
    Args:
        directory: Directory containing audio files
        extensions: List of file extensions to include (e.g. ['mp3', 'wav'])
                   If None, defaults to ['mp3', 'mp4']
    
    Returns:
        Total size in bytes
    """
    if extensions is None:
        extensions = ['mp3', 'mp4']
    
    # Normalize extensions (remove leading dots, convert to lowercase)
    extensions = [ext.lstrip('.').lower() for ext in extensions]
    
    total_size = 0
    directory = Path(directory)
    
    for file_path in directory.glob('**/*'):
        if file_path.is_file() and file_path.suffix.lstrip('.').lower() in extensions:
            total_size += file_path.stat().st_size
    
    return total_size


def estimate_m4b_size(
    input_folder: Union[str, Path],
    bitrate: str = '64k',
    extensions: Optional[List[str]] = None
) -> Tuple[int, int, float, Dict[str, int]]:
    """
    Estimate the size of the M4B file that would be generated from the input folder.
    
    Args:
        input_folder: Directory containing audio files to convert
        bitrate: Target bitrate for the M4B file (e.g. '64k', '128k')
        extensions: List of file extensions to include (e.g. ['mp3', 'wav'])
    
    Returns:
        Tuple containing:
        - Estimated M4B size in bytes
        - Original audio files total size in bytes
        - Compression ratio (original size / estimated size)
        - Dictionary with detailed size information
    """
    if extensions is None:
        extensions = ['mp3', 'mp4']

    input_folder = Path(input_folder)

    extensions_set = {ext.lstrip('.').lower() for ext in extensions}

    audio_files: List[Path] = []
    for file_path in input_folder.rglob('*'):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lstrip('.').lower()
        if suffix in extensions_set:
            audio_files.append(file_path)

    total_duration_seconds = 0.0
    file_sizes: Dict[str, int] = {}

    for file_path in audio_files:
        file_size = file_path.stat().st_size
        file_sizes[str(file_path)] = file_size

        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
            duration_text = result.stdout.strip()
            if duration_text:
                total_duration_seconds += float(duration_text)
        except (subprocess.SubprocessError, ValueError) as e:
            print(f"Warning: Could not get duration for {file_path}: {e}")

    original_size = sum(file_sizes.values())
    
    # Parse bitrate string to get bits per second
    if bitrate.endswith('k'):
        bits_per_second = int(bitrate[:-1]) * 1000
    elif bitrate.endswith('m'):
        bits_per_second = int(bitrate[:-1]) * 1000000
    else:
        bits_per_second = int(bitrate)
    
    # Calculate estimated size: (bits per second * duration in seconds) / 8 bits per byte
    # Add 5% overhead for container, metadata, chapters, etc.
    estimated_size = int((bits_per_second * total_duration_seconds / 8) * 1.05) if total_duration_seconds > 0 else 0

    if estimated_size == 0 and original_size > 0:
        estimated_size = original_size
        compression_ratio = 1.0
    else:
        compression_ratio = original_size / estimated_size if estimated_size > 0 else 0
    
    # Prepare detailed info
    size_info = {
        'original_size': original_size,
        'estimated_m4b_size': estimated_size,
        'total_duration_seconds': total_duration_seconds,
        'compression_ratio': compression_ratio,
        'file_sizes': file_sizes
    }
    
    return estimated_size, original_size, compression_ratio, size_info


PathLikeType = Union[str, PathLike]


def is_ffmpeg_available() -> bool:
    """Return True if the ``ffmpeg`` executable is available."""

    return shutil.which("ffmpeg") is not None


def probe_audio_bitrate(audio_file: Union[str, Path]) -> Optional[int]:
    """
    Probe an audio file and return its bitrate in bits per second.
    
    Args:
        audio_file: Path to the audio file
        
    Returns:
        Bitrate in bits per second, or None if unable to determine
    """
    if not is_ffmpeg_available():
        return None
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
        bitrate_str = result.stdout.strip()
        if bitrate_str and bitrate_str.isdigit():
            return int(bitrate_str)
    except (subprocess.SubprocessError, ValueError):
        pass
    
    return None


def probe_audio_codec(audio_file: Union[str, Path]) -> Optional[str]:
    """Return the codec name of the primary audio stream using ffprobe."""

    if not is_ffmpeg_available():
        return None

    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        codec = result.stdout.strip()
        return codec or None
    except subprocess.SubprocessError:
        return None


def _probe_audio_stream(audio_file: Union[str, Path]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """Return (stream_info, format_info, error_message)."""

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-select_streams",
        "a:0",
        "-of",
        "json",
        str(audio_file),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as err:
        reason = err.stderr.strip() if err.stderr else "ffprobe failed"
        return None, None, reason or "ffprobe failed"
    except json.JSONDecodeError:
        return None, None, "ffprobe JSON parse error"

    streams = data.get("streams") or []
    stream_info = streams[0] if streams else None
    format_info = data.get("format")
    return stream_info, format_info, None


def _slim_audio_metadata(stream_info: Optional[Dict[str, Any]], format_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Reduce ffprobe metadata to a compact dictionary for logging."""

    details: Dict[str, Any] = {}

    if stream_info:
        for key in [
            "codec_name",
            "codec_long_name",
            "profile",
            "codec_tag_string",
            "codec_tag",
            "sample_rate",
            "channels",
            "channel_layout",
            "bit_rate",
            "bits_per_raw_sample",
            "sample_fmt",
        ]:
            value = stream_info.get(key)
            if value not in (None, "", "N/A"):
                details[key] = value

    if format_info:
        for key in ["format_name", "format_long_name", "bit_rate", "duration"]:
            value = format_info.get(key)
            if value not in (None, "", "N/A"):
                details[f"format_{key}"] = value

    return details


def _find_first_audio_file(folder: Path, extensions: Sequence[str]) -> Optional[Path]:

    for ext in extensions:
        direct = sorted(folder.glob(f"*.{ext}"))
        if direct:
            return direct[0]
    for ext in extensions:
        recursive = sorted(folder.glob(f"**/*.{ext}"))
        if recursive:
            return recursive[0]
    return None


def _extract_tags_from_audio(audio_file: Optional[Path], debug: bool = False) -> Dict[str, str]:
    if not audio_file:
        return {}

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "format_tags:stream_tags",
        str(audio_file)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
        data = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        if debug:
            print(f"Debug: Failed to extract tags from {audio_file}: {exc}")
        return {}

    format_tags = (data.get("format", {}) or {}).get("tags", {}) or {}
    stream_tags: Dict[str, Any] = {}
    for stream in data.get("streams", []) or []:
        tags = stream.get("tags") or {}
        stream_tags.update(tags)

    tags: Dict[str, str] = {}
    for source in (format_tags, stream_tags):
        for key, value in source.items():
            if isinstance(value, str) and value.strip():
                tags.setdefault(key.lower(), value.strip())

    if not tags and debug:
        print(f"Debug: No tags found for {audio_file}")

    return tags


def is_m4b_compatible_audio(audio_file: Union[str, Path]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Return (is_compatible, reason, metadata)."""

    if not is_ffmpeg_available():
        return False, "ffmpeg not installed", {}

    stream_info, format_info, error = _probe_audio_stream(audio_file)
    metadata = _slim_audio_metadata(stream_info, format_info)

    if error:
        return False, error, metadata

    if not stream_info:
        return False, "no audio streams", metadata

    codec = stream_info.get("codec_name")
    if codec in {"aac", "alac", "mp4a", "mp4", "mp3"}:
        return True, None, metadata

    return False, f"unsupported codec: {codec or 'unknown'}", metadata


def reencode_audio(
    input_file: PathLikeType,
    output_file: PathLikeType,
    *,
    bitrate: str = "64k",
    audio_codec: str = "aac",
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
    overwrite: bool = True,
    format: Optional[str] = None,
) -> Path:
    """Re-encode an audio file using FFmpeg."""

    if not is_ffmpeg_available():
        raise RuntimeError(
            "FFmpeg is not available on PATH. Install it from https://ffmpeg.org/download.html"
        )

    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
    ]

    cmd.append("-y" if overwrite else "-n")
    cmd.extend(["-i", str(input_path)])
    cmd.extend(["-map", "0:a:0"])
    cmd.extend(["-vn", "-sn", "-dn"])
    cmd.extend(["-map_metadata", "0"])
    cmd.extend(["-c:a", audio_codec])
    cmd.extend(["-b:a", bitrate])

    if sample_rate:
        cmd.extend(["-ar", str(sample_rate)])

    if channels:
        cmd.extend(["-ac", str(channels)])

    if extra_args:
        cmd.extend(list(extra_args))

    if format:
        cmd.extend(["-f", format])

    cmd.append(str(output_path))

    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no error output)"
        raise RuntimeError(
            f"FFmpeg failed to reencode '{input_path}' to '{output_path}': {stderr}"
        ) from exc

    if completed.stdout:
        print(completed.stdout.strip())

    return output_path


def encode_m4a(
    input_file: PathLikeType,
    output_file: PathLikeType,
    *,
    bitrate: str = "64k",
    audio_codec: str = "aac",
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    extra_args: Optional[Sequence[str]] = None,
    overwrite: bool = True,
) -> Path:
    """Encode ``input_file`` to an M4A (AAC) file using FFmpeg."""

    if not is_ffmpeg_available():
        raise RuntimeError(
            "FFmpeg is not available on PATH. Install it from https://ffmpeg.org/download.html"
        )

    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
    ]

    cmd.append("-y" if overwrite else "-n")
    cmd.extend(["-i", str(input_path)])
    cmd.extend(["-map", "0:a:0"])
    cmd.extend(["-vn", "-sn", "-dn"])
    cmd.extend(["-map_metadata", "0"])
    cmd.extend(["-c:a", audio_codec])
    cmd.extend(["-b:a", bitrate])

    if sample_rate:
        cmd.extend(["-ar", str(sample_rate)])

    if channels:
        cmd.extend(["-ac", str(channels)])

    if extra_args:
        cmd.extend(list(extra_args))

    cmd.append(str(output_path))

    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "(no error output)"
        raise RuntimeError(
            f"FFmpeg failed to encode '{input_path}' to '{output_path}': {stderr}"
        ) from exc

    if completed.stdout:
        print(completed.stdout.strip())

    return output_path


def convert_to_m4b(
    input_folder: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    cover_image: Optional[Union[str, Path]] = None,
    extensions: Optional[List[str]] = None,
    preferred_format: Optional[str] = None,
    chapter_pattern: Optional[str] = None,
    bitrate: Optional[str] = None,
    verbose: bool = False,
    estimate_size: bool = False,
    debug: bool = False,
    use_filename_as_chapter: bool = False,
    specific_files: Optional[List[Union[str, Path]]] = None,
    decode_durations: bool = False,
    date: Optional[str] = None,
    narrator: Optional[str] = None,
    force_transcode: bool = False,
) -> Union[str, Tuple[str, Dict[str, int]]]:
    """
    Convert a folder of audio files to a single M4B audiobook file.
    
    Args:
        input_folder: Directory containing audio files to convert
        output_file: Path to the output M4B file (optional)
        output_dir: Directory to save the output file (optional)
        title: Title of the audiobook
        author: Author of the audiobook
        cover_image: Path to cover image file
        extensions: List of file extensions to include (for filtering files, not passed to m4b-util)
        preferred_format: Preferred audio extension to use when multiple formats exist (e.g. 'm4a' or 'mp3')
        chapter_pattern: Pattern for chapter names (not directly supported by m4b-util)
        bitrate: Audio bitrate (e.g. '64k') to use for size estimation and m4b-util binding
        verbose: Whether to print verbose output
        estimate_size: Whether to estimate and return size information
        debug: Whether to enable debug mode with additional logging
        use_filename_as_chapter: Use filenames as chapter titles instead of metadata
        specific_files: List of specific files to use instead of scanning input_folder
        decode_durations: Fully decode each file to determine duration (more accurate)
        date: Date to include in metadata (e.g. "2023" or "2023-01-01")
        narrator: Narrator name (will be appended to title as "Title (Narrator: Name)" since m4b-util doesn't have a direct narrator field)
        force_transcode: If True, re-encode staged audio to AAC before binding
        
    Returns:
        If estimate_size is False:
            Path to the created M4B file
        If estimate_size is True:
            Tuple of (path to created M4B file, size information dictionary)
        
    Raises:
        RuntimeError: If m4b-util is not installed
        subprocess.SubprocessError: If the conversion fails
    """
    if not is_m4b_util_installed():
        raise RuntimeError(
            "m4b-util is not installed. Install it with 'pip install m4b-util'"
        )
    
    # Normalize input folder path
    input_folder_path = Path(input_folder)

    # Default bitrate if not specified - NOTE: m4b-util bind doesn't support bitrate directly
    if bitrate is None:
        bitrate = '64k'
    # Check if input folder exists and has audio files
    if not input_folder_path.exists() and not specific_files:
        raise ValueError(f"Input folder does not exist: {input_folder_path}")

    final_base_name = None

    usesource_mode = (
        specific_files is None
        and "$USESOURCE" in input_folder_path.name
    )

    preferred_normalized = None
    if preferred_format:
        preferred_normalized = preferred_format.lstrip('.').lower()

    # ... (rest of the code remains the same)

        metadata_from_source = _build_usesource_metadata(tags, fallback_name)

        if not metadata_from_source.get("author"):
            raise ValueError(f"USESOURCE mode requires an author tag in {input_folder_path}")

        new_folder_base = metadata_from_source.get('base_name') or fallback_name
        new_folder_base = sanitize_path(new_folder_base) or fallback_name
        final_base_name = new_folder_base

        original_folder_path = input_folder_path
        target_path = input_folder_path.parent / new_folder_base

        suffix = 1
        # ... (rest of the code remains the same)
        if metadata_from_source.get('narrator'):
            narrator = metadata_from_source['narrator']
        if metadata_from_source.get('date'):
            date = metadata_from_source['date']

    # Convert paths to strings for downstream processing
    input_folder = str(input_folder_path)

    if extensions:
        extensions = list(extensions)
    else:
        extensions = ['mp3', 'flac', 'm4a', 'm4b', 'aac', 'mp4']
    # ... (rest of the code remains the same)
        if preferred_normalized and preferred_normalized not in [ext.lstrip('.') for ext in extensions]:
            extensions.insert(0, preferred_normalized)

    # Normalize extensions (remove leading dots, convert to lowercase) while preserving order
    normalized_extensions: List[str] = []
    for ext in extensions:
        norm = ext.lstrip('.').lower()
        if norm not in normalized_extensions:
            normalized_extensions.append(norm)

    if preferred_normalized:
        if preferred_normalized not in normalized_extensions:
            normalized_extensions.insert(0, preferred_normalized)
        else:
            normalized_extensions.insert(0, normalized_extensions.pop(normalized_extensions.index(preferred_normalized)))

    # Check if there are any audio files in the input folder (only if not using specific_files)
    has_audio_files = False
    if not specific_files:
        for ext in normalized_extensions:
            if list(Path(input_folder).glob(f'**/*.{ext}')):
                has_audio_files = True
                break
        
        if not has_audio_files:
            raise ValueError(f"No audio files with extensions {extensions} found in {input_folder}")
    
    if debug:
        print(f"Debug: Input folder: {input_folder}")
        if specific_files:
            print(f"Debug: Using specific files: {specific_files}")
        else:
            print(f"Debug: Input folder exists: {os.path.exists(input_folder)}")
            print(f"Debug: Audio files found: {has_audio_files}")
            print(f"Debug: Extensions filter (not passed to m4b-util): {extensions}")
            print(f"Debug: Normalized extensions: {normalized_extensions}")
        print(f"Debug: Bitrate (for size estimation only): {bitrate}")
        if date:
            print(f"Debug: Date metadata: {date}")
        if narrator:
            print(f"Debug: Narrator: {narrator}")
    
    # Estimate size if requested
    size_info = None
    if estimate_size:
        _, original_size, compression_ratio, size_info = estimate_m4b_size(
            input_folder, 
            bitrate=bitrate, 
            extensions=extensions
        )
        if verbose or debug:
            print(f"Original size: {original_size / (1024*1024):.2f} MB")
            print(f"Estimated M4B size: {size_info['estimated_m4b_size'] / (1024*1024):.2f} MB")
            print(f"Compression ratio: {compression_ratio:.2f}x")
    
    # Build command
    cmd = ['bind']
    
    # If we have specific files, use them directly
    if specific_files:
        cmd.extend(['--files'] + [str(f) for f in specific_files])
    else:
        # If we're using a folder, we need to filter out image files
        # Create a temporary directory with symlinks to audio files only
        temp_dir_kwargs: Dict[str, Any] = {}
        temp_root_env = os.environ.get("AUDIOBOOK_TEMP_DIR")
        if temp_root_env:
            temp_root_path = Path(temp_root_env).expanduser()
            try:
                temp_root_path.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                if debug:
                    print(
                        f"Debug: Failed to prepare AUDIOBOOK_TEMP_DIR '{temp_root_path}': {err}"
                    )
            else:
                temp_dir_kwargs["dir"] = str(temp_root_path)

        with tempfile.TemporaryDirectory(**temp_dir_kwargs) as temp_dir:

            if debug:
                print(f"Debug: Created temporary directory for filtered files: {temp_dir}")

            # Discover candidate audio files while preferring the specified format
            selected_files: Dict[str, Path] = {}
            for audio_file in Path(input_folder).rglob('*'):
                if not audio_file.is_file():
                    continue

                suffix = audio_file.suffix.lstrip('.').lower()
                if suffix not in normalized_extensions:
                    continue

                lower_name = audio_file.name.lower()
                if any(img_ext in lower_name for img_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    if debug:
                        print(f"Debug: Skipping image masquerading as audio: {audio_file}")
                    continue

                rel_key = str(audio_file.relative_to(input_folder).with_suffix(''))
                current = selected_files.get(rel_key)
                if current is None:
                    selected_files[rel_key] = audio_file
                elif preferred_normalized and current.suffix.lstrip('.').lower() != preferred_normalized and suffix == preferred_normalized:
                    if debug:
                        print(f"Debug: Preferring {audio_file} over {current}")
                    selected_files[rel_key] = audio_file

            if debug:
                print(f"Debug: Found {len(selected_files)} candidate audio files before staging")

            # Create symlinks/copies (and optional transcodes) in the temp directory
            audio_file_count = 0

            def _unique_destination(base_path: Path) -> Path:
                candidate = base_path
                counter = 1
                while candidate.exists():
                    candidate = candidate.with_name(f"{base_path.stem}_{counter}{base_path.suffix}")
                    counter += 1
                return candidate

            for index, audio_file in enumerate(selected_files.values(), start=1):
                try:
                    suffix = audio_file.suffix.lower()
                    staged_base = sanitize_path(audio_file.stem) or f"track_{index:03d}"

                    if force_transcode and suffix not in {'.m4a', '.m4b', '.aac'}:
                        staged_suffix = '.m4a'
                    else:
                        staged_suffix = suffix if suffix else ''

                    dest_name = f"{staged_base}{staged_suffix}"
                    dest_path = _unique_destination(Path(temp_dir) / dest_name)

                    if force_transcode and suffix not in {'.m4a', '.m4b', '.aac'}:
                        if debug:
                            print(f"Debug: Transcoding {audio_file} -> {dest_path}")
                        reencode_audio(
                            audio_file,
                            dest_path,
                            bitrate=bitrate or '64k',
                            audio_codec='aac',
                            overwrite=True,
                        )
                    else:
                        if os.name == 'nt':
                            shutil.copy2(audio_file, dest_path)
                        else:
                            os.symlink(audio_file, dest_path)
                    audio_file_count += 1
                except (OSError, shutil.Error, RuntimeError) as e:
                    if debug:
                        print(f"Debug: Error preparing {audio_file}: {e}")

            if debug:
                print(f"Debug: Prepared {audio_file_count} audio files (force_transcode={force_transcode})")

            if audio_file_count == 0:
                raise ValueError(f"No valid audio files found in {input_folder}")
            
            # Use the temporary directory as input
            cmd.append(temp_dir)
            
            # Determine output file path and directory
            final_output_file = None
            
            if output_file:
                # Extract directory and filename from output_file
                output_dir_path = os.path.dirname(output_file)
                output_filename = os.path.basename(output_file)
                
                # If output_dir_path is empty, use current directory
                if output_dir_path:
                    cmd.extend(['--output-dir', output_dir_path])
                
                # If output_filename has an extension, use it as is, otherwise add .m4b
                if not output_filename.lower().endswith('.m4b'):
                    output_filename += '.m4b'
                
                cmd.extend(['--output-name', output_filename])
                final_output_file = output_file if output_file.lower().endswith('.m4b') else f"{output_file}.m4b"
            elif output_dir:
                cmd.extend(['--output-dir', str(output_dir)])
                # Use input folder name for output filename
                folder_name = os.path.basename(os.path.normpath(input_folder))
                base_name = final_base_name or folder_name
                output_filename = f"{base_name}.m4b"
                cmd.extend(['--output-name', output_filename])
                final_output_file = os.path.join(output_dir, output_filename)
            else:
                # Default to input folder name with .m4b extension in the same directory as input
                folder_name = os.path.basename(os.path.normpath(input_folder))
                output_dir_path = os.path.dirname(input_folder)
                base_name = final_base_name or folder_name
                output_filename = f"{base_name}.m4b"

                if output_dir_path:
                    cmd.extend(['--output-dir', output_dir_path])

                cmd.extend(['--output-name', output_filename])
                final_output_file = os.path.join(output_dir_path, output_filename)
            
            # Add optional parameters
            if title:
                # If narrator is provided, include it in the title
                if narrator:
                    modified_title = f"{title} (Narrator: {narrator})"
                    cmd.extend(['--title', modified_title])
                else:
                    cmd.extend(['--title', title])
            elif narrator:
                # If only narrator is provided (no title), create a title with just the narrator info
                cmd.extend(['--title', f"(Narrator: {narrator})"])
            
            if author:
                cmd.extend(['--author', author])
            
            if date:
                cmd.extend(['--date', date])
            
            if cover_image:
                if os.path.exists(cover_image):
                    cmd.extend(['--cover', str(cover_image)])
                else:
                    print(f"Warning: Cover image not found: {cover_image}")
            
            # Add other supported options
            if use_filename_as_chapter:
                cmd.append('--use-filename')
            
            if decode_durations:
                cmd.append('--decode-durations')


            if debug:
                print(f"Debug: Full command: m4b-util {' '.join(str(arg) for arg in cmd)}")
                print(f"Debug: Final output file: {final_output_file}")
                # Check if output directory exists
                output_dir_path = os.path.dirname(final_output_file)
                if output_dir_path:
                    print(f"Debug: Output directory exists: {os.path.exists(output_dir_path)}")
                    print(f"Debug: Output directory is writable: {os.access(output_dir_path, os.W_OK)}")
            
            # Set environment variables to fix Rich library color output issues
            env = os.environ.copy()
            env["TMPDIR"] = temp_dir
            env["TMP"] = temp_dir
            env["TEMP"] = temp_dir
            env["TERM"] = "dumb"  # Disable colored output
            env["PYTHONIOENCODING"] = "utf-8"  # Force UTF-8 encoding
            env["FORCE_COLOR"] = "0"  # Disable Rich color output
            
            # Run the command
            try:
                result = run_m4b_util_command(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env
                )
                
                if debug:
                    print(result.stdout)
                
                # Update size info with actual file size if available
                if estimate_size and os.path.exists(final_output_file):
                    actual_size = os.path.getsize(final_output_file)
                    size_info['actual_m4b_size'] = actual_size
                    size_info['actual_compression_ratio'] = size_info['original_size'] / actual_size if actual_size > 0 else 0
                    
                    if verbose or debug:
                        print(f"Actual M4B size: {actual_size / (1024*1024):.2f} MB")
                        print(f"Actual compression ratio: {size_info['actual_compression_ratio']:.2f}x")
                
                if estimate_size:
                    return final_output_file, size_info
                else:
                    return final_output_file
            
            except (subprocess.CalledProcessError, RuntimeError) as e:
                error_msg = f"Error converting to M4B: {e}"
                stderr_output = getattr(e, 'stderr', None)
                stdout_output = getattr(e, 'stdout', None)
                if stdout_output:
                    error_msg += f"\nStdout: {stdout_output.strip()}"
                if stderr_output:
                    error_msg += f"\nStderr: {stderr_output.strip()}"
                
                if debug:
                    print(f"Debug: Error occurred: {error_msg}")
                    print(f"Debug: Checking if m4b-util is properly installed...")
                    try:
                        version_result = subprocess.run(['m4b-util', '--version'], capture_output=True, text=True, encoding="utf-8", errors="replace")
                        print(f"Debug: m4b-util version: {version_result.stdout.strip()}")
                    except:
                        print("Debug: Could not get m4b-util version using command line")
                        try:
                            module_check = subprocess.run([sys.executable, '-m', 'm4b_util', '--version'], capture_output=True, text=True, encoding="utf-8", errors="replace")
                            print(f"Debug: m4b_util module version: {module_check.stdout.strip()}")
                        except:
                            print("Debug: Could not get m4b_util module version")
                    
                    # Check if ffmpeg is installed
                    try:
                        ffmpeg_result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, encoding="utf-8", errors="replace")
                        print(f"Debug: ffmpeg is installed")
                    except:
                        print("Debug: ffmpeg is NOT installed or not in PATH - this is required by m4b-util")
                
                raise RuntimeError(error_msg)


def add_cover_to_m4b(
    m4b_file: Union[str, Path],
    cover_image: Union[str, Path]
) -> None:
    """
    Add a cover image to an existing M4B file.
    
    Args:
        m4b_file: Path to the M4B file
        cover_image: Path to the cover image file
        
    Raises:
        RuntimeError: If m4b-util is not installed
        subprocess.SubprocessError: If adding the cover fails
    """
    if not is_m4b_util_installed():
        raise RuntimeError(
            "m4b-util is not installed. Install it with 'pip install m4b-util'"
        )
    
    cmd = [
        'cover',
        str(m4b_file),
        '--apply-cover', str(cover_image)
    ]
    
    try:
        run_m4b_util_command(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        error_msg = f"Error adding cover to M4B: {e}"
        if e.stderr:
            error_msg += f"\nError output: {e.stderr}"
        raise RuntimeError(error_msg)


def extract_cover_from_m4b(
    m4b_file: Union[str, Path],
    output_image: Union[str, Path]
) -> None:
    """
    Extract the cover image from an M4B file.
    
    Args:
        m4b_file: Path to the M4B file
        output_image: Path to save the extracted cover image
        
    Raises:
        RuntimeError: If m4b-util is not installed
        subprocess.SubprocessError: If extracting the cover fails
    """
    if not is_m4b_util_installed():
        raise RuntimeError(
            "m4b-util is not installed. Install it with 'pip install m4b-util'"
        )
    
    cmd = [
        'cover',
        str(m4b_file),
        '--extract', str(output_image)
    ]
    
    try:
        run_m4b_util_command(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        error_msg = f"Error extracting cover from M4B: {e}"
        if e.stderr:
            error_msg += f"\nError output: {e.stderr}"
        raise RuntimeError(error_msg)


def split_audiobook(
    input_file: Union[str, Path],
    output_dir: Union[str, Path],
    mode: str = 'silence',
    output_pattern: str = "chapter_{:03d}.mp3",
    min_silence_length: float = 1.0,
    silence_threshold: float = 0.05
) -> List[str]:
    """
    Split an audiobook file into chapters.
    
    Args:
        input_file: Path to the input audio file
        output_dir: Directory to save the split files
        mode: Split mode ('silence' or 'chapters')
        output_pattern: Pattern for output filenames
        min_silence_length: Minimum silence length in seconds (for silence mode)
        silence_threshold: Silence threshold (for silence mode)
        
    Returns:
        List of paths to the created chapter files
        
    Raises:
        RuntimeError: If m4b-util is not installed
        subprocess.SubprocessError: If splitting fails
    """
    if not is_m4b_util_installed():
        raise RuntimeError(
            "m4b-util is not installed. Install it with 'pip install m4b-util'"
        )
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        'split',
        mode,
        str(input_file),
        '--output-dir', str(output_dir),
        '--output-pattern', output_pattern
    ]
    
    if mode == 'silence':
        cmd.extend(['--min-silence-length', str(min_silence_length)])
        cmd.extend(['--silence-threshold', str(silence_threshold)])
    
    try:
        result = run_m4b_util_command(cmd, check=True, capture_output=True, text=True)
        
        # Parse output to get the list of created files
        output_files = []
        for line in result.stdout.splitlines():
            if line.startswith("Created "):
                file_path = line.split("Created ")[1].strip()
                output_files.append(file_path)
        
        return output_files
    
    except subprocess.CalledProcessError as e:
        error_msg = f"Error splitting audiobook: {e}"
        if e.stderr:
            error_msg += f"\n{e.stderr}"
        raise RuntimeError(error_msg)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert audio files to M4B audiobook format")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert audio files to M4B")
    convert_parser.add_argument("input_folder", help="Folder containing audio files")
    convert_parser.add_argument("--output", help="Output M4B file path")
    convert_parser.add_argument("--output-dir", help="Output directory")
    convert_parser.add_argument("--title", help="Audiobook title")
    convert_parser.add_argument("--author", help="Audiobook author")
    convert_parser.add_argument("--cover", help="Cover image path")
    convert_parser.add_argument("--extensions", nargs="+", help="File extensions to include")
    convert_parser.add_argument("--bitrate", help="Audio bitrate (e.g. 64k)")
    convert_parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    convert_parser.add_argument("--estimate-only", action="store_true", 
                               help="Only estimate size without converting")
    convert_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    convert_parser.add_argument("--date", help="Date to include in metadata (e.g. 2023 or 2023-01-01)")
    convert_parser.add_argument("--narrator", help="Narrator name")
    
    # Add cover command
    cover_parser = subparsers.add_parser("add-cover", help="Add cover to M4B file")
    cover_parser.add_argument("m4b_file", help="M4B file path")
    cover_parser.add_argument("cover_image", help="Cover image path")
    
    # Extract cover command
    extract_parser = subparsers.add_parser("extract-cover", help="Extract cover from M4B file")
    extract_parser.add_argument("m4b_file", help="M4B file path")
    extract_parser.add_argument("output_image", help="Output image path")
    
    # Split command
    split_parser = subparsers.add_parser("split", help="Split audiobook into chapters")
    split_parser.add_argument("input_file", help="Input audio file")
    split_parser.add_argument("output_dir", help="Output directory")
    split_parser.add_argument("--mode", choices=["silence", "chapters"], default="silence",
                             help="Split mode")
    split_parser.add_argument("--output-pattern", default="chapter_{:03d}.mp3",
                             help="Output filename pattern")
    split_parser.add_argument("--min-silence-length", type=float, default=1.0,
                             help="Minimum silence length in seconds")
    split_parser.add_argument("--silence-threshold", type=float, default=0.05,
                             help="Silence threshold")
    
    # Estimate command
    estimate_parser = subparsers.add_parser("estimate", 
                                          help="Estimate M4B file size without converting")
    estimate_parser.add_argument("input_folder", help="Folder containing audio files")
    estimate_parser.add_argument("--extensions", nargs="+", help="File extensions to include")
    estimate_parser.add_argument("--bitrate", default="64k", help="Audio bitrate (e.g. 64k)")
    
    args = parser.parse_args()
    
    if args.command == "convert":
        if args.estimate_only:
            _, original_size, compression_ratio, size_info = estimate_m4b_size(
                args.input_folder,
                bitrate=args.bitrate or "64k",
                extensions=args.extensions
            )
            print(f"Original size: {original_size / (1024*1024):.2f} MB")
            print(f"Estimated M4B size: {size_info['estimated_m4b_size'] / (1024*1024):.2f} MB")
            print(f"Compression ratio: {compression_ratio:.2f}x")
            print(f"Total audio duration: {size_info['total_duration_seconds'] / 60:.2f} minutes")
        else:
            result = convert_to_m4b(
                args.input_folder,
                args.output,
                args.output_dir,
                args.title,
                args.author,
                args.cover,
                args.extensions,
                None,  # chapter_pattern not exposed in CLI
                args.bitrate,
                args.verbose,
                estimate_size=True,
                debug=args.debug,
                date=args.date,
                narrator=args.narrator
            )
            if isinstance(result, tuple):
                output_file, size_info = result
                print(f"Successfully created: {output_file}")
                print(f"Original size: {size_info['original_size'] / (1024*1024):.2f} MB")
                print(f"M4B size: {size_info['actual_m4b_size'] / (1024*1024):.2f} MB")
                print(f"Compression ratio: {size_info['actual_compression_ratio']:.2f}x")
            else:
                print(f"Successfully created: {result}")
    
    elif args.command == "add-cover":
        add_cover_to_m4b(args.m4b_file, args.cover_image)
        print(f"Successfully added cover to {args.m4b_file}")
    
    elif args.command == "extract-cover":
        extract_cover_from_m4b(args.m4b_file, args.output_image)
        print(f"Successfully extracted cover to {args.output_image}")
    
    elif args.command == "split":
        output_files = split_audiobook(
            args.input_file,
            args.output_dir,
            args.mode,
            args.output_pattern,
            args.min_silence_length,
            args.silence_threshold
        )
        print(f"Successfully split into {len(output_files)} files:")
        for file in output_files:
            print(f"  - {file}")
    
    elif args.command == "estimate":
        estimated_size, original_size, compression_ratio, size_info = estimate_m4b_size(
            args.input_folder,
            bitrate=args.bitrate,
            extensions=args.extensions
        )
        print(f"Original size: {original_size / (1024*1024):.2f} MB")
        print(f"Estimated M4B size: {estimated_size / (1024*1024):.2f} MB")
        print(f"Compression ratio: {compression_ratio:.2f}x")
        print(f"Total audio duration: {size_info['total_duration_seconds'] / 60:.2f} minutes")
    
    else:
        parser.print_help()


def _build_usesource_metadata(tags: Dict[str, str], fallback_name: str) -> Dict[str, Optional[str]]:
    lowered = {k.lower(): v for k, v in tags.items()}

    comment = lowered.get("comment")
    if comment and "read by" in comment.lower():
        comment = re.sub(r"(?i)read by", "", comment).strip()

    author = lowered.get("artist") or lowered.get("album_artist") or lowered.get("composer")
    title = lowered.get("album") or lowered.get("title")
    narrator = (
        lowered.get("narrator")
        or lowered.get("performer")
        or comment
        or lowered.get("reader")
    )
    date = lowered.get("date") or lowered.get("year") or lowered.get("originaldate")

    components = [part for part in [author, date, title] if part]
    base = " ".join(components).strip()
    if narrator:
        base = f"{base}; {narrator}" if base else narrator

    if not base:
        base = fallback_name

    base = sanitize_path(base)

    return {
        "author": author,
        "title": title,
        "narrator": narrator,
        "date": date,
        "base_name": base,
    }