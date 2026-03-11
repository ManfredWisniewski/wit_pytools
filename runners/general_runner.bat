@echo off
REM general_runner.bat - Traverse subdirectories and run a Python script on each
REM Configure the script and root directory below
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

REM Path to Python executable (leave empty to use default 'python')
set "PYTHON_PATH="

REM Path to root directory containing subdirectories to process
set "ROOT_DIR=H:\midgard\encode\audiobooks-encode"

REM Python script to run for each subdirectory (absolute or relative path)
REM set "PYTHON_SCRIPT=P:\git\witnctools\wit_pytools\runners\convert_to_m4b.py"
set "PYTHON_SCRIPT=P:\git\witnctools\wit_pytools\runners\convert_to_m4a.py"

REM Optional output directory to pass to script via env var
set "OUTPUT_DIR=H:\midgard\encode\audiobooks-encode"

REM Environment variable names used by the target script
set "ENV_INPUT=AUDIOBOOK_INPUT_FOLDER"
set "ENV_OUTPUT=AUDIOBOOK_OUTPUT_DIR"

REM Additional environment variables (comma-separated KEY=VALUE pairs)
REM Example: set "EXTRA_ENV=BITRATE=64k,DEBUG=1"
set "EXTRA_ENV="

REM Log file (overwritten each run)
set "LOG_FILE=%~dp0runner.log"

call :MAIN > "%LOG_FILE%" 2>&1
exit /b %ERRORLEVEL%

:MAIN

REM ==============================================================================
REM VALIDATION
REM ==============================================================================

if "%PYTHON_PATH%"=="" set "PYTHON_PATH=python"

%PYTHON_PATH% --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found at '%PYTHON_PATH%'
    pause
    exit /b 1
)

if "%ROOT_DIR%"=="" (
    echo Error: ROOT_DIR is not set.
    pause
    exit /b 1
)
if not exist "%ROOT_DIR%\" (
    echo Error: Root directory not found: %ROOT_DIR%
    pause
    exit /b 1
)

if "%PYTHON_SCRIPT%"=="" (
    echo Error: PYTHON_SCRIPT is not set.
    pause
    exit /b 1
)
if not exist "%PYTHON_SCRIPT%" (
    echo Error: Python script not found: %PYTHON_SCRIPT%
    pause
    exit /b 1
)

REM ==============================================================================
REM PROCESSING
REM ==============================================================================

echo.
echo Running %PYTHON_SCRIPT% for subdirectories in:
echo   %ROOT_DIR%
echo.

set "OVERALL_EXIT=0"
for /d %%D in ("%ROOT_DIR%\*") do (
    if exist "%%D\" (
        echo ----------------------------------------
        echo Processing: %%~nD
        echo Path: %%~fD
        echo ----------------------------------------

        set "%ENV_INPUT%=%%~fD"
        if not "%OUTPUT_DIR%"=="" set "%ENV_OUTPUT%=%OUTPUT_DIR%"

        if not "%EXTRA_ENV%"=="" (
            for %%E in (%EXTRA_ENV%) do (
                for /f "tokens=1,2 delims==" %%K in ("%%E") do (
                    if not "%%K"=="" set "%%K=%%L"
                )
            )
        )

        echo Running: %PYTHON_PATH% "%PYTHON_SCRIPT%"
        %PYTHON_PATH% "%PYTHON_SCRIPT%"
        set "RC=!ERRORLEVEL!"

        if not "!RC!"=="0" (
            echo FAILED (exit code !RC!)
            set "OVERALL_EXIT=1"
        ) else (
            echo SUCCESS
        )
        echo.
    )
)

if %OVERALL_EXIT%==0 (
    echo All conversions completed successfully.
) else (
    echo One or more conversions failed.
)

exit /b %OVERALL_EXIT%
