@echo off
setlocal
cd /d "%~dp0"

rem Locate a system Python 3 (needed once to create the virtual environment).
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [Yayan] Python 3.10+ not found.
  echo [Yayan] Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

rem One-click bootstrap: create venv, install deps, fetch the renderer if missing,
rem then hand over to the reliable launcher.
%PY% "scripts\bootstrap_yayan.py"
set "YAYAN_EXIT=%ERRORLEVEL%"
if not "%YAYAN_EXIT%"=="0" (
  echo.
  echo [Yayan] Startup failed. The launcher kept the exact reason above.
  echo [Yayan] Detailed logs: output\runtime\bootstrap.log, start-command.log and desktop-startup.log
  pause
)
endlocal & exit /b %YAYAN_EXIT%
