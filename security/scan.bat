@echo off
REM Security Scan Wrapper - Windows
REM Usage: scan.bat [path] [output_dir] [docker_image]

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set TARGET_PATH=%~1
set OUTPUT_DIR=%~2
set DOCKER_IMAGE=%~3

if "%TARGET_PATH%"=="" set TARGET_PATH=%PROJECT_ROOT%
if "%OUTPUT_DIR%"=="" set OUTPUT_DIR=%PROJECT_ROOT%\reports\security

echo =========================================
echo Security Scan
echo Target: %TARGET_PATH%
echo Output: %OUTPUT_DIR%
echo =========================================

cd /d %PROJECT_ROOT%
python security\scan.py --path "%TARGET_PATH%" --output "%OUTPUT_DIR%" %DOCKER_IMAGE%

set EXIT_CODE=%ERRORLEVEL%

echo =========================================
if %EXIT_CODE% equ 0 (
    echo Scan completed - no critical/high findings
) else (
    echo Scan completed - critical/high findings detected
)
echo =========================================

exit /b %EXIT_CODE%