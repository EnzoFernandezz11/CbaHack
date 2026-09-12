param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [switch]$ConDemo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pptsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent $pptsRoot

if ($ConDemo) {
    $runScript = Join-Path $repositoryRoot 'web\run.ps1'
    if (-not (Test-Path -LiteralPath $runScript)) {
        throw "No se encontro $runScript"
    }
    Write-Host 'Arrancando el backend de la demo en http://localhost:8000 ...'
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $runScript `
        -WorkingDirectory $repositoryRoot | Out-Null
    Start-Sleep -Seconds 3
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw 'No se encontro python en el PATH.'
}

$url = "http://localhost:$Port/present.html"
Write-Host ''
Write-Host "Presentacion: $url"
Write-Host 'Flechas o PageUp/PageDown para cambiar de diapositiva. F = pantalla completa. H = ayuda.'
Write-Host 'Ctrl+C para cortar el servidor.'
Write-Host ''

Start-Process $url
& $pythonCommand.Source -m http.server $Port --directory $pptsRoot --bind 127.0.0.1
