@echo off
:: ============================================================
:: CTI Analysis Dashboard — Launcher
:: ============================================================
setlocal EnableDelayedExpansion

set "PORT=8080"
set "AUTO_OPEN=1"
set "DASHBOARD_DIR=%~dp0"

:: Parse arguments
for %%a in (%*) do (
    if "%%a"=="--no-open" set "AUTO_OPEN=0"
    set "IS_NUM="
    for /f "delims=0123456789" %%b in ("%%a") do set "IS_NUM=%%b"
    if not defined IS_NUM set "PORT=%%a"
)

cls
echo.
echo   CTI Analysis Dashboard
echo   ======================
echo.

:: ============================================================
:: Kill any process already holding the port (reliable method)
:: ============================================================
echo   Checking port %PORT%...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr LISTENING') do (
    if NOT "%%p"=="0" (
        echo   Releasing port %PORT% from PID %%p...
        taskkill /F /PID %%p >nul 2>&1
    )
)

:: If still in use, try next port
netstat -ano 2>nul | findstr ":%PORT% " | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set /a PORT=%PORT%+1
    echo   Port busy, trying port !PORT!...
)

echo   Using port %PORT%
echo.

:: ============================================================
:: Find Python
:: ============================================================
set "PYTHON_CMD="

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=py -3"
        goto :launch
    )
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=python"
        goto :launch
    )
)

where python3 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python3"
    goto :launch
)

:: No Python — try Node
where npx >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   Using Node.js...
    if "%AUTO_OPEN%"=="1" (
        timeout /t 2 /nobreak >nul
        start "" "http://localhost:%PORT%"
    )
    cd /d "%DASHBOARD_DIR%"
    npx -y serve -l %PORT% -s .
    goto :eof
)

echo   [ERROR] Python not found. Please install Python from python.org
echo.
pause
goto :eof

:: ============================================================
:: Launch
:: ============================================================
:launch
cd /d "%DASHBOARD_DIR%"

if exist "run.py" (
    set "ARGS=!PORT!"
    if "%AUTO_OPEN%"=="0" set "ARGS=!ARGS! --no-open"
    %PYTHON_CMD% run.py !ARGS!
) else (
    echo   Starting on http://localhost:%PORT%
    echo   Press Ctrl+C to stop.
    echo.
    if "%AUTO_OPEN%"=="1" (
        timeout /t 1 /nobreak >nul
        start "" "http://localhost:%PORT%"
    )
    %PYTHON_CMD% -m http.server %PORT%
)

goto :eof
