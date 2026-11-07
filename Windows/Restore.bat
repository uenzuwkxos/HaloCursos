@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Cursors.ps1" -Restore
echo.
pause
