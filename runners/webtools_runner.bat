@echo off
REM webtools_runner.bat - Run webtools site automations (login, downloads)
REM Add more site subcommands to SITES to run several in sequence.
setlocal

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

if not defined PYTHON_PATH set "PYTHON_PATH=python"
set "PROJECT_ROOT=%~dp0..\.."
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

REM space-separated list of webtools subcommands to run
set "SITES=amex-de-statements mdcc-invoices"

set "OUT=P:\Downloads"
set "COUNT=1"

REM ==============================================================================
REM PROCESSING
REM ==============================================================================

pushd "%PROJECT_ROOT%"
set "OVERALL_EXIT=0"
for %%S in (%SITES%) do (
    echo ----------------------------------------
    echo Running: wit_pytools.webtools %%S
    echo ----------------------------------------
    %PYTHON_PATH% -m wit_pytools.webtools %%S --out "%OUT%" --count "%COUNT%"
    if errorlevel 1 set "OVERALL_EXIT=1"
    echo.
)
popd

if not "%OVERALL_EXIT%"=="0" echo One or more webtools runs failed.
exit /b %OVERALL_EXIT%
