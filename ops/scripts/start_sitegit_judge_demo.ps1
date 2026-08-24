[CmdletBinding()]
param(
    [string]$ProjectId = "SASANG-001",
    [switch]$Headless,
    [switch]$EditorUi
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

function Stop-SiteGitProcessTree {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $children = @(
        Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f $ProcessId) -ErrorAction SilentlyContinue
    )
    foreach ($child in $children) {
        Stop-SiteGitProcessTree -ProcessId ([int]$child.ProcessId)
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

$context = Get-SiteGitPortableContext
Set-Location $context.RepoRoot
if (-not (Test-Path -LiteralPath $context.EnvFile)) {
    throw "Environment is not prepared. Run .\start_sitegit_portable.bat first."
}
if (-not (Test-Path -LiteralPath $context.VenvPython)) {
    throw "The PC-specific Python environment is missing. Run .\start_sitegit_portable.bat first."
}
if (-not $context.IsaacPython) { throw "Isaac Sim was not found at <SSD>:\isaacsim\python.bat." }
if (-not $context.SiteAsset) { throw "The construction site USDZ was not found on the SSD." }
if (-not $context.EquipmentAsset) { throw "The excavator USD was not found on the SSD." }
Set-SiteGitPortableEnvironment -Context $context

$serverPortRaw = Get-DotEnvValue -EnvFile $context.EnvFile -Name "SERVER_PORT" -Default "8000"
$serverPort = 8000
if (-not [int]::TryParse($serverPortRaw, [ref]$serverPort)) { $serverPort = 8000 }
$localUrl = "http://127.0.0.1:$serverPort"

if (Test-SiteGitApi -Port $serverPort) {
    throw "A SiteGit Backend is already running. Close it before starting a fresh judge demo."
}

$resetScript = Join-Path $PSScriptRoot "reset_sitegit_demo_state.ps1"
& $resetScript -DataRoot $context.DataRoot -ProjectId $ProjectId -ServerPort $serverPort

$backendScript = Join-Path $PSScriptRoot "start_sitegit_backend_portable.ps1"
$backendArguments = @(
    "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", $backendScript, "-NoBrowser"
)
$backendHost = $null
try {
    Write-Host "Starting a fresh Backend for this judge..." -ForegroundColor Cyan
    $backendHost = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $backendArguments `
        -WorkingDirectory $context.RepoRoot `
        -WindowStyle Hidden `
        -PassThru

    for ($attempt = 0; $attempt -lt 120 -and -not (Test-SiteGitApi -Port $serverPort); $attempt++) {
        if ($backendHost.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-SiteGitApi -Port $serverPort)) {
        throw "Fresh SiteGit Backend did not become healthy."
    }

    Write-Host ("Backend ready: {0}" -f $localUrl) -ForegroundColor Green
    Start-Process $localUrl

    $isaacScript = Join-Path $PSScriptRoot "start_sitegit_isaac_portable.ps1"
    $isaacArguments = @(
        "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $isaacScript
    )
    if ($Headless) { $isaacArguments += "-Headless" }
    if (-not $Headless -and -not $EditorUi) { $isaacArguments += "-Presentation" }

    Write-Host "Starting Isaac Sim from the untouched initial terrain..." -ForegroundColor Cyan
    if (-not $Headless -and -not $EditorUi) {
        Write-Host "Presentation window: maximized and movable (Alt+Tab Web, F11 optional fullscreen)" -ForegroundColor Green
    }
    & powershell.exe @isaacArguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Isaac Sim demo exited with code {0}." -f $LASTEXITCODE)
    }
} finally {
    if ($backendHost -and -not $backendHost.HasExited) {
        Write-Host "Stopping the Backend owned by this judge-demo session..." -ForegroundColor DarkGray
        Stop-SiteGitProcessTree -ProcessId $backendHost.Id
    }
}
