$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $root "open_trainer.cmd"

if (-not (Test-Path $launcher)) {
    Write-Host "Cannot find open_trainer.cmd in $root" -ForegroundColor Red
    exit 1
}

$protocolRoot = "HKCU:\Software\Classes\domaintrainer"
New-Item -Path $protocolRoot -Force | Out-Null
New-ItemProperty -Path $protocolRoot -Name "(default)" -Value "URL:Domain Trainer Protocol" -Force | Out-Null
New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -Force | Out-Null
New-Item -Path "$protocolRoot\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$protocolRoot\shell\open\command" -Name "(default)" -Value "`"$launcher`" `"%1`""

Write-Host "domaintrainer:// protocol installed successfully." -ForegroundColor Green
Write-Host "You can now open domaintrainer://open from the web system."
Read-Host "Press Enter to exit"
