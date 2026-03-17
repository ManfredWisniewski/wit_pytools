@echo off
REM audiobook_runner.bat - Configurable wrapper for convert_to_m4b
REM Location: Adjust and copy where convenient
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Path to wit_pytools directory containing audiotools.py
set "SCRIPT_DIR=P:\git\witnctools\wit_pytools"

REM Folder with audio files to convert (required)
set "INPUT_FOLDER="

REM Optional: Explicit output M4B file path (including filename)
set "OUTPUT_FILE="

REM Optional: Output directory (used if OUTPUT_FILE is empty)
set "OUTPUT_DIR=.\"

REM Optional metadata overrides
set "TITLE="
set "AUTHOR="
set "DATE="
set "NARRATOR="

REM Optional cover image path (leave empty for auto-detection)
set "COVER_IMAGE="

REM Audio settings
set "BITRATE=64k"
set "EXTENSIONS=mp3"

REM Behaviour toggles (0 = disabled, 1 = enabled)
set "ESTIMATE_ONLY=0"
set "DEBUG=1"
set "VERBOSE=0"
set "USE_FILENAME_AS_CHAPTER=0"
set "DECODE_DURATIONS=1"

REM Maximum allowed size increase in percent (e.g. 20 = allow up to +20%)
set "MAX_SIZE_INCREASE=20"

REM ==============================================================================
REM SCRIPT LOGIC - Do not edit below this line unless necessary
REM ==============================================================================

if "%PYTHON_PATH%"=="" set "PYTHON_PATH=python"
if "%BITRATE%"=="" set "BITRATE=64k"
if "%EXTENSIONS%"=="" set "EXTENSIONS=mp3"
if "%MAX_SIZE_INCREASE%"=="" set "MAX_SIZE_INCREASE=20"

for %%V in (ESTIMATE_ONLY DEBUG VERBOSE USE_FILENAME_AS_CHAPTER DECODE_DURATIONS) do (
    if "!%%V!"=="" set "%%V=0"
)

REM Verify Python is available
%PYTHON_PATH% --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found at '%PYTHON_PATH%'
    echo Please set PYTHON_PATH in the configuration section
    pause
    exit /b 1
)

REM Verify script directory exists
if "%SCRIPT_DIR%"=="" (
    echo Error: SCRIPT_DIR is not set.
    pause
    exit /b 1
)
if not exist "%SCRIPT_DIR%\" (
    echo Error: Script directory not found: %SCRIPT_DIR%
    pause
    exit /b 1
)

REM Verify audiotools.py exists
if not exist "%SCRIPT_DIR%\audiotools.py" (
    echo Error: audiotools.py not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

REM Validate input folder
if "%INPUT_FOLDER%"=="" (
    echo Error: INPUT_FOLDER is required.
    pause
    exit /b 1
)
if not exist "%INPUT_FOLDER%\" (
    echo Error: Input folder not found: %INPUT_FOLDER%
    pause
    exit /b 1
)

REM Ensure output directory exists when specified
if not "%OUTPUT_DIR%"=="" (
    if not exist "%OUTPUT_DIR%\" (
        echo Creating output directory: %OUTPUT_DIR%
        mkdir "%OUTPUT_DIR%"
        if errorlevel 1 (
            echo Error: Failed to create output directory.
            pause
            exit /b 1
        )
    )
)

REM Ensure parent directory of OUTPUT_FILE exists if provided
if not "%OUTPUT_FILE%"=="" (
    for %%I in ("%OUTPUT_FILE%") do set "OUTPUT_PARENT=%%~dpI"
    if not exist "!OUTPUT_PARENT!" (
        echo Creating output directory: !OUTPUT_PARENT!
        mkdir "!OUTPUT_PARENT!"
        if errorlevel 1 (
            echo Error: Failed to create output directory for OUTPUT_FILE.
            pause
            exit /b 1
        )
    )
)

