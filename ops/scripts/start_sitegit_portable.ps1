[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "sitegit_portable_common.ps1")

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 68) -ForegroundColor DarkGray
    Write-Host ("  " + $Title) -ForegroundColor Cyan
    Write-Host ("=" * 68) -ForegroundColor DarkGray
}

function Write-Check {
    param(
        [ValidateSet("OK", "WARN", "FAIL")][string]$State,
        [string]$Label,
        [string]$Detail = ""
    )
    $color = switch ($State) {
        "OK" { "Green" }
        "WARN" { "Yellow" }
        default { "Red" }
    }
    Write-Host ("[{0,-4}] {1}" -f $State, $Label) -ForegroundColor $color -NoNewline
    if ($Detail) { Write-Host ("  " + $Detail) -ForegroundColor Gray } else { Write-Host "" }
}

$context = Get-SiteGitPortableContext
Set-Location $context.RepoRoot

Write-Section "SiteGit external SSD environment setup"
Write-Check "OK" "Repository" $context.RepoRoot
Write-Check "OK" "Detected SSD root" $context.SsdRoot

if (-not (Test-Path -LiteralPath $context.EnvFile)) {
    if ($CheckOnly) {
        Write-Check "WARN" ".env" "Missing; normal setup will create it from .env.example."
    } else {
        Copy-Item -LiteralPath (Join-Path $context.RepoRoot ".env.example") -Destination $context.EnvFile
        Write-Check "WARN" ".env" "Created. Review passwords and JWT_SECRET before publishing the server."
        $context = Get-SiteGitPortableContext
    }
} else {
    Write-Check "OK" ".env" "Found"
}

if (-not $CheckOnly) { Set-SiteGitPortableEnvironment -Context $context }

$python = Find-SystemPython
if (-not $python -and -not $CheckOnly) {
    Install-WingetPackage -PackageId "Python.Python.3.12" -DisplayName "Python 3.12"
    $python = Find-SystemPython
}
if ($python) {
    Write-Check "OK" "Python 3.11+" ("Python {0}" -f $python.Version)
} else {
    Write-Check "FAIL" "Python 3.11+" "Missing; normal setup installs Python 3.12 with winget."
}

$venvVersion = Test-PythonCandidate -Executable $context.VenvPython
if (-not $CheckOnly -and -not $venvVersion) {
    if (-not $python) { throw "Python installation completed but python.exe could not be found. Open a new terminal and run setup again." }
    if (Test-Path -LiteralPath $context.VenvDirectory) {
        $backup = $context.VenvDirectory + ".broken-" + (Get-Date -Format "yyyyMMdd-HHmmss")
        Move-Item -LiteralPath $context.VenvDirectory -Destination $backup
        Write-Check "WARN" "Old PC environment" ("Preserved at {0}" -f $backup)
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $context.VenvDirectory) | Out-Null
    Write-Host "Creating a Python environment for this PC..." -ForegroundColor Cyan
    & $python.Executable @($python.Prefix) -m venv $context.VenvDirectory
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the PC-specific Python environment." }
    $venvVersion = Test-PythonCandidate -Executable $context.VenvPython
}

$pipReady = $venvVersion -and (Test-Path -LiteralPath (Join-Path $context.VenvDirectory "Lib\site-packages\pip"))
if (-not $CheckOnly -and $venvVersion -and -not $pipReady) {
    Write-Host "Preparing pip..." -ForegroundColor Cyan
    & $context.VenvPython -m ensurepip --upgrade --default-pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to prepare pip." }
    $pipReady = $true
}

$requirementsMarker = Join-Path $context.VenvDirectory ".sitegit-requirements.sha256"
$requirementsHash = (Get-FileHash -LiteralPath $context.RequirementsFile -Algorithm SHA256).Hash
$installedHash = if (Test-Path -LiteralPath $requirementsMarker) { (Get-Content -LiteralPath $requirementsMarker -Raw).Trim() } else { "" }
if (-not $CheckOnly -and $installedHash -ne $requirementsHash) {
    Write-Host "Installing SiteGit backend packages..." -ForegroundColor Cyan
    & $context.VenvPython -m pip install -r $context.RequirementsFile
    if ($LASTEXITCODE -ne 0) { throw "Failed to install SiteGit backend packages." }
    Set-Content -LiteralPath $requirementsMarker -Value $requirementsHash -Encoding ascii
    $installedHash = $requirementsHash
}
Write-Check $(if ($venvVersion -and $pipReady -and $installedHash -eq $requirementsHash) { "OK" } else { "WARN" }) "PC-specific Python environment" $context.VenvDirectory

