param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$beRoot = Split-Path -Parent $PSScriptRoot
$exportRoot = Join-Path (Split-Path -Parent $beRoot) 'AI/models/model2-pilot-v1'
$modelPath = (Resolve-Path -LiteralPath $exportRoot).Path
$wheelFiles = @(Get-ChildItem -LiteralPath $modelPath -Filter 'nunchi_glare-*-py3-none-any.whl')
if ($wheelFiles.Count -ne 1) { throw 'Build exactly one AI nunchi-glare wheel before starting BE.' }
$previousModel = $env:MODEL_DIR
$previousPythonPath = $env:PYTHONPATH
$previousOrigins = $env:ALLOWED_ORIGINS
try {
    $env:MODEL_DIR = $modelPath
    $env:PYTHONPATH = $wheelFiles[0].FullName + [IO.Path]::PathSeparator + $previousPythonPath
    if (-not $env:ALLOWED_ORIGINS) { $env:ALLOWED_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173' }
    Push-Location -LiteralPath $beRoot
    try { python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1 }
    finally { Pop-Location }
} finally {
    $env:MODEL_DIR = $previousModel
    $env:PYTHONPATH = $previousPythonPath
    $env:ALLOWED_ORIGINS = $previousOrigins
}
