@echo off
REM generate_image_runner.bat - Configurable wrapper for aitools.generate_image
REM Loads the OpenRouter environment from set_ENV.bat (git-ignored, holds the key).
for /f "tokens=2 delims=:" %%C in ('chcp') do set "ORIGINAL_CODEPAGE=%%C"
set "ORIGINAL_CODEPAGE=%ORIGINAL_CODEPAGE: =%"
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Prompt is read as UTF-8 from this file. A first command-line argument overrides it.
set "PROMPT_FILE=%~dp0generate_image_prompt.txt"

REM Negative prompt is read as UTF-8 from this file. Leave empty to disable it.
set "NEGATIVE_PROMPT_FILE=%~dp0generate_image_negative_prompt.txt"

REM Image model id (leave empty to use OPENROUTER_IMAGE_MODEL from set_ENV.bat)
set "IMAGE_MODEL=bytedance-seed/seedream-5-0-lite"

REM Output directory for images and the JSON sidecar
set "OUT_DIR=.\images"

REM Number of images (1-10, provider permitting)
set "N=1"

REM Optional image parameters (leave empty to omit)
set "NEGATIVE_PROMPT="
set "ASPECT_RATIO="
set "RESOLUTION="
set "QUALITY="
set "OUTPUT_FORMAT="

REM Optional reference images, separated by ; (paths or URLs)
set "REFERENCES=ref.jpg"

REM Behaviour toggles (0 = disabled, 1 = enabled)
set "OVERWRITE=0"
set "SKIP_COST_CONFIRM=0"

REM Cost limit in USD (leave empty to use OPENROUTER_MAX_COST / default 0.50)
set "MAX_COST="

REM Log file (appended each run). Console output stays visible for the cost prompt.
set "LOG_FILE=%~dpn0.log"

REM Skip the set_ENV.bat connection check (1 = skip)
set "SKIP_CHECK=1"

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
set PROMPT_ARGS=--prompt-file "%PROMPT_FILE%"
if not "%~1"=="" set PROMPT_ARGS="%~1"

REM ==============================================================================
REM VALIDATION
REM ==============================================================================

if "%~1"=="" if not exist "%PROMPT_FILE%" (
    echo Error: prompt file not found: %PROMPT_FILE%
    goto :FAIL
)
if "%IMAGE_MODEL%"=="" if "%OPENROUTER_IMAGE_MODEL%"=="" (
    echo Error: no model. Set IMAGE_MODEL here or OPENROUTER_IMAGE_MODEL in set_ENV.bat.
    goto :FAIL
)

REM ==============================================================================
REM BUILD ARGUMENTS
REM ==============================================================================

set ARGS=--out-dir "%OUT_DIR%" -n %N% --log "%LOG_FILE%"
if exist "%NEGATIVE_PROMPT_FILE%" set ARGS=!ARGS! --negative-prompt-file "%NEGATIVE_PROMPT_FILE%"
if not "%NEGATIVE_PROMPT%"=="" set ARGS=!ARGS! --negative-prompt "%NEGATIVE_PROMPT%"
if not "%IMAGE_MODEL%"=="" set ARGS=!ARGS! --model "%IMAGE_MODEL%"
if not "%ASPECT_RATIO%"=="" set ARGS=!ARGS! --aspect-ratio %ASPECT_RATIO%
if not "%RESOLUTION%"=="" set ARGS=!ARGS! --resolution %RESOLUTION%
if not "%QUALITY%"=="" set ARGS=!ARGS! --quality %QUALITY%
if not "%OUTPUT_FORMAT%"=="" set ARGS=!ARGS! --output-format %OUTPUT_FORMAT%
if not "%MAX_COST%"=="" set ARGS=!ARGS! --max-cost %MAX_COST%
if "%OVERWRITE%"=="1" set ARGS=!ARGS! --overwrite
if "%SKIP_COST_CONFIRM%"=="1" set ARGS=!ARGS! --yes

if not "%REFERENCES%"=="" call :ADD_REFERENCES

REM ==============================================================================
REM RUN
REM ==============================================================================

echo.
echo Running: %PYTHON_PATH% -m wit_pytools.aitools.generate_image !PROMPT_ARGS! !ARGS!
echo.
"%PYTHON_PATH%" -m wit_pytools.aitools.generate_image !PROMPT_ARGS! !ARGS!
set "RC=!ERRORLEVEL!"

echo.
if "!RC!"=="0" (
    echo SUCCESS - see %LOG_FILE%
) else (
    echo FAILED ^(exit code !RC!^) - see %LOG_FILE%
)
pause
call :RESTORE_CODEPAGE
exit /b !RC!

:FAIL
echo.
pause
call :RESTORE_CODEPAGE
exit /b 1

:ADD_REFERENCES
for %%R in ("%REFERENCES:;=" "%") do set "ARGS=!ARGS! --reference "%%~R""
exit /b 0

:RESTORE_CODEPAGE
if defined ORIGINAL_CODEPAGE chcp %ORIGINAL_CODEPAGE% >nul
exit /b 0
