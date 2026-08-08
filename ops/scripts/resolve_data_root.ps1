# ================================================================
# SITEGIT_DATA_ROOT 해석 공통 함수
#
# `.env`의 SITEGIT_DATA_ROOT는 절대경로(E:/SiteGitData)와 상대경로
# (../SiteGitData) 둘 다 허용합니다. 외장 SSD를 다른 PC에 꽂으면 드라이브
# 문자가 바뀌므로 상대경로를 권장하며, 이때 기준점은 스크립트를 실행한
# 위치가 아니라 항상 저장소 루트입니다.
#
# Backend(backend/app/core/config.py)와 Isaac Adapter
# (isaac_adapter/map_publisher.py)도 동일한 규칙을 사용합니다.
#
# 사용법:
#   . (Join-Path $PSScriptRoot "resolve_data_root.ps1")
#   $DataRoot = Get-SiteGitDataRoot -RepoRoot $RepoRoot
# ================================================================

function Get-SiteGitDataRoot {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $envFile = Join-Path $RepoRoot ".env"
    if (-not (Test-Path $envFile)) {
        throw ".env not found: $envFile  (ops/scripts/setup_windows.ps1 먼저 실행)"
    }

    $line = Get-Content $envFile |
        Where-Object { $_ -match '^\s*SITEGIT_DATA_ROOT\s*=' } |
        Select-Object -First 1

    $value = ""
    if ($line) {
        $value = ($line -replace '^\s*SITEGIT_DATA_ROOT\s*=', '').Trim().Trim('"').Trim("'")
    }
    # 비어 있으면 backend와 동일하게 저장소 내부 runtime 폴더로 대체합니다.
    if (-not $value) { $value = "runtime" }

    if (-not [System.IO.Path]::IsPathRooted($value)) {
        $value = Join-Path $RepoRoot $value
    }
    return [System.IO.Path]::GetFullPath($value)
}
