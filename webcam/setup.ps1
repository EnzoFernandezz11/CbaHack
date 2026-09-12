param(
    [string]$PythonCommand = 'python',
    [string]$VenvPath = '',
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$webRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($VenvPath)) {
    $VenvPath = Join-Path $webRoot '.venv'
}
$requirements = Join-Path $webRoot 'requirements.txt'
$tests = Join-Path $webRoot 'tests'
$pytestConfig = Join-Path $webRoot 'pytest.ini'

Write-Host ('=' * 72)
Write-Host 'INSTALACIÓN DEL RELAY DE CÁMARA'
Write-Host ('=' * 72)
& $PythonCommand --version
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo ejecutar Python mediante '$PythonCommand'."
}

if (-not (Test-Path -LiteralPath $VenvPath)) {
    Write-Host "Creando entorno virtual en $VenvPath..."
    & $PythonCommand -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Falló la creación del entorno virtual.'
    }
} else {
    Write-Host 'El entorno virtual ya existe; se actualizará.'
}

$venvPython = Join-Path $VenvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "No existe el intérprete del entorno: $venvPython"
}

Write-Host 'Instalando dependencias...'
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install --upgrade --requirement $requirements
if ($LASTEXITCODE -ne 0) {
    throw 'Falló la instalación de dependencias.'
}

if (-not $SkipTests) {
    Write-Host 'Ejecutando pruebas automáticas...'
    & $venvPython -m pytest -c $pytestConfig $tests -q
    if ($LASTEXITCODE -ne 0) {
        throw 'Las pruebas automáticas fallaron.'
    }
}

Write-Host ('=' * 72)
Write-Host 'Entorno listo.'
Write-Host 'Inicie el servidor con: .\webcam\run.ps1'
Write-Host ('=' * 72)
