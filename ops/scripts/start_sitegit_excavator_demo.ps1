[CmdletBinding()]
param(
    [switch]$Headless,
    [switch]$EditorUi,
    [switch]$CloseOnFinish,
    [switch]$Fast,
    [switch]$IntentionalDefect,
    [switch]$SkipSensors,
    [ValidateRange(1, 12)]
    [int]$Scoops = 1,
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
if (-not $context.SiteAsset) {
    throw "The construction-site demolition USDZ was not found on the SSD."
}
if (-not $context.EquipmentAsset) {
    throw "The animated excavator USD was not found on the SSD."
}
Set-SiteGitPortableEnvironment -Context $context

$runner = Join-Path $context.RepoRoot "isaac_adapter\three_excavator_demo.py"
$arguments = @(
    $runner,
    "--site", $context.SiteAsset,
    "--equipment", $context.EquipmentAsset,
    "--scoops", $Scoops
)
if ($Headless) { $arguments += "--headless" }
if (-not $Headless -and -not $EditorUi) { $arguments += "--presentation" }
if ($CloseOnFinish) { $arguments += "--close-on-finish" }
if ($Fast) { $arguments += @("--animation-seconds", "1.3") }
if ($IntentionalDefect) { $arguments += "--intentional-defect" }
if ($SkipSensors) { $arguments += "--skip-sensors" }
if ($SaveUsd) { $arguments += @("--save-usd", [System.IO.Path]::GetFullPath($SaveUsd)) }

Write-Host "Starting the standalone three-excavator Isaac Sim demo..." -ForegroundColor Cyan
Write-Host "Backend   : not used"
Write-Host ("Site      : {0}" -f $context.SiteAsset)
Write-Host ("Equipment : {0}" -f $context.EquipmentAsset)
Write-Host ("Scenario  : 3 parallel work fronts; {0} incremental scoops" -f $Scoops)
Write-Host ("Defect    : {0}" -f $(if ($IntentionalDefect) { "EXC-002 under-excavation enabled" } else { "disabled; all three fronts finish" }))
Write-Host ("Sensors   : {0}" -f $(if ($SkipSensors) { "disabled" } else { "3 mounted cameras + 3D LiDAR before/after" }))
Write-Host ("Window    : {0}" -f $(if ($EditorUi) { "Isaac editor" } elseif ($Headless) { "headless" } else { "viewport-only maximized window" }))
& $context.IsaacPython @arguments
if ($LASTEXITCODE -ne 0) {
    throw ("Isaac Sim demo exited with code {0}." -f $LASTEXITCODE)
}
