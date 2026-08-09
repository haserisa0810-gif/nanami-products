Set-StrictMode -Version Latest

function Assert-DeployableGitState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $insideWorkTree = & git -C $RepoRoot rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0 -or $insideWorkTree.Trim() -ne "true") {
        throw "Repository not found: $RepoRoot"
    }

    $dirty = @(& git -C $RepoRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the Git worktree."
    }
    if ($dirty.Count -gt 0) {
        $details = $dirty -join [Environment]::NewLine
        throw "Deployment stopped: the worktree has uncommitted changes (including untracked files).`n$details"
    }

    $branch = (& git -C $RepoRoot symbolic-ref --quiet --short HEAD 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
        throw "Deployment stopped: HEAD is detached."
    }

    $upstream = (& git -C $RepoRoot rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($upstream)) {
        throw "Deployment stopped: branch '$branch' has no upstream. Push it first."
    }

    $counts = (& git -C $RepoRoot rev-list --left-right --count "HEAD...$upstream" 2>$null).Trim() -split "\s+"
    if ($LASTEXITCODE -ne 0 -or $counts.Count -ne 2) {
        throw "Deployment stopped: could not compare HEAD with '$upstream'."
    }
    if ([int]$counts[0] -ne 0 -or [int]$counts[1] -ne 0) {
        throw "Deployment stopped: HEAD and '$upstream' differ (ahead=$($counts[0]), behind=$($counts[1])). Commit, pull/rebase as needed, and push first."
    }

    $commit = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $shortCommit = (& git -C $RepoRoot rev-parse --short=10 HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Deployment stopped: could not resolve HEAD."
    }

    [pscustomobject]@{
        Branch      = $branch
        Upstream    = $upstream
        Commit      = $commit
        ShortCommit = $shortCommit
    }
}

function Resolve-GcloudCommand {
    $command = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
    if (-not $command) {
        $command = Get-Command gcloud -ErrorAction SilentlyContinue
    }
    if (-not $command) {
        throw "gcloud was not found on PATH."
    }
    $command.Source
}