$modelPresent = $false
if (-not $SkipOllama) {
    if (-not $context.OllamaExecutable -and -not $CheckOnly) {
        Install-WingetPackage -PackageId "Ollama.Ollama" -DisplayName "Ollama"
        $context = Get-SiteGitPortableContext
        Set-SiteGitPortableEnvironment -Context $context
    }
    Write-Check $(if ($context.OllamaExecutable) { "OK" } else { "FAIL" }) "Ollama program" $(if ($context.OllamaExecutable) { $context.OllamaExecutable } else { "Missing; normal setup installs it with winget." })

    $modelManifest = Get-OllamaModelManifest -ModelsRoot $context.OllamaModels -Model $context.OllamaModel
    $modelPresent = $modelManifest -and (Test-Path -LiteralPath $modelManifest)
    if (-not $CheckOnly -and $context.OllamaExecutable -and -not $modelPresent) {
        New-Item -ItemType Directory -Force -Path $context.OllamaModels | Out-Null
        Write-Host ("Downloading {0} to the external SSD..." -f $context.OllamaModel) -ForegroundColor Cyan
        $ollamaProcess = $null
        try {
            $tags = Get-OllamaTags -BaseUrl $context.OllamaBaseUrl
            if (-not $tags) {
                $ollamaProcess = Start-Process -FilePath $context.OllamaExecutable -ArgumentList @("serve") -WindowStyle Hidden -PassThru
                for ($attempt = 0; $attempt -lt 30 -and -not $tags; $attempt++) {
                    Start-Sleep -Milliseconds 500
                    $tags = Get-OllamaTags -BaseUrl $context.OllamaBaseUrl
                }
            }
            if (-not $tags) { throw "The portable Ollama server did not start." }
            & $context.OllamaExecutable pull $context.OllamaModel
            if ($LASTEXITCODE -ne 0) { throw "Failed to download the Ollama model." }
        } finally {
            if ($ollamaProcess -and -not $ollamaProcess.HasExited) {
                Stop-Process -Id $ollamaProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
        $modelPresent = Test-Path -LiteralPath $modelManifest
    }
    Write-Check $(if ($modelPresent) { "OK" } else { "WARN" }) "Ollama model on SSD" ("{0} - {1}" -f $context.OllamaModel, $context.OllamaModels)
}

Write-Check $(if ($context.IsaacPython) { "OK" } else { "FAIL" }) "Isaac Sim on SSD" $(if ($context.IsaacPython) { $context.IsaacPython } else { "Expected <SSD>:\isaacsim\python.bat" })
Write-Check $(if ($context.SiteAsset) { "OK" } else { "FAIL" }) "Construction site asset" $(if ($context.SiteAsset) { $context.SiteAsset } else { "Site USDZ was not found." })
Write-Check $(if ($context.EquipmentAsset) { "OK" } else { "FAIL" }) "Excavator asset" $(if ($context.EquipmentAsset) { $context.EquipmentAsset } else { "Excavator.usd was not found." })
Write-Check $(if ($context.SensorReference) { "OK" } else { "WARN" }) "LiDAR reference asset" $(if ($context.SensorReference) { $context.SensorReference } else { "The adapter fallback offset will be used." })
$nvidia = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
Write-Check $(if ($nvidia) { "OK" } else { "WARN" }) "NVIDIA driver" $(if ($nvidia) { "Detected" } else { "Install a driver compatible with the SSD Isaac Sim build." })

$requiredReady = $python -and $venvVersion -and $pipReady -and ($installedHash -eq $requirementsHash) -and $context.IsaacPython -and $context.SiteAsset -and $context.EquipmentAsset
if (-not $SkipOllama) { $requiredReady = $requiredReady -and $context.OllamaExecutable -and $modelPresent }

Write-Section "Setup result"
if (-not $requiredReady) {
    if ($CheckOnly) {
        Write-Host "Some requirements are missing. Run start_sitegit_portable.bat without -CheckOnly to install them." -ForegroundColor Yellow
    } else {
        Write-Host "Setup is incomplete. Resolve the FAIL items above and run setup again." -ForegroundColor Red
    }
    exit 1
}

if ($CheckOnly) {
    Write-Host "This PC is ready. No programs were started." -ForegroundColor Green
} else {
    Write-Host "Environment setup is complete. No Backend or Isaac Sim process was started." -ForegroundColor Green
    Write-Host "Backend : .\start_sitegit_backend.bat"
    Write-Host "Isaac Sim: .\start_sitegit_isaac.bat"
}
