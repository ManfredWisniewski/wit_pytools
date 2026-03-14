#!/usr/bin/env python
"""Example script to convert audio files to M4B format."""

import argparse
import os
import sys
import re
import glob
from pathlib import Path

# Add repository root to path so we can import wit_pytools
sys.path.append(str(Path(__file__).resolve().parents[2]))

from wit_pytools.audiotools import convert_to_m4b, estimate_m4b_size

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
    args = parser.parse_args()

    # Replace with your actual MP3 folder path, or override via env
    mp3_folder = os.environ.get('AUDIOBOOK_INPUT_FOLDER', '.')
    
    # https://github.com/sandreas/m4b-tool
    # This bitrate is only used for size estimation, not passed to m4b-util
    bitrate = "64k"

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
    
    # Get output path (optional)
    output_directory = os.environ.get('AUDIOBOOK_OUTPUT_DIR', r".")
    if output_directory:
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

        output_file = os.path.join(output_directory, f"{filename_base}.m4b")
    else:
        output_file = None
    
    # Enable debug mode
    debug = True
    
    # Additional options
    use_filename_as_chapter = False
    decode_durations = True  # More accurate duration calculation
    
    # Maximum allowed size increase (1.2 means 20% larger)
    max_size_ratio = 1.2
    
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
    if compression_ratio < 1 / max_size_ratio:
        print(f"\n Conversion would result in a file that is more than {(max_size_ratio - 1) * 100:.0f}% larger.")
        print(f"  Expected size increase: {(1/compression_ratio - 1) * 100:.1f}%")
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
        
        # Print results
        if isinstance(result, tuple):
            output_file, size_info = result
            print("\nConversion complete!")
            print(f"Output file: {output_file}")
            print(f"Original size: {size_info['original_size'] / (1024*1024):.2f} MB")
            print(f"M4B size: {size_info['actual_m4b_size'] / (1024*1024):.2f} MB")
            print(f"Compression ratio: {size_info['actual_compression_ratio']:.2f}x")
            
            # Show savings
            if size_info['actual_compression_ratio'] > 1:
                savings = size_info['original_size'] - size_info['actual_m4b_size']
                savings_percent = (savings / size_info['original_size']) * 100
                print(f"\nYou saved {savings / (1024*1024):.2f} MB ({savings_percent:.1f}%)")
            else:
                increase = size_info['actual_m4b_size'] - size_info['original_size']
                increase_percent = (increase / size_info['original_size']) * 100
                print(f"\nFile size increased by {increase / (1024*1024):.2f} MB ({increase_percent:.1f}%)")
        else:
            print(f"\nConversion complete! Output file: {result}")
    
    except Exception as e:
        print(f"\n Error during conversion: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure FFmpeg is installed and in your PATH")
        print("2. Check that the input folder contains MP3 files")
        print("3. Verify you have write permissions to the output location")
        print("4. Try running the command directly: m4b-util bind --help")

if __name__ == "__main__":
    main()
