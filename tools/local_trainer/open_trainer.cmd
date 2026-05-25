@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where python >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  if exist "D:\Python\python3.11.3\python.exe" set "PYTHON_CMD=D:\Python\python3.11.3\python.exe"
)

if not defined PYTHON_CMD (
  echo Python was not found. Please install Python 3.11+ or add Python to PATH.
  echo 未找到 Python。请安装 Python 3.11 以上版本，或将 Python 添加到 PATH。
  pause
  exit /b 1
)

%PYTHON_CMD% local_trainer.py
if errorlevel 1 pause
