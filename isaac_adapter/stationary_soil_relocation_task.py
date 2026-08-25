"""Run the independent Zone B stationary soil-relocation scenario.

The excavator tracks stay at the drawing position.  Each cycle uses only the
authored boom/bucket and upper-body swing clips: scoop from the source mound,
swing 90 degrees, dump at the adjacent destination, and return to the source.
Both mound changes are authored on the live USD Stage so the normal SiteGit
evidence, Commit, review, and map-merge pipeline can consume them.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from equipment_physics import track_contact_pose
from isaac_bridge import per_scoop_cut_ratio, projected_mesh_volume
from site_stage import create_diggable_soil_pile


ProgressCallback = Callable[[str, int, int, dict[str, Any]], None]


def _xy(value: Any, *, name: str) -> tuple[float, float]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Zone B drawing is missing {name}")
    return float(value.get("x") or 0.0), float(value.get("y") or 0.0)


def _distance_xy(first: dict[str, float], second: dict[str, float]) -> float:
    return math.hypot(
        float(first["x"]) - float(second["x"]),
        float(first["y"]) - float(second["y"]),
    )


def _deposit_offsets(scoop_count: int) -> list[tuple[float, float]]:
    """Return a compact deterministic footprint around the design destination."""

    pattern = [
        (-0.8, -0.45),
        (0.65, -0.35),
        (-0.55, 0.65),
        (0.75, 0.55),
        (0.0, 0.0),
        (-0.95, 0.2),
        (0.95, 0.15),
    ]
    return [pattern[index % len(pattern)] for index in range(scoop_count)]


def _mesh_volume(prim: Any) -> float:
    """Read the source mound's authored projected volume without editing it."""

    from pxr import UsdGeom

    if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
        return 0.0
    mesh = UsdGeom.Mesh(prim)
    points = [
        (float(value[0]), float(value[1]), float(value[2]))
        for value in (mesh.GetPointsAttr().Get() or [])
    ]
    counts = [int(value) for value in (mesh.GetFaceVertexCountsAttr().Get() or [])]
    indices = [int(value) for value in (mesh.GetFaceVertexIndicesAttr().Get() or [])]
    top_face_count = prim.GetCustomDataByKey("sitegitTopFaceCount")
    return float(
        projected_mesh_volume(
            points,
            counts,
            indices,
            face_limit=int(top_face_count) if top_face_count is not None else None,
        )
    )


