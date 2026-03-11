@echo off
REM cinderellasort_runner.bat - Configurable wrapper for cinderellasort
REM Location: P:\sort\cinderellasort_runner.bat
setlocal enabledelayedexpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Path to wit_pytools directory containing cinderellasort.py
set "SCRIPT_DIR=P:\git\witnctools\wit_pytools"

REM Working directory (where cinderellasort.ini and files to sort are located)
set "WORK_DIR=P:\sort"

REM List of config INI files to process (space-separated, leave empty to use cinderellasort.ini in work dir)
REM Example: set "CONFIG_FILES=P:\sort\downloads.ini P:\sort\emails.ini"
set "CONFIG_FILES=P:\sort\downloads.ini P:\sort\movies.ini P:\sort\library.ini P:\sort\comics.ini"

REM Additional options to pass to cinderellasort
REM Options: --dryrun, --verbose, etc.
set "EXTRA_OPTS="
REM set "EXTRA_OPTS=--dryrun"

REM Example: move all files between directories (requires Python call)
python -c "import sys; sys.path.insert(0, r'P:\git\witnctools'); from wit_pytools.systools import moveallfiles; moveallfiles(r'H:\svartalvheim\usenet\done\3d', r'H:\midgard\sort-3d', False)"
python -c "import sys; sys.path.insert(0, r'P:\git\witnctools'); from wit_pytools.systools import moveallfiles; moveallfiles(r'H:\svartalvheim\usenet\done\courses', r'H:\midgard\encode\courses', False)"
python -c "import sys; sys.path.insert(0, r'P:\git\witnctools'); from wit_pytools.systools import moveallfiles; moveallfiles(r'H:\svartalvheim\usenet\done\audiobooks', r'H:\midgard\encode\audiobooks-sort', False)"
python -c "import sys; sys.path.insert(0, r'P:\git\witnctools'); from wit_pytools.systools import moveallfiles; moveallfiles(r'H:\svartalvheim\usenet\done\games', r'H:\midgard\sort-games', False)"
python -c "import sys; sys.path.insert(0, r'P:\git\witnctools'); from wit_pytools.systools import moveallfiles; moveallfiles(r'H:\svartalvheim\usenet\done\_music', r'H:\midgard\encode\music', False)"

REM ==============================================================================
REM SCRIPT LOGIC - Do not edit below this line unless necessary
REM ==============================================================================

echo DEBUG START: EXTRA_OPTS=%EXTRA_OPTS%
echo DEBUG START: EXTRA_OPTS delayed=!EXTRA_OPTS!


REM Set default Python if not specified
if "%PYTHON_PATH%"=="" set "PYTHON_PATH=python"

REM Verify Python is available
%PYTHON_PATH% --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found at '%PYTHON_PATH%'
    echo Please set PYTHON_PATH in the configuration section
    pause
    exit /b 1
)

REM Verify script directory exists
if not exist "%SCRIPT_DIR%\" (
    echo Error: Script directory not found: %SCRIPT_DIR%
    echo Please set SCRIPT_DIR in the configuration section
    pause
    exit /b 1
)

REM Verify cinderellasort.py exists
set "CINDERELLA_SCRIPT=%SCRIPT_DIR%\cinderellasort.py"
if not exist "%CINDERELLA_SCRIPT%" (
    echo Error: cinderellasort.py not found at: %CINDERELLA_SCRIPT%
    pause
    exit /b 1
)

REM Verify work directory exists
if not exist "%WORK_DIR%\" (
    echo Error: Work directory not found: %WORK_DIR%
    echo Please set WORK_DIR in the configuration section
    pause
    exit /b 1
)

REM Set default config files if not specified
if "%CONFIG_FILES%"=="" set "CONFIG_FILES=%WORK_DIR%\cinderellasort.ini"

REM Verify all config files exist
for %%F in (%CONFIG_FILES%) do (
    if not exist "%%F" (
        echo Error: Config file not found: %%F
        echo Please create the INI file or set CONFIG_FILES in the configuration section
        pause
        exit /b 1
    )
)

REM Set PYTHONPATH so Python can find wit_pytools module
for %%I in ("%SCRIPT_DIR%") do set "PYTHONPATH=%%~dpI"
echo PYTHONPATH set to: %PYTHONPATH%

REM Test Python can import wit_pytools
echo Testing Python imports...
%PYTHON_PATH% -c "import sys; sys.path.insert(0, '%PYTHONPATH:\=\\%'); from wit_pytools import cinderellasort; print('Import OK')" 2>&1
if errorlevel 1 (
    echo.
    echo Warning: Could not import wit_pytools module - see error above
    echo Trying direct script execution anyway...
    echo.
)

REM Change to work directory
cd /d "%WORK_DIR%"

REM Build command arguments
set "CMD_ARGS="

if not "%EXTRA_OPTS%"=="" (
    set "CMD_ARGS=%CMD_ARGS% %EXTRA_OPTS%"
)

REM Process each config file
set "OVERALL_EXIT_CODE=0"
echo.
echo ========================================
echo Processing config files: %CONFIG_FILES%
echo ========================================
echo.

for %%F in (%CONFIG_FILES%) do (
    echo.
    echo ----------------------------------------
    echo Processing: %%F
    echo ----------------------------------------
    echo DEBUG: EXTRA_OPTS=!EXTRA_OPTS!
    
    REM Build command arguments for wrapper
    set "WRAPPER_ARGS="
    if not "!EXTRA_OPTS!"=="" (
        set "WRAPPER_ARGS=!EXTRA_OPTS!"
    )
    set "WRAPPER_ARGS=!WRAPPER_ARGS! "%%F""
    
    REM Debug: show what we're running
    echo DEBUG: Running: %PYTHON_PATH% "%WORK_DIR%\run_cinderellasort.py" !WRAPPER_ARGS!
    REM Run the wrapper script
    %PYTHON_PATH% "%WORK_DIR%\run_cinderellasort.py" !WRAPPER_ARGS!
    
    if errorlevel 1 (
        echo FAILED: %%F
        set "OVERALL_EXIT_CODE=1"
    ) else (
        echo SUCCESS: %%F
    )
    echo.
)

set "EXIT_CODE=%OVERALL_EXIT_CODE%"

if %EXIT_CODE%==0 (
    echo.
    echo cinderellasort completed successfully
) else (
    echo.
    echo cinderellasort failed with exit code: %EXIT_CODE%
)

pause
exit /b %EXIT_CODE%
