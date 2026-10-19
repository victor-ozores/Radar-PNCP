# Executa o pipeline na sua máquina (Windows). Os dados ficam em .\data_local (fora do git).
# Uso:  .\scripts\run_local.ps1            (execução diária completa)
#       .\scripts\run_local.ps1 --dry-run  (só mostra a prévia do alerta)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = "1"

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m radar run --data-dir data_local --trigger local @args
exit $LASTEXITCODE
