#!/usr/bin/env python
"""Example script to convert audio files to M4B format."""

import argparse
import os
import sys
import re
import glob
import shutil
import subprocess
from pathlib import Path

# Add repository root to path so we can import wit_pytools
sys.path.append(str(Path(__file__).resolve().parents[2]))

from wit_pytools.audiotools import (
    convert_to_m4b,
    estimate_m4b_size,
    probe_audio_bitrate,
    reencode_audio,
)
from wit_pytools.datatools import bps_to_bitrate, bitrate_to_bps


def extract_title_from_directory(directory_path):
    """
    Extract title from directory name based on format:
    "Author Name YEAR Series Title Book Number, Title; Narrator Name"
    
    Returns the title part (Series Title Book Number, Title)
    """
    dir_name = os.path.basename(directory_path)
    
    # Try to match the full pattern
    match = re.search(r'[^-]+\d{4}\s+(.*?)(?:;\s*|$)', dir_name)
    if match:
        return match.group(1).strip()
    
    # Try to find a pattern with 4 digits (year)
    match = re.search(r'.*?\d{4}\s+(.*?)(?:;\s*|$)', dir_name)
    if match:
        return match.group(1).strip()
    
    # If no year pattern, try to extract title from common patterns
    # Pattern: Author - Title
    match = re.search(r'.*?\s+-\s+(.*?)(?:;\s*|$)', dir_name)
    if match:
        return match.group(1).strip()
    
    # If no patterns match, just return the directory name
    return dir_name

def extract_author_from_directory(directory_path):
    """
    Extract author from directory name based on format:
    "Author Name YEAR Series Title Book Number, Title; Narrator Name"
    
    Returns the author part (Author Name)
    """
    dir_name = os.path.basename(directory_path)
    
    # Try to match the pattern with year
    match = re.search(r'^(.*?)\s+\d{4}', dir_name)
    if match:
        return match.group(1).strip()
    
    # If no year, try to match pattern with dash
    match = re.search(r'^(.*?)\s+-', dir_name)
    if match:
        return match.group(1).strip()
    
    # If no patterns match, return Unknown
    return "Unknown Author"

def extract_year_from_directory(directory_path):
    """
    Extract year from directory name based on format:
    "Author Name YEAR Series Title Book Number, Title; Narrator Name"
    
    Returns the year part (YEAR)
    """
    dir_name = os.path.basename(directory_path)
    
    # Look for a 4-digit number that's likely a year
    match = re.search(r'\b(19\d{2}|20\d{2})\b', dir_name)
    if match:
        return match.group(1)
    
    return None

def extract_narrator_from_directory(directory_path):
    """
    Extract narrator from directory name based on format:
    "Author Name YEAR Series Title Book Number, Title; Narrator Name"
    
    Returns the narrator part (Narrator Name)
    """
    dir_name = os.path.basename(directory_path)
    
    # Look for text after semicolon
    match = re.search(r';\s*(.*?)$', dir_name)
    if match:
        return match.group(1).strip()
    
    return None

def find_cover_images(directory_path):
    """
    Find all JPG files in the directory that could be used as cover images.
    Returns a list of paths to JPG files.
    """
    # Look for common cover image filenames
    cover_patterns = [
        os.path.join(directory_path, "cover.jpg"),
        os.path.join(directory_path, "cover.jpeg"),
        os.path.join(directory_path, "folder.jpg"),
        os.path.join(directory_path, "folder.jpeg"),
        os.path.join(directory_path, "front.jpg"),
        os.path.join(directory_path, "front.jpeg"),
        os.path.join(directory_path, "artwork.jpg"),
        os.path.join(directory_path, "artwork.jpeg"),
        os.path.join(directory_path, "albumart.jpg"),
        os.path.join(directory_path, "albumart.jpeg")
    ]
    
    # Check for exact matches first
    for pattern in cover_patterns:
        if os.path.exists(pattern):
            return [pattern]
    
    # If no exact matches, get all JPG files
    jpg_files = glob.glob(os.path.join(directory_path, "*.jpg"))
    jpg_files.extend(glob.glob(os.path.join(directory_path, "*.jpeg")))
    
    return jpg_files


def detect_source_bitrate(directory_path, extensions, sample_limit=None):
    """Return the lowest detected bitrate (bps) across input audio files."""

    directory = Path(directory_path)
    if not directory.exists():
        return None

    detected = []

    for ext in extensions:
        for file_path in directory.glob(f"**/*.{ext}"):
            if not file_path.is_file():
                continue

            bitrate_bps = probe_audio_bitrate(file_path)
            if bitrate_bps:
                detected.append(bitrate_bps)
                if sample_limit and len(detected) >= sample_limit:
                    return min(detected) if detected else None

    return min(detected) if detected else None

