[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("bind", "start", "finish", "status", "help")]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Message
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$ProjectRoot = (Get-Location).Path
$BindingFile = Join-Path $ProjectRoot ".github/project-binding.json"

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Arguments -join ' ')"
    }
}

function Normalize-Remote {
    param([string]$Url)
    return $Url.Trim().TrimEnd("/").ToLowerInvariant().Replace(".git", "")
}

function Assert-ProjectBinding {
    if (-not (Test-Path -LiteralPath $BindingFile)) {
        throw "Project is not bound. Run pr.bat bind once from the intended current project."
    }
    $root = (& git rev-parse --show-toplevel).Trim()
    $remote = (& git remote get-url origin).Trim()
    $binding = Get-Content -LiteralPath $BindingFile -Raw | ConvertFrom-Json
    $actualRoot = [IO.Path]::GetFullPath($root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $boundRoot = [IO.Path]::GetFullPath([string]$binding.project_root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    if (-not [String]::Equals($actualRoot, $boundRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Current Git root does not match the saved project binding."
    }
    if ((Normalize-Remote $remote) -ne (Normalize-Remote $binding.repository_url)) {
        throw "origin does not match the saved project binding."
    }
}

function Get-StatusText {
    return (& git status --porcelain=v1 | Out-String).TrimEnd()
}

function Assert-NoSensitivePaths {
    param([string]$StatusText)
    $blocked = $StatusText -split [Environment]::NewLine | Where-Object {
        $_ -match "(?i)(.env($|.)|.pem$|.key$|.sqlite3$|.db$|(^|/)(data/raw|data/labels|data/holdout|data/results)/)"
    }
    if ($blocked) {
        $blocked | ForEach-Object { Write-Host "Blocked: $_" -ForegroundColor Red }
        Invoke-Git -Arguments @("reset")
        throw "Review sensitive or runtime paths before staging."
    }
}

function Show-Help {
    @"
pr.bat bind
pr.bat start feature-name
pr.bat status
pr.bat finish "Commit and PR title"

Bind once. Later commands verify the saved project identity automatically.
"@
}

switch ($Command) {
    "help" { Show-Help }

    "bind" {
        $root = (& git rev-parse --show-toplevel).Trim()
        $remote = (& git remote get-url origin).Trim()
        if ([string]::IsNullOrWhiteSpace($remote)) { throw "No origin remote is configured." }
        $defaultBranch = (& gh repo view --json defaultBranchRef --jq ".defaultBranchRef.name").Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($defaultBranch)) { throw "Could not read GitHub default branch." }
        Write-Host "Project: $root"
        Write-Host "Origin:  $remote"
        Write-Host "Branch:  $defaultBranch"
        if ((Read-Host "Type YES to bind this project") -cne "YES") { throw "Binding cancelled." }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BindingFile) | Out-Null
        [ordered]@{ project_root = $root; repository_url = $remote; default_branch = $defaultBranch } |
            ConvertTo-Json | Set-Content -LiteralPath $BindingFile -Encoding utf8
        Write-Host "Project binding saved." -ForegroundColor Green
    }

    "status" {
        Assert-ProjectBinding
        Invoke-Git -Arguments @("status", "-sb")
        Invoke-Git -Arguments @("remote", "-v")
        Write-Host "Project binding verified." -ForegroundColor Green
    }

    "start" {
        Assert-ProjectBinding
        if ([string]::IsNullOrWhiteSpace($Message)) { throw "Usage: pr.bat start feature-name" }
        if (Get-StatusText) { throw "Working tree is not clean. Resolve it before starting a branch." }
        Invoke-Git -Arguments @("switch", "main")
        Invoke-Git -Arguments @("pull", "--ff-only", "origin", "main")
        $slug = ($Message.ToLowerInvariant() -replace "[^a-z0-9]+", "-").Trim("-")
        if ([string]::IsNullOrWhiteSpace($slug)) { throw "Feature name must contain letters or numbers." }
        Invoke-Git -Arguments @("switch", "-c", "agent/$slug")
        Write-Host "Created agent/$slug from origin/main." -ForegroundColor Green
    }

    "finish" {
        Assert-ProjectBinding
        if ([string]::IsNullOrWhiteSpace($Message)) { throw 'Usage: pr.bat finish "Commit and PR title"' }
        $branch = (& git branch --show-current).Trim()
        if ($branch -eq "main") { throw "Refusing to commit directly to main." }
        $status = Get-StatusText
        if (-not $status) { throw "There are no local changes to commit." }
        Write-Host $status
        if ((Read-Host "Type YES to stage these files and create the draft PR") -cne "YES") { throw "Cancelled." }
        Assert-NoSensitivePaths $status
        Invoke-Git -Arguments @("add", "-A")
        Assert-NoSensitivePaths ((& git diff --cached --name-only | Out-String).TrimEnd())
        Invoke-Git -Arguments @("commit", "-m", $Message)
        Invoke-Git -Arguments @("push", "-u", "origin", $branch)
        & gh pr create --draft --base main --head $branch --title $Message --body "Review the complete diff and checks before merging."
        if ($LASTEXITCODE -ne 0) { throw "Push completed, but draft PR creation failed." }
        Write-Host "Draft PR created." -ForegroundColor Green
    }
}