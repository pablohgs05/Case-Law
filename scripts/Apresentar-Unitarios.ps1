param([string]$Node = 'node')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$root = Split-Path $PSScriptRoot -Parent
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$logs = Join-Path $root "documentation/testing/evidence/unitarios/$stamp"
New-Item -ItemType Directory -Path $logs | Out-Null
$python = Join-Path $root 'backend/.venv/Scripts/python.exe'
$useVenv = Test-Path -LiteralPath $python
if (-not $useVenv) { Get-Command uv -ErrorAction Stop | Out-Null }
Get-Command $Node -ErrorAction Stop | Out-Null
$sha = git -C $root rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível identificar o commit.' }
@("Data local: $(Get-Date -Format o)", "Commit base: $sha", 'Alterações locais (se houver):', (git -C $root status --porcelain)) | Set-Content (Join-Path $logs 'contexto.txt')
Push-Location (Join-Path $root 'backend')
try {
    if ($useVenv) { & $python -m pytest tests/test_scrum_ementa_bdd.py -m unit -v 2>&1 | Tee-Object (Join-Path $logs 'backend.txt') }
    else { & uv run pytest tests/test_scrum_ementa_bdd.py -m unit -v 2>&1 | Tee-Object (Join-Path $logs 'backend.txt') }
    if ($LASTEXITCODE -ne 0) { throw 'Teste da classe falhou; confira backend.txt.' }
} finally { Pop-Location }
Push-Location (Join-Path $root 'frontend')
try {
    & $Node node_modules/vitest/vitest.mjs run src/tests/scrumCardBdd.test.tsx 2>&1 | Tee-Object (Join-Path $logs 'frontend.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Teste do componente falhou; confira frontend.txt.' }
} finally { Pop-Location }
Push-Location (Join-Path $root 'backend')
try {
    if ($useVenv) { & $python scripts/demo_test_cycle.py 2>&1 | Tee-Object (Join-Path $logs 'ciclo.txt') }
    else { & uv run python scripts/demo_test_cycle.py 2>&1 | Tee-Object (Join-Path $logs 'ciclo.txt') }
    if ($LASTEXITCODE -ne 0) { throw 'Ensaio não comprovou falha/correção.' }
} finally { Pop-Location }
Write-Output "Demonstração técnica concluída. Logs: $logs. Revisão humana continua separada."