def cleanup_directory(directory_path):
    """Remove known temp files before running conversion."""

    directory = Path(directory_path)
    if not directory.exists():
        return

    position_file = directory / "position.sabp.dat"
    if position_file.exists():
        try:
            position_file.unlink()
            print(f"Removed stale file: {position_file}")
        except OSError as err:
            print(f"Warning: could not remove {position_file}: {err}")

    for cue_file in list(directory.glob("*.cue")) + list(directory.glob("*.CUE")):
        if cue_file.exists():
            try:
                cue_file.unlink()
                print(f"Removed cue file: {cue_file}")
            except OSError as err:
                print(f"Warning: could not remove {cue_file}: {err}")

def main():
    parser = argparse.ArgumentParser(
        description="Convert audiobook folders to M4B with optional format preference"
    )
    parser.add_argument(
        "--preferred-format",
        choices=["mp3", "m4a"],
        help="Preferred audio format to select when multiple encodings exist",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        help="Audio file extensions to consider (default: based on preferred format)",
    )
    parser.add_argument(
        "--bitrate",
        default=os.environ.get("AUDIOBOOK_TARGET_BITRATE", "64k"),
        help="Target audio bitrate for size estimation and final re-encode (default: 64k)",
    )
    args = parser.parse_args()

    # Replace with your actual MP3 folder path, or override via env
    mp3_folder = os.environ.get('AUDIOBOOK_INPUT_FOLDER', '.')
    
    # https://github.com/sandreas/m4b-tool
    # Bitrate used for size estimation and optional re-encode
    bitrate = args.bitrate

    if not os.path.exists(mp3_folder):
        print(f"Error: Folder '{mp3_folder}' does not exist.")
        return
    
    # Determine extensions to scan
    if args.extensions:
        extensions = [ext.lstrip('.').lower() for ext in args.extensions]
    else:
        extensions = ["mp3"]
        if args.preferred_format and args.preferred_format not in extensions:
            extensions.insert(0, args.preferred_format)

    cleanup_directory(mp3_folder)

    source_bitrate_bps = detect_source_bitrate(mp3_folder, extensions)
    target_bitrate_bps = bitrate_to_bps(bitrate)
    effective_bitrate_bps = target_bitrate_bps or source_bitrate_bps

    if source_bitrate_bps and target_bitrate_bps:
        if source_bitrate_bps < target_bitrate_bps:
            adjusted_bitrate = bps_to_bitrate(source_bitrate_bps)
            if adjusted_bitrate:
                if adjusted_bitrate != bitrate:
                    print(
                        "Detected source bitrate"
                        f" {bps_to_bitrate(source_bitrate_bps) or source_bitrate_bps}"
                        f" below configured target {bps_to_bitrate(target_bitrate_bps) or target_bitrate_bps}."
                    )
                    print("Using source bitrate for re-encoding.")
                bitrate = adjusted_bitrate
                effective_bitrate_bps = source_bitrate_bps
    elif source_bitrate_bps and not target_bitrate_bps:
        adjusted_bitrate = bps_to_bitrate(source_bitrate_bps)
        if adjusted_bitrate:
            bitrate = adjusted_bitrate
            effective_bitrate_bps = source_bitrate_bps

    if effective_bitrate_bps is None:
        effective_bitrate_bps = bitrate_to_bps(bitrate)

    # Extract metadata from directory name
    title = extract_title_from_directory(mp3_folder)
    author = extract_author_from_directory(mp3_folder)
    year = extract_year_from_directory(mp3_folder)
    narrator = extract_narrator_from_directory(mp3_folder)
    
    print(f"Extracted title: {title}")
    print(f"Extracted author: {author}")
    print(f"Extracted year: {year if year else 'Not found'}")
    print(f"Extracted narrator: {narrator if narrator else 'Not found'}")
    
    # Find cover images in the directory
    cover_images = find_cover_images(mp3_folder)
    cover_image = None
    
    if cover_images:
        if len(cover_images) == 1:
            cover_image = cover_images[0]
            print(f"Found cover image: {os.path.basename(cover_image)}")
        else:
            print("Found multiple cover images:")
            for i, img in enumerate(cover_images):
                print(f"  {i+1}. {os.path.basename(img)}")
            
            # Ask user to select one
            selection = input("Enter number to select a cover image (or press Enter to skip): ")
            if selection and selection.isdigit() and 1 <= int(selection) <= len(cover_images):
                cover_image = cover_images[int(selection) - 1]
                print(f"Selected cover image: {os.path.basename(cover_image)}")
            else:
                print("No cover image selected.")
    else:
        print("No cover images found in the directory.")
    
    # Get output path (same directory as source files)
    output_dir_path = Path(mp3_folder)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    filename_parts = []
    if author:
        filename_parts.append(author)
    if year:
        filename_parts.append(year)
    if title:
        filename_parts.append(title)
    filename_base = " ".join(part for part in filename_parts if part).strip()
    if narrator:
        filename_base = f"{filename_base}; {narrator}" if filename_base else narrator
    if not filename_base:
        filename_base = os.path.basename(mp3_folder)

    output_file = str(output_dir_path / f"{filename_base}.m4b")

    existing_output = Path(output_file)
    if existing_output.exists():
        try:
            existing_output.unlink()
            print(f"Removed existing output file: {existing_output}")
        except OSError as err:
            print(f"Warning: could not remove {existing_output}: {err}")

    # Handle directories that already contain a single M4B file
    existing_m4b_files = sorted(Path(mp3_folder).glob("*.m4b"))
    if len(existing_m4b_files) == 1:
        source_m4b = existing_m4b_files[0]
        print("\nSingle M4B detected in source directory. Re-encoding to target bitrate...")

        target_path = Path(output_file) if output_file else source_m4b
        target_path.parent.mkdir(parents=True, exist_ok=True)

        target_bitrate_bps = effective_bitrate_bps
        current_bitrate_bps = probe_audio_bitrate(source_m4b)
        if (
            target_bitrate_bps is not None
            and current_bitrate_bps is not None
            and current_bitrate_bps <= target_bitrate_bps
        ):
            print(
                "Existing M4B bitrate is lower or equal to target; skipping re-encode."
            )
            if target_path != source_m4b:
                shutil.copy2(source_m4b, target_path)
                print(f"Copied to output path: {target_path}")
            else:
                print("Output path matches source; no action taken.")

            final_size = target_path.stat().st_size if target_path.exists() else 0
            if final_size:
                print(f"File size: {final_size / (1024 * 1024):.2f} MB")
            return

        temp_reencode_path = target_path.with_name(f"{target_path.stem}_reencoded{target_path.suffix}")
        if temp_reencode_path.exists():
            temp_reencode_path.unlink()

        try:
            original_size = source_m4b.stat().st_size
            reencode_audio(
                source_m4b,
                temp_reencode_path,
                bitrate=bitrate,
                audio_codec="aac",
                overwrite=True,
            )
            os.replace(temp_reencode_path, target_path)
        except Exception as err:
            if temp_reencode_path.exists():
                temp_reencode_path.unlink()
            print(f"Error: Re-encode of existing M4B failed ({err})")
            return

        new_size = target_path.stat().st_size if target_path.exists() else 0
        print("Re-encode complete!")
        print(f"Source file: {source_m4b}")
        print(f"Output file: {target_path}")
        print(f"Original size: {original_size / (1024 * 1024):.2f} MB")
        if new_size:
            print(f"New size: {new_size / (1024 * 1024):.2f} MB")
        return
    
    # Enable debug mode
    debug = True
    
    # Additional options
    use_filename_as_chapter = False
    decode_durations = True  # More accurate duration calculation
    
    # Maximum allowed size increase (1.2 means 20% larger)
    max_size_ratio = 1.9
    
    print(f"\nConverting files in: {mp3_folder}")
    print(f"Title: {title}")
    print(f"Author: {author}")
    if year:
        print(f"Year: {year}")
    if narrator:
        print(f"Narrator: {narrator}")
    if cover_image:
        print(f"Cover image: {cover_image}")
    print(f"Bitrate (for size estimation only): {bitrate}")
    print(f"Use filename as chapter title: {use_filename_as_chapter}")
    print(f"Decode durations: {decode_durations}")
    print(f"Debug mode: {'Enabled' if debug else 'Disabled'}")
    if args.preferred_format:
        print(f"Preferred format: {args.preferred_format}")
    print(f"Extensions scanned: {', '.join(extensions)}")
    print(f"Max size increase allowed: {(max_size_ratio - 1) * 100:.0f}%")
    print("-" * 50)
    
    # Check if ffmpeg is installed
    try:
        import subprocess
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print(" FFmpeg is installed and available in PATH")
    except (subprocess.SubprocessError, FileNotFoundError):
        print(" FFmpeg is NOT installed or not in PATH - this is required by m4b-util")
        print("  Please install FFmpeg from https://ffmpeg.org/download.html")
        return
    
    # First estimate the size
    print("\nEstimating file sizes...")
    estimated_size, original_size, compression_ratio, size_info = estimate_m4b_size(
        mp3_folder,
        bitrate=bitrate,
        extensions=extensions
    )
    
    print(f"Original size: {original_size / (1024*1024):.2f} MB")
    print(f"Estimated M4B size: {estimated_size / (1024*1024):.2f} MB")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    
    # Check if the estimated size meets our criteria
    if compression_ratio == 0:
        print("\nUnable to estimate compression ratio (estimated size is 0). Skipping conversion.")
        return

    if compression_ratio < 1 / max_size_ratio:
        print(f"\n Conversion would result in a file that is more than {(max_size_ratio - 1) * 100:.0f}% larger.")
        expected_increase = (1 / compression_ratio - 1) * 100
        print(f"  Expected size increase: {expected_increase:.1f}%")
        print("  Skipping conversion.")
        return
    
    print(f"\n Size criteria met. Proceeding with conversion...")
    
    # Convert to M4B with size estimation
    try:
        result = convert_to_m4b(
            mp3_folder,
            output_file=output_file,
            title=title,
            author=author,
            cover_image=cover_image,
            bitrate=bitrate,
            extensions=extensions,
            preferred_format=args.preferred_format,
            verbose=True,
            estimate_size=True,
            debug=debug,
            use_filename_as_chapter=use_filename_as_chapter,
            decode_durations=decode_durations,
            date=year,
            narrator=narrator
        )
        
        if isinstance(result, tuple):
            final_output_path_str, size_info = result
        else:
            final_output_path_str = result
            size_info = None

        final_output_path = Path(final_output_path_str)

        # Optional re-encode step to enforce target bitrate/codec
        if final_output_path.exists():
            temp_reencode_path = final_output_path.with_name(
                f"{final_output_path.stem}_reencoded{final_output_path.suffix}"
            )
            if temp_reencode_path.exists():
                temp_reencode_path.unlink()

            try:
                print("\nRe-encoding final M4B to target bitrate...")
                reencode_audio(
                    final_output_path,
                    temp_reencode_path,
                    bitrate=bitrate,
                    audio_codec="aac",
                    overwrite=True,
                )
                os.replace(temp_reencode_path, final_output_path)
            except Exception as re_err:
                if temp_reencode_path.exists():
                    temp_reencode_path.unlink()
                print(f"Warning: Re-encode step failed ({re_err})")
            else:
                # Update size metrics after re-encode if available
                if size_info is not None:
                    new_size = final_output_path.stat().st_size
                    size_info['actual_m4b_size'] = new_size
                    size_info['actual_compression_ratio'] = (
                        size_info['original_size'] / new_size if new_size else 0
                    )

        # Print results
        if size_info is not None:
            print("\nConversion complete!")
            print(f"Output file: {final_output_path}")
            print(f"Original size: {size_info['original_size'] / (1024*1024):.2f} MB")
            print(f"M4B size: {size_info['actual_m4b_size'] / (1024*1024):.2f} MB")
            print(f"Compression ratio: {size_info['actual_compression_ratio']:.2f}x")

            # Show savings or increase
            if size_info['actual_compression_ratio'] > 1:
                savings = size_info['original_size'] - size_info['actual_m4b_size']
                savings_percent = (savings / size_info['original_size']) * 100
                print(f"\nYou saved {savings / (1024*1024):.2f} MB ({savings_percent:.1f}%)")
            else:
                increase = size_info['actual_m4b_size'] - size_info['original_size']
                increase_percent = (increase / size_info['original_size']) * 100
                print(f"\nFile size increased by {increase / (1024*1024):.2f} MB ({increase_percent:.1f}%)")
        else:
            print(f"\nConversion complete! Output file: {final_output_path}")
    
    except Exception as e:
        print(f"\n Error during conversion: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure FFmpeg is installed and in your PATH")
        print("2. Check that the input folder contains MP3 files")
        print("3. Verify you have write permissions to the output location")
        print("4. Try running the command directly: m4b-util bind --help")

if __name__ == "__main__":
    main()
