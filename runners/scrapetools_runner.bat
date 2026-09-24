@echo off
REM scrapetools_runner.bat - Scrape XPath-selected values into a CSV
setlocal

set "PYTHON_PATH=python"
set "PYTHONPATH=%~dp0..\..;%PYTHONPATH%"
set "URL=https://example.com/"
set "SELECTOR=//*/div/table/"
set "OUTPUT=.\scraped_values.csv"
set "METHOD=lxml"
set "TIMEOUT=30"
set "RETRIES=2"
set "USER_AGENT=witnctools-scrapetools/0.1"
set "OVERWRITE=1"

if "%OUTPUT%"=="" (
    echo Error: set OUTPUT in the configuration section.
    exit /b 1
)

if "%OVERWRITE%"=="1" (
    %PYTHON_PATH% -m wit_pytools.scrapetools "%URL%" "%SELECTOR%" --output "%OUTPUT%" --method "%METHOD%" --timeout "%TIMEOUT%" --retries "%RETRIES%" --user-agent "%USER_AGENT%" --overwrite
) else (
    %PYTHON_PATH% -m wit_pytools.scrapetools "%URL%" "%SELECTOR%" --output "%OUTPUT%" --method "%METHOD%" --timeout "%TIMEOUT%" --retries "%RETRIES%" --user-agent "%USER_AGENT%"
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Scrape failed with exit code %RC%.
exit /b %RC%
