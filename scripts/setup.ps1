# MeetingMind one-time setup (Windows PowerShell). Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment (.venv)..."
    python -m venv .venv
}
$py = Join-Path $root ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip

# Install the CPU build of PyTorch first unless torch is already importable (avoids a multi-GB CUDA download).
& $py -c "import torch" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyTorch (CPU build)..."
    & $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
}
& $py -m pip install -r backend\requirements-dev.txt
& $py -m spacy download en_core_web_sm

Write-Host "Installing frontend packages..."
Push-Location frontend
npm install
Pop-Location

Write-Host ""
Write-Host "Setup complete. Start the app with:"
Write-Host "  scripts\start-backend.ps1   (terminal 1)"
Write-Host "  scripts\start-frontend.ps1  (terminal 2)"
