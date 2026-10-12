@echo off
REM ai_avatar_image_runner.bat - Generate images for every subdirectory
REM of ROOT_DIR that contains a prompt file. Reference images are extracted
REM from agents_base.zip into ROOT_DIR before the run and deleted afterwards.
for /f "tokens=2 delims=:" %%C in ('chcp') do set "ORIGINAL_CODEPAGE=%%C"
set "ORIGINAL_CODEPAGE=%ORIGINAL_CODEPAGE: =%"
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Root directory: subdirectories hold the prompts, root holds references
set "ROOT_DIR=P:\git\arr\obs-seo-witconsult\w1t.org\media\agents"

REM Prompt filename inside each subdirectory (subdirs without it are skipped)
set "PROMPT_FILENAME=prompt.txt"

REM Optional negative prompt filename inside each subdirectory
set "NEGATIVE_PROMPT_FILENAME=negative_prompt.txt"

REM Reference image files in ROOT_DIR (space-separated glob patterns)
set "REF_PATTERN=*.png *.jpg *.jpeg *.webp"

REM Image model id (leave empty to use OPENROUTER_IMAGE_MODEL from set_ENV.bat)
set "IMAGE_MODEL=google/gemini-3-pro-image"
REM bytedance-seed/seedream-5-0-lite

REM Number of images per subdirectory (1-10, provider permitting)
set "N=1"

REM Optional image parameters (leave empty to omit)
set "ASPECT_RATIO="
set "RESOLUTION="
set "QUALITY="
set "OUTPUT_FORMAT="

REM Behaviour toggles (0 = disabled, 1 = enabled)
set "OVERWRITE=0"
set "SKIP_COST_CONFIRM=1"

REM Cost limit in USD (leave empty to use OPENROUTER_MAX_COST / default 0.50)
set "MAX_COST="

REM Log file (appended each run)
set "LOG_FILE=%~dpn0.log"

REM ==============================================================================
REM ENVIRONMENT
REM ==============================================================================

if not exist "%~dp0set_ENV.bat" (
    echo Error: %~dp0set_ENV.bat not found. Copy set_ENV_template.bat to set_ENV.bat and add your key.
    goto :FAIL
)
call "%~dp0set_ENV.bat"
if errorlevel 1 (
    echo Error: set_ENV.bat failed.
    goto :FAIL
)

if "%PYTHON_PATH%"=="" set "PYTHON_PATH=python"
set "PYTHONPATH=%~dp0..\..;%PYTHONPATH%"

REM ==============================================================================
REM VALIDATION
REM ==============================================================================

if not exist "%ROOT_DIR%\" (
    echo Error: ROOT_DIR not found: %ROOT_DIR%
    goto :FAIL
)
if "%IMAGE_MODEL%"=="" if "%OPENROUTER_IMAGE_MODEL%"=="" (
    echo Error: no model. Set IMAGE_MODEL here or OPENROUTER_IMAGE_MODEL in set_ENV.bat.
    goto :FAIL
)
if not exist "%ROOT_DIR%\agents_base.zip" (
    echo Error: agents_base.zip not found in %ROOT_DIR%
    goto :FAIL
)

REM ==============================================================================
REM EXTRACT BASE IMAGES
REM ==============================================================================

echo Extracting agents_base.zip ...
tar -xf "%ROOT_DIR%\agents_base.zip" -C "%ROOT_DIR%"
if errorlevel 1 (
    echo Error: could not extract agents_base.zip
    goto :FAIL
)

REM ==============================================================================
REM BUILD SHARED ARGUMENTS
REM ==============================================================================

set ARGS=-n %N% --log "%LOG_FILE%"
if not "%IMAGE_MODEL%"=="" set ARGS=!ARGS! --model "%IMAGE_MODEL%"
if not "%ASPECT_RATIO%"=="" set ARGS=!ARGS! --aspect-ratio %ASPECT_RATIO%
if not "%RESOLUTION%"=="" set ARGS=!ARGS! --resolution %RESOLUTION%
if not "%QUALITY%"=="" set ARGS=!ARGS! --quality %QUALITY%
if not "%OUTPUT_FORMAT%"=="" set ARGS=!ARGS! --output-format %OUTPUT_FORMAT%
if not "%MAX_COST%"=="" set ARGS=!ARGS! --max-cost %MAX_COST%
if "%OVERWRITE%"=="1" set ARGS=!ARGS! --overwrite
if "%SKIP_COST_CONFIRM%"=="1" set ARGS=!ARGS! --yes

REM collect reference images from ROOT_DIR (unquoted glob needs pushd)
pushd "%ROOT_DIR%"
for %%E in (%REF_PATTERN%) do (
    for %%R in (%%E) do set "ARGS=!ARGS! --reference "%%~fR""
)
popd

REM ==============================================================================
REM RUN: one generate_image call per subdirectory
REM ==============================================================================

set "OVERALL_EXIT=0"
set "PROCESSED=0"
for /d %%D in ("%ROOT_DIR%\*") do (
    if exist "%%~fD\%PROMPT_FILENAME%" (
        set /a PROCESSED+=1
        set "SUB_ARGS=--prompt-file "%%~fD\%PROMPT_FILENAME%" --out-dir "%%~fD""
        if exist "%%~fD\%NEGATIVE_PROMPT_FILENAME%" (
            set "SUB_ARGS=!SUB_ARGS! --negative-prompt-file "%%~fD\%NEGATIVE_PROMPT_FILENAME%""
        )
        echo.
        echo ----------------------------------------
        echo Processing: %%~nD
        echo ----------------------------------------
        "%PYTHON_PATH%" -m wit_pytools.aitools.generate_image !SUB_ARGS! !ARGS!
        if errorlevel 1 (
            echo FAILED: %%~nD
            set "OVERALL_EXIT=1"
        ) else (
            echo SUCCESS: %%~nD
        )
    ) else (
        echo Skipping %%~nD ^(no %PROMPT_FILENAME%^)
    )
)

echo.
if "%PROCESSED%"=="0" echo Warning: no subdirectory contained %PROMPT_FILENAME%

REM cleanup extracted reference images in ROOT_DIR
del /q "%ROOT_DIR%\*.jpg" "%ROOT_DIR%\*.JPG" 2>nul

if "%OVERALL_EXIT%"=="0" (
    echo Done - see %LOG_FILE%
) else (
    echo One or more generations failed - see %LOG_FILE%
)
pause
call :RESTORE_CODEPAGE
exit /b %OVERALL_EXIT%

:FAIL
echo.
pause
call :RESTORE_CODEPAGE
exit /b 1

:RESTORE_CODEPAGE
if defined ORIGINAL_CODEPAGE chcp %ORIGINAL_CODEPAGE% >nul
exit /b 0
