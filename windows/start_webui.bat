@echo off
REM ============================================================================
REM GridBot Windows WebUI Startup Script
REM ============================================================================
REM 
REM Starts the WebUI backend on Windows
REM 
REM Usage:
REM   start_webui.bat
REM
REM ============================================================================

setlocal

set "PROJECT_DIR=D:\Projects\WorkingBot"
set "PYTHON=python"
set "CYAN=[96m"
set "GREEN=[92m"
set "RED=[91m"
set "NC=[0m"

echo %CYAN%========================================%NC%
echo %CYAN%   GridBot WebUI Startup%NC%
echo %CYAN%========================================%NC%
echo.

cd /d "%PROJECT_DIR%" || (
    echo %RED%Error: Project directory not found%NC%
    pause
    exit /b 1
)

REM Set PYTHONPATH
set "PYTHONPATH=%PROJECT_DIR%"

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Start WebUI backend
echo Starting WebUI backend on port 5555...
echo.

%PYTHON% webui\backend\app.py

pause

endlocal
