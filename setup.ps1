$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $projectRoot "requirements.txt"
$installMarker = Join-Path $venvDir ".requirements-installed"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "Creating the project virtual environment..."
    & py -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$installRequired = -not (Test-Path -LiteralPath $installMarker)
if (-not $installRequired) {
    $installRequired = (Get-Item -LiteralPath $requirementsFile).LastWriteTimeUtc -gt (Get-Item -LiteralPath $installMarker).LastWriteTimeUtc
    if (-not $installRequired) {
        & $pythonExe -c "import flask, flask_mail, flask_sqlalchemy, sqlalchemy"
        $installRequired = $LASTEXITCODE -ne 0
    }
}

if ($installRequired) {
    Write-Host "Installing project dependencies into .venv..."
    $env:DISABLE_SQLALCHEMY_CEXT = "1"
    & $pythonExe -m pip install -r $requirementsFile --no-binary=sqlalchemy
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content -LiteralPath $installMarker -Value (Get-Date -Format o)
}

Write-Host "AgriTrust is ready. VS Code will run it with $pythonExe"

