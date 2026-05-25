$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $root "install_protocol.cmd"
Start-Process -FilePath $installer -Wait
