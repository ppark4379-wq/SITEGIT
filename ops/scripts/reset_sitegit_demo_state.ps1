[CmdletBinding()]
param(
    [string]$DataRoot = "",
    [string]$ProjectId = "SASANG-001",
    [int]$ServerPort = 0,
    [switch]$SkipProcessCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

function Assert-SafeChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    $rootPrefix = $rootFull + '\'
    if (
        $pathFull -ne $rootFull -and
        -not $pathFull.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw ("Unsafe {0} path outside the data root: {1}" -f $Label, $pathFull)
    }
    return $pathFull
}

function Get-SafeRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $pathFull = Assert-SafeChildPath -Root $rootFull -Path $Path -Label "relative"
    if ($pathFull -eq $rootFull) { return "." }
    return $pathFull.Substring($rootFull.Length + 1).Replace('\', '/')
}

function Move-ToDemoArchive {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RelativeDestination
    )

    $sourceFull = Assert-SafeChildPath -Root $script:ResolvedDataRoot -Path $Source -Label "source"
    if (-not (Test-Path -LiteralPath $sourceFull)) { return }

    $destination = Join-Path $script:ArchiveRoot $RelativeDestination
    $destinationFull = Assert-SafeChildPath -Root $script:ArchiveRoot -Path $destination -Label "archive destination"
    $destinationParent = Split-Path -Parent $destinationFull
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Move-Item -LiteralPath $sourceFull -Destination $destinationFull
    $script:MovedItems.Add([pscustomobject]@{
        source = Get-SafeRelativePath -Root $script:ResolvedDataRoot -Path $sourceFull
        archive = Get-SafeRelativePath -Root $script:ArchiveRoot -Path $destinationFull
    })
    Write-Host ("  archived: {0}" -f $sourceFull) -ForegroundColor DarkGray
}

if ($ProjectId -notmatch '^[A-Za-z0-9_.-]+$') {
    throw "ProjectId may contain only letters, numbers, dot, underscore, and hyphen."
}

$context = Get-SiteGitPortableContext
if (-not $DataRoot) { $DataRoot = $context.DataRoot }
$script:ResolvedDataRoot = [System.IO.Path]::GetFullPath($DataRoot).TrimEnd('\')
$driveRoot = [System.IO.Path]::GetPathRoot($script:ResolvedDataRoot).TrimEnd('\')
if (-not $script:ResolvedDataRoot -or $script:ResolvedDataRoot -eq $driveRoot) {
    throw "Refusing to use a drive root as SITEGIT_DATA_ROOT."
}

New-Item -ItemType Directory -Force -Path $script:ResolvedDataRoot | Out-Null

if ($ServerPort -le 0) {
    $serverPortRaw = Get-DotEnvValue -EnvFile $context.EnvFile -Name "SERVER_PORT" -Default "8000"
    $ServerPort = 8000
    if (-not [int]::TryParse($serverPortRaw, [ref]$ServerPort)) { $ServerPort = 8000 }
}

if (-not $SkipProcessCheck) {
    if (Test-SiteGitApi -Port $ServerPort) {
        throw "SiteGit Backend is still running on port $ServerPort. Close its window before resetting the demo."
    }

    $runningIsaac = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and (
                    $_.CommandLine -match 'isaac_runner\.py' -or
                    $_.CommandLine -match 'start_sitegit_isaac_portable\.ps1'
                )
            }
    )
    if ($runningIsaac.Count -gt 0) {
        throw "Isaac Sim SiteGit runner is still running. Close Isaac Sim before resetting the demo."
    }
}