REM Set environment variables for Python helper script
set "AB_PYTHONPATH=%SCRIPT_DIR%"
set "AB_INPUT_FOLDER=%INPUT_FOLDER%"
set "AB_OUTPUT_FILE=%OUTPUT_FILE%"
set "AB_OUTPUT_DIR=%OUTPUT_DIR%"
set "AB_TITLE=%TITLE%"
set "AB_AUTHOR=%AUTHOR%"
set "AB_DATE=%DATE%"
set "AB_NARRATOR=%NARRATOR%"
set "AB_COVER_IMAGE=%COVER_IMAGE%"
set "AB_BITRATE=%BITRATE%"
set "AB_EXTENSIONS=%EXTENSIONS%"
set "AB_ESTIMATE_ONLY=%ESTIMATE_ONLY%"
set "AB_DEBUG=%DEBUG%"
set "AB_VERBOSE=%VERBOSE%"
set "AB_USE_FILENAME_AS_CHAPTER=%USE_FILENAME_AS_CHAPTER%"
set "AB_DECODE_DURATIONS=%DECODE_DURATIONS%"
set "AB_MAX_SIZE_INCREASE=%MAX_SIZE_INCREASE%"

REM Create temporary Python helper script
set "TEMP_SCRIPT=%TEMP%\audiobook_runner_!RANDOM!!RANDOM!.py"
>
"%TEMP_SCRIPT%" ( 
    echo import os
    echo import sys
    echo from pathlib import Path
    echo
    echo def env(name, default=""):
    echo     return os.environ.get(name, default)
    echo
    echo def env_bool(name):
    echo     value = env(name, "").strip().lower()
    echo     return value in {"1", "true", "yes", "on"}
    echo
    echo def env_list(name):
    echo     raw = env(name, "")
    echo     if not raw:
    echo         return []
    echo     items = []
    echo     for part in raw.replace(",", " ").split():
    echo         part = part.strip()
    echo         if part:
    echo             items.append(part)
    echo     return items
    echo
    echo script_path = env("AB_PYTHONPATH", "").strip()
    echo if not script_path:
    echo     raise SystemExit("AB_PYTHONPATH is not set")
    echo if not os.path.isdir(script_path):
    echo     raise SystemExit(f"Script directory not found: {script_path}")
    echo sys.path.insert(0, script_path)
    echo
    echo from audiotools import convert_to_m4b, estimate_m4b_size
    echo
    echo input_folder = env("AB_INPUT_FOLDER", "").strip()
    echo if not input_folder:
    echo     raise SystemExit("INPUT_FOLDER is not set")
    echo if not os.path.isdir(input_folder):
    echo     raise SystemExit(f"Input folder does not exist: {input_folder}")
    echo
    echo output_file = env("AB_OUTPUT_FILE", "").strip() or None
    echo output_dir = env("AB_OUTPUT_DIR", "").strip() or None
    echo title = env("AB_TITLE", "").strip() or None
    echo author = env("AB_AUTHOR", "").strip() or None
    echo date = env("AB_DATE", "").strip() or None
    echo narrator = env("AB_NARRATOR", "").strip() or None
    echo cover_image = env("AB_COVER_IMAGE", "").strip() or None
    echo if cover_image and not os.path.isfile(cover_image):
    echo     print(f"Warning: Cover image not found: {cover_image}")
    echo     cover_image = None
    echo
    echo bitrate = env("AB_BITRATE", "").strip() or None
    echo extensions = env_list("AB_EXTENSIONS")
    echo if not extensions:
    echo     extensions = None
    echo
    echo estimate_only = env_bool("AB_ESTIMATE_ONLY")
    echo debug = env_bool("AB_DEBUG")
    echo verbose = env_bool("AB_VERBOSE")
    echo use_filename_as_chapter = env_bool("AB_USE_FILENAME_AS_CHAPTER")
    echo decode_durations = env_bool("AB_DECODE_DURATIONS")
    echo
    echo max_size_value = env("AB_MAX_SIZE_INCREASE", "20").strip()
    echo try:
    echo     max_size_increase = float(max_size_value)
    echo except ValueError:
    echo     raise SystemExit(f"Invalid MAX_SIZE_INCREASE value: {max_size_value}")
    echo max_size_ratio = 1 + max_size_increase / 100.0
    echo
    echo print("Converting files in:", input_folder)
    echo if title:
    echo     print("Title:", title)
    echo if author:
    echo     print("Author:", author)
    echo if date:
    echo     print("Date:", date)
    echo if narrator:
    echo     print("Narrator:", narrator)
    echo if cover_image:
    echo     print("Cover image:", cover_image)
    echo if bitrate:
    echo     print("Bitrate (for size estimation only):", bitrate)
    echo if extensions:
    echo     print("Extensions:", ", ".join(extensions))
    echo print("Debug mode:", "Enabled" if debug else "Disabled")
    echo print("Verbose mode:", "Enabled" if verbose else "Disabled")
    echo print(f"Max size increase allowed: {max_size_increase:.1f}%%")
    echo print("-" * 50)
    echo
    echo print("\nEstimating file sizes...")
    echo est_size, original_size, compression_ratio, size_info = estimate_m4b_size(
    echo     input_folder,
    echo     bitrate=bitrate or "64k",
    echo     extensions=extensions
    echo )
    echo
    echo def format_mb(value):
    echo     return f"{value / (1024 * 1024):.2f} MB"
    echo
    echo print("Original size:", format_mb(original_size))
    echo print("Estimated M4B size:", format_mb(est_size))
    echo print(f"Compression ratio: {compression_ratio:.2f}x")
    echo
    echo if compression_ratio < 1 / max_size_ratio:
    echo     increase = (1 / compression_ratio - 1) * 100
    echo     print()
    echo     print(f"Conversion would exceed allowed size increase ({max_size_increase:.1f}%%).")
    echo     print(f"Expected increase: {increase:.1f}%%")
    echo     raise SystemExit(0)
    echo
    echo if estimate_only:
    echo     print("Estimate-only mode enabled. Skipping conversion.")
    echo     raise SystemExit(0)
    echo
    echo kwargs = dict(
    echo     input_folder=input_folder,
    echo     output_file=output_file,
    echo     output_dir=output_dir,
    echo     title=title,
    echo     author=author,
    echo     cover_image=cover_image,
    echo     extensions=extensions,
    echo     bitrate=bitrate,
    echo     estimate_size=True,
    echo     debug=debug,
    echo     verbose=verbose,
    echo     use_filename_as_chapter=use_filename_as_chapter,
    echo     decode_durations=decode_durations,
    echo     date=date,
    echo     narrator=narrator
    echo )
    echo
    echo result = convert_to_m4b(**kwargs)
    echo
    echo if isinstance(result, tuple):
    echo     output_path, final_info = result
    echo     actual_size = final_info.get("actual_m4b_size")
    echo     compression = final_info.get("actual_compression_ratio")
    echo else:
    echo     output_path = result
    echo     actual_size = size_info.get("estimated_m4b_size")
    echo     compression = compression_ratio
    echo
    echo print("\nConversion complete!")
    echo print("Output file:", output_path)
    echo if actual_size:
    echo     print("M4B size:", format_mb(actual_size))
    echo if compression:
    echo     print(f"Compression ratio: {compression:.2f}x")
    echo
    echo if actual_size and original_size:
    echo     diff = actual_size - original_size
    echo     percent = (diff / original_size) * 100
    echo     if diff < 0:
    echo         print(f"Saved {-diff / (1024 * 1024):.2f} MB ({-percent:.1f}%%)")
    echo     else:
    echo         print(f"File size increased by {diff / (1024 * 1024):.2f} MB ({percent:.1f}%%)")
)

REM Execute helper script
%PYTHON_PATH% "%TEMP_SCRIPT%"
set "RC=%ERRORLEVEL%"
if exist "%TEMP_SCRIPT%" del "%TEMP_SCRIPT%"

if %RC%==0 (
    echo.
    echo Audiobook conversion completed.
) else (
    echo.
    echo Audiobook conversion failed with exit code %RC%.
)

exit /b %RC%
