param(
    [switch]$ForceDownload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& (Join-Path $PSScriptRoot "setup_and_run.ps1") -InstallOnly

$Project1 = Join-Path $RepoRoot "projects\credit-risk-pd-model"
$Project3 = Join-Path $RepoRoot "projects\model-validation-framework"
$RawFile = Join-Path $Project1 "data\raw\accepted_2007_to_2018Q4.csv.gz"
$PreparedFile = Join-Path $Project1 "data\processed\lendingclub_pd.csv"
$AuditFile = Join-Path $Project1 "data\processed\lendingclub_ingestion_audit.csv"
$VintageResolutionFile = Join-Path $Project1 "data\processed\lendingclub_vintage_resolution.csv"
$PublicRun = Join-Path $Project1 "data\processed\public_run"
$PublicReports = Join-Path $Project1 "reports\public_lendingclub"
$PublicValidation = Join-Path $PublicRun "validation"
$PublishedValidation = Join-Path $Project3 "reports\public_lendingclub"

$DownloadArguments = @(
    (Join-Path $Project1 "scripts\download_lendingclub_data.py"),
    "--output-dir",
    (Join-Path $Project1 "data\raw")
)
if ($ForceDownload) {
    $DownloadArguments += "--force"
}
& $VenvPython @DownloadArguments

& $VenvPython (Join-Path $Project1 "scripts\prepare_lendingclub_data.py") `
    --input $RawFile `
    --output $PreparedFile `
    --audit $AuditFile `
    --vintage-resolution $VintageResolutionFile `
    --chunk-size 100000

& $VenvPython (Join-Path $Project1 "scripts\run_pipeline.py") `
    --input $PreparedFile `
    --oot-cutoff 2017-01-01 `
    --reports (Join-Path $PublicRun "reports") `
    --models (Join-Path $PublicRun "models")

& $VenvPython (Join-Path $Project1 "scripts\publish_public_run.py") `
    --source-reports (Join-Path $PublicRun "reports") `
    --ingestion-audit $AuditFile `
    --vintage-resolution $VintageResolutionFile `
    --raw-input $RawFile `
    --output-dir $PublicReports

& $VenvPython (Join-Path $Project3 "scripts\run_validation.py") `
    --prediction-path (Join-Path $PublicRun "reports\oot_predictions.csv") `
    --output-dir $PublicValidation `
    --data-context public_lendingclub

& $VenvPython (Join-Path $Project3 "scripts\publish_public_validation.py") `
    --source-reports $PublicValidation `
    --project1-lineage (Join-Path $PublicReports "data_lineage.json") `
    --output-dir $PublishedValidation

& $VenvPython (Join-Path $RepoRoot "scripts\build_showcase.py")
