$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lock = Get-Content -Raw (Join-Path $root 'data\holdout\protocol.lock.json') | ConvertFrom-Json
$failed = @()

foreach ($entry in $lock.files.PSObject.Properties) {
    $actual = (Get-FileHash -Algorithm SHA256 (Join-Path $root $entry.Name)).Hash
    if ($actual -ne $entry.Value) { $failed += $entry.Name }
}

if ($failed) { throw "Protocol lock mismatch: $($failed -join ', ')" }
Write-Output "Protocol lock verified: $($lock.protocol_id)"
