# Audio Tools - M4B Audiobook Conversion

This guide explains how to use the M4B audiobook conversion tools in the witnctools repository.

## Overview

The audio tools provide functionality to convert folders of audio files (typically MP3) into M4B audiobook format using the `m4b-util` package. The tools support automatic metadata extraction, cover image handling, and size estimation.

## Installation Requirements

**Required:**
1. Install m4b-util:
   ```bash
   pip install m4b-util
   ```

2. Install FFmpeg (required by m4b-util):
   - Download from https://ffmpeg.org/download.html
   - Ensure FFmpeg is in your PATH

**Note:** Make sure to install `m4b-util` (with an 'l'), not `m4b-uti`

## Tools Available

### 1. convert_to_m4b.py
Single folder conversion script with advanced metadata extraction.

**Key Features:**
- Automatic metadata extraction from directory names
- Cover image detection and selection
- Size estimation before conversion
- Support for various directory naming patterns

**Usage:**
1. Edit the script and set your input folder path on line 129:
   ```python
   mp3_folder = r'YOUR_INPUT_FOLDER_PATH'
   ```
2. Set output directory on line 181:
   ```python
   output_file = r'YOUR_OUTPUT_DIRECTORY'
   ```
3. Run the script:
   ```bash
   python convert_to_m4b.py
   ```

### 2. batch_convert_to_m4b.py
Batch conversion script for processing multiple audiobook folders.

**Key Features:**
- Process multiple subfolders in a parent directory
- Configuration variables for automated execution
- Summary statistics for batch operations
- Size estimation for each conversion

**Usage:**
1. Set configuration variables at the top of `main()`:
   ```python
   PARENT_FOLDER = "PATH_TO_PARENT_FOLDER"
   OUTPUT_DIR = "PATH_TO_OUTPUT_DIRECTORY"
   BITRATE = "64k"
   ```
2. Run the script:
   ```bash
   python batch_convert_to_m4b.py
   ```

### 3. audiotools.py Module
Core module containing all conversion functions.

**Key Functions:**
- `convert_to_m4b()` - Main conversion function
- `estimate_m4b_size()` - Estimate output file size
- `add_cover_to_m4b()` - Add cover to existing M4B
- `extract_cover_from_m4b()` - Extract cover from M4B
- `split_audiobook()` - Split audiobook into chapters

## Directory Naming Patterns

The tools support automatic metadata extraction from these directory naming patterns:

### Standard Format (Recommended)
```
Author Name YEAR Series Title Book Number, Title; Narrator Name
```

Examples:
- `John Doe 2023 The Great Series 01, First Book; Jane Smith`
- `Jane Smith 2022 Mystery Series 02, Second Investigation; Bob Jones`

### Alternative Formats
- `Author Name YEAR Title; Narrator`
- `Author Name - Title`
- `Simple Book Name` (fallback)

## Cover Image Support

### Automatic Detection
The tools automatically look for cover images with these common names:
- `cover.jpg/jpeg`
- `folder.jpg/jpeg`
- `front.jpg/jpeg`
- `artwork.jpg/jpeg`
- `albumart.jpg/jpeg`

### Manual Selection
If multiple images are found, you'll be prompted to select one. You can also manually specify a cover image path.

## Configuration Options

### Bitrate
- Used for size estimation (not passed to m4b-util)
- Common values: `64k`, `128k`, `96k`
- Default: `64k`

### Size Estimation
- Estimates final M4B file size before conversion
- Can set maximum allowed size increase (default: 20%)
- Helps avoid creating files that are too large

### Debug Mode
- Enable additional logging for troubleshooting
- Shows command details and file processing information

## Command Line Interface

The audiotools module also provides a CLI:

```bash
# Convert single folder
python -m wit_pytools.audiotools convert INPUT_FOLDER --output OUTPUT_FILE --title "Title" --author "Author"

# Estimate size only
python -m wit_pytools.audiotools estimate INPUT_FOLDER --bitrate 64k

# Add cover to existing M4B
python -m wit_pytools.audiotools add-cover BOOK.m4b cover.jpg

# Extract cover from M4B
python -m wit_pytools.audiotools extract-cover BOOK.m4b output_cover.jpg

# Split audiobook
python -m wit_pytools.audiotools split BOOK.m4b OUTPUT_DIR --mode silence
```

## Troubleshooting

### Common Issues

1. **"m4b-util is not installed"**
   - Run: `pip install m4b-util`

2. **"FFmpeg is NOT installed"**
   - Install FFmpeg and ensure it's in your PATH

3. **No audio files found**
   - Check that your folder contains MP3 files
   - Verify file extensions are correct

4. **Permission errors**
   - Ensure you have write permissions to output directory

5. **Rich library color issues**
   - The tools automatically disable color output on Windows

### Debug Tips

- Enable debug mode in the scripts
- Check that m4b-util is working: `m4b-util --version`
- Verify FFmpeg is working: `ffmpeg -version`

## File Size Considerations

- M4B files are typically smaller than original MP3 files
- Size estimation helps avoid unexpected large files
- Default maximum size increase is 20%
- Compression ratio of 2x+ is common

## Metadata Fields Supported

- **Title**: Extracted from directory name or manually specified
- **Author**: Extracted from directory name or manually specified
- **Year**: 4-digit year from directory name
- **Narrator**: Text after semicolon in directory name
- **Cover**: JPG/JPEG image file
- **Date**: Publication date (overrides year if specified)

## Best Practices

1. Use consistent directory naming for automatic metadata extraction
2. Place cover images as `cover.jpg` in each audiobook folder
3. Run size estimation before large batch conversions
4. Test with a single folder before processing large batches
5. Keep FFmpeg and m4b-util updated

## Example Workflow

1. Organize audiobooks in folders with proper naming
2. Add cover images as `cover.jpg`
3. Configure script variables
4. Run size estimation to verify acceptable file sizes
5. Execute conversion
6. Verify output files and metadata

## Integration

The audio tools are designed to work with:
- Windows environments (with automatic color output handling)
- Various audio formats (primarily MP3)
- Existing audiobook libraries
- Batch processing workflows
