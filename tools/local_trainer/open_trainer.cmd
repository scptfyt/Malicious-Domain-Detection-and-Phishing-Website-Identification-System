@echo off
setlocal
cd /d "%~dp0"

set "LOG_FILE=%~dp0trainer_launch.log"
echo ==== Domain Trainer Launch %date% %time% ==== > "%LOG_FILE%"
echo Working directory: %cd% >> "%LOG_FILE%"

set "PYTHON_CMD="
where python >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  if exist "D:\Python\python3.11.3\python.exe" set "PYTHON_CMD="D:\Python\python3.11.3\python.exe""
)

if not defined PYTHON_CMD (
  if exist "D:\Python\python.exe" set "PYTHON_CMD="D:\Python\python.exe""
)

if not defined PYTHON_CMD (
  echo Python was not found. Please install Python 3.11+ or add Python to PATH.
  echo Python was not found. >> "%LOG_FILE%"
  pause
  exit /b 1
)

echo Python command: %PYTHON_CMD% >> "%LOG_FILE%"
%PYTHON_CMD% local_trainer.py >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%errorlevel%"
echo Exit code: %EXIT_CODE% >> "%LOG_FILE%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Local trainer failed to start. See trainer_launch.log in this folder.
  echo 本地训练助手启动失败，请查看当前目录下的 trainer_launch.log。
  pause
  exit /b %EXIT_CODE%
)
