@echo off
REM ai_avatar_runner.bat - render AI-labelled 512x512 avatars
REM Traverses subdirectories of ROOT_DIR and creates a
REM <image>-avatar_512x512<ext> next to every image. *_avatar_512x512*
REM inputs are normalized to -avatar; *-avatar* files count as done.
for /f "tokens=2 delims=:" %%C in ('chcp') do set "ORIGINAL_CODEPAGE=%%C"
set "ORIGINAL_CODEPAGE=%ORIGINAL_CODEPAGE: =%"
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Root directory; its subdirectories are scanned for images
set "ROOT_DIR=P:\git\arr\obs-seo-witconsult\w1t.org\media\agents"

REM Image extensions to process (space-separated)
set "EXTENSIONS=jpg jpeg png webp"

REM Output marker appended to the filename
set "MARKER=avatar_512x512"

REM Canvas size in px
set "SIZE=512"

REM Overwrite existing avatar files (0 = no, 1 = yes)
set "OVERWRITE=0"

REM Log file (appended each run)
set "LOG_FILE=%~dpn0.log"

REM ==============================================================================
REM ENVIRONMENT
REM ==============================================================================

if "%PYTHON_PATH%"=="" set "PYTHON_PATH=python"
set "PYTHONPATH=%~dp0..\..;%PYTHONPATH%"

if not exist "%ROOT_DIR%\" (
    echo Error: ROOT_DIR not found: %ROOT_DIR%
    goto :FAIL
)

set "ARGS=--size %SIZE%"
if "%OVERWRITE%"=="1" set "ARGS=!ARGS! --overwrite"

REM ==============================================================================
REM RUN
REM ==============================================================================

set "FAILURES=0"
set "PROCESSED=0"
for /d %%D in ("%ROOT_DIR%\*") do (
    pushd "%%~fD"
    for %%E in (%EXTENSIONS%) do (
        for %%F in (*.%%E) do call :PROCESS "%%~fF"
    )
    popd
)

echo.
echo Done: %PROCESSED% image(s) processed, %FAILURES% failed - see %LOG_FILE%
pause
call :RESTORE_CODEPAGE
exit /b %FAILURES%

:PROCESS
if not exist "%~1" exit /b 0
set "SRC=%~1"
set "NAME=%~nx1"
set "STEM=%~n1"
if not "!STEM:-%MARKER%=!"=="!STEM!" (
    echo Skipping %NAME% ^(is an avatar^)
    exit /b 0
)
REM normalize _avatar -> -avatar in the target name
set "TARGET=!STEM:_%MARKER%=-%MARKER%!"
if "!TARGET!"=="!STEM!" set "TARGET=!STEM!-%MARKER%"
if exist "%~dp1!TARGET!.*" (
    echo Skipping %NAME% ^(variant exists^)
    exit /b 0
)
set /a PROCESSED+=1
"%PYTHON_PATH%" -m wit_pytools.imgtools "%SRC%" "%~dp1!TARGET!%~x1" %ARGS% >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo FAILED: %NAME% - see %LOG_FILE%
    set /a FAILURES+=1
) else (
    echo OK: !TARGET!%~x1
)
exit /b 0

:FAIL
echo.
pause
call :RESTORE_CODEPAGE
exit /b 1

:RESTORE_CODEPAGE
if defined ORIGINAL_CODEPAGE chcp %ORIGINAL_CODEPAGE% >nul
exit /b 0
