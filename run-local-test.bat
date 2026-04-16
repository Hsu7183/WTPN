@echo off
setlocal

cd /d "%~dp0"

set "PY_CMD="

where py >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py"

if not defined PY_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo [ERROR] Python not found. Please install Python 3 first.
  pause
  exit /b 1
)

echo [1/2] Starting local server on http://localhost:8000/
start "" cmd /c "ping 127.0.0.1 -n 3 >nul && start http://localhost:8000/"

echo [2/2] Press Ctrl+C to stop the server.
%PY_CMD% local_server.py

endlocal
