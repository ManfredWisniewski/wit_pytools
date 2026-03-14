#!/usr/bin/env python
"""
Example script to estimate M4B file size without converting.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import wit_pytools
sys.path.append(str(Path(__file__).parent.parent))

from wit_pytools.audiotools import estimate_m4b_size

def main():
    mp3_folder = os.environ.get('AUDIOBOOK_INPUT_FOLDER', r'.\')
    bitrate = "64k"
    
    print(f"\nnEstimating M4B size for files in: {mp3_folder}")
    print(f"Target bitrate: {bitrate}")
    print("-" * 50)
    
    # Estimate size
    estimated_size, original_size, compression_ratio, size_info = estimate_m4b_size(
        mp3_folder,
        bitrate=bitrate,
        extensions=["mp3"]  # You can add more extensions if needed
    )
    
    # Print results
    print("\nResults:")
    print(f"Total audio duration: {size_info['total_duration_seconds'] / 60:.2f} minutes")
    print(f"Original MP3 size: {original_size / (1024*1024):.2f} MB")
    print(f"Estimated M4B size: {estimated_size / (1024*1024):.2f} MB")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    
    # Show savings
    if compression_ratio > 1:
        savings = original_size - estimated_size
        savings_percent = (savings / original_size) * 100
        print(f"\nYou'll save approximately {savings / (1024*1024):.2f} MB ({savings_percent:.1f}%)")
    else:
        print("\nThe M4B file will be larger than the original MP3 files.")
    
    # Show individual file sizes if requested
    show_details = input("\nShow individual file sizes? (y/n): ").lower() == 'y'
    if show_details:
        print("\nIndividual file sizes:")
        for file_path, size in size_info['file_sizes'].items():
            print(f"  {os.path.basename(file_path)}: {size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
