@echo off
rem Birth Chart Museum - Personal Edition (Windows launcher)
rem Starts a local-only web server and opens the museum in your browser.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\server.ps1"
if errorlevel 1 (
  echo.
  echo Server exited with an error. See message above.
  pause
)
