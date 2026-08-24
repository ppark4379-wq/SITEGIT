"""Geometry and planning helpers for the SiteGit pipe-installation demo.

The real project will eventually reference a surveyed pipe catalogue and a
dedicated lifting-machine asset.  The current demo keeps that boundary clean:
it converts the canonical design centerline into deterministic hollow pipe
segments and authors only the pipe geometry required by Isaac Sim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Callable, Iterable, Sequence


PIPE_INSTALLATION_ROOT_PATH = "/World/Installed/Pipeline"
PIPE_MATERIAL_PATH = "/World/Looks/SiteGitConcretePipe"


@dataclass(frozen=True)
class PipeSegmentPlan:
    """One installable pipe piece expressed in the SiteGit world frame."""

    segment_id: str
    prim_path: str
    station_start_m: float
    station_end_m: float
    start_xyz: tuple[float, float, float]
    end_xyz: tuple[float, float, float]
    center_xyz: tuple[float, float, float]
    direction_xyz: tuple[float, float, float]
    length_m: float
    outside_radius_m: float
    inside_radius_m: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable installation-plan record."""

        return asdict(self)


def _point_value(point: Any, name: str, default: float = 0.0) -> float:
    if isinstance(point, dict):
        return float(point.get(name, default))
    return float(getattr(point, name, default))


def trim_centerline_terminals(
    centerline: Sequence[Any],
    terminal_inset_m: float,
) -> list[dict[str, float]]:
    """Trim non-excavated terminal caps from a station-based centerline.

    The demolition backfill deliberately extends onto intact ground at both
    ends so the initial soil volume has closed caps. Installed pipe must stop
    inside that footprint, otherwise its end sections sit above the original
    terrain. This helper interpolates exact inset endpoints while preserving
    all design vertices between them.
    """

    if len(centerline) < 2:
        raise ValueError("pipe centerline requires at least two points")
    inset = float(terminal_inset_m)
    if inset < 0:
        raise ValueError("terminal_inset_m must not be negative")
    points = [
        {
            "station_m": _point_value(point, "station_m"),
            "x": _point_value(point, "x"),
            "y": _point_value(point, "y"),
            "z": _point_value(point, "z"),
            "width_m": _point_value(point, "width_m"),
        }
        for point in centerline
    ]
    start_station = points[0]["station_m"] + inset
    end_station = points[-1]["station_m"] - inset
    if end_station <= start_station:
        raise ValueError("terminal inset removes the complete pipe centerline")

    def interpolate(station: float) -> dict[str, float]:
        for first, second in zip(points, points[1:]):
            if first["station_m"] <= station <= second["station_m"]:
                span = second["station_m"] - first["station_m"]
                ratio = 0.0 if abs(span) <= 1e-9 else (
                    station - first["station_m"]
                ) / span
                return {
                    "station_m": station,
                    **{
                        key: first[key] + (second[key] - first[key]) * ratio
                        for key in ("x", "y", "z", "width_m")
                    },
                }
        raise ValueError(f"station is outside the centerline: {station}")

    trimmed = [interpolate(start_station)]
    trimmed.extend(
        point
        for point in points
        if start_station < point["station_m"] < end_station
    )
    trimmed.append(interpolate(end_station))
    return trimmed


def clip_centerline_station_range(
    centerline: Sequence[Any],
    station_start_m: float,
    station_end_m: float,
) -> list[dict[str, float]]:
    """Return the exact part of a centerline inside an excavated station range.

    The first and last profiles of the demolition scenario are terrain-closing
    caps on intact grade.  They are deliberately asymmetric, so a single
    terminal inset cannot describe the actually open trench.  This helper
    interpolates both requested limits and preserves every design vertex
    between them.
    """

    if len(centerline) < 2:
        raise ValueError("pipe centerline requires at least two points")
    points = [
        {
            "station_m": _point_value(point, "station_m"),
            "x": _point_value(point, "x"),
            "y": _point_value(point, "y"),
            "z": _point_value(point, "z"),
            "width_m": _point_value(point, "width_m"),
        }
        for point in centerline
    ]
    route_start = points[0]["station_m"]
    route_end = points[-1]["station_m"]
    start = float(station_start_m)
    end = float(station_end_m)
    if start < route_start or end > route_end or end <= start:
        raise ValueError(
            "installation station range must be ordered and inside the centerline"
        )

    def interpolate(station: float) -> dict[str, float]:
        for first, second in zip(points, points[1:]):
            if first["station_m"] <= station <= second["station_m"]:
                span = second["station_m"] - first["station_m"]
                ratio = 0.0 if abs(span) <= 1e-9 else (
                    station - first["station_m"]
                ) / span
                return {
                    "station_m": station,
                    **{
                        key: first[key] + (second[key] - first[key]) * ratio
                        for key in ("x", "y", "z", "width_m")
                    },
                }
        raise ValueError(f"station is outside the centerline: {station}")

    clipped = [interpolate(start)]
    clipped.extend(point for point in points if start < point["station_m"] < end)
    clipped.append(interpolate(end))
    return clipped


