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

echo [1/3] Refreshing news data...
%PY_CMD% scrape_news.py
if not %errorlevel%==0 (
  if exist "docs\data\news.json" (
    echo [WARN] Failed to refresh live news. Using existing docs\data\news.json instead.
  ) else (
    echo [ERROR] Could not generate docs\data\news.json.
    pause
    exit /b 1
  )
)

echo [2/3] Starting local server on http://localhost:8000/docs/
start "" cmd /c "ping 127.0.0.1 -n 3 >nul && start http://localhost:8000/docs/"

echo [3/3] Press Ctrl+C to stop the server.
%PY_CMD% -m http.server 8000

endlocal
