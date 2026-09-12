param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
$cloudflaredExecutable = if ($cloudflaredCommand) { $cloudflaredCommand.Source } else { $null }
if (-not $cloudflaredExecutable) {
    $knownLocations = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\cloudflared.exe'),
        'C:\Program Files\cloudflared\cloudflared.exe',
        'C:\Program Files (x86)\cloudflared\cloudflared.exe'
    )
    $cloudflaredExecutable = $knownLocations |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}
if (-not $cloudflaredExecutable) {
    throw 'No se encontró cloudflared. Instálelo con: winget install --id Cloudflare.cloudflared'
}

Write-Host "Creando túnel HTTPS hacia http://localhost:$Port ..."
Write-Host 'Abra la URL /camera en el teléfono y /viewer en la computadora.'
& $cloudflaredExecutable tunnel --url "http://localhost:$Port"
