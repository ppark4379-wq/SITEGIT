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
from typing import Any, Callable

SITE_PRIM_PATH = "/World/Site"
DIGGABLE_ROOT_PATH = "/World/Diggable"
DEFAULT_SOIL_PILE_PRIM_PATH = f"{DIGGABLE_ROOT_PATH}/ZoneC_SoilPile_01"
# USD Prim names must be valid identifiers. Keep the business-facing equipment
# ID as ``EXC-001``, but use an underscore in the Stage path.
DEFAULT_EQUIPMENT_PRIM_PATH = "/World/Equipment/EXC_001"

# 기본 현장 에셋. 대용량이라 Git이 아니라 SSD 데이터 루트에 둡니다.
DEFAULT_SITE_ASSET = "isaac/assets/construction_site_demolition.usdz"


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
    configured = os.getenv("SITEGIT_SITE_ASSET", DEFAULT_SITE_ASSET).strip()
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        candidate = resolved_data_root(data_root) / candidate
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


def _triangle_surface_z_at_xy(
    x: float,
    y: float,
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    third: tuple[float, float, float],
) -> float | None:
    """Return the interpolated Z where an XY point falls inside a triangle."""

    denominator = (
        (second[1] - third[1]) * (first[0] - third[0])
        + (third[0] - second[0]) * (first[1] - third[1])
    )
    if abs(denominator) < 1e-12:
        return None
    first_weight = (
        (second[1] - third[1]) * (x - third[0])
        + (third[0] - second[0]) * (y - third[1])
    ) / denominator
    second_weight = (
        (third[1] - first[1]) * (x - third[0])
        + (first[0] - third[0]) * (y - third[1])
    ) / denominator
    third_weight = 1.0 - first_weight - second_weight
    tolerance = 1e-7
    if min(first_weight, second_weight, third_weight) < -tolerance:
        return None
    if max(first_weight, second_weight, third_weight) > 1.0 + tolerance:
        return None
    return (
        first_weight * first[2]
        + second_weight * second[2]
        + third_weight * third[2]
    )


def site_surface_height(stage: Any, x: float, y: float) -> float:
    """Find the topmost terrain triangle below one SiteGit XY coordinate.

    The imported mud map has no semantic height-field. Its authored mesh is
    therefore sampled directly so the demo soil pile does not float or sink.
    """

    from pxr import Gf, Usd, UsdGeom

    root = stage.GetPrimAtPath(SITE_PRIM_PATH)
    if not root.IsValid():
        raise RuntimeError(f"현장 Prim이 없습니다: {SITE_PRIM_PATH}")

    highest: float | None = None
    nearest_distance_squared = float("inf")
    nearest_z = 0.0
    for prim in Usd.PrimRange(root):
        if not prim.IsActive() or not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        authored_points = mesh.GetPointsAttr().Get(Usd.TimeCode.Default()) or []
        counts = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.Default()) or []
        indices = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.Default()) or []
        if not authored_points or not counts or not indices:
            continue
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        points: list[tuple[float, float, float]] = []
        for value in authored_points:
            world = matrix.Transform(Gf.Vec3d(float(value[0]), float(value[1]), float(value[2])))
            point = (float(world[0]), float(world[1]), float(world[2]))
            points.append(point)
            distance_squared = (point[0] - x) ** 2 + (point[1] - y) ** 2
            if distance_squared < nearest_distance_squared:
                nearest_distance_squared = distance_squared
                nearest_z = point[2]

        offset = 0
        for raw_count in counts:
            count = int(raw_count)
            face = [int(index) for index in indices[offset : offset + count]]
            offset += count
            if count < 3 or any(index < 0 or index >= len(points) for index in face):
                continue
            first = points[face[0]]
            for triangle_index in range(1, count - 1):
                second = points[face[triangle_index]]
                third = points[face[triangle_index + 1]]
                if x < min(first[0], second[0], third[0]) - 1e-7:
                    continue
                if x > max(first[0], second[0], third[0]) + 1e-7:
                    continue
                if y < min(first[1], second[1], third[1]) - 1e-7:
                    continue
                if y > max(first[1], second[1], third[1]) + 1e-7:
                    continue
                height = _triangle_surface_z_at_xy(x, y, first, second, third)
                if height is not None and (highest is None or height > highest):
                    highest = height

    if highest is not None:
        return highest
    if nearest_distance_squared < float("inf"):
        return nearest_z
    raise RuntimeError("현장 Mesh에서 토사 더미 배치 높이를 계산하지 못했습니다.")