$databasePath = Join-Path $script:ResolvedDataRoot "database\sitegit.db"
if (Test-Path -LiteralPath $databasePath) {
    try {
        $lockTest = [System.IO.File]::Open(
            $databasePath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        $lockTest.Dispose()
    } catch {
        throw "The SiteGit database is in use. Close Backend and retry. $($_.Exception.Message)"
    }
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$script:ArchiveRoot = Join-Path $script:ResolvedDataRoot ("backups\demo-runs\" + $timestamp)
$script:ArchiveRoot = Assert-SafeChildPath -Root $script:ResolvedDataRoot -Path $script:ArchiveRoot -Label "archive root"
New-Item -ItemType Directory -Force -Path $script:ArchiveRoot | Out-Null
$script:MovedItems = [System.Collections.Generic.List[object]]::new()

Write-Host "" 
Write-Host "====================================================================" -ForegroundColor DarkCyan
Write-Host "SiteGit judge demo reset" -ForegroundColor Cyan
Write-Host ("Data root : {0}" -f $script:ResolvedDataRoot)
Write-Host ("Project   : {0}" -f $ProjectId)
Write-Host ("Archive   : {0}" -f $script:ArchiveRoot)
Write-Host "====================================================================" -ForegroundColor DarkCyan

# Database rows, authentication users, Work Packages, commits, reviews, and
# shared UI state belong to one demo run. The next Backend startup recreates
# the schema and deterministic seed users/state.
Move-ToDemoArchive -Source $databasePath -RelativeDestination "database\sitegit.db"
Move-ToDemoArchive -Source ($databasePath + "-wal") -RelativeDestination "database\sitegit.db-wal"
Move-ToDemoArchive -Source ($databasePath + "-shm") -RelativeDestination "database\sitegit.db-shm"

# Evidence is keyed by Work Package UUID rather than project ID, so the whole
# current run directory is archived together with its database.
Move-ToDemoArchive `
    -Source (Join-Path $script:ResolvedDataRoot "evidence\work-packages") `
    -RelativeDestination "evidence\work-packages"

# Remove the approved/pending Stage lineage for this project. Without HEAD,
# isaac_runner loads the original site USDZ and constructs the initial fill.
Move-ToDemoArchive `
    -Source (Join-Path $script:ResolvedDataRoot ("isaac\branches\" + $ProjectId)) `
    -RelativeDestination ("isaac\branches\" + $ProjectId)
Move-ToDemoArchive `
    -Source (Join-Path $script:ResolvedDataRoot ("isaac\pending\" + $ProjectId)) `
    -RelativeDestination ("isaac\pending\" + $ProjectId)

# The approved Work map baseline must be recaptured from the freshly started
# initial Isaac Stage instead of replaying the previous judge's approved map.
Move-ToDemoArchive `
    -Source (Join-Path $script:ResolvedDataRoot ("isaac\stage_inventory_" + $ProjectId + ".json")) `
    -RelativeDestination ("isaac\stage_inventory_" + $ProjectId + ".json")
Move-ToDemoArchive `
    -Source (Join-Path $script:ResolvedDataRoot ("isaac\published_stage_baseline_" + $ProjectId + ".json")) `
    -RelativeDestination ("isaac\published_stage_baseline_" + $ProjectId + ".json")

foreach ($directory in @(
    (Join-Path $script:ResolvedDataRoot "database"),
    (Join-Path $script:ResolvedDataRoot "evidence\work-packages"),
    (Join-Path $script:ResolvedDataRoot "isaac\branches"),
    (Join-Path $script:ResolvedDataRoot "isaac\pending")
)) {
    Assert-SafeChildPath -Root $script:ResolvedDataRoot -Path $directory -Label "recreated directory" | Out-Null
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$manifest = [ordered]@{
    schema_version = "1.0"
    reset_at = (Get-Date).ToString("o")
    project_id = $ProjectId
    data_root = $script:ResolvedDataRoot
    archive_root = $script:ArchiveRoot
    moved_items = @($script:MovedItems)
    preserved = @(
        "isaac/assets",
        "isaac/site-work-map",
        "isaac/terrain_collision_proxy_2m.npz",
        "site_plans",
        "tooling",
        "logs"
    )
}
$manifestPath = Join-Path $script:ArchiveRoot "reset-manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "--------------------------------------------------------------------"
Write-Host "Demo state reset complete." -ForegroundColor Green
Write-Host "The next Backend startup creates a fresh DB." -ForegroundColor Green
Write-Host "The next Isaac startup loads the original terrain and initial fill." -ForegroundColor Green
Write-Host ("Previous run is recoverable from: {0}" -f $script:ArchiveRoot) -ForegroundColor Yellow
Write-Host "====================================================================" -ForegroundColor DarkCyan
