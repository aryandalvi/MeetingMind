# Starts the FastAPI backend on http://127.0.0.1:8000 (API docs at /docs).
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "No .venv found. Run scripts\setup.ps1 first."; exit 1 }
Set-Location (Join-Path $root "backend")
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
