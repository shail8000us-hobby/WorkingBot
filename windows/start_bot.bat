@echo off
REM ============================================================================
REM GridBot Windows Startup Script
REM ============================================================================
REM 
REM Starts the GridBot trading system on Windows
REM 
REM Usage:
REM   start_bot.bat [mode]
REM   start_bot.bat live     (live trading)
REM   start_bot.bat demo     (demo mode)
REM
REM ============================================================================

setlocal enabledelayedexpansion

REM Colors for output (Windows 10+)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "NC=[0m"

REM Configuration
set "PROJECT_DIR=D:\Projects\WorkingBot"
set "PYTHON=python"
set "TRADING_MODE=%1"

if "%TRADING_MODE%"=="" set "TRADING_MODE=demo"

echo %CYAN%========================================%NC%
echo %CYAN%   GridBot Windows Startup%NC%
echo %CYAN%========================================%NC%
echo.
echo Mode: %TRADING_MODE%
echo Project: %PROJECT_DIR%
echo.

REM Change to project directory
cd /d "%PROJECT_DIR%" || (
    echo %RED%Error: Project directory not found: %PROJECT_DIR%%NC%
    pause
    exit /b 1
)

REM Set PYTHONPATH
set "PYTHONPATH=%PROJECT_DIR%"
echo PYTHONPATH set to: %PYTHONPATH%
echo.

REM Check if Python is installed
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo %RED%Error: Python not found in PATH%NC%
    echo Please install Python 3.8+ or add it to PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo %CYAN%Activating virtual environment...%NC%
    call .venv\Scripts\activate.bat
    echo %GREEN%Virtual environment activated%NC%
    echo.
)

REM Check if grid_config.env exists
if not exist "grid_config.env" (
    echo %RED%Error: grid_config.env not found%NC%
    echo Please copy grid_config.env.example to grid_config.env
    pause
    exit /b 1
)

REM Check if API keys exist
if not exist "secrets\api_keys.env" (
    echo %YELLOW%Warning: secrets\api_keys.env not found%NC%
    echo Please create secrets\api_keys.env with your Delta Exchange API keys
    pause
)

REM Set trading mode
set "TRADING_MODE_ENV=%TRADING_MODE%"

REM Start the bot
echo %CYAN%Starting GridBot in %TRADING_MODE% mode...%NC%
echo.

%PYTHON% bot\run.py

REM Check exit code
if errorlevel 1 (
    echo.
    echo %RED%Bot exited with errors%NC%
    pause
    exit /b 1
) else (
    echo.
    echo %GREEN%Bot stopped normally%NC%
    pause
)

endlocal
