@echo off
setlocal
cd /d "%~dp0" || exit /b 1
where python >nul 2>&1 || (echo Install Python 3.11+ and put python on PATH. & exit /b 1)
where npm.cmd >nul 2>&1 || (echo Install Node.js 22.12+ with npm. & exit /b 1)
if not exist ".venv\Scripts\python.exe" (python -m venv .venv || exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1
pushd frontend || exit /b 1
call npm.cmd ci --no-fund --no-audit || exit /b 1
call npm.cmd run build || exit /b 1
popd
echo Setup complete. Run start.cmd to open the workbench locally.
