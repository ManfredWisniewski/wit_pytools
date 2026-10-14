@echo off
REM agent_accounts_runner.bat - Assisted account signups for persona mail
REM addresses. Add more flow subcommands to FLOWS to run several in sequence.
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION
REM ==============================================================================

if not defined PYTHON_PATH set "PYTHON_PATH=python"
set "PROJECT_ROOT=%~dp0..\.."
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"

REM space-separated list of webtools subcommands to run
set "FLOWS=ms-account google-account"

REM mailbox tag for <TAG>_IMAP_* env vars (verification-link polling)
set "MAILBOX=claudia"

REM extra args appended to every flow (e.g. --timeout 3600)
set "EXTRA_ARGS="

REM ==============================================================================
REM PROCESSING
REM ==============================================================================

pushd "%PROJECT_ROOT%"
set "OVERALL_EXIT=0"
for %%F in (%FLOWS%) do (
    echo ----------------------------------------
    echo Running: wit_pytools.webtools %%F
    echo ----------------------------------------
    %PYTHON_PATH% -m wit_pytools.webtools %%F --mailbox %MAILBOX% %EXTRA_ARGS%
    if errorlevel 1 set "OVERALL_EXIT=1"
    echo.
)
popd

if not "%OVERALL_EXIT%"=="0" echo One or more account flows failed.
exit /b %OVERALL_EXIT%
