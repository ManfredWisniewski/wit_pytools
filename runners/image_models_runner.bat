@echo off
REM image_models_runner.bat - Generate images for every subdirectory of
REM ROOT_DIR that contains a prompt file, once per model in MODELS.
REM Reference images are taken from ROOT_DIR (REF_PATTERN), output lands
REM in <subdir>\<model-name>\ so variants stay comparable.
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
set "ROOT_DIR=P:\clients\client-wuttkeklimatechnik\solutions\@assets\images"

REM Prompt filename inside each subdirectory (subdirs without it are skipped)
set "PROMPT_FILENAME=prompt.txt"

REM Optional negative prompt filename inside each subdirectory
set "NEGATIVE_PROMPT_FILENAME=negative_prompt.txt"

REM Reference image files in ROOT_DIR (space-separated glob patterns)
set "REF_PATTERN=reference.png"

REM Space-separated model ids, one run each (empty: OPENROUTER_IMAGE_MODEL)
set "MODELS=bytedance-seed/seedream-5-0-lite recraft/recraft-v4.1-pro qwen/qwen-image-3 qwen/qwen-image-3-pro"

REM Providers that reject n>1: N single-image calls each instead
set "MODELS_N1=black-forest-labs/flux.2-klein-4b google/gemini-3-pro-image"

REM Number of images per model and subdirectory (1-10, provider permitting)
set "N=2"

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
if "%MODELS%"=="" if "%OPENROUTER_IMAGE_MODEL%"=="" (
    echo Error: no model. Set MODELS here or OPENROUTER_IMAGE_MODEL in set_ENV.bat.
    goto :FAIL
)
if "%MODELS%"=="" set "MODELS=%OPENROUTER_IMAGE_MODEL%"

REM ==============================================================================
REM BUILD SHARED ARGUMENTS
REM ==============================================================================

set ARGS=--log "%LOG_FILE%"
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
REM RUN: one generate_image call per model x subdirectory
REM ==============================================================================

set "OVERALL_EXIT=0"
set "PROCESSED=0"
for %%M in (%MODELS%) do (
    for /f "tokens=2 delims=/" %%B in ("%%~M") do set "MODEL_DIR_SUFFIX=%%B"
    if "!MODEL_DIR_SUFFIX!"=="" set "MODEL_DIR_SUFFIX=%%~nM"
    for /d %%D in ("%ROOT_DIR%\*") do (
        if exist "%%~fD\%PROMPT_FILENAME%" (
            set /a PROCESSED+=1
            set "SUB_OUT=%%~fD\!MODEL_DIR_SUFFIX!"
            if not exist "!SUB_OUT!\" mkdir "!SUB_OUT!"
            set "SUB_ARGS=-n %N% --prompt-file "%%~fD\%PROMPT_FILENAME%" --out-dir "!SUB_OUT!" --model "%%~M""
            if exist "%%~fD\%NEGATIVE_PROMPT_FILENAME%" (
                set "SUB_ARGS=!SUB_ARGS! --negative-prompt-file "%%~fD\%NEGATIVE_PROMPT_FILENAME%""
            )
            echo.
            echo ----------------------------------------
            echo Processing: %%~nD ^| %%~M
            echo ----------------------------------------
            "%PYTHON_PATH%" -m wit_pytools.aitools.generate_image !SUB_ARGS! !ARGS!
            if errorlevel 1 (
                echo FAILED: %%~nD ^| %%~M
                set "OVERALL_EXIT=1"
            ) else (
                echo SUCCESS: %%~nD ^| %%~M
            )
        ) else (
            echo Skipping %%~nD ^(no %PROMPT_FILENAME%^)
        )
    )
)

REM single-image providers: N calls with -n 1
for %%M in (%MODELS_N1%) do (
    for /f "tokens=2 delims=/" %%B in ("%%~M") do set "MODEL_DIR_SUFFIX=%%B"
    if "!MODEL_DIR_SUFFIX!"=="" set "MODEL_DIR_SUFFIX=%%~nM"
    for /d %%D in ("%ROOT_DIR%\*") do (
        if exist "%%~fD\%PROMPT_FILENAME%" (
            set "SUB_OUT=%%~fD\!MODEL_DIR_SUFFIX!"
            if not exist "!SUB_OUT!\" mkdir "!SUB_OUT!"
            set "SUB_ARGS=-n 1 --prompt-file "%%~fD\%PROMPT_FILENAME%" --out-dir "!SUB_OUT!" --model "%%~M""
            if exist "%%~fD\%NEGATIVE_PROMPT_FILENAME%" (
                set "SUB_ARGS=!SUB_ARGS! --negative-prompt-file "%%~fD\%NEGATIVE_PROMPT_FILENAME%""
            )
            for /l %%I in (1,1,%N%) do (
                set /a PROCESSED+=1
                echo.
                echo ----------------------------------------
                echo Processing: %%~nD ^| %%~M ^(image %%I/%N%^)
                echo ----------------------------------------
                "%PYTHON_PATH%" -m wit_pytools.aitools.generate_image !SUB_ARGS! !ARGS!
                if errorlevel 1 (
                    echo FAILED: %%~nD ^| %%~M ^(image %%I^)
                    set "OVERALL_EXIT=1"
                ) else (
                    echo SUCCESS: %%~nD ^| %%~M ^(image %%I^)
                )
            )
        )
    )
)

echo.
if "%PROCESSED%"=="0" echo Warning: no subdirectory contained %PROMPT_FILENAME%

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
