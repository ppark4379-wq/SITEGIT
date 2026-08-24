$ErrorActionPreference = "Stop"

function Find-FirstExistingPath {
    param([AllowNull()][string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$EnvFile,
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Default = ""
    )

    if (-not (Test-Path -LiteralPath $EnvFile)) { return $Default }
    $escaped = [regex]::Escape($Name)
    $line = Get-Content -LiteralPath $EnvFile |
        Where-Object { $_ -match ("^\s*" + $escaped + "\s*=") } |
        Select-Object -First 1
    if (-not $line) { return $Default }
    return ($line -replace ("^\s*" + $escaped + "\s*="), "").Trim().Trim('"').Trim("'")
}

function Test-PythonCandidate {
    param([string]$Executable, [string[]]$PrefixArguments = @())

    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable)) { return $null }
    try {
        $version = & $Executable @PrefixArguments -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $version) { return $null }
        if ([version]$version -lt [version]"3.11") { return $null }
        return [string]$version
    } catch {
        return $null
    }
}

function Find-SystemPython {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($selector in @("-3.12", "-3.13", "-3.11", "-3")) {
            $version = Test-PythonCandidate -Executable $launcher.Source -PrefixArguments @($selector)
            if ($version) {
                return [pscustomobject]@{ Executable = $launcher.Source; Prefix = @($selector); Version = $version }
            }
        }
    }

    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    $programFiles = [Environment]::GetFolderPath("ProgramFiles")
    $candidates = @()
    if ($localAppData) {
        $candidates += @(
            (Join-Path $localAppData "Programs\Python\Python312\python.exe"),
            (Join-Path $localAppData "Programs\Python\Python313\python.exe"),
            (Join-Path $localAppData "Programs\Python\Python311\python.exe")
        )
    }
    if ($programFiles) {
        $candidates += @(
            (Join-Path $programFiles "Python312\python.exe"),
            (Join-Path $programFiles "Python313\python.exe"),
            (Join-Path $programFiles "Python311\python.exe")
        )
    }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { $candidates += $pythonCommand.Source }

    foreach ($candidate in $candidates) {
        $version = Test-PythonCandidate -Executable $candidate
        if ($version) {
            return [pscustomobject]@{ Executable = [System.IO.Path]::GetFullPath($candidate); Prefix = @(); Version = $version }
        }
    }
    return $null
}

function Find-OllamaExecutable {
    param([string]$SsdRoot)

    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    $programFiles = [Environment]::GetFolderPath("ProgramFiles")
    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    return Find-FirstExistingPath @(
        $(if ($localAppData) { Join-Path $localAppData "Programs\Ollama\ollama.exe" } else { $null }),
        $(if ($programFiles) { Join-Path $programFiles "Ollama\ollama.exe" } else { $null }),
        $(if ($programFilesX86) { Join-Path $programFilesX86 "Ollama\ollama.exe" } else { $null }),
        (Join-Path $SsdRoot "ollama\ollama.exe")
    )
}

function Get-OllamaModelManifest {
    param([string]$ModelsRoot, [string]$Model)

    if (-not $ModelsRoot) { return $null }
    $parts = $Model.Split(":", 2)
    $name = $parts[0]
    $tag = if ($parts.Count -gt 1) { $parts[1] } else { "latest" }
    return Join-Path $ModelsRoot ("manifests\registry.ollama.ai\library\{0}\{1}" -f $name, $tag)
}

function Test-SiteGitApi {
    param([int]$Port)
    try {
        $response = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/api/v1/health" -f $Port) -TimeoutSec 2
        return $null -ne $response
    } catch { return $false }
}

function Get-OllamaTags {
    param([string]$BaseUrl)
    try {
        return Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + "/api/tags") -TimeoutSec 2
    } catch { return $null }
}

