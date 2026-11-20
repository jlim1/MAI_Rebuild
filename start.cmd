@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (echo Run setup.cmd first. & exit /b 1)
if not exist "frontend\dist\index.html" (echo The browser app has not been built. Run setup.cmd first. & exit /b 1)
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C here to stop.
".venv\Scripts\python.exe" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
exit /b %errorlevel%
