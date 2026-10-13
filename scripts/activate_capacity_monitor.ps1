[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Confirm,
    [string]$NotificationChannel = 'projects/nanami-astro/notificationChannels/5039093415990627844',
    [long]$WarningBytes = 700000000,
    [long]$CriticalBytes = 850000000
)

$ErrorActionPreference = 'Stop'
$project = 'nanami-astro'
$region = 'asia-northeast1'
$jobName = 'nanami-capacity-monitor'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'production_deploy_guard.ps1')
if ($Confirm -cne 'ACTIVATE:nanami-capacity-monitor') { throw 'Explicit production-monitor activation approval is required.' }
if ($NotificationChannel -notmatch '^projects/nanami-astro/notificationChannels/\d+$') { throw 'Invalid notification channel.' }
if ($WarningBytes -le 0 -or $CriticalBytes -le $WarningBytes) { throw 'Invalid capacity thresholds.' }
$gitState = Assert-DeployableGitState -RepoRoot $repoRoot
$gcloud = Resolve-GcloudCommand
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python was not found.' }
& $python -B -m pytest tests/test_capacity_monitor.py -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw 'Capacity monitor tests failed.' }

function Invoke-Cloud([string[]]$Arguments) {
    & $gcloud @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Cloud operation failed: $($Arguments[0..1] -join ' ')" }
}

$service = Invoke-Cloud @('run','services','describe','nanami-products','--region',$region,'--project',$project,'--format=json') | ConvertFrom-Json
$active = @($service.status.traffic | Where-Object { $_.PSObject.Properties['percent'] -and $_.percent -gt 0 })
if ($active.Count -ne 1 -or $active[0].percent -ne 100) { throw 'Inspect production traffic before activating monitoring.' }
$revision = Invoke-Cloud @('run','revisions','describe',$active[0].revisionName,'--region',$region,'--project',$project,'--format=json') | ConvertFrom-Json
$databaseSources = @($revision.spec.containers[0].env | Where-Object { $_.name -eq 'DATABASE_URL' })
if ($databaseSources.Count -ne 1) { throw 'Expected one DATABASE_URL configuration source.' }
$source = $databaseSources[0]
if (-not $source.PSObject.Properties['valueFrom'] -or -not $source.valueFrom.secretKeyRef) { throw 'DATABASE_URL must be provided through Secret Manager.' }
$secret = $source.valueFrom.secretKeyRef
$policyDirectory = Join-Path $env:TEMP "nanami-capacity-$($gitState.ShortCommit)"
& $python -B (Join-Path $repoRoot 'ops\capacity\policies.py') --project $project --channel $NotificationChannel --warning-bytes $WarningBytes --critical-bytes $CriticalBytes --output $policyDirectory
if ($LASTEXITCODE -ne 0) { throw 'Policy configuration generation failed.' }

$accessToken = Invoke-Cloud @('auth','print-access-token')
$headers = @{ Authorization = "Bearer $accessToken" }
$channel = Invoke-RestMethod -Uri "https://monitoring.googleapis.com/v3/$NotificationChannel" -Headers $headers
if ($channel.type -ne 'email' -or ($channel.PSObject.Properties['enabled'] -and $channel.enabled -eq $false)) { throw 'Selected notification channel is not an enabled email channel.' }

