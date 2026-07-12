$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lock = Get-Content -Raw (Join-Path $root 'data\holdout\protocol.lock.json') | ConvertFrom-Json
$failed = @()

function Get-NormalizedTextHash([string]$Path) {
    $text = [IO.File]::ReadAllText($Path).Replace("`r`n", "`n").Replace("`r", "`n")
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '') }
    finally { $sha.Dispose() }
}

if (-not $lock.git_commit) { throw 'Protocol lock has no implementation commit' }
git -C $root cat-file -e "$($lock.git_commit)^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Protocol implementation commit does not exist' }
git -C $root merge-base --is-ancestor $lock.git_commit HEAD
if ($LASTEXITCODE -ne 0) { throw 'Protocol implementation commit is not an ancestor of HEAD' }

$lockedNames = @($lock.files.PSObject.Properties.Name)
$criticalFiles = @(git -C $root ls-files src/v5_eval scripts schemas data/baseline/v4_parser_lock.json)
$missingCritical = @($criticalFiles | Where-Object { $_ -notin $lockedNames })
if ($missingCritical) { throw "Protocol lock omits critical files: $($missingCritical -join ', ')" }

foreach ($entry in $lock.files.PSObject.Properties) {
    $actual = Get-NormalizedTextHash (Join-Path $root $entry.Name)
    if ($actual -ne $entry.Value) { $failed += $entry.Name }
}

if ($failed) { throw "Protocol lock mismatch: $($failed -join ', ')" }
Write-Output "Protocol lock verified: $($lock.protocol_id)"
