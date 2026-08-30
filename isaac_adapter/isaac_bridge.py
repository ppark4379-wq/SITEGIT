"""Isaac Sim 실행 계층.

중요한 제약: `pxr`과 `omni`는 SimulationApp이 부팅된 뒤에만 import됩니다.
그래서 이 파일은 모듈 최상단에서 USD를 import하지 않고 메서드 안에서 합니다.
실행 진입점은 `isaac_runner.py`이며, SimulationApp을 먼저 띄운 뒤 이 클래스를
사용합니다.
"""

from __future__ import annotations

import os
from typing import Any, Callable

# Isaac Stage에서 SiteGit이 만든 오브젝트가 모이는 위치.
SITEGIT_ROOT_PATH = "/World/SiteGit"

# One shortened demo cycle represents the previous five-pass excavation. Keep
# the complete measured quantity in the evidence payload, while rendering one
# bounded five-pass stockpile that is large enough to read clearly but cannot
# spread across the trench or nearby site geometry.
MAX_EXCAVATED_SPOIL_LENGTH_M = 10.0
MAX_EXCAVATED_SPOIL_WIDTH_M = 8.0
# General volume matching is also used by the separate soil-relocation demo.
# Keep its existing limit and use the tighter visual limit only for excavation.
MAX_EXCAVATED_SPOIL_HEIGHT_M = 2.5
MAX_EXCAVATED_SPOIL_VISUAL_HEIGHT_M = 3.2
MAX_EXCAVATED_SPOIL_VISUAL_VOLUME_M3 = 75.0


def grounded_equipment_center_z(
    surface_z: float,
    equipment_height: float,
    clearance_m: float = 0.03,
) -> float:
    """Return a bounds-center Z that keeps equipment above the terrain."""

    if equipment_height <= 0:
        raise ValueError("equipment height must be positive")
    return float(surface_z) + float(equipment_height) * 0.5 + max(0.0, float(clearance_m))


def zone_id_for_world_position(
    position: dict[str, float],
    terrain_center: dict[str, float],
    terrain_size: dict[str, float],
    fallback: str | None = None,
) -> str | None:
    """Return the A-D work zone that contains one SiteGit XY position."""

    size_x = float(terrain_size.get("x", 0.0))
    size_y = float(terrain_size.get("y", 0.0))
    if size_x <= 0.0 or size_y <= 0.0:
        return fallback
    x = float(position.get("x", 0.0))
    y = float(position.get("y", 0.0))
    center_x = float(terrain_center.get("x", 0.0))
    center_y = float(terrain_center.get("y", 0.0))
    half_x = size_x * 0.5
    half_y = size_y * 0.5
    if not (
        center_x - half_x <= x <= center_x + half_x
        and center_y - half_y <= y <= center_y + half_y
    ):
        return fallback
    if y >= center_y:
        return "A" if x <= center_x else "B"
    return "C" if x <= center_x else "D"


def excavation_approach_plan(
    equipment_position: dict[str, float],
    target_position: dict[str, float],
    target_size: dict[str, float],
    track_size: dict[str, float],
    requested_clearance_m: float,
    safety_margin_m: float = 0.75,
) -> dict[str, Any]:
    """Plan a target-facing stop outside both the soil and track footprints."""

    import math

    dx = float(target_position["x"]) - float(equipment_position["x"])
    dy = float(target_position["y"]) - float(equipment_position["y"])
    distance = math.hypot(dx, dy)
    if distance <= 1e-6:
        # The imported excavator initially faces site -Y.  When a malformed
        # scene starts at the target center, place it on the +Y side so the
        # retained -Y working direction still faces the target.
        direction_x, direction_y = 0.0, -1.0
    else:
        direction_x, direction_y = dx / distance, dy / distance
    target_radius = (
        abs(direction_x) * max(0.0, float(target_size.get("x", 0.0))) * 0.5
        + abs(direction_y) * max(0.0, float(target_size.get("y", 0.0))) * 0.5
    )
    track_radius = max(
        max(0.0, float(track_size.get("x", 0.0))),
        max(0.0, float(track_size.get("y", 0.0))),
    ) * 0.5
    edge_clearance = max(
        max(0.5, float(requested_clearance_m)),
        track_radius + max(0.1, float(safety_margin_m)),
    )
    center_standoff = target_radius + edge_clearance
    return {
        "destination_xy": [
            float(target_position["x"]) - direction_x * center_standoff,
            float(target_position["y"]) - direction_y * center_standoff,
        ],
        "target_xy": [float(target_position["x"]), float(target_position["y"])],
        "approach_direction_xy": [direction_x, direction_y],
        "target_radius_m": float(target_radius),
        "track_radius_m": float(track_radius),
        "edge_clearance_m": float(edge_clearance),
        "center_standoff_m": float(center_standoff),
    }


def per_scoop_cut_ratio(total_cut_ratio: float, scoop_count: int) -> float:
    """Return an equal per-scoop ratio for one requested cumulative cut.

    The soil sculpt is multiplicative: every pass lowers the surface that
    remains after the previous pass. Converting the requested final ratio this
    way makes several visible bucket passes converge on the former one-shot
    deformation target.
    """

    if scoop_count < 1:
        raise ValueError("scoop_count must be at least one")
    total = max(0.0, min(0.999, float(total_cut_ratio)))
    return float(1.0 - (1.0 - total) ** (1.0 / int(scoop_count)))


def skeletal_joint_matches(
    joint_name: str,
    *,
    suffixes: tuple[str, ...] = (),
    prefixes: tuple[str, ...] = (),
) -> bool:
    """Return whether a skeleton joint belongs to an explicitly animated set.

    Suffixes select one exact joint (for example ``/Rotator``), while prefixes
    select a complete mechanism branch such as the boom and bucket hierarchy.
    Keeping this decision independent from USD makes the safety rule easy to
    test without launching Isaac Sim.
    """

    name = str(joint_name)
    return any(name.endswith(suffix) for suffix in suffixes) or any(
        name == prefix or name.startswith(prefix.rstrip("/") + "/")
        for prefix in prefixes
    )


def moved_soil_dump_position(
    equipment_position: dict[str, float],
    approach_direction_xy: list[float] | tuple[float, float],
    moved_size: tuple[float, float, float],
    *,
    track_radius_m: float,
    dump_side: float,
    dump_sequence_index: int,
    bank_inset_m: float = 0.0,
) -> dict[str, Any]:
    """Place spoil on a stable side bank without drifting behind the machine.

    A mound is wider than its centre point. Merely putting its centre beside
    the tracks lets the near edge hang over the newly exposed trench. This
    calculation includes the mound's projected radius. Later dumps extend the
    same side bank laterally, rather than marching backwards into buildings or
    other site geometry behind the excavator.
    """

    import math

    direction_x = float(approach_direction_xy[0])
    direction_y = float(approach_direction_xy[1])
    direction_length = math.hypot(direction_x, direction_y)
    if direction_length <= 1e-6:
        direction_x, direction_y = 0.0, -1.0
    else:
        direction_x /= direction_length
        direction_y /= direction_length

    side_sign = -1.0 if float(dump_side) < 0.0 else 1.0
    side_x = -direction_y * side_sign
    side_y = direction_x * side_sign
    half_x = max(0.5, float(moved_size[0]) * 0.5)
    half_y = max(0.5, float(moved_size[1]) * 0.5)
    side_radius = abs(side_x) * half_x + abs(side_y) * half_y
    lateral_offset = max(0.5, float(track_radius_m)) + side_radius + 1.5
    sequence_spacing = max(
        0.8,
        min(1.5, max(float(moved_size[0]), float(moved_size[1])) * 0.10),
    )
    lateral_offset += max(0, int(dump_sequence_index)) * sequence_spacing
    # Most work fronts need no longitudinal offset because the machine has
    # already stopped outside the target footprint. A small, explicit inset is
    # still useful where a wide mound would otherwise overhang a curved trench.
    # It is configured per work front so the centre machine is never pushed
    # backwards into the demolition-site building again.
    bank_inset = max(0.0, float(bank_inset_m))
    return {
        "position_xy": (
            float(equipment_position["x"])
            + side_x * lateral_offset
            - direction_x * bank_inset,
            float(equipment_position["y"])
            + side_y * lateral_offset
            - direction_y * bank_inset,
        ),
        "dump_side": "left" if side_sign > 0.0 else "right",
        "lateral_offset_m": float(lateral_offset),
        "bank_inset_m": float(bank_inset),
        "sequence_spacing_m": float(sequence_spacing),
    }


def projected_mesh_volume(
    points: list[tuple[float, float, float]],
    face_vertex_counts: list[int],
    face_vertex_indices: list[int],
    *,
    face_limit: int | None = None,
) -> float:
    """Estimate soil volume above the lowest vertex using XY triangle projection."""

    if not points:
        return 0.0
    base_z = min(point[2] for point in points)
    volume = 0.0
    offset = 0
    for face_number, raw_count in enumerate(face_vertex_counts):
        if face_limit is not None and face_number >= face_limit:
            break
        count = int(raw_count)
        face = [int(value) for value in face_vertex_indices[offset : offset + count]]
        offset += count
        if count < 3 or any(index < 0 or index >= len(points) for index in face):
            continue
        first = points[face[0]]
        for face_index in range(1, count - 1):
            second = points[face[face_index]]
            third = points[face[face_index + 1]]
            twice_area = abs(
                (second[0] - first[0]) * (third[1] - first[1])
                - (second[1] - first[1]) * (third[0] - first[0])
            )
            average_height = sum(
                max(0.0, point[2] - base_z) for point in (first, second, third)
            ) / 3.0
            volume += 0.5 * twice_area * average_height
    return float(volume)


