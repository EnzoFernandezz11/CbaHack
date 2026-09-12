param(
    [ValidateSet('Auto', 'Cpu', 'Cuda')]
    [string]$Backend = 'Auto',

    [ValidateSet('cu118', 'cu126', 'cu128')]
    [string]$CudaIndex = 'cu128',

    [string]$PythonCommand = 'python',

    [string]$VenvPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($VenvPath)) {
    $VenvPath = Join-Path $scriptDirectory '.venv'
}
$requirementsPath = Join-Path $scriptDirectory 'requirements-yolo26.txt'
$checkerPath = Join-Path $scriptDirectory 'scripts\check_training_environment.py'

Write-Host ('=' * 72)
Write-Host 'INSTALACIÓN DEL ENTORNO YOLO26'
Write-Host ('=' * 72)
Write-Host "Python base: $PythonCommand"
Write-Host "Entorno virtual: $VenvPath"

if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "No existe el archivo de dependencias: $requirementsPath"
}

& $PythonCommand --version
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo ejecutar Python mediante '$PythonCommand'."
}

if (-not (Test-Path -LiteralPath $VenvPath)) {
    Write-Host 'Creando entorno virtual...'
    & $PythonCommand -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Falló la creación del entorno virtual.'
    }
} else {
    Write-Host 'El entorno virtual ya existe; se actualizará en el lugar.'
}

$venvPython = Join-Path $VenvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "No se encontró el Python del entorno virtual: $venvPython"
}

Write-Host 'Actualizando pip, setuptools y wheel...'
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw 'Falló la actualización de pip.'
}

$effectiveBackend = $Backend
if ($Backend -eq 'Auto') {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $effectiveBackend = 'Cuda'
    } else {
        $effectiveBackend = 'Cpu'
    }
}
Write-Host "Backend seleccionado: $effectiveBackend"

if ($effectiveBackend -eq 'Cuda') {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw 'Se solicitó CUDA, pero nvidia-smi no está disponible.'
    }
    $torchIndexUrl = "https://download.pytorch.org/whl/$CudaIndex"
    Write-Host "Instalando PyTorch 2.7.0 con backend $CudaIndex..."
} else {
    $torchIndexUrl = 'https://download.pytorch.org/whl/cpu'
    Write-Host 'Instalando PyTorch 2.7.0 para CPU...'
}

& $venvPython -m pip install --upgrade torch==2.7.0 torchvision==0.22.0 --index-url $torchIndexUrl
if ($LASTEXITCODE -ne 0) {
    throw "Falló la instalación de PyTorch desde $torchIndexUrl"
}

Write-Host 'Instalando Ultralytics YOLO26 y dependencias del proyecto...'
& $venvPython -m pip install --upgrade --requirement $requirementsPath
if ($LASTEXITCODE -ne 0) {
    throw 'Falló la instalación de requirements-yolo26.txt.'
}

Write-Host 'Verificando el entorno instalado...'
& $venvPython $checkerPath
if ($LASTEXITCODE -ne 0) {
    throw 'El verificador detectó un entorno incompleto.'
}

Write-Host ('=' * 72)
Write-Host 'Instalación completada.'
Write-Host "Ejecute: $venvPython $scriptDirectory\scripts\train_yolo26.py"
Write-Host ('=' * 72)
