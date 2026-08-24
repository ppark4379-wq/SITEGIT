[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

$context = Get-SiteGitPortableContext
Set-Location $context.RepoRoot
if (-not (Test-Path -LiteralPath $context.EnvFile)) {
    throw "Environment is not prepared. Run .\start_sitegit_portable.bat first."
}
if (-not (Test-Path -LiteralPath $context.VenvPython)) {
    throw "The PC-specific Python environment is missing. Run .\start_sitegit_portable.bat first."
}
Set-SiteGitPortableEnvironment -Context $context

$serverPortRaw = Get-DotEnvValue -EnvFile $context.EnvFile -Name "SERVER_PORT" -Default "8000"
$serverPort = 8000
if (-not [int]::TryParse($serverPortRaw, [ref]$serverPort)) { $serverPort = 8000 }
$localUrl = "http://127.0.0.1:$serverPort"
$env:SITEGIT_API_URL = "$localUrl/api/v1"
$env:SERVER_HOST = "0.0.0.0"
$env:SERVER_PORT = [string]$serverPort

if (Test-SiteGitApi -Port $serverPort) {
    Write-Host ("SiteGit Backend is already running: {0}" -f $localUrl) -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $localUrl }
    exit 0
}

$ollamaProcess = $null
if (-not $SkipOllama) {
    $modelManifest = Get-OllamaModelManifest -ModelsRoot $context.OllamaModels -Model $context.OllamaModel
    if (-not $context.OllamaExecutable -or -not (Test-Path -LiteralPath $modelManifest)) {
        throw "Ollama or its SSD model is missing. Run .\start_sitegit_portable.bat first, or use -SkipOllama."
    }
    $tags = Get-OllamaTags -BaseUrl $context.OllamaBaseUrl
    if (-not $tags) {
        $ollamaProcess = Start-Process -FilePath $context.OllamaExecutable -ArgumentList @("serve") -WindowStyle Hidden -PassThru
        for ($attempt = 0; $attempt -lt 30 -and -not $tags; $attempt++) {
            Start-Sleep -Milliseconds 500
            $tags = Get-OllamaTags -BaseUrl $context.OllamaBaseUrl
        }
    }
    if (-not $tags) { throw "Portable Ollama failed to start." }
    Write-Host ("Ollama ready: {0} ({1})" -f $context.OllamaBaseUrl, $context.OllamaModel) -ForegroundColor Green
}

$backendProcess = $null
try {
    Write-Host ("Starting SiteGit Backend: {0}" -f $localUrl) -ForegroundColor Cyan
    $backendProcess = Start-Process -FilePath $context.VenvPython -ArgumentList @(
        "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", [string]$serverPort
    ) -WorkingDirectory $context.RepoRoot -NoNewWindow -PassThru
    for ($attempt = 0; $attempt -lt 60 -and -not (Test-SiteGitApi -Port $serverPort); $attempt++) {
        if ($backendProcess.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-SiteGitApi -Port $serverPort)) {
        throw "SiteGit Backend did not become healthy."
    }
    Write-Host "Backend is ready. Keep this window open; close it with Ctrl+C." -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $localUrl }
    Wait-Process -Id $backendProcess.Id
} finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($ollamaProcess -and -not $ollamaProcess.HasExited) {
        Stop-Process -Id $ollamaProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
