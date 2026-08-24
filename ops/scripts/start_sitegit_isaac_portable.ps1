[CmdletBinding()]
param(
    [switch]$Headless,
    [switch]$Presentation
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

$context = Get-SiteGitPortableContext
Set-Location $context.RepoRoot
if (-not (Test-Path -LiteralPath $context.EnvFile)) {
    throw "Environment is not prepared. Run .\start_sitegit_portable.bat first."
}
if (-not $context.IsaacPython) { throw "Isaac Sim was not found at <SSD>:\isaacsim\python.bat." }
if (-not $context.SiteAsset) { throw "The construction site USDZ was not found on the SSD." }
if (-not $context.EquipmentAsset) { throw "The excavator USD was not found on the SSD." }
Set-SiteGitPortableEnvironment -Context $context

$serverPortRaw = Get-DotEnvValue -EnvFile $context.EnvFile -Name "SERVER_PORT" -Default "8000"
$serverPort = 8000
if (-not [int]::TryParse($serverPortRaw, [ref]$serverPort)) { $serverPort = 8000 }
$env:SITEGIT_API_URL = "http://127.0.0.1:$serverPort/api/v1"
if (-not (Test-SiteGitApi -Port $serverPort)) {
    Write-Host "WARNING: SiteGit Backend is not running. Start start_sitegit_backend.bat first." -ForegroundColor Yellow
}

$runner = Join-Path $context.RepoRoot "isaac_adapter\isaac_runner.py"
$arguments = @($runner, "--site", $context.SiteAsset, "--equipment", $context.EquipmentAsset)
if ($Headless) { $arguments += "--headless" }
if ($Presentation -and -not $Headless) { $arguments += "--presentation" }

Write-Host "Starting Isaac Sim from the external SSD..." -ForegroundColor Cyan
Write-Host ("Site      : {0}" -f $context.SiteAsset)
Write-Host ("Equipment : {0}" -f $context.EquipmentAsset)
Write-Host ("Backend   : {0}" -f $env:SITEGIT_API_URL)
Write-Host ("Window    : {0}" -f $(if ($Presentation -and -not $Headless) { "viewport-only maximized window" } else { "Isaac editor" }))
& $context.IsaacPython @arguments
if ($LASTEXITCODE -ne 0) { throw ("Isaac Sim exited with code {0}." -f $LASTEXITCODE) }