def create_diggable_soil_pile(
    stage: Any,
    *,
    prim_path: str = DEFAULT_SOIL_PILE_PRIM_PATH,
    position_xy: tuple[float, float] = (-26.5, -40.5),
    size: tuple[float, float, float] = (6.0, 5.0, 2.5),
    zone_id: str = "C",
    diggable_id: str = "ZoneC-SoilPile-01",
    display_color: str = "#6B4F2A",
    simulation_app: Any = None,
    surface_height: Callable[[float, float, float], float] | None = None,
) -> dict[str, Any]:
    """Create one small, semantic and independently removable soil Mesh Prim."""

    import math

    from pxr import Gf, Sdf, UsdGeom, UsdPhysics

    if any(value <= 0 for value in size):
        raise ValueError("토사 더미 크기는 모두 0보다 커야 합니다.")
    if max(size[0], size[1]) > 25.0:
        raise ValueError("데모 토사 더미의 가로·세로 크기는 25m 이하여야 합니다.")

    prepare_stage(stage)
    UsdGeom.Xform.Define(stage, Sdf.Path(DIGGABLE_ROOT_PATH))
    existing = stage.GetPrimAtPath(prim_path)
    if existing.IsValid():
        position_range = _world_range(stage, prim_path)
        return {
            "prim_path": prim_path,
            "position": [float(value) for value in position_xy],
            "base_z": float(position_range.GetMin()[2]),
            "size": [float(value) for value in size],
            "zone_id": zone_id,
            "existing": True,
        }

    base_z = (
        surface_height(float(position_xy[0]), float(position_xy[1]), 0.0)
        if surface_height is not None
        else site_surface_height(stage, float(position_xy[0]), float(position_xy[1]))
    )
    radius_x, radius_y, height = size[0] * 0.5, size[1] * 0.5, size[2]
    segments = 24
    # Center peak plus three rings produces a rounded mound without relying on
    # an external asset or subdivision at runtime.
    points = [Gf.Vec3f(0.0, 0.0, float(height))]
    rings = ((0.34, 0.76), (0.70, 0.34), (1.0, 0.0))
    for ring_scale, height_scale in rings:
        for segment in range(segments):
            angle = 2.0 * math.pi * segment / segments
            # A deterministic ripple avoids a perfectly machined cone.
            ripple = 1.0 + 0.045 * math.sin(segment * 2.7 + ring_scale * 3.0)
            points.append(
                Gf.Vec3f(
                    float(math.cos(angle) * radius_x * ring_scale * ripple),
                    float(math.sin(angle) * radius_y * ring_scale * ripple),
                    float(height * height_scale),
                )
            )

    faces: list[int] = []
    for segment in range(segments):
        current = 1 + segment
        following = 1 + (segment + 1) % segments
        faces.extend((0, current, following))
    for ring in range(len(rings) - 1):
        inner_start = 1 + ring * segments
        outer_start = inner_start + segments
        for segment in range(segments):
            next_segment = (segment + 1) % segments
            inner = inner_start + segment
            inner_next = inner_start + next_segment
            outer = outer_start + segment
            outer_next = outer_start + next_segment
            faces.extend((inner, outer, outer_next, inner, outer_next, inner_next))

    mesh = UsdGeom.Mesh.Define(stage, Sdf.Path(prim_path))
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([3] * (len(faces) // 3))
    mesh.CreateFaceVertexIndicesAttr(faces)
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr(True)
    color_text = str(display_color).lstrip("#")
    if len(color_text) != 6:
        raise ValueError("토사 색상은 #RRGGBB 형식이어야 합니다.")
    try:
        color_value = Gf.Vec3f(
            int(color_text[0:2], 16) / 255.0,
            int(color_text[2:4], 16) / 255.0,
            int(color_text[4:6], 16) / 255.0,
        )
    except ValueError as error:
        raise ValueError("토사 색상은 #RRGGBB 형식이어야 합니다.") from error
    mesh.CreateDisplayColorAttr([color_value])
    mesh.CreateExtentAttr(
        [
            Gf.Vec3f(float(-radius_x * 1.05), float(-radius_y * 1.05), 0.0),
            Gf.Vec3f(float(radius_x * 1.05), float(radius_y * 1.05), float(height)),
        ]
    )
    UsdGeom.XformCommonAPI(mesh).SetTranslate(
        Gf.Vec3d(float(position_xy[0]), float(position_xy[1]), float(base_z - 0.03))
    )
    prim = mesh.GetPrim()
    prim.SetCustomDataByKey("sitegitDiggable", True)
    prim.SetCustomDataByKey("sitegitDiggableId", str(diggable_id))
    prim.SetCustomDataByKey("sitegitZoneId", zone_id)
    prim.SetCustomDataByKey("sitegitDisplayColor", f"#{color_text.upper()}")
    UsdPhysics.CollisionAPI.Apply(prim)

    if simulation_app is not None:
        for _ in range(10):
            simulation_app.update()
    aligned = _world_range(stage, prim_path)
    minimum, maximum = aligned.GetMin(), aligned.GetMax()
    return {
        "prim_path": prim_path,
        "position": [
            float((minimum[0] + maximum[0]) * 0.5),
            float((minimum[1] + maximum[1]) * 0.5),
            float((minimum[2] + maximum[2]) * 0.5),
        ],
        "base_z": float(minimum[2]),
        "size": [float(maximum[index] - minimum[index]) for index in range(3)],
        "zone_id": zone_id,
        "existing": False,
    }


def load_equipment(
    stage: Any,
    asset_path: str | Path,
    *,
    prim_path: str = DEFAULT_EQUIPMENT_PRIM_PATH,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    simulation_app: Any = None,
    settle_frames: int = 180,
    surface_height: Callable[[float, float, float], float] | None = None,
) -> dict[str, Any]:
    """Reference one excavator asset, normalize units/up-axis, and place it on site ground."""
    from pxr import Gf, Sdf, Usd, UsdGeom

    asset = Path(asset_path).resolve()
    if not asset.is_file():
        raise FileNotFoundError(f"장비 에셋을 찾을 수 없습니다: {asset}")
    asset_stage = Usd.Stage.Open(asset.as_posix(), load=Usd.Stage.LoadNone)
    asset_meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(asset_stage))
    asset_up_axis = str(UsdGeom.GetStageUpAxis(asset_stage))

    prepare_stage(stage)
    UsdGeom.Xform.Define(stage, Sdf.Path("/World/Equipment"))
    equipment = UsdGeom.Xform.Define(stage, Sdf.Path(prim_path))
    if not equipment.GetPrim().GetReferences().AddReference(asset.as_posix()):
        raise RuntimeError(f"장비 USD 참조를 추가하지 못했습니다: {asset}")
    xform = UsdGeom.XformCommonAPI(equipment)
    xform.SetScale(Gf.Vec3f(asset_meters_per_unit, asset_meters_per_unit, asset_meters_per_unit))
    xform.SetRotate(Gf.Vec3f(90.0 if asset_up_axis.lower() == "y" else 0.0, 0.0, 0.0))

    world_range = None
    for _ in range(settle_frames):
        if simulation_app is not None:
            simulation_app.update()
        world_range = _world_range(stage, prim_path)
        if not world_range.IsEmpty():
            break
    if world_range is None or world_range.IsEmpty():
        raise RuntimeError("장비 메시의 bounds를 계산하지 못했습니다.")
    minimum, maximum = world_range.GetMin(), world_range.GetMax()
    # ``position.z`` is a clearance above the local terrain, not an absolute
    # world Z. The mud site is uneven, so a fixed Z=0 can bury the machine.
    ground_z = float(position[2])
    if stage.GetPrimAtPath(SITE_PRIM_PATH).IsValid():
        sampled_surface = (
            surface_height(float(position[0]), float(position[1]), 0.0)
            if surface_height is not None
            else site_surface_height(stage, float(position[0]), float(position[1]))
        )
        ground_z = float(sampled_surface) + float(position[2])
    xform.SetTranslate(
        Gf.Vec3d(
            position[0] - float((minimum[0] + maximum[0]) * 0.5),
            position[1] - float((minimum[1] + maximum[1]) * 0.5),
            ground_z - float(minimum[2]),
        )
    )
    if simulation_app is not None:
        for _ in range(10):
            simulation_app.update()
    equipment_prim = stage.GetPrimAtPath(prim_path)
    equipment_prim.SetCustomDataByKey("sitegitEquipmentId", "EXC-001")
    equipment_prim.SetCustomDataByKey("sitegitAssetPath", str(asset))
    equipment_prim.SetCustomDataByKey(
        "sitegitAssetMetersPerUnit", asset_meters_per_unit
    )
    equipment_prim.SetCustomDataByKey("sitegitAssetUpAxis", asset_up_axis)
    equipment_prim.SetCustomDataByKey(
        "sitegitEquipmentAnchor",
        {
            "x": float(position[0]),
            "y": float(position[1]),
            "z": ground_z,
        },
    )
    skeleton_paths: list[str] = []
    animation_paths: list[str] = []
    for descendant in Usd.PrimRange(equipment_prim):
        if descendant.GetTypeName() == "Skeleton":
            skeleton_paths.append(str(descendant.GetPath()))
        elif descendant.GetTypeName() == "SkelAnimation":
            animation_paths.append(str(descendant.GetPath()))
    return {
        "asset": str(asset),
        "prim_path": prim_path,
        "position": [float(position[0]), float(position[1]), ground_z],
        "ground_surface_z": ground_z - float(position[2]),
        "meters_per_unit": 1.0,
        "skeleton_paths": skeleton_paths,
        "animation_paths": animation_paths,
    }
