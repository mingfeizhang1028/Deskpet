@echo off
setlocal
cd /d "%~dp0"

set "YAYAN_PYTHONW="
if exist ".venv\Scripts\pythonw.exe" set "YAYAN_PYTHONW=%CD%\.venv\Scripts\pythonw.exe"
if not defined YAYAN_PYTHONW where pythonw.exe >nul 2>nul && set "YAYAN_PYTHONW=pythonw.exe"

if not defined YAYAN_PYTHONW (
  echo pythonw.exe was not found. Yayan cannot stop safely.
  pause
  exit /b 1
)

"%YAYAN_PYTHONW%" "%~dp0desktop\main.pyw" --quit
if errorlevel 1 (
  echo.
  echo Yayan could not stop safely.
  pause
)
endlocal
