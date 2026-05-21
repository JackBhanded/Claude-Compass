@echo off
REM ===========================================================================
REM  Claude Compass - test runner (just double-click me)
REM
REM  Proves the safe-write engine (and the rest) before Compass ever edits your
REM  real memory files. Green = trustworthy. If anything's red, nothing ships.
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo   Checking Compass's bearings... (running the safety tests)
echo.

python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo   First run - fetching the test tool ^(pytest^). One moment...
    python -m pip install --quiet pytest
)

python -m pytest
set RESULT=%errorlevel%

echo.
if "%RESULT%"=="0" (
    echo   All good - every bearing holds. Compass points true. :^)
) else (
    echo   Some tests didn't pass. Nothing of yours was touched - these run in a
    echo   scratch folder only. Send me the output above and I'll fix it.
)
echo.
pause
endlocal
