# Starts the React dev server on http://localhost:5173 (proxies /api to the backend).
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root "frontend")
npm run dev
