@echo off
rem Personal ACG Map launcher (Windows)
rem Starts the local-only web server and opens ACG directly.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\server.ps1" -OpenPath "/acg/"
if errorlevel 1 (
  echo.
  echo Server exited with an error. See message above.
  pause
)
