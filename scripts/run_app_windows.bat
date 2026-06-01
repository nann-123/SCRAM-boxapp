@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

if defined SCRAM_PYTHON (
  "%SCRAM_PYTHON%" scripts\launch_app.py
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\launch_app.py
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py scripts\launch_app.py
  exit /b %ERRORLEVEL%
)

echo No Python interpreter was found. Install Python 3.10+ or set SCRAM_PYTHON.
exit /b 1
