@echo off
REM pdf2md_runner.bat - Configurable wrapper for documenttools.pdf2md (PDF to Markdown)
REM Loads the OpenRouter environment from set_ENV.bat (git-ignored, holds the key).
REM Drag a PDF onto this file or pass its path as the first argument.
for /f "tokens=2 delims=:" %%C in ('chcp') do set "ORIGINAL_CODEPAGE=%%C"
set "ORIGINAL_CODEPAGE=%ORIGINAL_CODEPAGE: =%"
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ==============================================================================
REM CONFIGURATION - Edit these variables as needed
REM ==============================================================================

REM Path to Python executable (leave empty to use system default 'python')
set "PYTHON_PATH="

REM Input PDF. A first command-line argument overrides it.
set "INPUT_PDF=%~dp0document.pdf"

REM Conversion mode: vision (multimodal model) or text (text layer only, no API cost)
set "MODE=vision"

REM Vision model id (leave empty to use OPENROUTER_PDF_MODEL from set_ENV.bat)
set "PDF_MODEL="

REM Page range (leave empty for the whole document)
set "START_PAGE="
set "END_PAGE="

REM Output .md path (leave empty to write <stem>.md beside the PDF)
set "OUTPUT_MD="

REM Optional prompt override, read as UTF-8 (leave empty for the built-in prompt)
set "PROMPT_FILE="

REM Render resolution for page images
set "DPI=150"

REM Marker language for failed pages: en or de
set "LANGUAGE=de"

REM Behaviour toggles (0 = disabled, 1 = enabled)
set "OVERWRITE=0"
set "KEEP_PAGES=0"
set "CONTINUE_ON_ERROR=0"
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
if not "%~1"=="" set "INPUT_PDF=%~1"

REM ==============================================================================
REM VALIDATION
REM ==============================================================================

if not exist "%INPUT_PDF%" (
    echo Error: input PDF not found: %INPUT_PDF%
    goto :FAIL
)
if "%MODE%"=="vision" if "%PDF_MODEL%"=="" if "%OPENROUTER_PDF_MODEL%"=="" if "%OPENROUTER_MODEL%"=="" (
    echo Error: no model. Set PDF_MODEL here or OPENROUTER_PDF_MODEL in set_ENV.bat.
    goto :FAIL
)

REM ==============================================================================
REM BUILD ARGUMENTS
REM ==============================================================================

set ARGS=--mode %MODE% --dpi %DPI% --language %LANGUAGE% --log "%LOG_FILE%"
if not "%PDF_MODEL%"=="" set ARGS=!ARGS! --model "%PDF_MODEL%"
if not "%START_PAGE%"=="" set ARGS=!ARGS! --start %START_PAGE%
if not "%END_PAGE%"=="" set ARGS=!ARGS! --end %END_PAGE%
if not "%OUTPUT_MD%"=="" set ARGS=!ARGS! --output "%OUTPUT_MD%"
if not "%PROMPT_FILE%"=="" set ARGS=!ARGS! --prompt-file "%PROMPT_FILE%"
if not "%MAX_COST%"=="" set ARGS=!ARGS! --max-cost %MAX_COST%
if "%OVERWRITE%"=="1" set ARGS=!ARGS! --overwrite
if "%KEEP_PAGES%"=="1" set ARGS=!ARGS! --keep-pages
if "%CONTINUE_ON_ERROR%"=="1" set ARGS=!ARGS! --continue-on-error
if "%SKIP_COST_CONFIRM%"=="1" set ARGS=!ARGS! --yes

REM ==============================================================================
REM RUN
REM ==============================================================================

echo.
echo Running: %PYTHON_PATH% -m wit_pytools.documenttools.pdf2md "%INPUT_PDF%" !ARGS!
echo.
"%PYTHON_PATH%" -m wit_pytools.documenttools.pdf2md "%INPUT_PDF%" !ARGS!
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

:RESTORE_CODEPAGE
if defined ORIGINAL_CODEPAGE chcp %ORIGINAL_CODEPAGE% >nul
exit /b 0
