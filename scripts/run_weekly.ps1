param(
    [switch]$Corrected
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "MFPI virtual environment is missing. Follow README.md setup first."
}

Push-Location $projectRoot
try {
    & $python -m pytest -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw "MFPI tests failed; rankings were not calculated." }

    $rankingArguments = @("calculate_rankings.py", "--live")
    if ($Corrected) {
        $rankingArguments += "--corrected"
    }

    & $python @rankingArguments
    if ($LASTEXITCODE -ne 0) { throw "MFPI validation failed; data/current was not changed. Read the reported draft validation file." }

    Write-Host "MFPI weekly ranking completed successfully."
}
finally {
    Pop-Location
}
