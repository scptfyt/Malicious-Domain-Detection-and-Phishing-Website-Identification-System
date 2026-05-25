$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $root "open_trainer.cmd"

if (-not (Test-Path $launcher)) {
    Write-Host "Cannot find open_trainer.cmd in $root" -ForegroundColor Red
    exit 1
}

$command = "cmd.exe /c `"`"$launcher`" `"%1`"`""

& reg.exe add "HKCU\Software\Classes\domaintrainer" /ve /d "URL:Domain Trainer Protocol" /f | Out-Null
& reg.exe add "HKCU\Software\Classes\domaintrainer" /v "URL Protocol" /d "" /f | Out-Null
& reg.exe add "HKCU\Software\Classes\domaintrainer\DefaultIcon" /ve /d "`"$launcher`",0" /f | Out-Null
& reg.exe add "HKCU\Software\Classes\domaintrainer\shell\open\command" /ve /d $command /f | Out-Null

Write-Host "domaintrainer:// protocol installed successfully." -ForegroundColor Green
Write-Host "You can now open domaintrainer://open from the web system."
Read-Host "Press Enter to exit"
