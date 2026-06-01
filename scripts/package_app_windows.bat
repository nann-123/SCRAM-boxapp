@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package_app_windows.ps1" %*
exit /b %ERRORLEVEL%
