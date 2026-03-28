@echo off
REM general_runner.bat - Traverse subdirectories and run a Python script on each
REM Configure the script and root directory below
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

REM Path to Python executable (leave empty to use default 'python')
if not defined PYTHON_PATH set "PYTHON_PATH=python"

REM Whether to append the subdirectory path as the final argument (1=yes,0=no)
if not defined PASS_SUBDIR_AS_ARG set "PASS_SUBDIR_AS_ARG=1"

REM Log file (overwritten each run) uses runner script name by default
if not defined LOG_FILE set "LOG_FILE=%~dpn0.log"

REM Required environment variables: ROOT_DIR, PYTHON_SCRIPT
if not defined ROOT_DIR (
    echo Error: ROOT_DIR environment variable is not set.
    exit /b 1
)

if not defined PYTHON_SCRIPT (
    echo Error: PYTHON_SCRIPT environment variable is not set.
    exit /b 1
)

if not defined SCRIPT_ARGS set "SCRIPT_ARGS="

set "SCRIPT_ARGS_CMD="
if defined SCRIPT_ARGS set "SCRIPT_ARGS_CMD= %SCRIPT_ARGS%"

echo.
echo Running %PYTHON_SCRIPT% for subdirectories in:
echo   %ROOT_DIR%
echo All further output deferred to %LOG_FILE%.
echo.

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

        if "%PASS_SUBDIR_AS_ARG%"=="1" (
            echo Running: %PYTHON_PATH% "%PYTHON_SCRIPT%"%SCRIPT_ARGS_CMD% "%%~fD"
            call "%PYTHON_PATH%" "%PYTHON_SCRIPT%"%SCRIPT_ARGS_CMD% "%%~fD"
        ) else (
            echo Running: %PYTHON_PATH% "%PYTHON_SCRIPT%"%SCRIPT_ARGS_CMD%
            call "%PYTHON_PATH%" "%PYTHON_SCRIPT%"%SCRIPT_ARGS_CMD%
        )
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

REM echo Initiating system shutdown in 60 seconds...
shutdown /s /f /t 60 /c "general_runner.bat completed. System will shut down in 60 seconds."

exit /b %OVERALL_EXIT%
