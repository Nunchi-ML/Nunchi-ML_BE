param(
    [Parameter(Mandatory=$true)][string]$Bundle,
    [int]$Port = 8766
)
$ErrorActionPreference = 'Stop'
$beRoot = Split-Path -Parent $PSScriptRoot
$bundlePath = (Resolve-Path -LiteralPath $Bundle).Path
Push-Location -LiteralPath $beRoot
try { python scripts/run_prototype.py --bundle $bundlePath --port $Port }
finally { Pop-Location }