def nearest_centerline_station(
    centerline: Sequence[Any],
    x: float,
    y: float,
) -> float:
    """Project an XY position onto a station-based centerline."""

    if len(centerline) < 2:
        raise ValueError("pipe centerline requires at least two points")
    nearest_distance_squared = math.inf
    nearest_station = _point_value(centerline[0], "station_m")
    for first, second in zip(centerline, centerline[1:]):
        x0, y0 = _point_value(first, "x"), _point_value(first, "y")
        x1, y1 = _point_value(second, "x"), _point_value(second, "y")
        dx, dy = x1 - x0, y1 - y0
        length_squared = dx * dx + dy * dy
        ratio = 0.0 if length_squared <= 1e-12 else max(
            0.0,
            min(1.0, ((float(x) - x0) * dx + (float(y) - y0) * dy) / length_squared),
        )
        projected_x = x0 + dx * ratio
        projected_y = y0 + dy * ratio
        distance_squared = (
            (float(x) - projected_x) ** 2 + (float(y) - projected_y) ** 2
        )
        if distance_squared < nearest_distance_squared:
            nearest_distance_squared = distance_squared
            station0 = _point_value(first, "station_m")
            station1 = _point_value(second, "station_m")
            nearest_station = station0 + (station1 - station0) * ratio
    return float(nearest_station)


def terminal_grade_clamped_floor_sampler(
    centerline: Sequence[Any],
    floor_height: Callable[[float, float, float], float],
    *,
    grade_start_station_m: float,
    grade_end_station_m: float,
) -> Callable[[float, float, float], float]:
    """Keep terminal pipe bedding below intact terrain closing the trench.

    The route can remain close to its drawing length while its terminal pieces
    pass under the two intact-grade caps.  Interior stations still use the
    measured photogrammetry floor unchanged.
    """

    grade_points = clip_centerline_station_range(
        centerline,
        grade_start_station_m,
        grade_end_station_m,
    )
    start_point, end_point = grade_points[0], grade_points[-1]
    start_floor = float(
        floor_height(start_point["x"], start_point["y"], start_point["z"])
    )
    end_floor = float(
        floor_height(end_point["x"], end_point["y"], end_point["z"])
    )

    def sample(x: float, y: float, fallback: float) -> float:
        measured = float(floor_height(float(x), float(y), float(fallback)))
        station = nearest_centerline_station(centerline, x, y)
        if station < float(grade_start_station_m):
            return min(measured, start_floor)
        if station > float(grade_end_station_m):
            return min(measured, end_floor)
        return measured

    return sample