Invoke-Cloud @('services','enable','cloudscheduler.googleapis.com','monitoring.googleapis.com','run.googleapis.com','--project',$project,'--quiet')
$probeAccount = "nanami-capacity-probe@$project.iam.gserviceaccount.com"
$schedulerAccount = "nanami-capacity-scheduler@$project.iam.gserviceaccount.com"
$accounts = @(Invoke-Cloud @('iam','service-accounts','list','--project',$project,'--format=value(email)'))
foreach ($id in @('nanami-capacity-probe','nanami-capacity-scheduler')) {
    if ($accounts -notcontains "$id@$project.iam.gserviceaccount.com") {
        Invoke-Cloud @('iam','service-accounts','create',$id,'--project',$project,'--quiet')
    }
}
Invoke-Cloud @('secrets','add-iam-policy-binding',$secret.name,'--project',$project,'--member',"serviceAccount:$probeAccount",'--role','roles/secretmanager.secretAccessor','--format=none','--quiet')
Invoke-Cloud @('projects','add-iam-policy-binding',$project,'--member',"serviceAccount:$probeAccount",'--role','roles/monitoring.metricWriter','--condition=None','--format=none','--quiet')
$image = "$region-docker.pkg.dev/$project/cloud-run-source-deploy/nanami-capacity:$($gitState.ShortCommit)"
Invoke-Cloud @('builds','submit',$repoRoot,'--region',$region,'--project',$project,'--config',(Join-Path $repoRoot 'ops\capacity\cloudbuild.yaml'),'--substitutions',"_IMAGE=$image",'--quiet')
# Independent batch job: no web-service deployment or production traffic change.
Invoke-Cloud @('run','jobs','deploy',$jobName,'--image',$image,'--region',$region,'--project',$project,'--service-account',$probeAccount,'--tasks=1','--max-retries=1','--task-timeout=60s','--memory=256Mi','--cpu=1','--set-env-vars',"GOOGLE_CLOUD_PROJECT=$project",'--set-secrets',('DATABASE_URL={0}:{1}' -f $secret.name,$secret.key),'--quiet')
Invoke-Cloud @('run','jobs','execute',$jobName,'--region',$region,'--project',$project,'--wait','--quiet')
Invoke-Cloud @('run','jobs','add-iam-policy-binding',$jobName,'--region',$region,'--project',$project,'--member',"serviceAccount:$schedulerAccount",'--role','roles/run.invoker','--format=none','--quiet')

$jobUrl = "https://run.googleapis.com/v2/projects/$project/locations/$region/jobs/${jobName}:run"
$existingScheduler = @(Invoke-Cloud @('scheduler','jobs','list','--location',$region,'--project',$project,'--format=value(name)'))
$mode = if ($existingScheduler | Where-Object { $_.EndsWith("/jobs/$jobName") }) { 'update' } else { 'create' }
Invoke-Cloud @('scheduler','jobs',$mode,'http',$jobName,'--location',$region,'--project',$project,'--schedule','0 3,9,15,21 * * *','--time-zone','Asia/Tokyo','--uri',$jobUrl,'--http-method','POST','--oauth-service-account-email',$schedulerAccount,'--oauth-token-scope','https://www.googleapis.com/auth/cloud-platform','--message-body','{}','--quiet')

$existingPolicies = Invoke-RestMethod -Uri "https://monitoring.googleapis.com/v3/projects/$project/alertPolicies?pageSize=1000" -Headers $headers
if ($existingPolicies.PSObject.Properties['nextPageToken'] -and $existingPolicies.nextPageToken) { throw 'Inspect paginated alert policies before activation; no policies overwritten.' }
$policyList = if ($existingPolicies.PSObject.Properties['alertPolicies']) { @($existingPolicies.alertPolicies) } else { @() }
foreach ($path in Get-ChildItem -LiteralPath $policyDirectory -Filter 'policy-*.json') {
    $policy = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
    $match = @($policyList | Where-Object { $_.displayName -eq $policy.displayName })
    if ($match.Count -gt 1) { throw "Duplicate capacity alert policies: $($policy.displayName)" }
    if ($match.Count -eq 1) { $policy | Add-Member -NotePropertyName name -NotePropertyValue $match[0].name }
    $body = [Text.Encoding]::UTF8.GetBytes(($policy | ConvertTo-Json -Depth 12))
    if ($match.Count -eq 1) {
        $uri = 'https://monitoring.googleapis.com/v3/' + $match[0].name
        Invoke-RestMethod -Method Patch -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body | Select-Object name,displayName
    } else {
        Invoke-RestMethod -Method Post -Uri "https://monitoring.googleapis.com/v3/projects/$project/alertPolicies" -Headers $headers -ContentType 'application/json' -Body $body | Select-Object name,displayName
    }
}
Remove-Variable accessToken,headers
Write-Host 'Capacity monitoring activated. Inspect the first metrics and the email destination. Customer rows and web-service traffic were not changed.'
