"""Execute the approved Zone A Phase 3 backfill group in the live Isaac Stage.

This module is the web-connected counterpart of ``pipeline_backfill_demo.py``.
It consumes the three excavation spoil banks, restores the approved trench-fill
meshes in synchronized steps, and returns one Stage-readback result per work
front.  HTTP, Commit, and Evidence handling remain in ``cube_task_runner``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


PreparedCallback = Callable[[dict[str, Any], dict[str, Any]], None]
ProgressCallback = Callable[[str, int, int, dict[str, Any]], None]


def _load_plan(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    workfronts = (payload.get("work_area") or {}).get("workfronts") or []
    if len(workfronts) != 3:
        raise ValueError("pipeline backfill requires exactly three work fronts")
    return payload


def _instruction_runtime(
    instructions: list[dict[str, Any]],
    raw_workfronts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(item["id"]): item for item in raw_workfronts}
    runtime: list[dict[str, Any]] = []
    for instruction in instructions:
        params = instruction.get("params") or {}
        workfront_id = str(params.get("workfront_id") or "")
        workfront = by_id.get(workfront_id)
        if workfront is None:
            raise RuntimeError(f"unknown backfill work front: {workfront_id}")
        equipment_path = str(
            (params.get("resource_bindings") or {}).get("equipment")
            or params.get("equipment_prim_path")
            or workfront.get("equipment_prim_path")
            or ""
        )
        target_paths = [
            str(value)
            for value in (
                params.get("target_prim_paths")
                or workfront.get("target_prim_paths")
                or []
            )
        ]
        runtime.append(
            {
                "instruction": instruction,
                "workfront": workfront,
                "equipment_prim_path": equipment_path,
                "target_prim_paths": target_paths,
            }
        )
    runtime.sort(key=lambda item: str(item["workfront"]["id"]))
    if len(runtime) != 3 or len({item["equipment_prim_path"] for item in runtime}) != 3:
        raise RuntimeError("Zone A Phase 3 backfill needs three unique excavators")
    return runtime


def _map_upsert(bridge: Any, prim: Any, *, label: str) -> dict[str, Any]:
    position, size = bridge._world_bounds(prim)
    return {
        "action": "upsert",
        "type": "terrain_patch",
        "label": label,
        "color": "#9A7B4F",
        "prim_path": str(prim.GetPath()),
        "position": position,
        "size": size,
        "geometry": bridge._mesh_geometry_snapshot(prim),
    }


def execute_parallel_pipeline_backfill(
    bridge: Any,
    world: Any,
    instructions: list[dict[str, Any]],
    *,
    surface_height: Callable[[float, float, float], float],
    plan_path: str | Path,
    base_color_texture: str | Path | None = None,
    normal_texture: str | Path | None = None,
    animation_seconds: float = 3.0,
    scoop_count: int = 1,
    render: bool = True,
    prepared_callback: PreparedCallback | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, dict[str, Any]]:
    """Backfill the installed route and return one result per work front."""

    from pxr import Sdf, UsdPhysics

    from equipment_physics import track_contact_pose
    from pipeline_backfill_demo import (
        _collect_spoil_groups,
        _consume_spoil_geometry,
        _play_backfill_motion_cycle,
        _restore_target_records,
        _restore_target_geometry,
        _set_collision,
        _set_mesh_points,
    )
    from pipeline_installation import PIPE_INSTALLATION_ROOT_PATH
    from pipeline_scenario import PIPELINE_ROOT_PATH, create_pipeline_backfill
    from three_excavator_demo import load_demo_workfronts

    stage = bridge.stage
    plan = _load_plan(plan_path)
    raw_workfronts = list(plan["work_area"]["workfronts"])
    runtime = _instruction_runtime(instructions, raw_workfronts)
    canonical = {item.workfront_id: item for item in load_demo_workfronts(plan_path)}

    installed_root = stage.GetPrimAtPath(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
    if not installed_root.IsValid():
        raise RuntimeError("backfill is blocked because the installed pipeline was not found")

    workfronts: list[Any] = []
    equipment_prims: list[Any] = []
    for state in runtime:
        workfront_id = str(state["workfront"]["id"])
        workfront = canonical.get(workfront_id)
        if workfront is None:
            raise RuntimeError(f"missing canonical work front: {workfront_id}")
        equipment = stage.GetPrimAtPath(Sdf.Path(state["equipment_prim_path"]))
        if not equipment.IsValid():
            raise RuntimeError(
                f"backfill equipment is missing: {state['equipment_prim_path']}"
            )
        workfronts.append(workfront)
        equipment_prims.append(equipment)

    spoil_groups = _collect_spoil_groups(stage, workfronts)
    missing_spoil = [
        workfront.equipment_id
        for workfront, group in zip(workfronts, spoil_groups)
        if not group
    ]
    if missing_spoil:
        raise RuntimeError("backfill spoil bank is missing for: " + ", ".join(missing_spoil))

    # Preserve bounds before the spoil meshes are progressively collapsed so
    # the approved Commit can remove their previous map overlays exactly.
    for group in spoil_groups:
        for record in group:
            position, size = bridge._world_bounds(record["prim"])
            record["map_position"] = position
            record["map_size"] = size

    # Position evidence at the actual work fronts before arm/bucket motion.
    for index, (state, workfront, equipment) in enumerate(
        zip(runtime, workfronts, equipment_prims)
    ):
        pose = track_contact_pose(stage, state["equipment_prim_path"])
        bridge.drive_equipment_to(
            state["equipment_prim_path"],
            [float(pose["x"]), float(pose["y"])],
            requested_seconds=0.5,
        )
        facing = bridge.face_equipment_toward(
            state["equipment_prim_path"],
            list(workfront.target_center_xy),
        )
        equipment.SetCustomDataByKey(
            "sitegitBackfillReferenceHeading", "pipeline-target-forward"
        )
        if prepared_callback is not None:
            prepared_callback(
                state["instruction"],
                {
                    "equipment_prim_path": state["equipment_prim_path"],
                    "target_prim_path": state["target_prim_paths"][0],
                    "target_prim_paths": state["target_prim_paths"],
                    "target_xy": list(workfront.target_center_xy),
                    "facing": facing,
                    "spoil_prim_paths": [
                        item["prim_path"]
                        for item in spoil_groups[index]
                    ],
                },
            )

    existing_fill = stage.GetPrimAtPath(Sdf.Path(PIPELINE_ROOT_PATH))
    if existing_fill.IsValid():
        stage.RemovePrim(Sdf.Path(PIPELINE_ROOT_PATH))
    create_pipeline_backfill(
        stage,
        surface_height=surface_height,
        base_color_texture=base_color_texture,
        normal_texture=normal_texture,
        update_callback=lambda: world.step(render=render),
    )
    target_groups = _restore_target_records(stage, workfronts)

    # Keep the carriers physically stable while the imported upper-structure
    # clips play.  This matches the standalone demo and prevents slope impulses.
    for equipment in equipment_prims:
        rigid = UsdPhysics.RigidBodyAPI(equipment)
        rigid.CreateVelocityAttr().Set((0.0, 0.0, 0.0))
        rigid.CreateAngularVelocityAttr().Set((0.0, 0.0, 0.0))
        rigid.CreateKinematicEnabledAttr().Set(True)
        equipment.SetCustomDataByKey("sitegitBackfillCarrierMode", "stationary-kinematic")
    for _ in range(12):
        world.step(render=render)
    bridge.play_skeletal_animations_parallel(
        equipment_prims, "Default_Pose", duration_seconds=0.8
    )

    cycles = max(1, min(10, int(scoop_count)))
    nominal = max(0.75, float(animation_seconds))
    swing_seconds = max(1.8, nominal)
    reach_seconds = max(1.4, nominal * 0.72)
    dig_seconds = max(1.8, nominal * 0.9)
    lift_seconds = max(1.5, nominal * 0.78)
    dump_seconds = max(1.6, nominal * 0.8)

    for cycle in range(cycles):
        progress = float(cycle + 1) / float(cycles)

        def consume_spoil() -> None:
            _consume_spoil_geometry(spoil_groups, progress)
            for _ in range(12):
                world.step(render=render)

        def restore_trench() -> None:
            _restore_target_geometry(target_groups, progress)
            for _ in range(18):
                world.step(render=render)

        _play_backfill_motion_cycle(
            bridge,
            equipment_prims,
            swing_seconds=swing_seconds,
            reach_seconds=reach_seconds,
            dig_seconds=dig_seconds,
            lift_seconds=lift_seconds,
            dump_seconds=dump_seconds,
            pickup_callback=consume_spoil,
            dump_callback=restore_trench,
        )
        for state in runtime:
            if progress_callback is not None:
                planned = float(
                    ((state["instruction"].get("params") or {}).get("planned_quantity") or {}).get(
                        "value"
                    )
                    or state["workfront"].get("target_volume_m3")
                    or 0.0
                )
                progress_callback(
                    str(state["instruction"]["id"]),
                    cycle + 1,
                    cycles,
                    {
                        "phase": "backfilling",
                        "backfilled_volume_m3": planned * progress,
                    },
                )

    for group in spoil_groups:
        for record in group:
            record["prim"].SetActive(False)
    for targets in target_groups:
        for record in targets:
            _set_mesh_points(record["prim"], record["final_points"])
            _set_collision(record["prim"], True)
            record["prim"].SetCustomDataByKey("sitegitTerrainRevision", cycles)
            record["prim"].SetCustomDataByKey(
                "sitegitScenarioRole", "pipeline_backfilled"
            )
    for _ in range(30):
        world.step(render=render)

    results: dict[str, dict[str, Any]] = {}
    for state, targets, spoils in zip(runtime, target_groups, spoil_groups):
        instruction_id = str(state["instruction"]["id"])
        workfront_id = str(state["workfront"]["id"])
        planned = float(
            ((state["instruction"].get("params") or {}).get("planned_quantity") or {}).get(
                "value"
            )
            or state["workfront"].get("target_volume_m3")
            or 0.0
        )
        map_changes = [
            _map_upsert(bridge, record["prim"], label=f"Zone A Phase 3 backfill · {workfront_id}")
            for record in targets
        ]
        map_changes.extend(
            {
                "action": "remove",
                "type": "removed_prim",
                "label": "Consumed excavation spoil",
                "color": "#8B6A3D",
                "prim_path": record["prim_path"],
                "position": record["map_position"],
                "size": record["map_size"],
            }
            for record in spoils
        )
        results[instruction_id] = {
            "schema_version": "1.0",
            "operation": "pipeline_backfill",
            "execution_mode": "parallel-reverse-excavation-backfill",
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "phase_id": "backfill",
            "zone_id": "C",
            "workfront_id": workfront_id,
            "equipment_prim_path": state["equipment_prim_path"],
            "target_prim_path": state["target_prim_paths"][0],
            "target_prim_paths": state["target_prim_paths"],
            "target_active_after": True,
            "backfilled_volume_m3": planned,
            "performed_quantity": {
                "value": planned,
                "unit": "m3",
                "method": "approved-usd-mesh-restoration",
                "estimated": True,
            },
            "map_changes": map_changes,
            "action_log": [
                {
                    "operation": "parallel_pipeline_backfill",
                    "equipment_prim_path": state["equipment_prim_path"],
                    "workfront_id": workfront_id,
                    "cycle_count": cycles,
                    "backfilled_volume_m3": planned,
                }
            ],
            "final_track_pose": track_contact_pose(stage, state["equipment_prim_path"]),
        }
    return results
