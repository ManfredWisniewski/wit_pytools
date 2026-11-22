@echo off
REM xlsx_anonymize_runner.bat - Identify or anonymize one XLSX file per subdirectory
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

REM Root directory containing the subdirectories to process.
if not defined ROOT_DIR set "ROOT_DIR=."

REM XLSX filename expected in each subdirectory.
if not defined XLSX_FILE set "XLSX_FILE=20260905 Klassenkasse Stand 2026ber.xlsx"

REM Path to Python executable (leave empty to use default 'python').
if not defined PYTHON_PATH set "PYTHON_PATH=python"

REM Existing mapping and anonymized files may be overwritten when set to 1.
if not defined OVERWRITE_OUTPUTS set "OVERWRITE_OUTPUTS=1"

REM Group contained candidate values under one replacement when set to 1.
if not defined GROUP_CONTAINED_VALUES set "GROUP_CONTAINED_VALUES=1"

REM Log file (overwritten each run) uses runner script name by default.
if not defined LOG_FILE set "LOG_FILE=%~dpn0.log"

if not defined ROOT_DIR (
    echo Error: ROOT_DIR environment variable is not set.
    exit /b 1
)

if not defined XLSX_FILE (
    echo Error: XLSX_FILE is not set.
    exit /b 1
)

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

if not exist "%ROOT_DIR%\" (
    echo Error: Root directory not found: %ROOT_DIR%
    exit /b 1
)

set "PYTHON_ROOT=%~dp0..\.."
set "PYTHONPATH=%PYTHON_ROOT%;%PYTHONPATH%"

if not "%OVERWRITE_OUTPUTS%"=="0" if not "%OVERWRITE_OUTPUTS%"=="1" (
    echo Error: OVERWRITE_OUTPUTS must be 0 or 1.
    exit /b 1
)
if not "%GROUP_CONTAINED_VALUES%"=="0" if not "%GROUP_CONTAINED_VALUES%"=="1" (
    echo Error: GROUP_CONTAINED_VALUES must be 0 or 1.
    exit /b 1
)

echo.
echo Current directory: %CD%
echo Script directory: %~dp0
echo XLSX file: %XLSX_FILE%
echo Root directory: %ROOT_DIR%
echo.

REM ==============================================================================
REM PROCESSING
REM ==============================================================================

set "OVERALL_EXIT=0"
if exist "%ROOT_DIR%\%XLSX_FILE%" (
    echo ----------------------------------------
    echo Processing root directory
    echo Path: %ROOT_DIR%\%XLSX_FILE%
    echo ----------------------------------------
    call :PROCESS_DIRECTORY "%ROOT_DIR%"
    if errorlevel 1 set "OVERALL_EXIT=1"
    echo.
)

for /d %%D in ("%ROOT_DIR%\*") do (
    if exist "%%D\" if /I not "%%~nxD"=="__pycache__" (
        echo ----------------------------------------
        echo Processing: %%~nD
        echo Path: %%~fD\%XLSX_FILE%
        echo ----------------------------------------
        call :PROCESS_DIRECTORY "%%~fD"
        if errorlevel 1 set "OVERALL_EXIT=1"
        echo.
    )
)

if "!OVERALL_EXIT!"=="0" echo XLSX processing completed successfully.
if not "!OVERALL_EXIT!"=="0" echo One or more XLSX operations failed.
exit /b !OVERALL_EXIT!

:PROCESS_DIRECTORY
set "SOURCE_FILE=%~1\%XLSX_FILE%"
echo Debug current directory: %CD%
echo Debug directory argument: %~1
echo Debug XLSX_FILE: %XLSX_FILE%
echo Debug SOURCE_FILE: %SOURCE_FILE%
if exist "%SOURCE_FILE%" echo Debug source status: FOUND
if not exist "%SOURCE_FILE%" (
    echo Debug source status: NOT FOUND
    echo SKIPPED: XLSX file not found.
    exit /b 0
)

for %%F in ("%SOURCE_FILE%") do set "CANDIDATE_FILE=%%~dpnF_candidates.csv"
if exist "%CANDIDATE_FILE%" goto APPLY_MAPPING

echo Candidate file not found. Generating candidates.
echo Running candidate identification.
call "%PYTHON_PATH%" "%~dp0xlsx_anonymize_runner.py" "%SOURCE_FILE%" "%CANDIDATE_FILE%" "%OVERWRITE_OUTPUTS%" "%GROUP_CONTAINED_VALUES%"
if errorlevel 1 exit /b 1
echo CANDIDATES CREATED: %CANDIDATE_FILE%
echo Review the candidate CSV before the next run.
exit /b 0

:APPLY_MAPPING
echo Candidate file found. Creating mapping and anonymized workbook.
call "%PYTHON_PATH%" "%~dp0xlsx_anonymize_runner.py" "%SOURCE_FILE%" "%CANDIDATE_FILE%" "%OVERWRITE_OUTPUTS%" "%GROUP_CONTAINED_VALUES%"
if errorlevel 1 exit /b 1
echo SUCCESS
exit /b 0
