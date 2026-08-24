[CmdletBinding()]
param(
    [switch]$Headless,
    [switch]$EditorUi,
    [switch]$CloseOnFinish,
    [switch]$Fast,
    [ValidateRange(1, 12)]
    [int]$BatchSize = 3,
    [ValidateRange(1.0, 12.0)]
    [double]$SegmentLength = 4.0,
    [string]$ExcavatedStage = "",
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

$runner = Join-Path $context.RepoRoot "isaac_adapter\pipeline_installation_demo.py"
$arguments = @(
    $runner,
    "--site", $context.SiteAsset,
    "--equipment", $context.EquipmentAsset,
    "--batch-size", $BatchSize,
    "--segment-length", $SegmentLength
)
if ($Headless) { $arguments += "--headless" }
if (-not $Headless -and -not $EditorUi) { $arguments += "--presentation" }
if ($CloseOnFinish) { $arguments += "--close-on-finish" }
if ($Fast) {
    $arguments += @("--animation-seconds", "0.65", "--batch-size", "6")
}
if ($ExcavatedStage) {
    $arguments += @("--excavated-stage", [System.IO.Path]::GetFullPath($ExcavatedStage))
}
if ($SaveUsd) {
    $arguments += @("--save-usd", [System.IO.Path]::GetFullPath($SaveUsd))
}

Write-Host "Starting the three-excavator pipe pickup and installation demo..." -ForegroundColor Cyan
Write-Host "Backend  : not used"
Write-Host ("Site     : {0}" -f $context.SiteAsset)
Write-Host ("Equipment: {0}" -f $context.EquipmentAsset)
Write-Host "Pipes    : three short handling props, then one complete drawing route"
Write-Host ("Window   : {0}" -f $(if ($EditorUi) { "Isaac editor" } elseif ($Headless) { "headless" } else { "viewport-only maximized window" }))
if ($ExcavatedStage) {
    Write-Host ("Input    : {0}" -f ([System.IO.Path]::GetFullPath($ExcavatedStage)))
} else {
    Write-Host "Input    : saved excavation Stage when available; otherwise prepared approved state"
}
& $context.IsaacPython @arguments
if ($LASTEXITCODE -ne 0) {
    throw ("Isaac Sim pipe-installation demo exited with code {0}." -f $LASTEXITCODE)
}
