@echo off
setlocal
cd /d "%~dp0"

set "LOG_DIR=%LOCALAPPDATA%\DomainTrainer"
if "%LOCALAPPDATA%"=="" set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\protocol_install.log"

echo ==== Domain Trainer Protocol Install %date% %time% ==== > "%LOG_FILE%"
echo Script directory: %cd% >> "%LOG_FILE%"

set "LAUNCHER=%~dp0open_trainer.cmd"
if not exist "%LAUNCHER%" (
  echo open_trainer.cmd was not found. >> "%LOG_FILE%"
  echo open_trainer.cmd was not found.
  echo Log file: %LOG_FILE%
  pause
  exit /b 1
)

reg add "HKCU\Software\Classes\domaintrainer" /ve /d "URL:Domain Trainer Protocol" /f >> "%LOG_FILE%" 2>&1
reg add "HKCU\Software\Classes\domaintrainer" /v "URL Protocol" /d "" /f >> "%LOG_FILE%" 2>&1
reg add "HKCU\Software\Classes\domaintrainer\DefaultIcon" /ve /d "\"%LAUNCHER%\",0" /f >> "%LOG_FILE%" 2>&1
reg add "HKCU\Software\Classes\domaintrainer\shell\open\command" /ve /d "cmd.exe /d /c \"\"%LAUNCHER%\" \"%%1\"\"" /f >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
  echo Protocol registration failed.
  echo Log file: %LOG_FILE%
  pause
  exit /b 1
)

echo Protocol registration completed.
echo You can now open domaintrainer://open from the web system.
echo Log file: %LOG_FILE%
pause
