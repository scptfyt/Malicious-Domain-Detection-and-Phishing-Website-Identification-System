@echo off
setlocal
cd /d "%~dp0"

set "LOG_DIR=%LOCALAPPDATA%\DomainTrainer"
if "%LOCALAPPDATA%"=="" set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\install_all.log"

echo ==== Domain Trainer Full Install %date% %time% ==== > "%LOG_FILE%"
echo Script directory: %cd% >> "%LOG_FILE%"

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Please install Python 3.11 or later first. >> "%LOG_FILE%"
  echo Python was not found. Please install Python 3.11 or later first.
  echo Log file: %LOG_FILE%
  pause
  exit /b 1
)

echo Installing Python dependencies...
echo Installing Python dependencies... >> "%LOG_FILE%"
python -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  echo Failed to upgrade pip. >> "%LOG_FILE%"
  echo Failed to upgrade pip. See log file: %LOG_FILE%
  pause
  exit /b 1
)

python -m pip install scikit-learn==1.7.2 joblib==1.5.3 >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  echo Failed to install dependencies. >> "%LOG_FILE%"
  echo Failed to install dependencies. See log file: %LOG_FILE%
  pause
  exit /b 1
)

echo Registering local protocol...
echo Registering local protocol... >> "%LOG_FILE%"
call "%~dp0install_protocol.cmd" --no-pause >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  echo Protocol registration failed. >> "%LOG_FILE%"
  echo Protocol registration failed. See log file: %LOG_FILE%
  pause
  exit /b 1
)

echo Local trainer installation completed.
echo Local trainer installation completed. >> "%LOG_FILE%"
echo You can now open the local trainer from the web system.
echo Log file: %LOG_FILE%
pause