def reshape_mound_points_for_volume(
    points: list[tuple[float, float, float]],
    face_vertex_counts: list[int],
    face_vertex_indices: list[int],
    desired_volume_m3: float,
    *,
    max_height_m: float = MAX_EXCAVATED_SPOIL_HEIGHT_M,
) -> list[tuple[float, float, float]]:
    """Resize a mound to one volume while keeping it broad and low.

    Scaling only vertex Z made a large excavation volume look like a tall
    needle.  This keeps the mound below ``max_height_m`` and distributes any
    remaining volume over X/Y, preserving the represented soil volume.
    """

    if not points:
        return []
    if desired_volume_m3 <= 0.0:
        raise ValueError("desired mound volume must be positive")
    if max_height_m <= 0.0:
        raise ValueError("maximum mound height must be positive")

    current_volume = projected_mesh_volume(
        points,
        face_vertex_counts,
        face_vertex_indices,
    )
    if current_volume <= 1e-9:
        return list(points)

    minimum_z = min(point[2] for point in points)
    maximum_z = max(point[2] for point in points)
    current_height = maximum_z - minimum_z
    if current_height <= 1e-9:
        return list(points)

    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    center_x = (minimum_x + maximum_x) * 0.5
    center_y = (minimum_y + maximum_y) * 0.5

    volume_ratio = float(desired_volume_m3) / current_volume
    isotropic_scale = volume_ratio ** (1.0 / 3.0)
    target_height = min(
        float(max_height_m),
        current_height * isotropic_scale,
    )
    vertical_scale = target_height / current_height
    horizontal_scale = (volume_ratio / vertical_scale) ** 0.5

    return [
        (
            center_x + (x - center_x) * horizontal_scale,
            center_y + (y - center_y) * horizontal_scale,
            minimum_z + (z - minimum_z) * vertical_scale,
        )
        for x, y, z in points
    ]


def excavated_spoil_visual_profile(
    target_size: dict[str, float],
    removed_volume_m3: float,
) -> tuple[tuple[float, float, float], float]:
    """Return a bounded five-pass visual profile for excavated spoil.

    ``removed_volume_m3`` is the measured work quantity and may describe a
    whole work front. It must not be converted directly into one unbounded
    mound. The 75 m3 visual cap reproduces the combined footprint of the
    previous five visible bucket passes in one low stockpile; evidence and
    quantity accounting retain the full measured volume.
    """

    if removed_volume_m3 <= 0.0:
        raise ValueError("removed soil volume must be positive")

    length = min(
        MAX_EXCAVATED_SPOIL_LENGTH_M,
        max(7.5, float(target_size["x"]) * 0.32),
    )
    width = min(
        MAX_EXCAVATED_SPOIL_WIDTH_M,
        max(6.0, float(target_size["y"]) * 0.32),
    )
    height = min(
        MAX_EXCAVATED_SPOIL_VISUAL_HEIGHT_M,
        max(2.4, float(target_size["z"]) * 0.45),
    )
    visual_volume = min(
        float(removed_volume_m3),
        MAX_EXCAVATED_SPOIL_VISUAL_VOLUME_M3,
    )
    return (length, width, height), visual_volume


def sculpt_soil_mesh_points(
    points: list[tuple[float, float, float]],
    *,
    cut_ratio: float = 0.9,
    base_z_override: float | None = None,
    minimum_cut_influence: float = 0.0,
) -> list[tuple[float, float, float]]:
    """Carve a smooth bucket-shaped depression into a standalone soil mesh."""

    if len(points) < 4:
        raise ValueError("soil mesh needs at least four points")
    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    base_z = (
        float(base_z_override)
        if base_z_override is not None
        else min(point[2] for point in points)
    )
    center_x = (minimum_x + maximum_x) * 0.5
    center_y = (minimum_y + maximum_y) * 0.5
    radius_x = max((maximum_x - minimum_x) * 0.5, 1e-6)
    radius_y = max((maximum_y - minimum_y) * 0.5, 1e-6)
    ratio = max(0.05, min(0.98, float(cut_ratio)))
    minimum_influence = max(0.0, min(1.0, float(minimum_cut_influence)))
    sculpted: list[tuple[float, float, float]] = []
    for x, y, z in points:
        normalized_radius = (
            ((x - center_x) / radius_x) ** 2
            + ((y - center_y) / radius_y) ** 2
        ) ** 0.5
        # Preserve the outside rim and lower the central surface most. This
        # creates an actual crater rather than deleting or uniformly scaling.
        influence = max(
            minimum_influence,
            max(0.0, 1.0 - normalized_radius / 0.82) ** 1.35,
        )
        height = max(0.0, z - base_z)
        sculpted.append((x, y, base_z + height * (1.0 - ratio * influence)))
    return sculpted


