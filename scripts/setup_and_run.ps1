param(
    [switch]$WithTests,
    [switch]$VerifyCommitted,
    [switch]$InstallOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $ProjectBootstrap = Join-Path $RepoRoot "projects\credit-risk-pd-model\.venv\Scripts\python.exe"
    if ($env:PYTHON -and (Test-Path -LiteralPath $env:PYTHON)) {
        & $env:PYTHON -m venv (Join-Path $RepoRoot ".venv")
    }
    elseif (Test-Path -LiteralPath $ProjectBootstrap) {
        & $ProjectBootstrap -m venv (Join-Path $RepoRoot ".venv")
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $RepoRoot ".venv")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $RepoRoot ".venv")
    }
    else {
        throw "Python 3.11+ was not found. Install Python or set the PYTHON environment variable."
    }
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "The root virtual environment could not be created. Install Python 3.11+ or set PYTHON."
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")

if ($InstallOnly) {
    return
}

$RunnerArguments = @(
    (Join-Path $RepoRoot "scripts\run_portfolio.py"),
    "--output-root",
    (Join-Path $RepoRoot ".artifacts\portfolio-run")
)
if ($WithTests) {
    $RunnerArguments += "--with-tests"
}
if ($VerifyCommitted) {
    $RunnerArguments += "--verify-committed"
}

& $VenvPython @RunnerArguments
