@echo off
REM ============================================================================
REM GridBot Windows Stop Script
REM ============================================================================
REM 
REM Gracefully stops the GridBot trading system on Windows
REM 
REM Usage:
REM   stop_bot.bat
REM
REM ============================================================================

setlocal

set "GREEN=[92m"
set "RED=[91m"
set "CYAN=[96m"
set "NC=[0m"

echo %CYAN%========================================%NC%
echo %CYAN%   Stopping GridBot%NC%
echo %CYAN%========================================%NC%
echo.

REM Find and kill bot process
for /f "tokens=2" %%i in ('tasklist ^| findstr /i "python.*bot\\run.py"') do (
    echo Sending SIGTERM to PID: %%i
    taskkill /PID %%i /T
    echo %GREEN%Bot process stopped (PID: %%i^)%NC%
    goto :done
)

echo %YELLOW%No bot process found%NC%
echo.

:done
echo.
pause

endlocal
