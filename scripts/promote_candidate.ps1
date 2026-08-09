[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Revision,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Confirm
)

$ErrorActionPreference = "Stop"
$service = "nanami-products"
$region = "asia-northeast1"
$project = "nanami-astro"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "production_deploy_guard.ps1")

$gitState = Assert-DeployableGitState -RepoRoot $repoRoot
$expectedConfirmation = "PROMOTE:$Revision"
if ($Confirm -cne $expectedConfirmation) {
    throw "Promotion stopped: pass -Confirm `"$expectedConfirmation`" after explicit production approval."
}

$candidateTag = "candidate-$($gitState.ShortCommit)"
$gcloud = Resolve-GcloudCommand
$describeArgs = @("run", "services", "describe", $service, "--region", $region, "--project", $project, "--format=json")
$serviceState = (& $gcloud @describeArgs | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) {
    throw "Promotion stopped: Cloud Run service state could not be read."
}

$candidate = @($serviceState.status.traffic | Where-Object {
    $_.PSObject.Properties["tag"] -and
    $_.PSObject.Properties["revisionName"] -and
    $_.tag -eq $candidateTag -and
    $_.revisionName -eq $Revision
}) | Select-Object -First 1
if (-not $candidate) {
    throw "Promotion stopped: revision '$Revision' is not the candidate '$candidateTag' for current pushed commit $($gitState.Commit)."
}

$trafficArgs = @(
    "run", "services", "update-traffic", $service,
    "--region", $region,
    "--project", $project,
    "--to-revisions", "$Revision=100",
    "--quiet"
)

Write-Host "Promoting verified candidate '$Revision' to 100% production traffic..."
& $gcloud @trafficArgs
if ($LASTEXITCODE -ne 0) {
    throw "Production traffic update failed. Inspect Cloud Run immediately."
}
Write-Host "Production traffic now points to $Revision."
