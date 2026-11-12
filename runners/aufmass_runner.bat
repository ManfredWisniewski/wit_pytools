@echo off
REM aufmass_runner.bat - Convert KLIMAX XLS exports to CSV (recursive, room folders)
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

REM Source directory containing the room subdirectories with *.xls files.
if not defined SRC_DIR set "SRC_DIR=P:\tmp\aufmass-data\UG"

REM Output directory - the relative room structure is preserved below it.
if not defined OUT_DIR set "OUT_DIR=P:\tmp\aufmass-data"

REM Path to Python executable (leave empty to use default 'python').
if not defined PYTHON_PATH set "PYTHON_PATH=python"

REM Log file (overwritten each run) uses runner script name by default.
if not defined LOG_FILE set "LOG_FILE=%~dpn0.log"

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
    exit /b 1
)

if not exist "%SRC_DIR%\" (
    echo Error: Source directory not found: %SRC_DIR%
    exit /b 1
)

set "PYTHONPATH=%~dp0..\..;%PYTHONPATH%"

echo.
echo Source directory: %SRC_DIR%
echo Output directory: %OUT_DIR%
echo.

REM ==============================================================================
REM PROCESSING
REM ==============================================================================

call "%PYTHON_PATH%" -m wit_pytools.aufmass --src "%SRC_DIR%" --out "%OUT_DIR%"
if errorlevel 1 (
    echo.
    echo One or more conversions failed.
    exit /b 1
)

echo.
echo All conversions completed successfully.
exit /b 0
