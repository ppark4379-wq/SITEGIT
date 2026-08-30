[CmdletBinding()]
param(
    [switch]$Headless,
    [switch]$EditorUi,
    [switch]$CloseOnFinish,
    [switch]$Fast,
    [ValidateRange(1, 10)]
    [int]$Scoops = 1,
    [string]$InstalledStage = "",
    [string]$SaveUsd = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

$context = Get-SiteGitPortableContext
Set-Location $context.RepoRoot
if (-not (Test-Path -LiteralPath $context.EnvFile)) {
    throw "Environment is not prepared. Run .\start_sitegit_portable.bat first."
}
if (-not $context.IsaacPython) {
    throw "Isaac Sim was not found at <SSD>:\isaacsim\python.bat."
}
Set-SiteGitPortableEnvironment -Context $context

$runner = Join-Path $context.RepoRoot "isaac_adapter\pipeline_backfill_demo.py"
$arguments = @($runner, "--scoops", $Scoops)
if ($context.SiteAsset) { $arguments += @("--site", $context.SiteAsset) }
if ($context.EquipmentAsset) { $arguments += @("--equipment", $context.EquipmentAsset) }
if ($Headless) { $arguments += "--headless" }
if (-not $Headless -and -not $EditorUi) { $arguments += "--presentation" }
if ($CloseOnFinish) { $arguments += "--close-on-finish" }
if ($Fast) { $arguments += @("--animation-seconds", "0.75") }
if ($InstalledStage) {
    $arguments += @("--installed-stage", [System.IO.Path]::GetFullPath($InstalledStage))
}
if ($SaveUsd) {
    $arguments += @("--save-usd", [System.IO.Path]::GetFullPath($SaveUsd))
}

Write-Host "Starting the synchronized three-excavator backfill demo..." -ForegroundColor Cyan
Write-Host "Backend  : not used"
Write-Host "Sequence : spoil pickup -> face trench -> dump -> restore surface"
Write-Host ("Cycles   : {0}" -f $Scoops)
Write-Host ("Window   : {0}" -f $(if ($EditorUi) { "Isaac editor" } elseif ($Headless) { "headless" } else { "viewport-only maximized window" }))
if ($InstalledStage) {
    Write-Host ("Input    : {0}" -f ([System.IO.Path]::GetFullPath($InstalledStage)))
} else {
    Write-Host "Input    : SITEGIT_DATA_ROOT\isaac\pipeline-installation-demo\pipeline-installed-stage.usda"
}
& $context.IsaacPython @arguments
if ($LASTEXITCODE -ne 0) {
    throw ("Isaac Sim backfill demo exited with code {0}." -f $LASTEXITCODE)
}
