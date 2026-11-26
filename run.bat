@echo off
setlocal
title ResQ Command Launcher

rem Run this file from any location. All paths are resolved relative to this file.
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo.
echo  ==========================================
echo          ResQ Command - Windows Launcher
echo  ==========================================
echo.

rem Check that this is the repository root.
if not exist "%BACKEND_DIR%\requirements.txt" goto missing_files
if not exist "%FRONTEND_DIR%\package.json" goto missing_files
if not exist "%FRONTEND_DIR%\package-lock.json" goto missing_lockfile

rem Find a supported Python 3.10+ installation.
set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if errorlevel 1 goto missing_python
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 goto old_python
    set "PYTHON_CMD=python"
)

rem Check Node.js and npm.
where node >nul 2>&1
if errorlevel 1 goto missing_node
where npm >nul 2>&1
if errorlevel 1 goto missing_npm

node -e "const v=process.versions.node.split('.').map(Number); process.exit(v[0] > 18 || (v[0] === 18 && v[1] >= 18) ? 0 : 1)" >nul 2>&1
if errorlevel 1 goto old_node

echo [1/4] Preparing Python environment...
if not exist "%VENV_PYTHON%" (
    %PYTHON_CMD% -m venv "%BACKEND_DIR%\.venv"
    if errorlevel 1 goto setup_failed
)

echo Installing backend packages...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto setup_failed
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 goto setup_failed

echo.
echo [2/4] Installing frontend packages...
pushd "%FRONTEND_DIR%"
call npm ci
if errorlevel 1 (
    popd
    goto setup_failed
)
popd

echo.
echo [3/4] Preparing local configuration...
if not exist "%FRONTEND_DIR%\.env" if exist "%FRONTEND_DIR%\.env.example" (
    copy /Y "%FRONTEND_DIR%\.env.example" "%FRONTEND_DIR%\.env" >nul
    if errorlevel 1 goto setup_failed
)

echo.
echo [4/4] Starting ResQ Command...
echo Backend:  http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo Dashboard: http://127.0.0.1:5173
echo.

rem Keep each server in its own window so closing one does not kill the other.
start "ResQ Command Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && ""%VENV_PYTHON%"" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
start "ResQ Command Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && call npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

echo Waiting for the dashboard to become available...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(45); do { try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2; if ($response.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:5173'; exit 0 } } catch {}; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo.
    echo The servers were started, but the dashboard did not respond within 45 seconds.
    echo Check the Backend and Frontend windows for errors, then open:
    echo http://127.0.0.1:5173
) else (
    echo Dashboard opened in your default browser.
)

echo.
echo ResQ Command is running.
echo Close both ResQ Command server windows to stop the application.
echo.
pause
exit /b 0

:missing_files
echo ERROR: backend or frontend files are missing.
echo Run this file from the root of the ResQ Command repository.
goto failed

:missing_lockfile
echo ERROR: frontend/package-lock.json is missing.
goto failed

:missing_python
echo ERROR: Python 3.10 or newer was not found.
echo Install Python 3.10+ and enable "Add Python to PATH".
goto failed

:old_python
echo ERROR: Python 3.10 or newer is required.
goto failed

:missing_node
echo ERROR: Node.js was not found.
echo Install Node.js 18.18 or newer, then restart this launcher.
goto failed

:missing_npm
echo ERROR: npm was not found. Install Node.js with npm included.
goto failed

:old_node
echo ERROR: Node.js 18.18 or newer is required.
goto failed

:setup_failed
echo.
echo ERROR: Setup failed. Read the message above, fix the issue, and run run.bat again.
goto failed

:failed
echo.
pause
exit /b 1
