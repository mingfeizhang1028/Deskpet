@echo off
setlocal
cd /d "%~dp0"

set "YAYAN_PYTHON="
set "YAYAN_PYTHONW="

if exist ".venv\Scripts\python.exe" set "YAYAN_PYTHON=%CD%\.venv\Scripts\python.exe"
if exist ".venv\Scripts\pythonw.exe" set "YAYAN_PYTHONW=%CD%\.venv\Scripts\pythonw.exe"

if not defined YAYAN_PYTHON where python.exe >nul 2>nul && set "YAYAN_PYTHON=python.exe"
if not defined YAYAN_PYTHONW where pythonw.exe >nul 2>nul && set "YAYAN_PYTHONW=pythonw.exe"

if not defined YAYAN_PYTHON (
  echo Python was not found. Create .venv and install requirements.txt first.
  pause
  exit /b 1
)
if not defined YAYAN_PYTHONW (
  echo pythonw.exe was not found. Create .venv and install requirements.txt first.
  pause
  exit /b 1
)

if not exist "output\runtime" mkdir "output\runtime"
"%YAYAN_PYTHON%" -c "import PyQt5, openai, keyring" >nul 2>"output\runtime\start-preflight.err.log"
if errorlevel 1 (
  echo Yayan's Python environment is incomplete.
  echo Run: "%YAYAN_PYTHON%" -m pip install -r requirements.txt
  type "output\runtime\start-preflight.err.log"
  pause
  exit /b 1
)

>>"output\runtime\start-command.log" echo %date% %time% interpreter=%YAYAN_PYTHONW%
start "" "%YAYAN_PYTHONW%" "%~dp0desktop\main.pyw"
if errorlevel 1 (
  echo.
  echo Yayan could not start. See output\runtime\desktop-startup.log.
  pause
)
endlocal