def execute_stationary_soil_relocation(
    bridge: Any,
    world: Any,
    instruction: dict[str, Any],
    *,
    animation_seconds: float = 3.0,
    scoop_count: int | None = None,
    render: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Move one approved mound beside EXC-004 without moving its tracks."""

    params = instruction.get("params") or {}
    relocation = params.get("relocation") or {}
    bindings = params.get("resource_bindings") or {}
    instruction_id = str(instruction.get("id") or "unknown")
    equipment_path = str(
        bindings.get("equipment")
        or params.get("equipment_prim_path")
        or relocation.get("equipment_prim_path")
        or ""
    )
    source_path = str(
        bindings.get("target")
        or params.get("target_prim_path")
        or relocation.get("source_prim_path")
        or ""
    )
    destination_xy = _xy(
        relocation.get("destination_position"), name="destination_position"
    )
    requested_scoops = scoop_count or int(relocation.get("scoop_count") or 5)
    requested_scoops = max(1, min(12, int(requested_scoops)))

    if not bool(relocation.get("tracks_stationary", True)):
        raise RuntimeError("Zone B soil relocation must keep the tracks stationary")
    equipment = bridge.stage.GetPrimAtPath(equipment_path)
    source = bridge.stage.GetPrimAtPath(source_path)
    if not equipment.IsValid() or not equipment.IsActive():
        raise RuntimeError(f"Zone B equipment Prim is unavailable: {equipment_path}")
    if not source.IsValid() or not source.IsActive():
        raise RuntimeError(f"Zone B source soil Prim is unavailable: {source_path}")

    # The source exists before planning as ordinary site material.  The Zone
    # identity is assigned only after a manager confirms the drawing candidate
    # and the approved instruction reaches the Adapter.
    assigned_zone_id = str(params.get("zone_id") or "B").strip()
    source.SetCustomDataByKey("sitegitZoneId", assigned_zone_id)
    source.SetCustomDataByKey("sitegitWorkAreaStatus", "active")
    source.SetCustomDataByKey("sitegitWorkPackageId", str(params.get("work_package_id") or ""))

    start_track_pose = track_contact_pose(bridge.stage, equipment_path)
    source_position, source_size = bridge._world_bounds(source)
    initial_volume = _mesh_volume(source)
    if initial_volume <= 1e-6:
        raise RuntimeError("Zone B source mound has no measurable soil volume")

    bridge._notify_excavation_prepared(
        {
            "equipment_prim_path": equipment_path,
            "target_prim_path": source_path,
            "destination_position": {
                "x": destination_xy[0],
                "y": destination_xy[1],
            },
            "tracks_stationary": True,
            "track_pose": start_track_pose,
        }
    )

    phase_seconds = max(1.0, float(animation_seconds) * 0.55)
    dig_seconds = max(1.5, float(animation_seconds))
    swing_seconds = max(1.2, float(animation_seconds) * 0.7)
    dump_seconds = max(1.0, float(animation_seconds) * 0.55)
    per_cut = per_scoop_cut_ratio(0.995, requested_scoops)
    offsets = _deposit_offsets(requested_scoops)
    per_scoop_volume = initial_volume / float(requested_scoops)
    scoops: list[dict[str, Any]] = []
    animation_paths: list[str] = []
    deposited_soils: list[dict[str, Any]] = []

    for scoop_index in range(requested_scoops):
        for animation_name, duration in (
            ("ArmOut", phase_seconds),
            ("ArmDig", dig_seconds),
            ("ArmInDig", phase_seconds),
        ):
            animation_paths.extend(
                bridge.play_skeletal_animations_parallel(
                    [equipment],
                    animation_name,
                    duration_seconds=duration,
                )
            )

        progress = float(scoop_index + 1) / float(requested_scoops)
        deformation = bridge._deform_diggable_mesh(
            source,
            cut_ratio=max(0.95, per_cut) if scoop_index == requested_scoops - 1 else per_cut,
            minimum_cut_influence=min(1.0, 0.15 + 0.85 * progress**1.3),
        )

        animation_paths.extend(
            bridge.play_skeletal_animations_parallel(
                [equipment],
                "Rotate90",
                duration_seconds=swing_seconds,
            )
        )
        animation_paths.extend(
            bridge.play_skeletal_animations_parallel(
                [equipment],
                "ArmDump",
                duration_seconds=dump_seconds,
                pose_overlay_animation_name="Rotate90",
                pose_overlay_joint_suffixes=("/Rotator",),
            )
        )

        offset_x, offset_y = offsets[scoop_index]
        deposit_path = f"/World/Diggable/ZoneB_SoilDeposit_{scoop_index + 1:02d}"
        deposit_info = create_diggable_soil_pile(
            bridge.stage,
            prim_path=deposit_path,
            position_xy=(destination_xy[0] + offset_x, destination_xy[1] + offset_y),
            size=(3.8, 3.4, 1.45),
            zone_id="B",
            diggable_id=f"ZoneB-SoilDeposit-{scoop_index + 1:02d}",
            display_color=str(source.GetCustomDataByKey("sitegitDisplayColor") or "#8B6A3D"),
            surface_height=lambda x, y, fallback: bridge._terrain_surface_z(x, y, fallback),
        )
        deposit_prim = bridge.stage.GetPrimAtPath(deposit_path)
        deposited_volume = bridge._match_mesh_volume(deposit_prim, per_scoop_volume)
        deposit_position, deposit_size = bridge._world_bounds(deposit_prim)
        deposit = {
            **deposit_info,
            "position": deposit_position,
            "size": deposit_size,
            "geometry": bridge._mesh_geometry_snapshot(deposit_prim),
            "deposited_volume_m3": float(deposited_volume),
        }
        deposited_soils.append(deposit)

        animation_paths.extend(
            bridge.play_skeletal_animations_parallel(
                [equipment],
                "Rotate90",
                duration_seconds=swing_seconds,
                reverse=True,
            )
        )
        for _ in range(18):
            world.step(render=render)

        scoops.append(
            {
                "index": scoop_index + 1,
                "terrain_deformation": deformation,
                "moved_soil": deposit,
            }
        )
        if progress_callback is not None:
            progress_callback(
                instruction_id,
                scoop_index + 1,
                requested_scoops,
                deformation,
            )

    source.SetActive(False)
    for _ in range(12):
        world.step(render=render)

    end_track_pose = track_contact_pose(bridge.stage, equipment_path)
    track_displacement = _distance_xy(start_track_pose, end_track_pose)
    deposited_volume = sum(
        float(item.get("deposited_volume_m3") or 0.0) for item in deposited_soils
    )
    planned_quantity = params.get("planned_quantity") or {}
    planned_volume = max(0.0, float(planned_quantity.get("value") or initial_volume))
    quantity_ratio = min(1.0, deposited_volume / max(1e-6, planned_volume))
    weighted_x = sum(
        float(item["position"]["x"]) * float(item.get("deposited_volume_m3") or 0.0)
        for item in deposited_soils
    ) / max(1e-6, deposited_volume)
    weighted_y = sum(
        float(item["position"]["y"]) * float(item.get("deposited_volume_m3") or 0.0)
        for item in deposited_soils
    ) / max(1e-6, deposited_volume)
    destination_error = math.hypot(weighted_x - destination_xy[0], weighted_y - destination_xy[1])
    quality_status = (
        "pass"
        if quantity_ratio >= 0.95 and destination_error <= 0.5 and track_displacement <= 0.15
        else "needs_remediation"
    )

    map_changes: list[dict[str, Any]] = [
        {
            "action": "remove",
            "type": "removed_prim",
            "label": "Zone B 원토",
            "color": "#7C3AED",
            "prim_path": source_path,
            "position": source_position,
            "size": source_size,
            "geometry": None,
        }
    ]
    map_changes.extend(
        {
            "action": "upsert",
            "type": "soil_deposit",
            "label": "Zone B 이동 토사",
            "color": "#8B6A3D",
            "prim_path": item.get("prim_path"),
            "position": item.get("position"),
            "size": item.get("size"),
            "geometry": item.get("geometry"),
        }
        for item in deposited_soils
    )

    return {
        "schema_version": "1.0",
        "operation": "soil_relocation",
        "execution_mode": "stationary-upper-swing",
        "simulator": "isaac-sim",
        "source": "stage-readback",
        "equipment_prim_path": equipment_path,
        "target_prim_path": source_path,
        "target_active_after": False,
        "source_position": source_position,
        "destination_position": {"x": destination_xy[0], "y": destination_xy[1]},
        "scoop_count": requested_scoops,
        "scoops": scoops,
        "animation_paths": animation_paths,
        "terrain_deformation": {
            "available": True,
            "method": "usd_mesh_stationary_soil_relocation",
            "removed_volume_m3": float(initial_volume),
            "deposited_volume_m3": float(deposited_volume),
            "source_prim_path": source_path,
            "destination_center": {"x": weighted_x, "y": weighted_y},
        },
        "performed_quantity": {
            "value": float(deposited_volume),
            "unit": "m3",
            "method": "usd_mesh_volume_stage_readback",
            "estimated": True,
        },
        "quality_assessment": {
            "status": quality_status,
            "rule": "stationary_soil_relocation",
            "planned_volume_m3": planned_volume,
            "moved_volume_m3": float(deposited_volume),
            "quantity_ratio": quantity_ratio,
            "destination_center_error_m": destination_error,
            "track_displacement_m": track_displacement,
            "tracks_stationary": track_displacement <= 0.15,
            "message": (
                "Target soil quantity and destination were verified."
                if quality_status == "pass"
                else "Soil quantity, destination, or stationary-track criteria need review."
            ),
        },
        "map_changes": map_changes,
        "action_log": [
            {
                "operation": "stationary_soil_relocation",
                "equipment_prim_path": equipment_path,
                "target_prim_path": source_path,
                "scoop_count": requested_scoops,
                "moved_volume_m3": float(deposited_volume),
                "track_displacement_m": track_displacement,
            }
        ],
        "final_track_pose": end_track_pose,
    }
