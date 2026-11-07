@echo off
rem Runs the installer without changing the system execution policy (this run only).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Cursors.ps1" %*
echo.
pause
