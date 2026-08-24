"""Execute the approved Zone A Phase 2 pipe-installation group in the live Stage.

This is the web-connected counterpart of ``pipeline_installation_demo.py``.
It has no HTTP or database dependency: the Adapter supplies three approved
instructions, this module performs one synchronized Isaac task, and returns a
separate Stage-readback result for each work front.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable


PreparedCallback = Callable[[dict[str, Any], dict[str, Any]], None]
ProgressCallback = Callable[[str, int, int, dict[str, Any]], None]


def _load_plan(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    work_area = payload.get("work_area") or {}
    if len(work_area.get("centerline") or []) < 2:
        raise ValueError("pipeline plan has no usable centerline")
    if len(work_area.get("workfronts") or []) != 3:
        raise ValueError("pipeline installation requires exactly three work fronts")
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
            raise RuntimeError(f"unknown pipe-installation work front: {workfront_id}")
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
    if len(runtime) != 3:
        raise RuntimeError(
            f"Zone A Phase 2 pipeline installation needs 3 work fronts, received {len(runtime)}"
        )
    if len({item["equipment_prim_path"] for item in runtime}) != 3:
        raise RuntimeError("Zone A Phase 2 pipeline installation needs three unique excavators")
    return runtime


def _world_pipe_geometry(plan: Any, *, radial_segments: int = 16) -> dict[str, Any]:
    """Return one tube as world-coordinate SiteGit map geometry."""

    try:
        from .pipeline_installation import hollow_pipe_mesh_data
    except ImportError:  # Isaac Sim loads the adapter directory as script modules.
        from pipeline_installation import hollow_pipe_mesh_data

    data = hollow_pipe_mesh_data(
        float(plan.length_m),
        float(plan.outside_radius_m),
        float(plan.inside_radius_m),
        radial_segments=radial_segments,
    )
    direction = [float(value) for value in plan.direction_xyz]
    direction_length = math.sqrt(sum(value * value for value in direction))
    axis_z = [value / max(direction_length, 1e-9) for value in direction]
    reference = [0.0, 0.0, 1.0]
    if abs(sum(axis_z[index] * reference[index] for index in range(3))) > 0.95:
        reference = [0.0, 1.0, 0.0]
    axis_x = [
        reference[1] * axis_z[2] - reference[2] * axis_z[1],
        reference[2] * axis_z[0] - reference[0] * axis_z[2],
        reference[0] * axis_z[1] - reference[1] * axis_z[0],
    ]
    axis_x_length = math.sqrt(sum(value * value for value in axis_x))
    axis_x = [value / max(axis_x_length, 1e-9) for value in axis_x]
    axis_y = [
        axis_z[1] * axis_x[2] - axis_z[2] * axis_x[1],
        axis_z[2] * axis_x[0] - axis_z[0] * axis_x[2],
        axis_z[0] * axis_x[1] - axis_z[1] * axis_x[0],
    ]
    center = [float(value) for value in plan.center_xyz]
    points = [
        [
            center[axis]
            + axis_x[axis] * float(local[0])
            + axis_y[axis] * float(local[1])
            + axis_z[axis] * float(local[2])
            for axis in range(3)
        ]
        for local in data["points"]
    ]
    return {
        "format": "sitegit-triangle-mesh-v1",
        "points": points,
        "face_vertex_counts": data["face_vertex_counts"],
        "face_vertex_indices": data["face_vertex_indices"],
        "top_face_count": 0,
    }


def _map_change(plan: Any, workfront_id: str) -> dict[str, Any]:
    geometry = _world_pipe_geometry(plan)
    points = geometry["points"]
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {
        "action": "upsert",
        "type": "installed_pipe",
        "label": f"Zone A Phase 2 pipeline · {workfront_id}",
        "color": "#8A9297",
        "prim_path": str(plan.prim_path),
        "position": {
            axis: float(plan.center_xyz[index])
            for index, axis in enumerate(("x", "y", "z"))
        },
        "size": {
            axis: maximum[index] - minimum[index]
            for index, axis in enumerate(("x", "y", "z"))
        },
        "geometry": geometry,
    }


def execute_parallel_pipeline_installation(
    bridge: Any,
    world: Any,
    instructions: list[dict[str, Any]],
    *,
    floor_height: Callable[[float, float, float], float],
    plan_path: str | Path,
    animation_seconds: float = 1.6,
    render: bool = True,
    prepared_callback: PreparedCallback | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, dict[str, Any]]:
    """Install the drawing route with three excavators and return per-front results."""

    from pxr import Sdf, UsdGeom

    from equipment_physics import track_contact_pose
    from pipeline_installation import (
        PIPE_INSTALLATION_ROOT_PATH,
        build_pipe_segment_plans,
        clip_centerline_station_range,
        create_concrete_pipe_material,
        create_pipe_prim,
        select_workfront_pipe_plans,
        terminal_grade_clamped_floor_sampler,
        total_station_length,
    )
    from pipeline_installation_demo import (
        _animate_pipe_poses,
        _bank_staging_poses,
        _carrier_pipe_pose,
        _follow_pipe,
        _frame_from_result,
        _set_pipe_collision,
        _set_pipe_pose,
    )
    from three_excavator_demo import load_demo_workfronts

    stage = bridge.stage
    plan_payload = _load_plan(plan_path)
    work_area = plan_payload["work_area"]
    raw_workfronts = list(work_area["workfronts"])
    runtime = _instruction_runtime(instructions, raw_workfronts)
    canonical = {item.workfront_id: item for item in load_demo_workfronts(plan_path)}

    for state in runtime:
        equipment = stage.GetPrimAtPath(Sdf.Path(state["equipment_prim_path"]))
        if not equipment.IsValid():
            raise RuntimeError(
                f"pipe-installation equipment is missing: {state['equipment_prim_path']}"
            )
        still_filled = [
            path
            for path in state["target_prim_paths"]
            if stage.GetPrimAtPath(Sdf.Path(path)).IsValid()
            and stage.GetPrimAtPath(Sdf.Path(path)).IsActive()
        ]
        if still_filled:
            raise RuntimeError(
                "pipe installation is blocked because excavation is incomplete: "
                + ", ".join(still_filled)
            )
        planned = canonical.get(str(state["workfront"]["id"]))
        if planned is None:
            raise RuntimeError(f"missing canonical work front: {state['workfront']['id']}")
        state["planned"] = planned

    existing = stage.GetPrimAtPath(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
    UsdGeom.Xform.Define(stage, Sdf.Path("/World/Installed"))
    UsdGeom.Xform.Define(stage, Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))

    pipe_spec = work_area.get("pipe") or {}
    centerline = clip_centerline_station_range(
        work_area["centerline"],
        float(pipe_spec.get("installation_station_start_m") or 0.0),
        float(
            pipe_spec.get("installation_station_end_m")
            or work_area["centerline"][-1]["station_m"]
        ),
    )
    pipe_floor_height = terminal_grade_clamped_floor_sampler(
        work_area["centerline"],
        floor_height,
        grade_start_station_m=float(
            pipe_spec.get("terminal_grade_start_m")
            or pipe_spec.get("installation_station_start_m")
            or 0.0
        ),
        grade_end_station_m=float(
            pipe_spec.get("terminal_grade_end_m")
            or pipe_spec.get("installation_station_end_m")
            or work_area["centerline"][-1]["station_m"]
        ),
    )
    final_plans = build_pipe_segment_plans(
        centerline,
        floor_height=pipe_floor_height,
        outside_diameter_m=float(pipe_spec.get("outside_diameter_m") or 1.2),
        maximum_segment_length_m=4.0,
        root_path=f"{PIPE_INSTALLATION_ROOT_PATH}/Final",
    )
    handling_candidates = build_pipe_segment_plans(
        centerline,
        floor_height=pipe_floor_height,
        outside_diameter_m=float(pipe_spec.get("outside_diameter_m") or 1.2),
        maximum_segment_length_m=3.0,
        root_path=f"{PIPE_INSTALLATION_ROOT_PATH}/Handling",
    )
    handling_plans = select_workfront_pipe_plans(handling_candidates, raw_workfronts)
    material = create_concrete_pipe_material(stage)
    handling_records = [
        create_pipe_prim(stage, plan, material) for plan in handling_plans
    ]
    equipment_positions = [
        track_contact_pose(stage, state["equipment_prim_path"]) for state in runtime
    ]
    staging_poses = _bank_staging_poses(
        stage,
        handling_plans,
        raw_workfronts,
        equipment_positions,
        floor_height,
    )
    for record, pose in zip(handling_records, staging_poses):
        _set_pipe_pose(record, pose["position"], pose["direction"])
        _set_pipe_collision(record, False)

    total_steps = 4
    for state, record, staging_pose, equipment_position in zip(
        runtime, handling_records, staging_poses, equipment_positions
    ):
        bridge.drive_equipment_to(
            state["equipment_prim_path"],
            [float(equipment_position["x"]), float(equipment_position["y"])],
            requested_seconds=0.5,
        )
        facing = bridge.face_equipment_toward(
            state["equipment_prim_path"],
            [float(staging_pose["position"][0]), float(staging_pose["position"][1])],
        )
        state["pickup_facing"] = facing
        state["carrier_frame"] = _frame_from_result(facing)
        state["handling_record"] = record
        if prepared_callback is not None:
            prepared_callback(
                state["instruction"],
                {
                    "equipment_prim_path": state["equipment_prim_path"],
                    "target_prim_path": state["target_prim_paths"][0],
                    "target_prim_paths": state["target_prim_paths"],
                    "handling_pipe_prim_path": str(record["plan"].prim_path),
                },
            )
        if progress_callback is not None:
            progress_callback(
                str(state["instruction"]["id"]), 1, total_steps, {"phase": "prepared"}
            )

    duration = max(0.3, float(animation_seconds))
    carry_poses = [
        _carrier_pipe_pose(state["carrier_frame"], record["plan"].direction_xyz)
        for state, record in zip(runtime, handling_records)
    ]
    lift_poses = [
        {
            "position": [
                float(staging["position"][0]),
                float(staging["position"][1]),
                float(carry["position"][2]),
            ],
            "direction": list(staging["direction"]),
        }
        for staging, carry in zip(staging_poses, carry_poses)
    ]
    _animate_pipe_poses(
        world,
        handling_records,
        staging_poses,
        lift_poses,
        max(0.45, duration * 0.45),
        render=render,
    )
    _animate_pipe_poses(
        world,
        handling_records,
        lift_poses,
        carry_poses,
        max(0.35, duration * 0.35),
        render=render,
    )
    for state in runtime:
        if progress_callback is not None:
            progress_callback(
                str(state["instruction"]["id"]), 2, total_steps, {"phase": "picked_up"}
            )

    target_poses: list[dict[str, list[float]]] = []
    carrier_poses: list[dict[str, list[float]]] = []
    for state, record in zip(runtime, handling_records):
        plan = record["plan"]
        follow = _follow_pipe(record, plan.direction_xyz)
        facing = bridge.face_equipment_toward(
            state["equipment_prim_path"],
            [float(plan.center_xyz[0]), float(plan.center_xyz[1])],
            motion_frame_callback=follow,
        )
        carrier_poses.append(_carrier_pipe_pose(_frame_from_result(facing), plan.direction_xyz))
        target_poses.append(
            {
                "position": [float(value) for value in plan.center_xyz],
                "direction": [float(value) for value in plan.direction_xyz],
            }
        )
        state["target_facing"] = facing
        if progress_callback is not None:
            progress_callback(
                str(state["instruction"]["id"]), 3, total_steps, {"phase": "at_trench"}
            )

    hover_poses = [
        {
            "position": [
                float(target["position"][0]),
                float(target["position"][1]),
                max(float(carrier["position"][2]), float(target["position"][2]) + 1.8),
            ],
            "direction": list(target["direction"]),
        }
        for carrier, target in zip(carrier_poses, target_poses)
    ]
    _animate_pipe_poses(
        world,
        handling_records,
        carrier_poses,
        hover_poses,
        max(0.45, duration * 0.45),
        render=render,
    )
    _animate_pipe_poses(
        world,
        handling_records,
        hover_poses,
        target_poses,
        max(0.55, duration * 0.55),
        render=render,
    )

    for record in handling_records:
        record["prim"].SetActive(False)
    final_records = [create_pipe_prim(stage, plan, material) for plan in final_plans]
    for record in final_records:
        _set_pipe_collision(record, True)
    for _ in range(30):
        world.step(render=render)

    installed_by_front: dict[str, list[Any]] = {
        str(item["id"]): [] for item in raw_workfronts
    }
    for plan in final_plans:
        midpoint = (float(plan.station_start_m) + float(plan.station_end_m)) * 0.5
        owner = next(
            (
                item
                for item in raw_workfronts
                if float(item["station_start_m"])
                <= midpoint
                <= float(item["station_end_m"])
            ),
            raw_workfronts[-1],
        )
        installed_by_front[str(owner["id"])].append(plan)

    results: dict[str, dict[str, Any]] = {}
    for state in runtime:
        instruction_id = str(state["instruction"]["id"])
        workfront_id = str(state["workfront"]["id"])
        owned_plans = installed_by_front[workfront_id]
        installed_length_m = total_station_length(owned_plans)
        if progress_callback is not None:
            progress_callback(
                instruction_id,
                4,
                total_steps,
                {"phase": "installed", "installed_length_m": installed_length_m},
            )
        results[instruction_id] = {
            "schema_version": "1.0",
            "operation": "pipeline_installation",
            "execution_mode": "parallel-short-pickup-full-route-reveal",
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "phase_id": "pipe_installation",
            "zone_id": "B",
            "workfront_id": workfront_id,
            "equipment_prim_path": state["equipment_prim_path"],
            "target_prim_path": state["target_prim_paths"][0],
            "target_prim_paths": state["target_prim_paths"],
            "target_active_after": False,
            "handling_pipe": state["handling_record"]["plan"].to_dict(),
            "installed_segments": [plan.to_dict() for plan in owned_plans],
            "installed_length_m": installed_length_m,
            "performed_quantity": {
                "value": installed_length_m,
                "unit": "m",
                "method": "design-aligned-usd-pipe-mesh",
                "estimated": False,
            },
            "map_changes": [_map_change(plan, workfront_id) for plan in owned_plans],
            "action_log": [
                {
                    "operation": "parallel_pipe_installation",
                    "equipment_prim_path": state["equipment_prim_path"],
                    "workfront_id": workfront_id,
                    "installed_length_m": installed_length_m,
                    "segment_count": len(owned_plans),
                }
            ],
            "final_track_pose": track_contact_pose(stage, state["equipment_prim_path"]),
        }
    return results
