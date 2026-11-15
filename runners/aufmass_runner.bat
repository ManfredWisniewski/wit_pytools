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

REM Provisioning target (Nextcloud Tables). PROJEKT_ID overrides the .env
REM PROJEKT-ID value; leave empty to use .env.
if not defined PROJEKT_ID set "PROJEKT_ID="
if not defined SLUG set "SLUG=Stadthalle"
if not defined ETAGE set "ETAGE=UG"

REM Existing Tables context (App) id the views are attached to.
if not defined CONTEXT_ID set "CONTEXT_ID=7"

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

REM ==============================================================================
REM PROVISIONING (push tables + views to Nextcloud Tables context)
REM ==============================================================================

set "PROJ_ARG="
if defined PROJEKT_ID set "PROJ_ARG=--projekt %PROJEKT_ID%"

echo.
echo Provisioning to context id: %CONTEXT_ID%

call "%PYTHON_PATH%" -m wit_pytools.aufmass.tablesprovision %PROJ_ARG% ^
    --slug "%SLUG%" --etage "%ETAGE%" ^
    --src "%OUT_DIR%" --context-id "%CONTEXT_ID%"
if errorlevel 1 (
    echo.
    echo Provisioning failed.
    exit /b 1
)

echo.
echo Provisioning completed successfully.
exit /b 0
