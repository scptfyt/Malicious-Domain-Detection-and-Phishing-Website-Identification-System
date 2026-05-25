@echo off
setlocal
cd /d "%~dp0"

set "LOG_DIR=%LOCALAPPDATA%\DomainTrainer"
if "%LOCALAPPDATA%"=="" set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\trainer_cmd.log"

echo ==== Domain Trainer CMD Launch %date% %time% ==== > "%LOG_FILE%"
echo Script directory: %cd% >> "%LOG_FILE%"

set "PYTHON_EXE="
where python >nul 2>nul
if %errorlevel%==0 set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
  where py >nul 2>nul
  if %errorlevel%==0 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
  if exist "D:\Python\python3.11.3\python.exe" set "PYTHON_EXE=D:\Python\python3.11.3\python.exe"
)

if not defined PYTHON_EXE (
  if exist "D:\Python\python.exe" set "PYTHON_EXE=D:\Python\python.exe"
)

if not defined PYTHON_EXE (
  echo Python was not found. >> "%LOG_FILE%"
  echo Python was not found. Please install Python 3.11+ or add Python to PATH.
  echo Log file: %LOG_FILE%
  pause
  exit /b 1
)

echo Python executable: %PYTHON_EXE% >> "%LOG_FILE%"
if "%PYTHON_EXE%"=="py" (
  py -3 launch_trainer.py
) else (
  "%PYTHON_EXE%" launch_trainer.py
)

set "EXIT_CODE=%errorlevel%"
echo CMD exit code: %EXIT_CODE% >> "%LOG_FILE%"

if not "%EXIT_CODE%"=="0" (
  echo Local trainer failed to start.
  echo Log file: %LOG_FILE%
  pause
  exit /b %EXIT_CODE%
)
