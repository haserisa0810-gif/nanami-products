$ErrorActionPreference = "Stop"
$service = "nanami-products"
$region = "asia-northeast1"
$project = "nanami-astro"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "production_deploy_guard.ps1")

$gitState = Assert-DeployableGitState -RepoRoot $repoRoot
$candidateTag = "candidate-$($gitState.ShortCommit)"
$gcloud = Resolve-GcloudCommand
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Deployment stopped: project Python was not found at $python"
}

Write-Host "Running the full test suite for commit $($gitState.Commit)..."
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
    throw "Deployment stopped: tests failed."
}

$deployArgs = @(
    "run", "deploy", $service,
    "--source", $repoRoot,
    "--region", $region,
    "--project", $project,
    "--allow-unauthenticated",
    "--no-traffic",
    "--tag", $candidateTag,
    "--quiet"
)

Write-Host "Deploying candidate '$candidateTag' with 0% production traffic..."
& $gcloud @deployArgs
if ($LASTEXITCODE -ne 0) {
    throw "Candidate deployment failed."
}

$describeArgs = @("run", "services", "describe", $service, "--region", $region, "--project", $project, "--format=json")
$serviceState = (& $gcloud @describeArgs | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) {
    throw "Candidate deployed, but its URL could not be read. Inspect Cloud Run before continuing."
}
$candidate = @($serviceState.status.traffic | Where-Object {
    $_.PSObject.Properties["tag"] -and $_.tag -eq $candidateTag
}) | Select-Object -First 1
if (-not $candidate -or [string]::IsNullOrWhiteSpace($candidate.revisionName)) {
    throw "Candidate deployed, but tag '$candidateTag' was not found. Do not promote until inspected."
}

Write-Host "Candidate ready (production traffic unchanged)."
Write-Host "Revision: $($candidate.revisionName)"
Write-Host "URL: $($candidate.url)"
Write-Host "After smoke testing, request separate approval before promotion."
