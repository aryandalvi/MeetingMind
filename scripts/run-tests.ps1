# Runs backend tests (pytest), frontend tests (vitest), the TypeScript check and the evaluation.
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
Set-Location (Join-Path $root "backend")
& $py -m pytest            # add -m "not slow" to skip the test that loads the 1.2 GB summarizer
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py -m evaluation.evaluate
Set-Location (Join-Path $root "frontend")
npm test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npx tsc -b
