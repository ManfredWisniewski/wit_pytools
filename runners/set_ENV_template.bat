@echo off
REM set_ENV_template.bat - set environment and run checks where applicable
REM Copy or rename this file to set_ENV.bat (git ignored) and add your details
setlocal

REM ==============================================================================
REM CONFIGURATION OPEN ROUTER - only OPENROUTER_API_KEY is required
REM ==============================================================================
set "OPENROUTER_API_KEY="
set "OPENROUTER_MODEL="
set "OPENROUTER_IMAGE_MODEL="
set "OPENROUTER_PDF_MODEL=qwen/qwen3-vl-8b-instruct"
set "OPENROUTER_MAX_COST=0.50"

set "PYTHONPATH=%~dp0..\..;%PYTHONPATH%"

if "%OPENROUTER_API_KEY%"=="" (
    echo Error: OPENROUTER_API_KEY is empty. Edit %~nx0 and add your key.
    exit /b 1
)

echo.
echo Variables are set for this window only.

:DONE
endlocal & set "OPENROUTER_API_KEY=%OPENROUTER_API_KEY%" & set "OPENROUTER_MODEL=%OPENROUTER_MODEL%" & set "OPENROUTER_IMAGE_MODEL=%OPENROUTER_IMAGE_MODEL%" & set "OPENROUTER_PDF_MODEL=%OPENROUTER_PDF_MODEL%" & set "OPENROUTER_MAX_COST=%OPENROUTER_MAX_COST%" & set "PYTHONPATH=%PYTHONPATH%"