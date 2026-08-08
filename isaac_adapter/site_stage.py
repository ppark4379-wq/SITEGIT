"""현장 지형 USD를 Isaac Sim Stage에 올리고 좌표를 정규화합니다.

Isaac Sim은 Z-up·meter를 전제로 물리를 계산하므로 Stage를 그 기준으로 고정하고,
현장 메시를 다음 규칙으로 배치합니다.

    XY 중심 → 원점
    최저점   → Z = 0 (지면)

이 규칙이 SiteGit의 **현장 좌표계** 정의입니다. 웹이 내리는 지시도, Isaac이
돌려주는 read-back 값도 모두 이 좌표계를 씁니다.

이 모듈의 함수는 SimulationApp이 부팅된 뒤에만 호출할 수 있습니다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SITE_PRIM_PATH = "/World/Site"

# 기본 현장 에셋. 대용량이라 Git이 아니라 SSD 데이터 루트에 둡니다.
DEFAULT_SITE_ASSET = "isaac/assets/construction_site_mud.usdz"


def resolved_data_root(data_root: str | Path | None = None) -> Path:
    """Backend와 동일한 규칙으로 SITEGIT_DATA_ROOT를 해석합니다.

    SITEGIT_DATA_ROOT는 isaac_adapter/.env가 아니라 루트 .env에 있으므로
    map_publisher.py와 똑같이 루트 .env를 직접 읽습니다. 상대경로는 실행
    위치가 아니라 저장소 루트를 기준으로 해석합니다.
    """
    from dotenv import load_dotenv

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")
    raw = Path(data_root or os.getenv("SITEGIT_DATA_ROOT", repo_root / "runtime"))
    if not raw.is_absolute():
        raw = repo_root / raw
    return raw.resolve()


def default_site_asset(data_root: str | Path | None = None) -> Path | None:
    """SITEGIT_DATA_ROOT 아래의 기본 현장 에셋 경로를 돌려줍니다."""
    candidate = resolved_data_root(data_root) / DEFAULT_SITE_ASSET
    return candidate if candidate.is_file() else None


def write_site_frame(info: dict[str, Any], data_root: str | Path | None = None) -> Path:
    """현장 좌표계를 파일로 남깁니다.

    Kit이 headless에서 Python stdout을 삼키기도 하고, 무엇보다 웹 쪽이 Isaac의
    좌표 기준을 알아야 하므로 파일로 고정합니다.
    """
    import json

    target = resolved_data_root(data_root) / "isaac" / "site_frame.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def prepare_stage(stage: Any) -> Any:
    """Stage를 Z-up·meter로 고정하고 /World를 기본 Prim으로 만듭니다."""
    from pxr import Sdf, UsdGeom

    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    world = UsdGeom.Xform.Define(stage, Sdf.Path("/World")).GetPrim()
    stage.SetDefaultPrim(world)
    return world


def add_lighting(stage: Any) -> None:
    """현장이 검게 보이지 않도록 기본 조명을 답니다."""
    from pxr import Sdf, UsdLux

    if stage.GetPrimAtPath("/World/SiteGitLight").IsValid():
        return
    light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/SiteGitLight"))
    light.CreateIntensityAttr(1800.0)
    light.CreateAngleAttr(1.5)
    dome = UsdLux.DomeLight.Define(stage, Sdf.Path("/World/SiteGitDome"))
    dome.CreateIntensityAttr(320.0)


def _world_range(stage: Any, prim_path: str):
    from pxr import Usd, UsdGeom

    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
        useExtentsHint=True,
    )
    return cache.ComputeWorldBound(stage.GetPrimAtPath(prim_path)).ComputeAlignedRange()


def load_site(
    stage: Any,
    asset_path: str | Path,
    *,
    simulation_app: Any = None,
    settle_frames: int = 240,
) -> dict[str, Any]:
    """현장 USD를 참조로 붙이고 XY 중심·지면 정렬한 뒤 실제 범위를 돌려줍니다.

    302MB usdz는 비동기로 로드되므로 bounds가 확정될 때까지 프레임을 돌립니다.
    """
    from pxr import Gf, Sdf, UsdGeom

    from pxr import Usd

    asset = Path(asset_path).resolve()
    if not asset.is_file():
        raise FileNotFoundError(f"현장 에셋을 찾을 수 없습니다: {asset}")

    # USD는 참조를 붙일 때 단위·업축을 자동 변환하지 않습니다. 이 usdz는
    # centimeter·Y-up이라 그대로 두면 21km 크기로 옆으로 누워 들어옵니다.
    # 메타데이터를 읽어 직접 보정합니다.
    asset_stage = Usd.Stage.Open(asset.as_posix(), load=Usd.Stage.LoadNone)
    asset_meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(asset_stage))
    asset_up_axis = str(UsdGeom.GetStageUpAxis(asset_stage))

    prepare_stage(stage)
    site = UsdGeom.Xform.Define(stage, Sdf.Path(SITE_PRIM_PATH))
    if not site.GetPrim().GetReferences().AddReference(asset.as_posix()):
        raise RuntimeError(f"USD 참조를 추가하지 못했습니다: {asset}")

    # XformCommonAPI는 T * R * S 순서를 보장하므로 scale → rotate → translate가
    # 의도한 대로 적용됩니다.
    xform = UsdGeom.XformCommonAPI(site)
    scale = asset_meters_per_unit  # 스테이지가 meter이므로 그대로 배율이 됩니다.
    xform.SetScale(Gf.Vec3f(scale, scale, scale))
    # Y-up 자산을 Z-up 스테이지에 세웁니다. X축 +90°: (x,y,z) → (x,-z,y)
    rotate_x = 90.0 if asset_up_axis.lower() == "y" else 0.0
    xform.SetRotate(Gf.Vec3f(rotate_x, 0.0, 0.0))

    # 참조 로딩이 끝나야 bounds가 유효합니다.
    world_range = None
    for _ in range(settle_frames):
        if simulation_app is not None:
            simulation_app.update()
        world_range = _world_range(stage, SITE_PRIM_PATH)
        if not world_range.IsEmpty():
            extent = world_range.GetMax() - world_range.GetMin()
            if all(float(extent[i]) > 1.0 for i in range(3)):
                break
    if world_range is None or world_range.IsEmpty():
        raise RuntimeError("현장 메시의 bounds를 계산하지 못했습니다.")

    minimum, maximum = world_range.GetMin(), world_range.GetMax()
    xform.SetTranslate(
        Gf.Vec3d(
            -float((minimum[0] + maximum[0]) * 0.5),
            -float((minimum[1] + maximum[1]) * 0.5),
            -float(minimum[2]),
        )
    )
    if simulation_app is not None:
        for _ in range(10):
            simulation_app.update()

    add_lighting(stage)
    aligned = _world_range(stage, SITE_PRIM_PATH)
    return {
        "asset": str(asset),
        "prim_path": SITE_PRIM_PATH,
        "bounds": {
            "min": [float(aligned.GetMin()[i]) for i in range(3)],
            "max": [float(aligned.GetMax()[i]) for i in range(3)],
        },
        "up_axis": "Z",
        "meters_per_unit": 1.0,
        "source": {
            "meters_per_unit": asset_meters_per_unit,
            "up_axis": asset_up_axis,
            "applied_scale": scale,
            "applied_rotate_x_deg": rotate_x,
        },
    }