function Get-SiteGitPortableContext {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $ssdRoot = Split-Path -Parent $repoRoot
    $envFile = Join-Path $repoRoot ".env"
    $siblingDataRoot = Join-Path $ssdRoot "SiteGitData"
    if (Test-Path -LiteralPath $siblingDataRoot) {
        $dataRoot = [System.IO.Path]::GetFullPath($siblingDataRoot)
    } elseif (Test-Path -LiteralPath $envFile) {
        . (Join-Path $PSScriptRoot "resolve_data_root.ps1")
        $dataRoot = Get-SiteGitDataRoot -RepoRoot $repoRoot
    } else {
        $dataRoot = $siblingDataRoot
    }

    $assetRelative = "assets\construction_machinery\pbr-excavator-animated\source\Excavator"
    $siteAsset = Find-FirstExistingPath @(
        (Join-Path $dataRoot "isaac\assets\construction_site_demolition.usdz"),
        (Join-Path $repoRoot "assets\maps\construction-site-demolition\construction_site_demolition.usdz")
    )
    $equipmentAsset = Find-FirstExistingPath @(
        (Join-Path $repoRoot (Join-Path $assetRelative "Excavator.usd")),
        (Join-Path $ssdRoot (Join-Path "sitegit1" (Join-Path $assetRelative "Excavator.usd")))
    )
    $sensorReference = Find-FirstExistingPath @(
        (Join-Path $repoRoot (Join-Path $assetRelative "excavator_lidar.usd")),
        (Join-Path $ssdRoot (Join-Path "sitegit1" (Join-Path $assetRelative "excavator_lidar.usd")))
    )
    $soilBaseColor = Find-FirstExistingPath @(
        (Join-Path $dataRoot "isaac\assets\materials\demolition_soil_tile_diffuse.jpg"),
        (Join-Path $repoRoot "isaac_adapter\assets\demolition_soil_tile_diffuse.jpg")
    )
    $soilNormal = Find-FirstExistingPath @(
        (Join-Path $dataRoot "isaac\assets\materials\demolition_soil_tile_normal.jpg"),
        (Join-Path $repoRoot "isaac_adapter\assets\demolition_soil_tile_normal.jpg")
    )
    $isaacPython = Find-FirstExistingPath @(
        (Join-Path $ssdRoot "isaacsim\python.bat"),
        (Join-Path $ssdRoot "IsaacSim\python.bat")
    )
    $ollamaModels = Find-FirstExistingPath @(
        (Join-Path $ssdRoot "ollama\models"),
        (Join-Path $dataRoot "ollama\models"),
        $env:OLLAMA_MODELS
    )
    if (-not $ollamaModels) { $ollamaModels = Join-Path $ssdRoot "ollama\models" }

    $machineName = (($env:COMPUTERNAME + "-" + $env:USERNAME) -replace "[^A-Za-z0-9_.-]", "-").Trim("-")
    if (-not $machineName) { $machineName = "windows-pc" }
    $venvDirectory = Join-Path $dataRoot ("tooling\venvs\" + $machineName)
    $ollamaModel = Get-DotEnvValue -EnvFile $envFile -Name "OLLAMA_MODEL" -Default "qwen3:8b"

    return [pscustomobject]@{
        RepoRoot = $repoRoot; SsdRoot = $ssdRoot; EnvFile = $envFile; DataRoot = $dataRoot
        PortableTemp = Join-Path $dataRoot "tooling\tmp"
        RequirementsFile = Join-Path $repoRoot "backend\requirements.txt"
        VenvDirectory = $venvDirectory; VenvPython = Join-Path $venvDirectory "Scripts\python.exe"
        SiteAsset = $siteAsset; EquipmentAsset = $equipmentAsset; SensorReference = $sensorReference
        SoilBaseColor = $soilBaseColor; SoilNormal = $soilNormal; IsaacPython = $isaacPython
        OllamaModels = $ollamaModels; OllamaExecutable = Find-OllamaExecutable -SsdRoot $ssdRoot
        OllamaModel = $ollamaModel; OllamaBaseUrl = "http://127.0.0.1:11435"
    }
}

function Set-SiteGitPortableEnvironment {
    param([Parameter(Mandatory = $true)]$Context)

    New-Item -ItemType Directory -Force -Path $Context.DataRoot, $Context.PortableTemp | Out-Null
    $env:TEMP = $Context.PortableTemp
    $env:TMP = $Context.PortableTemp
    $env:SITEGIT_DATA_ROOT = $Context.DataRoot
    $env:PYTHONPATH = Join-Path $Context.RepoRoot "backend"
    $env:OLLAMA_MODELS = $Context.OllamaModels
    $env:OLLAMA_HOST = "127.0.0.1:11435"
    $env:OLLAMA_BASE_URL = $Context.OllamaBaseUrl
    if ($Context.SiteAsset) { $env:SITEGIT_SITE_ASSET = $Context.SiteAsset }
    if ($Context.EquipmentAsset) { $env:SITEGIT_EQUIPMENT_ASSET = $Context.EquipmentAsset }
    if ($Context.SensorReference) { $env:SITEGIT_SENSOR_REFERENCE_USD = $Context.SensorReference }
    if ($Context.SoilBaseColor) { $env:SITEGIT_PIPELINE_SOIL_BASECOLOR = $Context.SoilBaseColor }
    if ($Context.SoilNormal) { $env:SITEGIT_PIPELINE_SOIL_NORMAL = $Context.SoilNormal }
}

function Install-WingetPackage {
    param([Parameter(Mandatory = $true)][string]$PackageId, [Parameter(Mandatory = $true)][string]$DisplayName)

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw "winget is unavailable. Install Microsoft App Installer, then run setup again." }
    Write-Host ("Installing {0} with winget..." -f $DisplayName) -ForegroundColor Cyan
    & $winget.Source install --id $PackageId --exact --source winget --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw ("Failed to install {0}." -f $DisplayName) }
}
