#!/usr/bin/env python
# requires: m4b-util
"""
Audio conversion tools for creating M4B audiobook files.
This module provides a simple wrapper around the m4b-util package.
"""

import os
import re
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Union, Tuple, Dict
import tempfile
import importlib.util


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
            env=env
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
                    env=env
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
                   If None, defaults to ['mp3']
    
    Returns:
        Total size in bytes
    """
    if extensions is None:
        extensions = ['mp3']
    
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
        extensions = ['mp3']
    
    input_folder = Path(input_folder)
    
    # Get total duration of all audio files
    total_duration_seconds = 0
    file_sizes = {}
    
    for ext in extensions:
        ext = ext.lstrip('.')
        for file_path in input_folder.glob(f'**/*.{ext}'):
            try:
                # Get audio duration using ffprobe
                cmd = [
                    'ffprobe', 
                    '-v', 'error', 
                    '-show_entries', 'format=duration', 
                    '-of', 'default=noprint_wrappers=1:nokey=1', 
                    str(file_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                duration = float(result.stdout.strip())
                total_duration_seconds += duration
                
                # Store file size
                file_size = file_path.stat().st_size
                file_sizes[str(file_path)] = file_size
                
            except (subprocess.SubprocessError, ValueError) as e:
                print(f"Warning: Could not get duration for {file_path}: {e}")
    
    # Calculate original total size
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
    estimated_size = int((bits_per_second * total_duration_seconds / 8) * 1.05)
    
    # Calculate compression ratio
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


def convert_to_m4b(
    input_folder: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    cover_image: Optional[Union[str, Path]] = None,
    extensions: Optional[List[str]] = None,
    chapter_pattern: Optional[str] = None,
    bitrate: Optional[str] = None,
    verbose: bool = False,
    estimate_size: bool = False,
    debug: bool = False,
    use_filename_as_chapter: bool = False,
    specific_files: Optional[List[Union[str, Path]]] = None,
    decode_durations: bool = False,
    date: Optional[str] = None,
    narrator: Optional[str] = None
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
        chapter_pattern: Pattern for chapter names (not directly supported by m4b-util)
        bitrate: Audio bitrate (e.g. '64k') - NOTE: Not directly supported by m4b-util bind
        verbose: Whether to print verbose output
        estimate_size: Whether to estimate and return size information
        debug: Whether to enable debug mode with additional logging
        use_filename_as_chapter: Use filenames as chapter titles instead of metadata
        specific_files: List of specific files to use instead of scanning input_folder
        decode_durations: Fully decode each file to determine duration (more accurate)
        date: Date to include in metadata (e.g. "2023" or "2023-01-01")
        narrator: Narrator name (will be appended to title as "Title (Narrator: Name)" since m4b-util doesn't have a direct narrator field)
        
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
    
    # Convert paths to strings
    input_folder = str(input_folder)
    
    # Default bitrate if not specified - NOTE: m4b-util bind doesn't support bitrate directly
    if bitrate is None:
        bitrate = '64k'
    
    # Check if input folder exists and has audio files
    if not os.path.exists(input_folder) and not specific_files:
        raise ValueError(f"Input folder does not exist: {input_folder}")
    
    if extensions is None:
        extensions = ['mp3']
    
    # Normalize extensions (remove leading dots, convert to lowercase)
    normalized_extensions = [ext.lstrip('.').lower() for ext in extensions]
    
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
        with tempfile.TemporaryDirectory() as temp_dir:
            if debug:
                print(f"Debug: Created temporary directory for filtered files: {temp_dir}")
            
            # Create symlinks to audio files only
            audio_file_count = 0
            for ext in normalized_extensions:
                for audio_file in Path(input_folder).glob(f'**/*.{ext}'):
                    # Skip image files that might have audio extensions
                    if any(img_ext in audio_file.name.lower() for img_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                        if debug:
                            print(f"Debug: Skipping image file with audio extension: {audio_file}")
                        continue
                    
                    # Create symlink in temp directory
                    link_path = os.path.join(temp_dir, audio_file.name)
                    try:
                        # On Windows, we need to use a different approach for symlinks
                        if os.name == 'nt':
                            # For Windows, copy the file instead of symlinking
                            shutil.copy2(audio_file, link_path)
                        else:
                            os.symlink(audio_file, link_path)
                        audio_file_count += 1
                    except (OSError, shutil.Error) as e:
                        if debug:
                            print(f"Debug: Error creating link for {audio_file}: {e}")
            
            if debug:
                print(f"Debug: Created links for {audio_file_count} audio files")
            
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
                output_filename = f"{folder_name}.m4b"
                cmd.extend(['--output-name', output_filename])
                final_output_file = os.path.join(output_dir, output_filename)
            else:
                # Default to input folder name with .m4b extension in the same directory as input
                folder_name = os.path.basename(os.path.normpath(input_folder))
                output_dir_path = os.path.dirname(input_folder)
                output_filename = f"{folder_name}.m4b"
                
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
            env["TERM"] = "dumb"  # Disable colored output
            env["PYTHONIOENCODING"] = "utf-8"  # Force UTF-8 encoding
            env["FORCE_COLOR"] = "0"  # Disable Rich color output
            
            # Run the command
            try:
                result = run_m4b_util_command(
                    cmd,
                    check=True,
                    capture_output=not (verbose or debug),
                    text=True,
                    env=env
                )
                
                if (verbose or debug) and result.stdout:
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
                if hasattr(e, 'stderr') and e.stderr:
                    error_msg += f"\nError output: {e.stderr}"
                
                if debug:
                    print(f"Debug: Error occurred: {error_msg}")
                    print(f"Debug: Checking if m4b-util is properly installed...")
                    try:
                        version_result = subprocess.run(['m4b-util', '--version'], 
                                                    capture_output=True, 
                                                    text=True)
                        print(f"Debug: m4b-util version: {version_result.stdout.strip()}")
                    except:
                        print("Debug: Could not get m4b-util version using command line")
                        try:
                            module_check = subprocess.run([sys.executable, '-m', 'm4b_util', '--version'], 
                                                        capture_output=True, 
                                                        text=True)
                            print(f"Debug: m4b_util module version: {module_check.stdout.strip()}")
                        except:
                            print("Debug: Could not get m4b_util module version")
                    
                    # Check if ffmpeg is installed
                    try:
                        ffmpeg_result = subprocess.run(['ffmpeg', '-version'], 
                                                    capture_output=True, 
                                                    text=True)
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