def build_pipe_segment_plans(
    centerline: Sequence[Any],
    *,
    floor_height: Callable[[float, float, float], float],
    outside_diameter_m: float = 1.2,
    wall_thickness_m: float = 0.12,
    maximum_segment_length_m: float = 4.0,
    bedding_clearance_m: float = 0.08,
    root_path: str = PIPE_INSTALLATION_ROOT_PATH,
) -> list[PipeSegmentPlan]:
    """Split a design polyline into pipe pieces seated on the trench floor."""

    if len(centerline) < 2:
        raise ValueError("pipe centerline requires at least two points")
    if outside_diameter_m <= 0:
        raise ValueError("outside_diameter_m must be greater than zero")
    if not 0 < wall_thickness_m < outside_diameter_m * 0.5:
        raise ValueError("wall_thickness_m must be smaller than the pipe radius")
    if maximum_segment_length_m <= 0:
        raise ValueError("maximum_segment_length_m must be greater than zero")

    outside_radius = outside_diameter_m * 0.5
    inside_radius = outside_radius - wall_thickness_m
    plans: list[PipeSegmentPlan] = []
    index = 0
    for raw_start, raw_end in zip(centerline, centerline[1:]):
        start_x = _point_value(raw_start, "x")
        start_y = _point_value(raw_start, "y")
        end_x = _point_value(raw_end, "x")
        end_y = _point_value(raw_end, "y")
        start_station = _point_value(raw_start, "station_m")
        end_station = _point_value(raw_end, "station_m")
        plan_length = math.hypot(end_x - start_x, end_y - start_y)
        if plan_length <= 1e-6:
            continue
        piece_count = max(1, math.ceil(plan_length / maximum_segment_length_m))
        for piece_index in range(piece_count):
            start_fraction = piece_index / piece_count
            end_fraction = (piece_index + 1) / piece_count
            x0 = start_x + (end_x - start_x) * start_fraction
            y0 = start_y + (end_y - start_y) * start_fraction
            x1 = start_x + (end_x - start_x) * end_fraction
            y1 = start_y + (end_y - start_y) * end_fraction
            fallback_z0 = _point_value(raw_start, "z")
            fallback_z1 = _point_value(raw_end, "z")
            floor_z0 = float(floor_height(x0, y0, fallback_z0))
            floor_z1 = float(floor_height(x1, y1, fallback_z1))
            z0 = floor_z0 + outside_radius + bedding_clearance_m
            z1 = floor_z1 + outside_radius + bedding_clearance_m
            dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if length <= 1e-6:
                continue
            index += 1
            station0 = start_station + (end_station - start_station) * start_fraction
            station1 = start_station + (end_station - start_station) * end_fraction
            plans.append(
                PipeSegmentPlan(
                    segment_id=f"PIPE-{index:03d}",
                    prim_path=f"{root_path}/PIPE_{index:03d}",
                    station_start_m=station0,
                    station_end_m=station1,
                    start_xyz=(x0, y0, z0),
                    end_xyz=(x1, y1, z1),
                    center_xyz=((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5),
                    direction_xyz=(dx / length, dy / length, dz / length),
                    length_m=length,
                    outside_radius_m=outside_radius,
                    inside_radius_m=inside_radius,
                )
            )
    if not plans:
        raise ValueError("pipe centerline produced no installable segments")
    return plans


def hollow_pipe_mesh_data(
    length_m: float,
    outside_radius_m: float,
    inside_radius_m: float,
    *,
    radial_segments: int = 32,
) -> dict[str, list[Any]]:
    """Build a watertight open-bore tube aligned with the local Z axis."""

    if length_m <= 0:
        raise ValueError("length_m must be greater than zero")
    if not 0 < inside_radius_m < outside_radius_m:
        raise ValueError("pipe radii must satisfy 0 < inside < outside")
    if radial_segments < 8:
        raise ValueError("radial_segments must be at least eight")

    half_length = length_m * 0.5
    points: list[tuple[float, float, float]] = []
    for radius, z_value in (
        (outside_radius_m, -half_length),
        (outside_radius_m, half_length),
        (inside_radius_m, -half_length),
        (inside_radius_m, half_length),
    ):
        for index in range(radial_segments):
            angle = 2.0 * math.pi * index / radial_segments
            points.append((radius * math.cos(angle), radius * math.sin(angle), z_value))

    outer_start = 0
    outer_end = radial_segments
    inner_start = radial_segments * 2
    inner_end = radial_segments * 3
    counts: list[int] = []
    indices: list[int] = []
    for index in range(radial_segments):
        following = (index + 1) % radial_segments
        # Outside wall.
        indices.extend(
            (
                outer_start + index,
                outer_start + following,
                outer_end + following,
                outer_end + index,
            )
        )
        counts.append(4)
        # Inside wall, with reversed winding.
        indices.extend(
            (
                inner_start + index,
                inner_end + index,
                inner_end + following,
                inner_start + following,
            )
        )
        counts.append(4)
        # Start and end annuli close the concrete wall without blocking the bore.
        indices.extend(
            (
                outer_start + index,
                inner_start + index,
                inner_start + following,
                outer_start + following,
            )
        )
        counts.append(4)
        indices.extend(
            (
                outer_end + index,
                outer_end + following,
                inner_end + following,
                inner_end + index,
            )
        )
        counts.append(4)

    return {
        "points": points,
        "face_vertex_counts": counts,
        "face_vertex_indices": indices,
    }


def total_pipe_length(plans: Iterable[PipeSegmentPlan]) -> float:
    """Return the summed three-dimensional length of pipe pieces."""

    return sum(float(plan.length_m) for plan in plans)


def total_station_length(plans: Iterable[PipeSegmentPlan]) -> float:
    """Return design chainage coverage independent of vertical route slope."""

    return sum(
        max(0.0, float(plan.station_end_m) - float(plan.station_start_m))
        for plan in plans
    )


def select_workfront_pipe_plans(
    plans: Sequence[PipeSegmentPlan],
    workfronts: Sequence[dict[str, Any]],
) -> list[PipeSegmentPlan]:
    """Select one representative pipe piece inside each construction front.

    The standalone handling demo deliberately installs three pieces instead of
    silently completing the whole design route.  Each selected piece is the
    closest available segment to its work-front station midpoint.
    """

    if not plans:
        raise ValueError("at least one pipe plan is required")
    selected: list[PipeSegmentPlan] = []
    used_paths: set[str] = set()
    for index, workfront in enumerate(workfronts, 1):
        station_start = float(workfront.get("station_start_m", 0.0))
        station_end = float(workfront.get("station_end_m", station_start))
        midpoint = (station_start + station_end) * 0.5
        candidates = [
            plan
            for plan in plans
            if plan.prim_path not in used_paths
            and plan.station_end_m > station_start
            and plan.station_start_m < station_end
        ]
        if not candidates:
            raise ValueError(f"work front {index} contains no pipe segment")
        chosen = min(
            candidates,
            key=lambda plan: abs(
                (plan.station_start_m + plan.station_end_m) * 0.5 - midpoint
            ),
        )
        selected.append(chosen)
        used_paths.add(chosen.prim_path)
    return selected


def build_workfront_pipe_plans(
    centerline: Sequence[Any],
    workfronts: Sequence[dict[str, Any]],
    *,
    floor_height: Callable[[float, float, float], float],
    outside_diameter_m: float = 1.2,
    wall_thickness_m: float = 0.12,
    bedding_clearance_m: float = 0.08,
    root_path: str = PIPE_INSTALLATION_ROOT_PATH,
) -> list[PipeSegmentPlan]:
    """Create three connected demonstration pipes, one per work front.

    Work-front boundaries in the canonical plan coincide with surveyed
    centerline stations. Interpolating those exact boundaries guarantees that
    the three pipe endpoints meet with no gap when lowered into the trench.
    """

    if len(centerline) < 2:
        raise ValueError("pipe centerline requires at least two points")
    if not workfronts:
        raise ValueError("at least one work front is required")
    if outside_diameter_m <= 0:
        raise ValueError("outside_diameter_m must be greater than zero")
    outside_radius = float(outside_diameter_m) * 0.5
    inside_radius = outside_radius - float(wall_thickness_m)
    if inside_radius <= 0:
        raise ValueError("wall_thickness_m must be smaller than the pipe radius")

    stations = [
        (
            _point_value(point, "station_m"),
            _point_value(point, "x"),
            _point_value(point, "y"),
            _point_value(point, "z"),
        )
        for point in centerline
    ]

    def point_at_station(station: float) -> tuple[float, float, float]:
        if station <= stations[0][0]:
            _, x, y, fallback_z = stations[0]
        elif station >= stations[-1][0]:
            _, x, y, fallback_z = stations[-1]
        else:
            for first, second in zip(stations, stations[1:]):
                if first[0] <= station <= second[0]:
                    span = max(1e-9, second[0] - first[0])
                    ratio = (station - first[0]) / span
                    x = first[1] + (second[1] - first[1]) * ratio
                    y = first[2] + (second[2] - first[2]) * ratio
                    fallback_z = first[3] + (second[3] - first[3]) * ratio
                    break
            else:  # pragma: no cover - guarded by range checks above
                raise ValueError(f"station is outside the centerline: {station}")
        z = float(floor_height(x, y, fallback_z)) + outside_radius + bedding_clearance_m
        return float(x), float(y), float(z)

    plans: list[PipeSegmentPlan] = []
    for index, workfront in enumerate(workfronts, 1):
        station_start = float(workfront["station_start_m"])
        station_end = float(workfront["station_end_m"])
        if station_end <= station_start:
            raise ValueError(f"work front {index} has an invalid station range")
        start = point_at_station(station_start)
        end = point_at_station(station_end)
        delta = tuple(end[axis] - start[axis] for axis in range(3))
        length = math.sqrt(sum(value * value for value in delta))
        if length <= 1e-6:
            raise ValueError(f"work front {index} produced a zero-length pipe")
        plans.append(
            PipeSegmentPlan(
                segment_id=f"PIPE-WF-{index:02d}",
                prim_path=f"{root_path}/PIPE_WF_{index:02d}",
                station_start_m=station_start,
                station_end_m=station_end,
                start_xyz=start,
                end_xyz=end,
                center_xyz=tuple((start[axis] + end[axis]) * 0.5 for axis in range(3)),
                direction_xyz=tuple(value / length for value in delta),
                length_m=length,
                outside_radius_m=outside_radius,
                inside_radius_m=inside_radius,
            )
        )
    return plans


def create_concrete_pipe_material(stage: Any) -> Any:
    """Create the neutral concrete material used by generated pipe pieces."""

    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(stage, Sdf.Path(PIPE_MATERIAL_PATH))
    shader = UsdShade.Shader.Define(
        stage, Sdf.Path(f"{PIPE_MATERIAL_PATH}/PreviewSurface")
    )
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.38, 0.40, 0.41)
    )
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.92)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def create_pipe_prim(stage: Any, plan: PipeSegmentPlan, material: Any) -> dict[str, Any]:
    """Author one hollow pipe and return transform handles for animation."""

    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

    parent_path = Sdf.Path(plan.prim_path).GetParentPath()
    if not stage.GetPrimAtPath(parent_path).IsValid():
        UsdGeom.Xform.Define(stage, parent_path)
    xform = UsdGeom.Xform.Define(stage, Sdf.Path(plan.prim_path))
    xform_prim = xform.GetPrim()
    xform_prim.SetCustomDataByKey("sitegitRole", "installed_pipe")
    xform_prim.SetCustomDataByKey("sitegitZoneId", "B")
    xform_prim.SetCustomDataByKey("sitegitSegmentId", plan.segment_id)
    xform_prim.SetCustomDataByKey("sitegitStationStartM", plan.station_start_m)
    xform_prim.SetCustomDataByKey("sitegitStationEndM", plan.station_end_m)

    xformable = UsdGeom.Xformable(xform_prim)
    xformable.ClearXformOpOrder()
    translate_op = xformable.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)
    orient_op = xformable.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
    translate_op.Set(Gf.Vec3d(*plan.center_xyz))
    rotation = Gf.Rotation(
        Gf.Vec3d(0.0, 0.0, 1.0),
        Gf.Vec3d(*plan.direction_xyz),
    )
    orient_op.Set(rotation.GetQuat())

    mesh = UsdGeom.Mesh.Define(stage, Sdf.Path(f"{plan.prim_path}/Mesh"))
    data = hollow_pipe_mesh_data(
        plan.length_m,
        plan.outside_radius_m,
        plan.inside_radius_m,
    )
    mesh.CreatePointsAttr(data["points"])
    mesh.CreateFaceVertexCountsAttr(data["face_vertex_counts"])
    mesh.CreateFaceVertexIndicesAttr(data["face_vertex_indices"])
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr().Set(True)
    UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(material)
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    return {
        "plan": plan,
        "prim": xform_prim,
        "mesh_prim": mesh.GetPrim(),
        "translate_op": translate_op,
        "orient_op": orient_op,
    }
