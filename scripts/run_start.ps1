# need "Install-Module VirtualDesktop"

Get-Desktop 0 | Switch-Desktop
$cnt=Get-DesktopCount
$cnt
if ( $cnt -eq 1 ) 
{
	"new"
	New-Desktop
}
$desk=Get-Desktop 1

# 주석 해제 필요
$desk | Move-Window (Get-ConsoleHandle)

$CommandLine=Get-WmiObject Win32_Process -Filter "name = 'cmd.exe'" | Select-Object CommandLine
# $CommandLine
# $CommandLine -Match "_srart_run.cmd"

Start-Process -PassThru -WorkingDirectory "Y:\ComfyU-auto-script-data-cleaning" "Y:\ComfyU-auto-script-data-cleaning\_calculate_sha256.cmd"
Start-Process -PassThru -WorkingDirectory "Y:\ComfyU-auto-script-data-cleaning" "Y:\ComfyU-auto-script-data-cleaning\_sync_char_yml.cmd"
Start-Process -PassThru -WorkingDirectory "Y:\ComfyU-auto-script-data-cleaning" "Y:\ComfyU-auto-script-data-cleaning\_sync_checkpoint_yml.cmd"

$parentPath = Split-Path -Parent $PSScriptRoot

if ( -Not ( $CommandLine -Match "_run_nvidia_gpu.cmd" ) ){
	$run=Start-Process -PassThru -WorkingDirectory $parentPath "$parentPath\_run_nvidia_gpu.cmd"
	Start-Sleep -Seconds 1
	$desk | Move-Window ($run).MainWindowHandle
}

if ( -Not ( $CommandLine -Match "_run_script.cmd" ) ){
	$run=Start-Process -PassThru -WorkingDirectory $parentPath "$parentPath\_run_script.cmd"
	Start-Sleep -Seconds 1
	$desk | Move-Window ($run).MainWindowHandle
}


if ( -Not ( $CommandLine -Match "_run_my.cmd" ) ){
	$run=Start-Process -PassThru -WorkingDirectory $parentPath "$parentPath\_run_my.cmd"
	Start-Sleep -Seconds 1
	$desk | Move-Window ($run).MainWindowHandle
}