class IsaacBridge:
    """실제 Isaac Sim Stage에 작업을 반영합니다.

    핵심 원칙은 **지시값을 그대로 되돌려주지 않는다**는 것입니다. Prim을 만든 뒤
    Stage에서 월드 변환을 다시 읽어 그 값을 반환합니다. 웹 맵은 이 값을 그리므로,
    Isaac 쪽에서 위치가 보정되면 웹도 보정된 위치를 보여줍니다.
    """

    def __init__(self, stage: Any = None, update_callback: Callable[[], None] | None = None):
        self._stage = stage
        self._update_callback = update_callback
        self._known_diggable_records: dict[str, dict[str, Any]] = {}
        self._terrain_ray_limits: dict[str, tuple[float, float]] = {}
        self._rigid_prim_controllers: dict[str, Any] = {}
        self._skeletal_clip_cache: dict[str, tuple[int, dict[str, list[Any]]]] = {}
        self._excavation_prepared_callback: Callable[[dict[str, Any]], None] | None = None

    def set_excavation_prepared_callback(
        self,
        callback: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        """Set a one-shot callback fired after approach and before arm motion.

        The execution runner uses this boundary to capture the true ``before``
        evidence: the excavator has reached and faced the target, but the soil
        and the boom/bucket pose have not been changed yet.
        """

        self._excavation_prepared_callback = callback

    def _notify_excavation_prepared(self, details: dict[str, Any]) -> None:
        """Consume the pending callback exactly once for one excavation."""

        callback = self._excavation_prepared_callback
        self._excavation_prepared_callback = None
        if callback is not None:
            callback(details)

    @property
    def stage(self) -> Any:
        if self._stage is None:
            import omni.usd

            self._stage = omni.usd.get_context().get_stage()
            if self._stage is None:
                raise RuntimeError(
                    "USD Stage를 찾을 수 없습니다. SimulationApp이 먼저 부팅되어야 합니다."
                )
        return self._stage

    def dispatch(self, command: dict[str, Any]) -> str:
        raise NotImplementedError("Connect this method to the actual Isaac Sim execution layer.")

    def read_progress(self, execution_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _ensure_scope(self) -> None:
        """/World/SiteGit 계층이 없으면 만듭니다."""
        from pxr import UsdGeom

        stage = self.stage
        for path in ("/World", SITEGIT_ROOT_PATH):
            if not stage.GetPrimAtPath(path).IsValid():
                UsdGeom.Xform.Define(stage, path)

    def _read_world_transform(self, prim_path: str) -> tuple[dict, dict]:
        """Stage에서 실제 월드 위치와 크기를 다시 읽습니다.

        지시값을 신뢰하지 않고 Stage를 진실의 원본으로 삼습니다.
        """
        from pxr import Gf, Usd, UsdGeom

        prim = self.stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Prim을 만들지 못했습니다: {prim_path}")

        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = matrix.ExtractTranslation()
        # 회전이 없는 축정렬 변환이므로 각 행의 길이가 곧 축별 배율입니다.
        axis_scale = [
            Gf.Vec3d(matrix[row][0], matrix[row][1], matrix[row][2]).GetLength()
            for row in range(3)
        ]
        # UsdGeom.Cube는 size 속성이 한 변의 길이입니다. 배율과 함께 실제 크기를 만듭니다.
        cube_size = UsdGeom.Cube(prim).GetSizeAttr().Get() or 1.0
        position = {"x": float(translation[0]), "y": float(translation[1]), "z": float(translation[2])}
        size = {
            "x": float(axis_scale[0] * cube_size),
            "y": float(axis_scale[1] * cube_size),
            "z": float(axis_scale[2] * cube_size),
        }
        return position, size

    def place_cube(self, instruction: dict[str, Any]) -> dict[str, Any]:
        """지시받은 위치에 큐브 Prim을 만들고, Stage에서 실제 값을 읽어 반환합니다."""
        from pxr import Gf, UsdGeom

        params = instruction.get("params") or {}
        position = params.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
        size = params.get("size") or {"x": 4.0, "y": 4.0, "z": 4.0}

        self._ensure_scope()
        prim_path = f"{SITEGIT_ROOT_PATH}/cube_{str(instruction.get('id', 'unknown')).replace('-', '')[:12]}"

        cube = UsdGeom.Cube.Define(self.stage, prim_path)
        cube.GetSizeAttr().Set(1.0)  # 단위 큐브로 두고 크기는 Scale로 표현합니다.
        cube_prim = cube.GetPrim()
        cube_prim.SetCustomDataByKey("sitegitSceneObject", True)
        cube_prim.SetCustomDataByKey("sitegitObjectLabel", str(params.get("label") or cube_prim.GetName()))
        xform = UsdGeom.XformCommonAPI(cube)
        xform.SetTranslate(
            Gf.Vec3d(float(position.get("x", 0)), float(position.get("y", 0)), float(position.get("z", 0)))
        )
        xform.SetScale(
            Gf.Vec3f(float(size.get("x", 1)), float(size.get("y", 1)), float(size.get("z", 1)))
        )

        color = params.get("color")
        if color:
            cube.GetDisplayColorAttr().Set([_hex_to_gf_color(color)])
            cube_prim.SetCustomDataByKey("sitegitDisplayColor", str(color).upper())

        placed_position, placed_size = self._read_world_transform(prim_path)
        return {
            "placed_position": placed_position,
            "placed_size": placed_size,
            "prim_path": prim_path,
            "simulator": "isaac-sim",
            "source": "stage-readback",
        }

    def _world_bounds(self, prim: Any) -> tuple[dict[str, float], dict[str, float]]:
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        )
        aligned = cache.ComputeWorldBound(prim).ComputeAlignedBox()
        minimum, maximum = aligned.GetMin(), aligned.GetMax()
        position = {
            "x": float((minimum[0] + maximum[0]) * 0.5),
            "y": float((minimum[1] + maximum[1]) * 0.5),
            "z": float((minimum[2] + maximum[2]) * 0.5),
        }
        size = {
            "x": max(0.0, float(maximum[0] - minimum[0])),
            "y": max(0.0, float(maximum[1] - minimum[1])),
            "z": max(0.0, float(maximum[2] - minimum[2])),
        }
        return position, size

    def _mesh_geometry_snapshot(self, prim: Any) -> dict[str, Any] | None:
        """Serialize one small USD Mesh as world-space triangles for web merge."""

        from pxr import Gf, Usd, UsdGeom

        if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
            return None
        mesh = UsdGeom.Mesh(prim)
        authored_points = mesh.GetPointsAttr().Get() or []
        counts = [int(value) for value in (mesh.GetFaceVertexCountsAttr().Get() or [])]
        indices = [int(value) for value in (mesh.GetFaceVertexIndicesAttr().Get() or [])]
        if not authored_points or not counts or not indices:
            return None
        if len(authored_points) > 20_000 or len(indices) > 120_000:
            return None
        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        world_points: list[list[float]] = []
        for point in authored_points:
            world = matrix.Transform(Gf.Vec3d(float(point[0]), float(point[1]), float(point[2])))
            world_points.append([float(world[0]), float(world[1]), float(world[2])])
        geometry = {
            "format": "sitegit-triangle-mesh-v1",
            "points": world_points,
            "face_vertex_counts": counts,
            "face_vertex_indices": indices,
        }
        top_face_count = prim.GetCustomDataByKey("sitegitTopFaceCount")
        if top_face_count is not None:
            geometry["top_face_count"] = max(
                0, min(int(top_face_count), len(counts))
            )
        st = UsdGeom.PrimvarsAPI(mesh).GetPrimvar("st")
        interpolation = str(st.GetInterpolation()) if st and st.HasValue() else ""
        if st and st.HasValue() and interpolation in {"vertex", "varying", "faceVarying"}:
            uv_values = st.Get(Usd.TimeCode.Default()) or []
            uv_indices = st.GetIndices(Usd.TimeCode.Default()) if st.IsIndexed() else []
            expanded = (
                [uv_values[int(index)] for index in uv_indices]
                if uv_indices
                else uv_values
            )
            if len(expanded) == len(authored_points):
                geometry["uvs"] = [
                    [float(value[0]), float(value[1])] for value in expanded
                ]
            elif interpolation == "faceVarying" and len(expanded) == len(indices):
                geometry["face_uvs"] = [
                    [float(value[0]), float(value[1])] for value in expanded
                ]
        return geometry

    def _deform_diggable_mesh(
        self,
        target: Any,
        *,
        cut_ratio: float | None = None,
        minimum_cut_influence: float = 0.0,
    ) -> dict[str, Any]:
        """Carve the target Mesh in place and refresh its collision shape."""

        from pxr import Gf, UsdGeom, UsdPhysics

        if not target.IsA(UsdGeom.Mesh):
            return {
                "available": False,
                "reason": "target Prim is not a USD Mesh",
            }
        mesh = UsdGeom.Mesh(target)
        authored = mesh.GetPointsAttr().Get() or []
        counts = [int(value) for value in (mesh.GetFaceVertexCountsAttr().Get() or [])]
        indices = [int(value) for value in (mesh.GetFaceVertexIndicesAttr().Get() or [])]
        local_points = [
            (float(point[0]), float(point[1]), float(point[2])) for point in authored
        ]
        if not local_points or not counts or not indices:
            return {
                "available": False,
                "reason": "target Mesh has no editable topology",
            }
        raw_top_vertex_count = target.GetCustomDataByKey("sitegitTopVertexCount")
        raw_top_face_count = target.GetCustomDataByKey("sitegitTopFaceCount")
        top_vertex_count = (
            int(raw_top_vertex_count)
            if raw_top_vertex_count is not None
            else len(local_points)
        )
        top_face_count = (
            int(raw_top_face_count)
            if raw_top_face_count is not None
            else None
        )
        top_vertex_count = max(1, min(top_vertex_count, len(local_points)))
        base_z = min(point[2] for point in local_points)
        before_volume = projected_mesh_volume(
            local_points,
            counts,
            indices,
            face_limit=top_face_count,
        )
        applied_cut_ratio = (
            float(cut_ratio)
            if cut_ratio is not None
            else float(os.getenv("SITEGIT_EXCAVATION_CUT_RATIO", "0.9"))
        )
        sculpted_surface = sculpt_soil_mesh_points(
            local_points[:top_vertex_count],
            cut_ratio=applied_cut_ratio,
            base_z_override=base_z,
            minimum_cut_influence=minimum_cut_influence,
        )
        after_points = sculpted_surface + local_points[top_vertex_count:]
        after_volume = projected_mesh_volume(
            after_points,
            counts,
            indices,
            face_limit=top_face_count,
        )
        mesh.GetPointsAttr().Set([Gf.Vec3f(*point) for point in after_points])
        extent = UsdGeom.PointBased.ComputeExtent([Gf.Vec3f(*point) for point in after_points])
        mesh.GetExtentAttr().Set(extent)
        collision = UsdPhysics.CollisionAPI(target)
        if not collision:
            collision = UsdPhysics.CollisionAPI.Apply(target)
        enabled = collision.GetCollisionEnabledAttr()
        enabled.Set(False)
        if self._update_callback:
            self._update_callback()
        enabled.Set(True)
        if self._update_callback:
            for _ in range(8):
                self._update_callback()
        revision = int(target.GetCustomDataByKey("sitegitTerrainRevision") or 0) + 1
        target.SetCustomDataByKey("sitegitTerrainRevision", revision)
        position, size = self._world_bounds(target)
        removed_volume = max(0.0, before_volume - after_volume)
        return {
            "available": True,
            "method": "usd_mesh_vertex_sculpt",
            "before_volume_m3": float(before_volume),
            "after_volume_m3": float(after_volume),
            "removed_volume_m3": float(removed_volume),
            "cut_ratio": max(0.05, min(0.98, applied_cut_ratio)),
            "minimum_cut_influence": max(
                0.0,
                min(1.0, float(minimum_cut_influence)),
            ),
            "revision": revision,
            "position": position,
            "size": size,
            "geometry": self._mesh_geometry_snapshot(target),
        }

    def _create_moved_soil_pile(
        self,
        *,
        target: Any,
        target_size: dict[str, float],
        equipment_position: dict[str, float],
        approach_plan: dict[str, Any],
        removed_volume_m3: float,
        dump_side: float = 1.0,
        dump_sequence_index: int = 0,
        dump_bank_inset_m: float = 0.0,
    ) -> dict[str, Any] | None:
        """Create a second physical soil mound representing excavated material."""

        import re

        try:
            from .site_stage import create_diggable_soil_pile
        except ImportError:
            from site_stage import create_diggable_soil_pile

        if removed_volume_m3 <= 1e-6:
            return None
        direction = approach_plan.get("approach_direction_xy") or [0.0, -1.0]
        moved_size, visual_target_volume = excavated_spoil_visual_profile(
            target_size,
            removed_volume_m3,
        )
        placement = moved_soil_dump_position(
            equipment_position,
            direction,
            moved_size,
            track_radius_m=float(approach_plan.get("track_radius_m") or 2.0),
            dump_side=dump_side,
            dump_sequence_index=dump_sequence_index,
            bank_inset_m=dump_bank_inset_m,
        )
        position_xy = placement["position_xy"]
        source_name = re.sub(r"[^A-Za-z0-9_]", "_", str(target.GetName()))
        suffix = int(target.GetCustomDataByKey("sitegitTerrainRevision") or 1)
        prim_path = f"/World/Diggable/{source_name}_MovedSoil_{suffix:02d}"
        while self.stage.GetPrimAtPath(prim_path).IsValid():
            suffix += 1
            prim_path = f"/World/Diggable/{source_name}_MovedSoil_{suffix:02d}"
        zone_id = str(target.GetCustomDataByKey("sitegitZoneId") or "C")
        display_color = str(target.GetCustomDataByKey("sitegitDisplayColor") or "#6B4F2A")
        info = create_diggable_soil_pile(
            self.stage,
            prim_path=prim_path,
            position_xy=position_xy,
            size=moved_size,
            zone_id=zone_id,
            diggable_id=f"{source_name}-Moved-{suffix:02d}",
            display_color=display_color,
            surface_height=lambda x, y, fallback: self._terrain_surface_z(x, y, fallback),
        )
        if self._update_callback:
            for _ in range(10):
                self._update_callback()
        moved_prim = self.stage.GetPrimAtPath(prim_path)
        visualized_volume = self._match_mesh_volume(
            moved_prim,
            visual_target_volume,
            max_height_m=MAX_EXCAVATED_SPOIL_VISUAL_HEIGHT_M,
        )
        moved_prim.SetCustomDataByKey(
            "sitegitRepresentedVolumeM3",
            float(removed_volume_m3),
        )
        moved_prim.SetCustomDataByKey(
            "sitegitVisualizedVolumeM3",
            float(visualized_volume),
        )
        position, size = self._world_bounds(moved_prim)
        return {
            **info,
            "position": position,
            "size": size,
            "geometry": self._mesh_geometry_snapshot(moved_prim),
            "source_removed_volume_m3": float(removed_volume_m3),
            # Quantity conservation is an evidence/accounting concern. The
            # rendered mound is deliberately a bounded five-pass proxy.
            "deposited_volume_m3": float(removed_volume_m3),
            "visualized_volume_m3": float(visualized_volume),
            "dump_side": placement["dump_side"],
            "dump_sequence_index": max(0, int(dump_sequence_index)),
            "lateral_offset_m": placement["lateral_offset_m"],
            "bank_inset_m": placement["bank_inset_m"],
            "sequence_spacing_m": placement["sequence_spacing_m"],
        }

    def _match_mesh_volume(
        self,
        prim: Any,
        desired_volume_m3: float,
        *,
        max_height_m: float = MAX_EXCAVATED_SPOIL_HEIGHT_M,
    ) -> float:
        """Resize a low, broad mound so deposited volume matches excavation."""

        from pxr import Gf, UsdGeom, UsdPhysics

        if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
            return 0.0
        mesh = UsdGeom.Mesh(prim)
        values = mesh.GetPointsAttr().Get() or []
        counts = [int(value) for value in (mesh.GetFaceVertexCountsAttr().Get() or [])]
        indices = [int(value) for value in (mesh.GetFaceVertexIndicesAttr().Get() or [])]
        points = [(float(value[0]), float(value[1]), float(value[2])) for value in values]
        current_volume = projected_mesh_volume(points, counts, indices)
        if current_volume <= 1e-9 or desired_volume_m3 <= 1e-9:
            return current_volume
        adjusted = reshape_mound_points_for_volume(
            points,
            counts,
            indices,
            desired_volume_m3,
            max_height_m=max_height_m,
        )
        mesh.GetPointsAttr().Set([Gf.Vec3f(*point) for point in adjusted])
        mesh.GetExtentAttr().Set(
            UsdGeom.PointBased.ComputeExtent([Gf.Vec3f(*point) for point in adjusted])
        )
        collision = UsdPhysics.CollisionAPI(prim)
        if not collision:
            collision = UsdPhysics.CollisionAPI.Apply(prim)
        collision.GetCollisionEnabledAttr().Set(False)
        if self._update_callback:
            self._update_callback()
        collision.GetCollisionEnabledAttr().Set(True)
        if self._update_callback:
            for _ in range(6):
                self._update_callback()
        prim.SetCustomDataByKey(
            "sitegitSpoilHeightLimitM",
            float(max_height_m),
        )
        return projected_mesh_volume(adjusted, counts, indices)

    def stage_inventory(
        self,
        *,
        equipment_paths: list[str],
        diggable_roots: list[str],
        scene_object_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        """Read exact executable Prim paths and transforms from the live Stage."""
        from pxr import Usd, UsdGeom

        terrain_center: dict[str, float] | None = None
        terrain_size: dict[str, float] | None = None
        terrain_path = os.getenv("SITEGIT_TERRAIN_PRIM_PATH", "/World/Site")
        terrain = self.stage.GetPrimAtPath(terrain_path)
        if terrain.IsValid() and terrain.IsActive():
            terrain_center, terrain_size = self._world_bounds(terrain)

        def record(prim: Any, role: str) -> dict[str, Any]:
            position, size = self._world_bounds(prim)
            if role == "equipment":
                custom_name = prim.GetCustomDataByKey("sitegitEquipmentId")
                anchor = prim.GetCustomDataByKey("sitegitEquipmentAnchor")
                if isinstance(anchor, dict) and all(
                    axis in anchor for axis in ("x", "y", "z")
                ):
                    position = {axis: float(anchor[axis]) for axis in ("x", "y", "z")}
            elif role == "diggable":
                custom_name = prim.GetCustomDataByKey("sitegitDiggableId")
            else:
                custom_name = prim.GetCustomDataByKey("sitegitObjectLabel")
            display_color = prim.GetCustomDataByKey("sitegitDisplayColor")
            if not display_color and prim.IsA(UsdGeom.Gprim):
                colors = UsdGeom.Gprim(prim).GetDisplayColorAttr().Get() or []
                if colors:
                    rgb = colors[0]
                    display_color = "#{:02X}{:02X}{:02X}".format(
                        *[max(0, min(255, round(float(channel) * 255))) for channel in rgb]
                    )
            authored_zone = str(prim.GetCustomDataByKey("sitegitZoneId") or "") or None
            physical_zone = (
                zone_id_for_world_position(
                    position,
                    terrain_center,
                    terrain_size,
                    fallback=authored_zone,
                )
                if terrain_center is not None and terrain_size is not None
                else authored_zone
            )
            return {
                "path": str(prim.GetPath()),
                "name": str(custom_name or prim.GetName()),
                "type_name": prim.GetTypeName() or "Prim",
                "role": role,
                "world_position": position,
                "bounds_size": size,
                "active": bool(prim.IsActive()),
                "zone_id": physical_zone,
                "capabilities": (
                    ["move_equipment", "play_animation", "excavate_prim"]
                    if role == "equipment"
                    else ["excavate_prim"] if role == "diggable" else []
                ),
                "display_color": str(display_color) if display_color else None,
                "geometry": (
                    self._mesh_geometry_snapshot(prim)
                    if role == "diggable"
                    else None
                ),
            }

        equipment: list[dict[str, Any]] = []
        for path in equipment_paths:
            prim = self.stage.GetPrimAtPath(path)
            if prim.IsValid() and prim.IsActive():
                equipment.append(record(prim, "equipment"))

        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root_path in diggable_roots:
            root = self.stage.GetPrimAtPath(root_path)
            if not root.IsValid() or not root.IsActive():
                continue
            for prim in Usd.PrimRange(root):
                path = str(prim.GetPath())
                if path in seen or not prim.IsActive() or not prim.IsA(UsdGeom.Mesh):
                    continue
                if prim.GetCustomDataByKey("sitegitDiggable") is not True:
                    continue
                seen.add(path)
                item = record(prim, "diggable")
                self._known_diggable_records[path] = item
                targets.append(item)
        # Deactivated Prim은 기본 Usd.PrimRange에서 빠집니다. 승인 전 웹은 기존
        # 지형을 유지해야 하므로 마지막 실제 bounds를 active=false로 함께 보고합니다.
        for path, cached in self._known_diggable_records.items():
            if path in seen:
                continue
            prim = self.stage.GetPrimAtPath(path)
            if prim.IsValid() and not prim.IsActive():
                inactive = dict(cached)
                inactive["active"] = False
                targets.append(inactive)
        targets.sort(key=lambda item: item["path"])

        scene_objects: list[dict[str, Any]] = []
        scene_seen: set[str] = set()
        for root_path in scene_object_roots or []:
            root = self.stage.GetPrimAtPath(root_path)
            if not root.IsValid() or not root.IsActive():
                continue
            # SiteGit-created objects are direct children of this scope.  Using
            # the roots explicitly avoids publishing the full terrain mesh as
            # hundreds of duplicate live overlays.
            for prim in root.GetChildren():
                path = str(prim.GetPath())
                if path in scene_seen or not prim.IsActive():
                    continue
                position, size = self._world_bounds(prim)
                if max(size.values(), default=0.0) <= 0.0:
                    continue
                scene_seen.add(path)
                scene_objects.append(record(prim, "scene_object"))
        scene_objects.sort(key=lambda item: item["path"])
        layer = self.stage.GetRootLayer()
        return {
            "stage_identifier": layer.realPath or layer.identifier or "anonymous-stage",
            "equipment": equipment,
            "diggable_targets": targets,
            "scene_objects": scene_objects,
        }

    def _set_world_translation(self, prim: Any, world_position: list[float]) -> None:
        """Move a root equipment Prim while preserving its existing rotation/scale ops."""
        from pxr import Gf, UsdGeom

        current_center, _ = self._world_bounds(prim)
        delta = Gf.Vec3d(
            world_position[0] - current_center["x"],
            world_position[1] - current_center["y"],
            world_position[2] - current_center["z"],
        )
        parent = prim.GetParent()
        if parent and parent.IsValid() and str(parent.GetPath()) != "/":
            parent_matrix = UsdGeom.Xformable(parent).ComputeLocalToWorldTransform(0)
            delta = parent_matrix.GetInverse().TransformDir(delta)

        xformable = UsdGeom.Xformable(prim)
        translate_op = next(
            (
                op
                for op in xformable.GetOrderedXformOps()
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate
            ),
            None,
        )
        if translate_op is None:
            translate_op = xformable.AddTranslateOp(opSuffix="sitegit")
        current_value = translate_op.Get() or Gf.Vec3d(0.0, 0.0, 0.0)
        translate_op.Set(Gf.Vec3d(current_value) + delta)

    def _terrain_surface_z(self, x: float, y: float, fallback: float) -> float:
        """Read the highest terrain collision at XY, with a mesh fallback."""

        terrain_root = os.getenv("SITEGIT_TERRAIN_PRIM", "/World/Site").rstrip("/")
        terrain = self.stage.GetPrimAtPath(terrain_root)
        if not terrain.IsValid() or not terrain.IsActive():
            return float(fallback)

        try:
            import omni.physx
            from pxr import Gf

            limits = self._terrain_ray_limits.get(terrain_root)
            if limits is None:
                center, size = self._world_bounds(terrain)
                limits = (
                    center["z"] + size["z"] * 0.5 + 10.0,
                    center["z"] - size["z"] * 0.5 - 10.0,
                )
                self._terrain_ray_limits[terrain_root] = limits
            top, bottom = limits
            hits: list[Any] = []

            def collect_hit(hit: Any) -> bool:
                hits.append(hit)
                return True

            omni.physx.get_physx_scene_query_interface().raycast_all(
                Gf.Vec3f(float(x), float(y), float(top)),
                Gf.Vec3f(0.0, 0.0, -1.0),
                float(top - bottom),
                collect_hit,
                True,
            )
            terrain_hits = [
                hit
                for hit in hits
                if str(hit.collision or hit.rigid_body) == terrain_root
                or str(hit.collision or hit.rigid_body).startswith(f"{terrain_root}/")
            ]
            if terrain_hits:
                return max(float(hit.position.z) for hit in terrain_hits)
        except Exception:
            # Collision cooking can still be finishing during startup.
            pass

        try:
            from site_stage import site_surface_height

            return float(site_surface_height(self.stage, float(x), float(y)))
        except Exception:
            return float(fallback)

    def _grounded_equipment_position(
        self,
        x: float,
        y: float,
        equipment_height: float,
        fallback_center_z: float,
    ) -> list[float]:
        """Build one terrain-following equipment center position."""

        fallback_surface = float(fallback_center_z) - float(equipment_height) * 0.5
        surface_z = self._terrain_surface_z(float(x), float(y), fallback_surface)
        clearance = float(os.getenv("SITEGIT_EQUIPMENT_GROUND_CLEARANCE_M", "0.03"))
        return [
            float(x),
            float(y),
            grounded_equipment_center_z(surface_z, equipment_height, clearance),
        ]

    def snap_equipment_to_terrain(self, equipment_prim_path: str) -> dict[str, Any]:
        """Place an existing equipment Prim on the current terrain surface."""

        equipment = self.stage.GetPrimAtPath(equipment_prim_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"장비 Prim이 Stage에 없습니다: {equipment_prim_path}")
        before, size = self._world_bounds(equipment)
        desired = self._grounded_equipment_position(
            before["x"], before["y"], size["z"], before["z"]
        )
        self._set_world_translation(equipment, desired)
        after, _ = self._world_bounds(equipment)
        surface_z = after["z"] - size["z"] * 0.5
        equipment.SetCustomDataByKey(
            "sitegitEquipmentAnchor",
            {"x": after["x"], "y": after["y"], "z": surface_z},
        )
        return {
            "equipment_prim_path": equipment_prim_path,
            "before": before,
            "after": after,
            "bounds_size": size,
            "surface_z": surface_z,
        }

    def _play_skeletal_animation(
        self,
        equipment: Any,
        animation_name: str,
        *,
        duration_seconds: float,
        reverse: bool = False,
    ) -> str | None:
        """Bind and play one authored animation below an equipment root.

        The PBR excavator stores its clips as ``SkelAnimation`` siblings and
        switches them through ``Skeleton.skel:animationSource``.  Clip samples
        are copied onto the current live timeline so animation playback never
        pauses gravity or contact solving for the physical carrier.
        """
        import omni.timeline

        timeline = omni.timeline.get_timeline_interface()
        time_codes_per_second = float(self.stage.GetTimeCodesPerSecond() or 24.0)
        start = float(timeline.get_current_time()) * time_codes_per_second
        path, frames = self._author_skeletal_animation(
            equipment,
            animation_name,
            duration_seconds=duration_seconds,
            start_time_code=start,
            reverse=reverse,
        )
        if path is None:
            return None
        timeline.play()
        for _ in range(frames):
            if self._update_callback:
                self._update_callback()
        return path

    def _author_skeletal_animation(
        self,
        equipment: Any,
        animation_name: str,
        *,
        duration_seconds: float,
        start_time_code: float,
        reverse: bool = False,
        joint_pose_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[str | None, int]:
        """Author one clip at an explicit live-timeline start without stepping."""

        from pxr import Usd

        skeleton = None
        for prim in Usd.PrimRange(equipment):
            type_name = prim.GetTypeName()
            if type_name == "Skeleton" and skeleton is None:
                skeleton = prim
        animation = self._find_skeletal_animation(equipment, animation_name)
        if skeleton is None or animation is None:
            return None, 0

        relationship = skeleton.GetRelationship("skel:animationSource")
        if not relationship:
            relationship = skeleton.CreateRelationship("skel:animationSource")
        relationship.SetTargets([animation.GetPath()])
        animated_attributes = [
            attribute
            for attribute in animation.GetAttributes()
            if attribute.GetName() in {"translations", "rotations", "scales"}
            and attribute.GetNumTimeSamples() > 0
        ]
        samples = sorted(
            {
                sample
                for attribute in animated_attributes
                for sample in attribute.GetTimeSamples()
            }
        )
        if not samples:
            return str(animation.GetPath()), 0

        time_codes_per_second = float(self.stage.GetTimeCodesPerSecond() or 24.0)
        # ``World.step`` advances the simulation at 60 Hz while USD animation
        # time is expressed in the Stage's time-codes-per-second (normally
        # 24). The former code authored one whole time code per physics step,
        # so a clip had not finished when the next clip was bound.
        update_hz = max(
            1.0, float(os.getenv("SITEGIT_ANIMATION_UPDATE_HZ", "60"))
        )
        clip_duration_seconds = max(0.25, float(duration_seconds))
        frames = max(2, min(900, round(clip_duration_seconds * update_hz)))
        cache_key = str(animation.GetPath())
        cached_clip = self._skeletal_clip_cache.get(cache_key)
        if cached_clip is None:
            source_values = {
                attribute.GetName(): [
                    attribute.Get(Usd.TimeCode(sample)) for sample in samples
                ]
                for attribute in animated_attributes
            }
            source_sample_count = len(samples)
            self._skeletal_clip_cache[cache_key] = (
                source_sample_count,
                source_values,
            )
        else:
            source_sample_count, source_values = cached_clip
        joint_names = [
            str(value)
            for value in (animation.GetAttribute("joints").Get() or [])
        ]
        joint_indexes = {name: index for index, name in enumerate(joint_names)}
        for frame in range(frames + 1):
            ratio = frame / frames
            source_ratio = 1.0 - ratio if reverse else ratio
            source_index = min(
                source_sample_count - 1,
                round(source_ratio * (source_sample_count - 1)),
            )
            destination_time = Usd.TimeCode(
                float(start_time_code)
                + ratio * clip_duration_seconds * time_codes_per_second
            )
            for attribute in animated_attributes:
                attribute_name = attribute.GetName()
                value = source_values[attribute_name][source_index]
                overrides = (joint_pose_overrides or {}).get(attribute_name) or {}
                if value is not None and overrides:
                    mutable_value = list(value)
                    for joint_name, joint_value in overrides.items():
                        joint_index = joint_indexes.get(joint_name)
                        if joint_index is not None and joint_index < len(mutable_value):
                            mutable_value[joint_index] = joint_value
                    value = mutable_value
                if value is not None:
                    attribute.Set(value, destination_time)
        self.stage.SetEndTimeCode(
            max(
                float(self.stage.GetEndTimeCode()),
                float(start_time_code)
                + clip_duration_seconds * time_codes_per_second
                + 1,
            )
        )
        return str(animation.GetPath()), frames

    def _find_skeletal_animation(self, equipment: Any, animation_name: str) -> Any:
        """Find one clip without confusing ``ArmIn`` with ``ArmInDig``."""

        from pxr import Usd

        wanted = str(animation_name).strip().lower()
        fallback = None
        for prim in Usd.PrimRange(equipment):
            if prim.GetTypeName() != "SkelAnimation":
                continue
            name = prim.GetName().lower()
            if name == wanted or name.endswith("_" + wanted):
                return prim
            if fallback is None and wanted in name:
                fallback = prim
        return fallback

    def _skeletal_joint_pose_overrides(
        self,
        equipment: Any,
        animation_name: str,
        joint_suffixes: tuple[str, ...] = (),
        *,
        joint_prefixes: tuple[str, ...] = (),
        invert_selection: bool = False,
        source_ratio: float = 1.0,
    ) -> dict[str, dict[str, Any]]:
        """Read selected joint poses from an unmodified cached source clip.

        Imported excavator clips animate the complete skeleton. Consequently,
        binding ``ArmDump`` after ``Rotate90`` would otherwise reset the upper
        structure to its forward pose. These overrides let arm/bucket motion
        come from the dump clip while the Rotator pose stays at the side.
        """

        from pxr import Usd

        animation = self._find_skeletal_animation(equipment, animation_name)
        if animation is None:
            return {}

        cache_key = str(animation.GetPath())
        cached_clip = self._skeletal_clip_cache.get(cache_key)
        if cached_clip is None:
            animated_attributes = [
                attribute
                for attribute in animation.GetAttributes()
                if attribute.GetName() in {"translations", "rotations", "scales"}
                and attribute.GetNumTimeSamples() > 0
            ]
            samples = sorted(
                {
                    sample
                    for attribute in animated_attributes
                    for sample in attribute.GetTimeSamples()
                }
            )
            if not samples:
                return {}
            source_values = {
                attribute.GetName(): [
                    attribute.Get(Usd.TimeCode(sample)) for sample in samples
                ]
                for attribute in animated_attributes
            }
            cached_clip = (len(samples), source_values)
            self._skeletal_clip_cache[cache_key] = cached_clip

        sample_count, source_values = cached_clip
        source_index = min(
            sample_count - 1,
            max(0, round(float(source_ratio) * (sample_count - 1))),
        )
        joint_names = [
            str(value)
            for value in (animation.GetAttribute("joints").Get() or [])
        ]
        selected = set()
        for index, name in enumerate(joint_names):
            matches = skeletal_joint_matches(
                name,
                suffixes=joint_suffixes,
                prefixes=joint_prefixes,
            )
            if matches != bool(invert_selection):
                selected.add((index, name))
        overrides: dict[str, dict[str, Any]] = {}
        for attribute_name, values in source_values.items():
            if source_index >= len(values) or values[source_index] is None:
                continue
            sample_value = values[source_index]
            overrides[attribute_name] = {
                name: sample_value[index]
                for index, name in selected
                if index < len(sample_value)
            }
        return overrides

    def play_skeletal_animations_parallel(
        self,
        equipment_prims: list[Any],
        animation_name: str,
        *,
        duration_seconds: float,
        reverse: bool = False,
        base_pose_animation_name: str | None = None,
        animated_joint_suffixes: tuple[str, ...] = (),
        animated_joint_prefixes: tuple[str, ...] = (),
        pose_overlay_animation_name: str | None = None,
        pose_overlay_joint_suffixes: tuple[str, ...] = (),
        pose_overlay_joint_prefixes: tuple[str, ...] = (),
        frame_callback: Callable[[float], None] | None = None,
    ) -> list[str]:
        """Play the same excavator clip on several machines concurrently."""

        import omni.timeline

        timeline = omni.timeline.get_timeline_interface()
        time_codes_per_second = float(self.stage.GetTimeCodesPerSecond() or 24.0)
        start = float(timeline.get_current_time()) * time_codes_per_second
        paths: list[str] = []
        max_frames = 0
        for equipment in equipment_prims:
            joint_pose_overrides: dict[str, dict[str, Any]] = {}
            if base_pose_animation_name:
                joint_pose_overrides = self._skeletal_joint_pose_overrides(
                    equipment,
                    base_pose_animation_name,
                    animated_joint_suffixes,
                    joint_prefixes=animated_joint_prefixes,
                    invert_selection=True,
                )
                if not any(joint_pose_overrides.values()):
                    raise RuntimeError(
                        "the requested base skeleton pose could not be read: "
                        f"{base_pose_animation_name}"
                    )
            overlay_overrides = (
                self._skeletal_joint_pose_overrides(
                    equipment,
                    pose_overlay_animation_name,
                    pose_overlay_joint_suffixes,
                    joint_prefixes=pose_overlay_joint_prefixes,
                )
                if pose_overlay_animation_name
                and (pose_overlay_joint_suffixes or pose_overlay_joint_prefixes)
                else {}
            )
            if (
                pose_overlay_animation_name
                and (pose_overlay_joint_suffixes or pose_overlay_joint_prefixes)
                and not any(overlay_overrides.values())
            ):
                raise RuntimeError(
                    "the requested skeletal pose overlay did not match any joints: "
                    f"{pose_overlay_animation_name} / "
                    f"{pose_overlay_joint_suffixes or pose_overlay_joint_prefixes}"
                )
            for attribute_name, values in overlay_overrides.items():
                joint_pose_overrides.setdefault(attribute_name, {}).update(values)
            path, frames = self._author_skeletal_animation(
                equipment,
                animation_name,
                duration_seconds=duration_seconds,
                start_time_code=start,
                reverse=reverse,
                joint_pose_overrides=joint_pose_overrides or None,
            )
            if path:
                paths.append(path)
            max_frames = max(max_frames, frames)
        timeline.play()
        for frame in range(max_frames):
            if frame_callback:
                frame_callback(float(frame + 1) / float(max(1, max_frames)))
            if self._update_callback:
                self._update_callback()
        return paths

    def _bind_looping_skeletal_animation(
        self,
        equipment: Any,
        animation_name: str,
        *,
        duration_seconds: float,
    ) -> str | None:
        """Bind an authored clip and extend its samples across live physics time."""

        from pxr import Usd
        import omni.timeline

        skeleton = None
        animation = None
        wanted = animation_name.lower()
        for prim in Usd.PrimRange(equipment):
            if prim.GetTypeName() == "Skeleton" and skeleton is None:
                skeleton = prim
            if prim.GetTypeName() == "SkelAnimation" and wanted in prim.GetName().lower():
                animation = prim
        if skeleton is None or animation is None:
            return None
        relationship = skeleton.GetRelationship("skel:animationSource")
        if not relationship:
            relationship = skeleton.CreateRelationship("skel:animationSource")
        relationship.SetTargets([animation.GetPath()])

        animated_attributes = [
            attribute
            for attribute in animation.GetAttributes()
            if attribute.GetName() in {"translations", "rotations", "scales"}
            and attribute.GetNumTimeSamples() > 0
        ]
        samples = sorted(
            {
                sample
                for attribute in animated_attributes
                for sample in attribute.GetTimeSamples()
            }
        )
        if not samples:
            return str(animation.GetPath())

        # Capture referenced values before authoring local repeated samples.
        source_values = {
            attribute.GetName(): [attribute.Get(Usd.TimeCode(sample)) for sample in samples]
            for attribute in animated_attributes
        }
        timeline = omni.timeline.get_timeline_interface()
        time_codes_per_second = float(self.stage.GetTimeCodesPerSecond() or 24.0)
        start = float(timeline.get_current_time()) * time_codes_per_second
        frame_count = max(2, round(max(0.25, duration_seconds) * time_codes_per_second))
        for frame in range(frame_count + 1):
            source_index = frame % len(samples)
            destination_time = Usd.TimeCode(start + frame)
            for attribute in animated_attributes:
                value = source_values[attribute.GetName()][source_index]
                if value is not None:
                    attribute.Set(value, destination_time)
        self.stage.SetEndTimeCode(max(float(self.stage.GetEndTimeCode()), start + frame_count + 1))
        return str(animation.GetPath())

    def drive_equipment_to(
        self,
        equipment_prim_path: str,
        destination_xy: list[float],
        *,
        requested_seconds: float,
        motion_frame_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Drive a dynamic excavator using PhysX velocities and track animation.

        ``motion_frame_callback`` receives the live carrier and track pose after
        every rendered physics step.  Installation demos use it to keep a load
        attached to the excavator while preserving the normal PhysX drive path.
        """

        import math
        import omni.timeline
        import numpy as np
        from isaacsim.core.prims import SingleRigidPrim
        from pxr import Gf, Usd, UsdGeom, UsdPhysics

        try:
            from .equipment_physics import is_physical_equipment, track_contact_pose
        except ImportError:
            from equipment_physics import is_physical_equipment, track_contact_pose

        equipment = self.stage.GetPrimAtPath(equipment_prim_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"장비 Prim이 Stage에 없습니다: {equipment_prim_path}")
        if not is_physical_equipment(self.stage, equipment_prim_path):
            raise RuntimeError(
                "굴착기에 물리 궤도 충돌체가 없습니다. isaac_runner.py를 다시 시작해 "
                "장비 물리 초기화를 완료하세요."
            )
        if self._update_callback is None:
            raise RuntimeError("PhysX World step callback is not configured")

        start = track_contact_pose(self.stage, equipment_prim_path)
        max_speed = max(0.2, float(os.getenv("SITEGIT_EQUIPMENT_DRIVE_SPEED_MPS", "1.8")))
        rigid = UsdPhysics.RigidBodyAPI(equipment)
        rigid.CreateKinematicEnabledAttr(False).Set(False)
        controller = self._rigid_prim_controllers.get(equipment_prim_path)
        if controller is None:
            controller = SingleRigidPrim(
                prim_path=equipment_prim_path,
                name=f"sitegit_{equipment.GetName()}_rigid",
                reset_xform_properties=False,
            )
            controller.initialize()
            self._rigid_prim_controllers[equipment_prim_path] = controller
        if not controller._rigid_prim_view.is_physics_handle_valid():
            raise RuntimeError(f"PhysX rigid-body handle is unavailable: {equipment_prim_path}")
        root_start, _ = controller.get_world_pose()
        track_offset = np.asarray(
            [
                start["x"] - float(root_start[0]),
                start["y"] - float(root_start[1]),
                start["z"] - float(root_start[2]),
            ],
            dtype=np.float64,
        )
        destination_root = np.asarray(
            [
                float(destination_xy[0]) - track_offset[0],
                float(destination_xy[1]) - track_offset[1],
            ],
            dtype=np.float64,
        )
        initial_distance = math.hypot(
            float(destination_root[0]) - float(root_start[0]),
            float(destination_root[1]) - float(root_start[1]),
        )
        timeout = max(
            max(1.0, float(requested_seconds)),
            initial_distance / max_speed + 4.0,
        )
        timeout = min(timeout, float(os.getenv("SITEGIT_EQUIPMENT_DRIVE_TIMEOUT_S", "45")))
        track_animation = self._bind_looping_skeletal_animation(
            equipment, "TrackAnimation", duration_seconds=timeout
        )

        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        update_hz = 60.0
        tolerance = max(0.15, float(os.getenv("SITEGIT_EQUIPMENT_ARRIVAL_TOLERANCE_M", "0.35")))
        max_turn_rate = max(5.0, float(os.getenv("SITEGIT_EQUIPMENT_TURN_RATE_DPS", "38")))
        max_steps = max(1, round(timeout * update_hz))
        reached = False
        steps = 0
        for steps in range(1, max_steps + 1):
            root_position, root_orientation = controller.get_world_pose()
            to_x = float(destination_root[0]) - float(root_position[0])
            to_y = float(destination_root[1]) - float(root_position[1])
            distance = math.hypot(to_x, to_y)
            if distance <= tolerance:
                reached = True
                break
            target_x, target_y = to_x / distance, to_y / distance

            quaternion = Gf.Quatd(
                float(root_orientation[0]),
                Gf.Vec3d(
                    float(root_orientation[1]),
                    float(root_orientation[2]),
                    float(root_orientation[3]),
                ),
            )
            # The source asset's boom/front direction is local +Z.  The root's
            # Y-up to Z-up normalization maps it to site -Y at startup.
            forward = quaternion.Transform(Gf.Vec3d(0.0, 0.0, 1.0))
            forward_length = math.hypot(float(forward[0]), float(forward[1]))
            if forward_length <= 1e-6:
                forward_x, forward_y = target_x, target_y
            else:
                forward_x = float(forward[0]) / forward_length
                forward_y = float(forward[1]) / forward_length
            cross = forward_x * target_y - forward_y * target_x
            dot = max(-1.0, min(1.0, forward_x * target_x + forward_y * target_y))
            heading_error = math.atan2(cross, dot)
            angular_speed = max(
                -max_turn_rate,
                min(max_turn_rate, math.degrees(heading_error) * 2.2),
            )
            alignment = max(0.0, math.cos(heading_error))
            speed = min(max_speed, max(0.15, distance * 1.2)) * max(0.12, alignment)
            previous_velocity = controller.get_linear_velocity()
            controller.set_linear_velocity(
                np.asarray(
                    [
                        float(forward_x * speed),
                        float(forward_y * speed),
                        float(previous_velocity[2]),
                    ],
                    dtype=np.float32,
                )
            )
            controller.set_angular_velocity(
                np.asarray([0.0, 0.0, math.radians(angular_speed)], dtype=np.float32)
            )
            self._update_callback()
            if motion_frame_callback is not None:
                callback_position, callback_orientation = controller.get_world_pose()
                motion_frame_callback(
                    {
                        "root_position": [float(value) for value in callback_position],
                        "root_orientation_wxyz": [
                            float(value) for value in callback_orientation
                        ],
                        "track_position": [
                            float(callback_position[index] + track_offset[index])
                            for index in range(3)
                        ],
                    }
                )

        controller.set_linear_velocity(np.zeros(3, dtype=np.float32))
        controller.set_angular_velocity(np.zeros(3, dtype=np.float32))
        for _ in range(12):
            self._update_callback()
        root_end, root_end_orientation = controller.get_world_pose()
        end = {
            "x": float(root_end[0] + track_offset[0]),
            "y": float(root_end[1] + track_offset[1]),
            "z": float(root_end[2] + track_offset[2]),
        }
        remaining = math.hypot(
            float(destination_xy[0]) - end["x"],
            float(destination_xy[1]) - end["y"],
        )
        blocked_distance = max(
            tolerance,
            float(os.getenv("SITEGIT_EQUIPMENT_BLOCKED_DISTANCE_M", "1.0")),
        )
        if not reached and remaining > blocked_distance:
            raise RuntimeError(
                f"굴착기가 물리 이동 중 목표 {remaining:.2f}m 앞에서 멈췄습니다. "
                "지형 경사나 충돌 장애물을 확인하세요."
            )
        equipment.SetCustomDataByKey("sitegitEquipmentAnchor", dict(end))
        return {
            "mode": "physx-track-drive",
            "start_track_pose": start,
            "end_track_pose": end,
            "destination_xy": [float(destination_xy[0]), float(destination_xy[1])],
            "remaining_distance_m": float(remaining),
            "arrival_tolerance_m": float(tolerance),
            "blocked_distance_m": float(blocked_distance),
            "arrived_within_working_range": bool(remaining <= blocked_distance),
            "steps": steps,
            "track_animation_prim_path": track_animation,
            "root_start_position": [float(value) for value in root_start],
            "root_end_position": [float(value) for value in root_end],
            "root_end_orientation_wxyz": [float(value) for value in root_end_orientation],
        }

    def face_equipment_toward(
        self,
        equipment_prim_path: str,
        target_xy: list[float],
        *,
        motion_frame_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Rotate the physical carrier until its boom faces the target."""

        import math
        import omni.timeline
        import numpy as np
        from pxr import Gf

        try:
            from .equipment_physics import track_contact_pose
        except ImportError:
            from equipment_physics import track_contact_pose

        if self._update_callback is None:
            raise RuntimeError("PhysX World step callback is not configured")
        controller = self._rigid_prim_controllers.get(equipment_prim_path)
        if controller is None or not controller._rigid_prim_view.is_physics_handle_valid():
            raise RuntimeError(
                f"굴착기 물리 제어기가 준비되지 않았습니다: {equipment_prim_path}"
            )

        start_track_pose = track_contact_pose(self.stage, equipment_prim_path)
        callback_root_start, _ = controller.get_world_pose()
        callback_track_offset = [
            float(start_track_pose[axis]) - float(callback_root_start[index])
            for index, axis in enumerate(("x", "y", "z"))
        ]
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        tolerance_degrees = max(
            1.0, float(os.getenv("SITEGIT_EQUIPMENT_FACING_TOLERANCE_DEG", "3"))
        )
        max_turn_rate = max(
            5.0, float(os.getenv("SITEGIT_EQUIPMENT_TURN_RATE_DPS", "38"))
        )
        timeout_seconds = max(
            1.0, float(os.getenv("SITEGIT_EQUIPMENT_FACE_TIMEOUT_S", "8"))
        )
        aligned = False
        heading_error_degrees = 180.0
        steps = 0
        for steps in range(1, round(timeout_seconds * 60.0) + 1):
            root_position, root_orientation = controller.get_world_pose()
            to_x = float(target_xy[0]) - float(root_position[0])
            to_y = float(target_xy[1]) - float(root_position[1])
            target_length = math.hypot(to_x, to_y)
            if target_length <= 1e-6:
                raise RuntimeError("굴착기와 굴착 대상의 XY 위치가 동일합니다.")
            target_x, target_y = to_x / target_length, to_y / target_length
            quaternion = Gf.Quatd(
                float(root_orientation[0]),
                Gf.Vec3d(
                    float(root_orientation[1]),
                    float(root_orientation[2]),
                    float(root_orientation[3]),
                ),
            )
            forward = quaternion.Transform(Gf.Vec3d(0.0, 0.0, 1.0))
            forward_length = math.hypot(float(forward[0]), float(forward[1]))
            if forward_length <= 1e-6:
                raise RuntimeError("굴착기 전면 방향을 계산할 수 없습니다.")
            forward_x = float(forward[0]) / forward_length
            forward_y = float(forward[1]) / forward_length
            cross = forward_x * target_y - forward_y * target_x
            dot_value = max(
                -1.0,
                min(1.0, forward_x * target_x + forward_y * target_y),
            )
            heading_error = math.atan2(cross, dot_value)
            heading_error_degrees = math.degrees(heading_error)
            if abs(heading_error_degrees) <= tolerance_degrees:
                aligned = True
                break
            angular_speed = max(
                -max_turn_rate,
                min(max_turn_rate, heading_error_degrees * 2.2),
            )
            previous_velocity = controller.get_linear_velocity()
            controller.set_linear_velocity(
                np.asarray([0.0, 0.0, float(previous_velocity[2])], dtype=np.float32)
            )
            controller.set_angular_velocity(
                np.asarray([0.0, 0.0, math.radians(angular_speed)], dtype=np.float32)
            )
            self._update_callback()
            if motion_frame_callback is not None:
                callback_position, callback_orientation = controller.get_world_pose()
                motion_frame_callback(
                    {
                        "root_position": [float(value) for value in callback_position],
                        "root_orientation_wxyz": [
                            float(value) for value in callback_orientation
                        ],
                        "track_position": [
                            float(callback_position[index] + callback_track_offset[index])
                            for index in range(3)
                        ],
                    }
                )

        controller.set_linear_velocity(np.zeros(3, dtype=np.float32))
        controller.set_angular_velocity(np.zeros(3, dtype=np.float32))
        for _ in range(12):
            self._update_callback()
        root_end, root_end_orientation = controller.get_world_pose()
        end_track_pose = track_contact_pose(self.stage, equipment_prim_path)
        if not aligned and abs(heading_error_degrees) > 12.0:
            raise RuntimeError(
                f"굴착기가 작업 대상을 바라보도록 회전하지 못했습니다: "
                f"오차 {heading_error_degrees:.1f}°"
            )
        return {
            "mode": "physx-face-target",
            "target_xy": [float(target_xy[0]), float(target_xy[1])],
            "aligned": bool(aligned or abs(heading_error_degrees) <= 12.0),
            "heading_error_degrees": float(heading_error_degrees),
            "tolerance_degrees": float(tolerance_degrees),
            "steps": int(steps),
            "end_track_pose": end_track_pose,
            "root_end_position": [float(value) for value in root_end],
            "root_end_orientation_wxyz": [
                float(value) for value in root_end_orientation
            ],
        }

    def excavate_prim(self, instruction: dict[str, Any]) -> dict[str, Any]:
        """Excavate a soil Mesh, move its volume, and return exact Stage changes."""
        from pxr import UsdGeom

        params = instruction.get("params") or {}
        equipment_path = str(params.get("equipment_prim_path") or "")
        target_path = str(params.get("target_prim_path") or "")
        equipment = self.stage.GetPrimAtPath(equipment_path)
        target = self.stage.GetPrimAtPath(target_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"장비 Prim이 Stage에 없습니다: {equipment_path}")
        if not target.IsValid() or not target.IsActive():
            raise RuntimeError(f"굴착 대상 Prim이 Stage에 없습니다: {target_path}")
        allowed_roots = _path_list(
            "SITEGIT_DIGGABLE_ROOTS", "/World/Diggable"
        )
        if not any(target_path == root or target_path.startswith(root + "/") for root in allowed_roots):
            raise RuntimeError(f"등록된 굴착 대상 루트 밖의 Prim입니다: {target_path}")

        equipment_start, equipment_size = self._world_bounds(equipment)
        try:
            from .equipment_physics import (
                is_physical_equipment,
                track_contact_pose,
                track_visual_bounds,
            )
        except ImportError:
            from equipment_physics import (
                is_physical_equipment,
                track_contact_pose,
                track_visual_bounds,
            )

        if is_physical_equipment(self.stage, equipment_path):
            equipment_start = track_contact_pose(self.stage, equipment_path)
            track_bounds = track_visual_bounds(self.stage, equipment_path)
            track_size = {
                axis: float(track_bounds["max"][index] - track_bounds["min"][index])
                for index, axis in enumerate(("x", "y", "z"))
            }
        else:
            track_size = dict(equipment_size)
        target_position, target_size = self._world_bounds(target)
        max_target_span = float(os.getenv("SITEGIT_MAX_EXCAVATION_TARGET_SPAN_M", "25"))
        target_span = max(float(target_size["x"]), float(target_size["y"]))
        if target_span > max_target_span:
            raise RuntimeError(
                f"굴착 대상 Prim의 최대 폭이 {target_span:.1f}m입니다. "
                f"전체 현장 Mesh 삭제를 막기 위해 {max_target_span:.0f}m 이하의 "
                "독립된 토사 Prim만 실행할 수 있습니다."
            )
        meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(self.stage) or 1.0)
        approach_plan = excavation_approach_plan(
            equipment_start,
            target_position,
            target_size,
            track_size,
            float(params.get("approach_distance_m", 3.0)) / meters_per_unit,
            float(os.getenv("SITEGIT_EXCAVATION_TRACK_MARGIN_M", "0.75"))
            / meters_per_unit,
        )
        destination_xy = list(approach_plan["destination_xy"])
        seconds = float(params.get("animation_seconds", 3.0))
        animation_paths: list[str] = []
        drive_result = self.drive_equipment_to(
            equipment_path,
            destination_xy,
            requested_seconds=seconds,
        )
        track_animation = drive_result.get("track_animation_prim_path")
        if track_animation:
            animation_paths.append(str(track_animation))

        facing_result = self.face_equipment_toward(
            equipment_path,
            list(approach_plan["target_xy"]),
        )
        drive_result["facing"] = facing_result
        drive_result["end_track_pose"] = dict(facing_result["end_track_pose"])
        drive_result["root_end_position"] = list(facing_result["root_end_position"])
        drive_result["root_end_orientation_wxyz"] = list(
            facing_result["root_end_orientation_wxyz"]
        )

        self._notify_excavation_prepared(
            {
                "equipment_prim_path": equipment_path,
                "target_prim_path": target_path,
                "equipment_pose": dict(facing_result["end_track_pose"]),
                "target_position": dict(target_position),
                "target_bounds_size": dict(target_size),
                "approach_plan": dict(approach_plan),
                "locomotion": dict(drive_result),
                "facing": dict(facing_result),
            }
        )

        animation_phase_seconds = max(0.5, seconds / 3.0)
        for animation_name, duration in (
            ("ArmOut", animation_phase_seconds),
            ("ArmDig", max(0.75, seconds)),
            ("ArmInDig", animation_phase_seconds),
        ):
            animation_path = self._play_skeletal_animation(
                equipment,
                animation_name,
                duration_seconds=duration,
            )
            if animation_path:
                animation_paths.append(animation_path)
        cut_ratio = float(
            params.get(
                "excavation_cut_ratio",
                os.getenv("SITEGIT_EXCAVATION_CUT_RATIO", "0.9"),
            )
        )
        terrain_deformation = self._deform_diggable_mesh(
            target,
            cut_ratio=cut_ratio,
        )
        target_removed = not bool(terrain_deformation.get("available"))
        if target_removed:
            # Compatibility fallback for an old non-Mesh diggable target.
            target.SetActive(False)

        swing_to_dump = bool(params.get("swing_to_dump", False))
        if swing_to_dump:
            swing_animation = self._play_skeletal_animation(
                equipment,
                "Rotate90",
                duration_seconds=max(0.75, animation_phase_seconds),
            )
            if swing_animation:
                animation_paths.append(swing_animation)

        dump_animation = self._play_skeletal_animation(
            equipment,
            "ArmDump",
            duration_seconds=max(0.75, animation_phase_seconds),
        )
        if dump_animation:
            animation_paths.append(dump_animation)

        moved_soil = None
        if terrain_deformation.get("available"):
            moved_soil = self._create_moved_soil_pile(
                target=target,
                target_size=target_size,
                equipment_position=dict(drive_result["end_track_pose"]),
                approach_plan=approach_plan,
                removed_volume_m3=float(
                    terrain_deformation.get("removed_volume_m3") or 0.0
                ),
                dump_side=float(params.get("dump_side", 1.0)),
            )

        if swing_to_dump:
            return_swing_animation = self._play_skeletal_animation(
                equipment,
                "Rotate90",
                duration_seconds=max(0.75, animation_phase_seconds),
                reverse=True,
            )
            if return_swing_animation:
                animation_paths.append(return_swing_animation)

        # Removing a supporting soil Prim does not automatically wake a rigid
        # body that PhysX has put to sleep.  Wake it with a tiny downward
        # velocity and continue the live timeline until it reaches the terrain
        # below instead of leaving the excavator frozen in mid-air.
        import numpy as np
        import omni.timeline

        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        controller = self._rigid_prim_controllers.get(equipment_path)
        if controller is not None and target_removed:
            velocity = controller.get_linear_velocity()
            controller.set_linear_velocity(
                np.asarray(
                    [float(velocity[0]), float(velocity[1]), min(-0.05, float(velocity[2]))],
                    dtype=np.float32,
                )
            )
        settle_limit = max(
            30,
            int(os.getenv("SITEGIT_POST_EXCAVATION_SETTLE_FRAMES", "180")),
        )
        stable_frames = 0
        settle_frames = 0
        if self._update_callback:
            for settle_frames in range(1, settle_limit + 1):
                self._update_callback()
                if controller is None or settle_frames < 30:
                    continue
                vertical_speed = abs(float(controller.get_linear_velocity()[2]))
                stable_frames = stable_frames + 1 if vertical_speed < 0.05 else 0
                if stable_frames >= 12:
                    break
        equipment_end = dict(drive_result["end_track_pose"])
        post_excavation_drop_m = 0.0
        if controller is not None:
            root_after, _ = controller.get_world_pose()
            root_before = drive_result["root_end_position"]
            contact_before = drive_result["end_track_pose"]
            equipment_end = {
                axis: float(root_after[index])
                + float(contact_before[axis])
                - float(root_before[index])
                for index, axis in enumerate(("x", "y", "z"))
            }
            post_excavation_drop_m = max(
                0.0,
                float(contact_before["z"]) - float(equipment_end["z"]),
            )
            equipment.SetCustomDataByKey("sitegitEquipmentAnchor", dict(equipment_end))
        target_after = self.stage.GetPrimAtPath(target_path)
        if target_after.IsValid() and target_after.IsActive():
            target_after_position, target_after_size = self._world_bounds(target_after)
        else:
            target_after_position, target_after_size = target_position, target_size
        map_changes: list[dict[str, Any]] = []
        if terrain_deformation.get("available"):
            map_changes.append(
                {
                    "action": "upsert",
                    "type": "deformed_soil",
                    "label": str(
                        target.GetCustomDataByKey("sitegitDiggableId")
                        or target.GetName()
                    ),
                    "color": str(
                        target.GetCustomDataByKey("sitegitDisplayColor") or "#6B4F2A"
                    ),
                    "prim_path": target_path,
                    "position": target_after_position,
                    "size": target_after_size,
                    "geometry": terrain_deformation.get("geometry"),
                }
            )
            if moved_soil:
                map_changes.append(
                    {
                        "action": "upsert",
                        "type": "soil_deposit",
                        "label": "굴착 이동 토사",
                        "color": str(
                            target.GetCustomDataByKey("sitegitDisplayColor") or "#6B4F2A"
                        ),
                        "prim_path": moved_soil["prim_path"],
                        "position": moved_soil["position"],
                        "size": moved_soil["size"],
                        "geometry": moved_soil.get("geometry"),
                    }
                )
        else:
            map_changes.append(
                {
                    "action": "remove",
                    "type": "removed_prim",
                    "label": str(target.GetName()),
                    "prim_path": target_path,
                    "position": target_position,
                    "size": target_size,
                }
            )
        return {
            "operation": "excavate_prim",
            "equipment_prim_path": equipment_path,
            "target_prim_path": target_path,
            "equipment_start_position": equipment_start,
            "equipment_end_position": equipment_end,
            "equipment_bounds_size": equipment_size,
            "target_position": target_position,
            "target_bounds_size": target_size,
            "target_after_position": target_after_position,
            "target_after_bounds_size": target_after_size,
            "target_active_before": True,
            "target_active_after": bool(target_after.IsActive()) if target_after.IsValid() else False,
            "terrain_deformation": terrain_deformation,
            "moved_soil": moved_soil,
            "map_changes": map_changes,
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "animation": (
                "authored-excavator-clips" if animation_paths else "equipment-root-approach"
            ),
            "animation_prim_paths": animation_paths,
            "swing_to_dump": swing_to_dump,
            "excavation_cut_ratio": float(
                terrain_deformation.get("cut_ratio") or cut_ratio
            ),
            "approach_plan": approach_plan,
            "facing": facing_result,
            "locomotion": drive_result,
            "post_excavation_settle_frames": int(settle_frames),
            "post_excavation_drop_m": float(post_excavation_drop_m),
        }


def _hex_to_gf_color(value: str):
    from pxr import Gf

    text = str(value).lstrip("#")
    if len(text) != 6:
        return Gf.Vec3f(0.94, 0.71, 0.16)
    return Gf.Vec3f(
        int(text[0:2], 16) / 255.0, int(text[2:4], 16) / 255.0, int(text[4:6], 16) / 255.0
    )


class SimulatedCubeBridge(IsaacBridge):
    """Isaac Sim 없이 배관만 검증하기 위한 대체 구현.

    Stage를 만들지 않고 지시값을 그대로 되돌려줍니다. 실제 Isaac 실행이 아니므로
    이 브릿지로 만든 결과는 "Isaac이 확인한 값"이 아닙니다.
    """

    def __init__(self):
        super().__init__(stage=None)

    def place_cube(self, instruction: dict[str, Any]) -> dict[str, Any]:
        params = instruction.get("params") or {}
        position = params.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
        size = params.get("size") or {"x": 4.0, "y": 4.0, "z": 4.0}
        return {
            "placed_position": position,
            "placed_size": size,
            "prim_path": f"{SITEGIT_ROOT_PATH}/cube_{str(instruction.get('id', 'unknown'))[:8]}",
            "simulator": "simulated-cube-bridge",
            "source": "echo",
        }

    def excavate_prim(self, instruction: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("실제 Prim 굴착은 Isaac Sim Stage에서만 실행할 수 있습니다.")


def _path_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
