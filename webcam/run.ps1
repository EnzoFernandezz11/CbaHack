param(
    [string]$ServerHost = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$Reload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$webRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $webRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Falta webcam/.venv. Ejecute primero: .\webcam\setup.ps1'
}

$uvicornArguments = @(
    '-m', 'uvicorn',
    'backend.main:app',
    '--app-dir', $webRoot,
    '--host', $ServerHost,
    '--port', $Port,
    '--workers', '1',
    '--ws-per-message-deflate', 'false'
)
if ($Reload) {
    $uvicornArguments += '--reload'
}

Write-Host "Viewer local: http://localhost:$Port/viewer"
Write-Host "Cámara local: http://localhost:$Port/camera"
Write-Host 'Para un teléfono use HTTPS mediante .\webcam\start_tunnel.ps1'
& $venvPython @uvicornArguments
