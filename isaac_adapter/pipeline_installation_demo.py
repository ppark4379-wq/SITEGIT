"""Run a simplified three-excavator pipe placement demo.

Three short handling pipes begin beside the spoil banks left by excavation.
EXC-001..003 pick them up together while remaining on stable ground, face the
trench, and lower them from above. At release, the handling props are replaced
by the complete drawing-aligned pipeline. This process is Isaac-only: no
Backend, commit, or web map is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable

from dotenv import load_dotenv


ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
DEFAULT_PLAN_PATH = REPO_ROOT / "contracts" / "site_plans" / "demolition_pipeline_v1.json"

load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def parse_args() -> argparse.Namespace:
    """Parse standalone installation-demo arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--presentation",
        action="store_true",
        help="show only the construction viewport in a maximized movable window",
    )
    parser.add_argument("--close-on-finish", action="store_true")
    parser.add_argument("--site", default=None, help="demolition-site USD/USDZ path")
    parser.add_argument("--equipment", default=None, help="animated excavator USD path")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH))
    parser.add_argument("--excavated-stage", default=None)
    parser.add_argument("--segment-length", type=float, default=4.0)
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--animation-seconds", type=float, default=1.6)
    parser.add_argument("--save-usd", default=None)
    return parser.parse_args()


def _required_asset(raw_value: str | None, fallback: Path | None, label: str) -> Path:
    candidate = Path(raw_value).expanduser() if raw_value else fallback
    if candidate is None or not candidate.resolve().is_file():
        raise FileNotFoundError(f"{label} was not found: {candidate}")
    return candidate.resolve()


def _load_plan(plan_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(plan_path).resolve().read_text(encoding="utf-8"))
    work_area = payload.get("work_area") or {}
    if len(work_area.get("centerline") or []) < 2:
        raise ValueError("pipeline plan has no usable centerline")
    if len(work_area.get("workfronts") or []) != 3:
        raise ValueError("pipe handling demo requires exactly three work fronts")
    return payload


def _set_viewport_camera(
    stage: Any, target_xyz: tuple[float, float, float] | None = None
) -> None:
    """Frame the complete corridor or a live installation target."""

    try:
        from omni.kit.viewport.utility import get_active_viewport
        from omni.kit.viewport.utility.camera_state import ViewportCameraState
        from pxr import Gf

        viewport = get_active_viewport()
        if viewport is None:
            return
        target = target_xyz or (-15.0, -7.0, 1.5)
        position = (target[0] + 28.0, target[1] - 34.0, target[2] + 20.0)
        camera = ViewportCameraState(viewport=viewport)
        camera.set_position_world(Gf.Vec3d(*position), True)
        camera.set_target_world(Gf.Vec3d(*target), True)
    except Exception as error:
        print(f"[pipe demo] viewport camera setup skipped: {error}", flush=True)


def _smooth_step(value: float) -> float:
    clamped = max(0.0, min(1.0, value))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def _set_pipe_pose(
    record: dict[str, Any],
    position: tuple[float, float, float] | list[float],
    direction: tuple[float, float, float] | list[float],
) -> None:
    """Set one pipe's world centre and long-axis direction."""

    from pxr import Gf

    dx, dy, dz = (float(value) for value in direction)
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 1e-6:
        dx, dy, dz, length = 0.0, 1.0, 0.0, 1.0
    record["translate_op"].Set(Gf.Vec3d(*(float(value) for value in position)))
    rotation = Gf.Rotation(
        Gf.Vec3d(0.0, 0.0, 1.0),
        Gf.Vec3d(dx / length, dy / length, dz / length),
    )
    record["orient_op"].Set(rotation.GetQuat())


def _set_pipe_collision(record: dict[str, Any], enabled: bool) -> None:
    from pxr import UsdPhysics

    collision = UsdPhysics.CollisionAPI(record["mesh_prim"])
    collision.CreateCollisionEnabledAttr().Set(bool(enabled))


def _animate_pipe_poses(
    world: Any,
    records: list[dict[str, Any]],
    starts: list[dict[str, Any]],
    ends: list[dict[str, Any]],
    duration_seconds: float,
    *,
    render: bool,
) -> None:
    """Interpolate several pipes together between two world poses."""

    frames = max(2, round(max(0.1, duration_seconds) * 30.0))
    for frame in range(frames + 1):
        _set_interpolated_pipe_poses(records, starts, ends, frame / frames)
        world.step(render=render)


def _set_interpolated_pipe_poses(
    records: list[dict[str, Any]],
    starts: list[dict[str, Any]],
    ends: list[dict[str, Any]],
    ratio: float,
) -> None:
    """Update pipe props without stepping so arm and pipe share one frame."""

    progress = _smooth_step(ratio)
    for record, start, end in zip(records, starts, ends):
        position = [
            float(start["position"][axis])
            + (float(end["position"][axis]) - float(start["position"][axis]))
            * progress
            for axis in range(3)
        ]
        direction = [
            float(start["direction"][axis])
            + (float(end["direction"][axis]) - float(start["direction"][axis]))
            * progress
            for axis in range(3)
        ]
        _set_pipe_pose(record, position, direction)


def _carrier_pipe_pose(
    frame: dict[str, Any],
    preferred_direction: tuple[float, float, float] | list[float] | None = None,
) -> dict[str, list[float]]:
    """Place a pipe at the stable bucket reach in front of the carrier."""

    from pxr import Gf

    orientation = frame["root_orientation_wxyz"]
    quaternion = Gf.Quatd(
        float(orientation[0]),
        Gf.Vec3d(float(orientation[1]), float(orientation[2]), float(orientation[3])),
    )
    forward = quaternion.Transform(Gf.Vec3d(0.0, 0.0, 1.0))
    planar_length = math.hypot(float(forward[0]), float(forward[1]))
    if planar_length <= 1e-6:
        forward_x, forward_y = 0.0, -1.0
    else:
        forward_x = float(forward[0]) / planar_length
        forward_y = float(forward[1]) / planar_length
    track = frame["track_position"]
    return {
        "position": [
            float(track[0]) + forward_x * 5.0,
            float(track[1]) + forward_y * 5.0,
            float(track[2]) + 1.05,
        ],
        "direction": (
            [float(value) for value in preferred_direction]
            if preferred_direction is not None
            else [-forward_y, forward_x, 0.0]
        ),
    }


def _frame_from_result(result: dict[str, Any]) -> dict[str, Any]:
    track = result.get("end_track_pose") or result.get("end_track_position")
    if isinstance(track, dict):
        track_position = [float(track[axis]) for axis in ("x", "y", "z")]
    elif isinstance(track, (list, tuple)):
        track_position = [float(value) for value in track]
    else:
        track_position = [float(value) for value in result["root_end_position"]]
    return {
        "root_position": [float(value) for value in result["root_end_position"]],
        "root_orientation_wxyz": [
            float(value) for value in result["root_end_orientation_wxyz"]
        ],
        "track_position": track_position,
    }


def _follow_pipe(
    record: dict[str, Any],
    preferred_direction: tuple[float, float, float] | list[float] | None = None,
) -> Callable[[dict[str, Any]], None]:
    def update(frame: dict[str, Any]) -> None:
        pose = _carrier_pipe_pose(frame, preferred_direction)
        _set_pipe_pose(record, pose["position"], pose["direction"])

    return update


def _bank_staging_poses(
    stage: Any,
    plans: list[Any],
    workfronts: list[dict[str, Any]],
    equipment_positions: list[dict[str, float]],
    surface_height: Callable[[float, float, float], float],
) -> list[dict[str, list[float]]]:
    """Place one short handling pipe beside each work front's spoil bank."""

    from pxr import Sdf, Usd, UsdGeom

    diggable_root = stage.GetPrimAtPath(Sdf.Path("/World/Diggable"))
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
        useExtentsHint=True,
    )
    poses: list[dict[str, list[float]]] = []
    for plan, workfront, equipment in zip(plans, workfronts, equipment_positions):
        target_names = {
            Path(str(path)).name
            for path in workfront.get("target_prim_paths") or []
        }
        spoil_centers: list[tuple[float, float]] = []
        if diggable_root.IsValid():
            for prim in Usd.PrimRange(diggable_root):
                name = str(prim.GetName())
                if "_MovedSoil_" not in name or not any(
                    name.startswith(target_name + "_MovedSoil_")
                    for target_name in target_names
                ):
                    continue
                bounds = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
                if bounds.IsEmpty():
                    continue
                minimum, maximum = bounds.GetMin(), bounds.GetMax()
                spoil_centers.append(
                    (
                        float((minimum[0] + maximum[0]) * 0.5),
                        float((minimum[1] + maximum[1]) * 0.5),
                    )
                )
        target_x, target_y, _ = plan.center_xyz
        if spoil_centers:
            bank_x = sum(point[0] for point in spoil_centers) / len(spoil_centers)
            bank_y = sum(point[1] for point in spoil_centers) / len(spoil_centers)
        else:
            bank_x = float(target_x)
            bank_y = float(target_y)
        # Explicitly put the pipe on the opposite side of the carrier from
        # the spoil bank: bank -> carrier -> short handling pipe.
        away_x = float(equipment["x"]) - bank_x
        away_y = float(equipment["y"]) - bank_y
        away_length = math.hypot(away_x, away_y)
        if away_length <= 1e-6:
            direction_x, direction_y, _ = plan.direction_xyz
            away_x, away_y = -direction_y, direction_x
            away_length = math.hypot(away_x, away_y)
        away_x /= away_length
        away_y /= away_length
        # Match the extended bucket reach.  The earlier 3.2 m placement put
        # the pipe under the upper structure and made it cross the cab.
        pickup_distance = 5.0
        x = float(equipment["x"]) + away_x * pickup_distance
        y = float(equipment["y"]) + away_y * pickup_distance
        poses.append(
            {
                "position": [
                    x,
                    y,
                    float(surface_height(x, y, plan.center_xyz[2]))
                    + plan.outside_radius_m
                    + 0.08,
                ],
                "direction": list(plan.direction_xyz),
            }
        )
    return poses


def _write_report(output_root: Path, payload: dict[str, Any]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    """Execute the three-machine Zone A Phase 2 handling demo."""

    args = parse_args()
    from isaacsim.simulation_app import SimulationApp
    from presentation_mode import enable_viewport_only_mode, simulation_app_config

    app = SimulationApp(
        simulation_app_config(
            headless=bool(args.headless),
            presentation=bool(args.presentation),
        )
    )
    enable_viewport_only_mode(
        app,
        enabled=bool(args.presentation and not args.headless),
    )
    output_root: Path | None = None
    timeline = None
    try:
        import omni.timeline
        import omni.usd
        from isaacsim.core.api import World
        from pxr import Sdf, UsdGeom

        from equipment_physics import prepare_equipment_physics, track_contact_pose
        from isaac_bridge import IsaacBridge
        from pipeline_installation import (
            PIPE_INSTALLATION_ROOT_PATH,
            build_pipe_segment_plans,
            clip_centerline_station_range,
            create_concrete_pipe_material,
            create_pipe_prim,
            select_workfront_pipe_plans,
            terminal_grade_clamped_floor_sampler,
            total_pipe_length,
            total_station_length,
        )
        from pipeline_scenario import create_pipeline_backfill
        from site_stage import (
            add_lighting,
            default_site_asset,
            load_equipment,
            load_site,
            resolved_data_root,
        )
        from terrain_collision_proxy import (
            collision_proxy_height_sampler,
            create_terrain_collision_proxy,
            load_or_build_collision_proxy_data,
        )
        from three_excavator_demo import load_demo_workfronts

        data_root = resolved_data_root()
        output_root = data_root / "isaac" / "pipeline-installation-demo"
        plan_payload = _load_plan(args.plan)
        work_area = plan_payload["work_area"]
        raw_workfronts = list(work_area["workfronts"])
        demo_workfronts = load_demo_workfronts(args.plan)
        target_paths = [
            str(path)
            for workfront in raw_workfronts
            for path in workfront.get("target_prim_paths") or []
        ]
        pipe_spec = work_area.get("pipe") or {}
        default_excavated_stage = (
            data_root / "isaac" / "three-excavator-demo" / "excavated-stage.usda"
        )
        source_stage = (
            Path(args.excavated_stage).expanduser().resolve()
            if args.excavated_stage
            else default_excavated_stage if default_excavated_stage.is_file() else None
        )
        context = omni.usd.get_context()
        prepared_excavation = False
        site_info: dict[str, Any]
        if source_stage is not None:
            print(f"Opening completed excavation Stage: {source_stage}", flush=True)
            context.open_stage(str(source_stage))
            for _ in range(60):
                app.update()
            stage = context.get_stage()
            if stage is None:
                raise RuntimeError(f"failed to open excavation Stage: {source_stage}")
            active_targets = [
                path
                for path in target_paths
                if stage.GetPrimAtPath(Sdf.Path(path)).IsValid()
                and stage.GetPrimAtPath(Sdf.Path(path)).IsActive()
            ]
            if active_targets:
                raise RuntimeError(
                    "pipe installation is blocked because excavation is incomplete: "
                    + ", ".join(active_targets)
                )
            site_info = {"source_stage": str(source_stage), "restored": True}
        else:
            site_asset = _required_asset(
                args.site or os.getenv("SITEGIT_SITE_ASSET"),
                default_site_asset(data_root),
                "demolition-site asset",
            )
            context.new_stage()
            stage = context.get_stage()
            site_info = load_site(stage, site_asset, simulation_app=app)
            add_lighting(stage)

        collision = create_terrain_collision_proxy(
            stage,
            data_root,
            resolution_m=float(os.getenv("SITEGIT_TERRAIN_COLLISION_RESOLUTION_M", "2")),
        )
        physics_surface = collision_proxy_height_sampler(collision["cache_path"])
        visual_height_cache = data_root / "isaac" / "terrain_backfill_height_0_5m.npz"
        visual_height_data, visual_height_cache_hit = load_or_build_collision_proxy_data(
            data_root / "isaac" / "site-work-map",
            visual_height_cache,
            resolution_m=float(os.getenv("SITEGIT_PIPELINE_HEIGHT_RESOLUTION_M", "0.5")),
        )
        floor_height = collision_proxy_height_sampler(visual_height_cache)

        if source_stage is None:
            material_root = data_root / "isaac" / "assets" / "materials"
            base_color = material_root / "demolition_soil_tile_diffuse.jpg"
            normal = material_root / "demolition_soil_tile_normal.jpg"
            create_pipeline_backfill(
                stage,
                surface_height=floor_height,
                base_color_texture=base_color if base_color.is_file() else None,
                normal_texture=normal if normal.is_file() else None,
                update_callback=app.update,
            )
            for path in target_paths:
                target = stage.GetPrimAtPath(Sdf.Path(path))
                if not target.IsValid():
                    raise RuntimeError(f"prepared excavation target is missing: {path}")
                target.SetActive(False)
            prepared_excavation = True

        missing_equipment = [
            workfront
            for workfront in demo_workfronts
            if not stage.GetPrimAtPath(Sdf.Path(workfront.equipment_prim_path)).IsValid()
        ]
        equipment_asset: Path | None = None
        if missing_equipment:
            equipment_asset = _required_asset(
                args.equipment or os.getenv("SITEGIT_EQUIPMENT_ASSET"),
                None,
                "animated excavator asset",
            )
            for workfront in missing_equipment:
                load_equipment(
                    stage,
                    equipment_asset,
                    prim_path=workfront.equipment_prim_path,
                    equipment_id=workfront.equipment_id,
                    position=workfront.start_position,
                    simulation_app=app,
                    settle_frames=120,
                    surface_height=physics_surface,
                )

        physics_reports = [
            prepare_equipment_physics(
                stage,
                workfront.equipment_prim_path,
                surface_height=physics_surface,
            )
            for workfront in demo_workfronts
        ]
        world = World(
            stage_units_in_meters=1.0,
            physics_prim_path="/World/PhysicsScene",
            set_defaults=False,
        )
        world.reset()
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(120):
            world.step(render=not args.headless)
        bridge = IsaacBridge(
            stage=stage,
            update_callback=lambda: world.step(render=not args.headless),
        )

        existing_root = stage.GetPrimAtPath(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
        if existing_root.IsValid():
            stage.RemovePrim(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
        UsdGeom.Xform.Define(stage, Sdf.Path("/World/Installed"))
        UsdGeom.Xform.Define(stage, Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
        installation_centerline = clip_centerline_station_range(
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
            installation_centerline,
            floor_height=pipe_floor_height,
            outside_diameter_m=float(pipe_spec.get("outside_diameter_m") or 1.2),
            maximum_segment_length_m=max(1.0, float(args.segment_length)),
            root_path=f"{PIPE_INSTALLATION_ROOT_PATH}/Final",
        )
        handling_candidates = build_pipe_segment_plans(
            installation_centerline,
            floor_height=pipe_floor_height,
            outside_diameter_m=float(pipe_spec.get("outside_diameter_m") or 1.2),
            maximum_segment_length_m=3.0,
            root_path=f"{PIPE_INSTALLATION_ROOT_PATH}/Handling",
        )
        plans = select_workfront_pipe_plans(handling_candidates, raw_workfronts)
        material = create_concrete_pipe_material(stage)
        records = [create_pipe_prim(stage, plan, material) for plan in plans]
        equipment_positions = [
            track_contact_pose(stage, workfront.equipment_prim_path)
            for workfront in demo_workfronts
        ]
        staging_poses = _bank_staging_poses(
            stage,
            plans,
            raw_workfronts,
            equipment_positions,
            floor_height,
        )
        for record, pose in zip(records, staging_poses):
            _set_pipe_pose(record, pose["position"], pose["direction"])
            _set_pipe_collision(record, False)

        animation_seconds = max(0.3, float(args.animation_seconds))
        runtime: list[dict[str, Any]] = []
        _set_viewport_camera(stage)
        print("=" * 68, flush=True)
        print("SiteGit simplified three-excavator pipe placement demo", flush=True)
        print("Three short handling pipes start beside the spoil banks.", flush=True)
        print("After all three are lowered, the complete design pipeline appears.", flush=True)
        print(f"Source excavation: {source_stage or 'prepared approved demo state'}", flush=True)
        print("=" * 68, flush=True)

        for index, (workfront, record, staging_pose, equipment_position) in enumerate(
            zip(demo_workfronts, records, staging_poses, equipment_positions), 1
        ):
            staging_x, staging_y, _ = staging_pose["position"]
            print(
                f"[bank pickup {index}/3] {workfront.equipment_id} -> "
                f"{record['plan'].segment_id}",
                flush=True,
            )
            # Calling the drive controller with the current track coordinate
            # initializes its PhysX handle without sending the carrier toward
            # the trench or down into the excavated floor.
            drive = bridge.drive_equipment_to(
                workfront.equipment_prim_path,
                [float(equipment_position["x"]), float(equipment_position["y"])],
                requested_seconds=0.5,
            )
            facing = bridge.face_equipment_toward(
                workfront.equipment_prim_path,
                [staging_x, staging_y],
            )
            runtime.append(
                {
                    "workfront": workfront,
                    "record": record,
                    "staging_pose": staging_pose,
                    "controller_initialization": drive,
                    "pickup_facing": facing,
                    "carrier_frame": _frame_from_result(facing),
                    "animation_paths": [],
                }
            )

        carry_poses = [
            _carrier_pipe_pose(
                item["carrier_frame"],
                item["record"]["plan"].direction_xyz,
            )
            for item in runtime
        ]
        # Do not bind the purchased ArmDig clip here.  It animates the whole
        # imported skeleton, not only the boom, and consequently resets the
        # carrier pose while PhysX is turning it.  A short vertical pickup is
        # clearer and keeps the equipment stable.
        pickup_lift_poses = [
            {
                "position": [
                    float(pose["position"][0]),
                    float(pose["position"][1]),
                    float(carry["position"][2]),
                ],
                "direction": list(pose["direction"]),
            }
            for pose, carry in zip(staging_poses, carry_poses)
        ]
        _animate_pipe_poses(
            world,
            records,
            staging_poses,
            pickup_lift_poses,
            max(0.45, animation_seconds * 0.45),
            render=not args.headless,
        )
        _animate_pipe_poses(
            world,
            records,
            pickup_lift_poses,
            carry_poses,
            max(0.35, animation_seconds * 0.35),
            render=not args.headless,
        )

        carrier_poses: list[dict[str, list[float]]] = []
        target_poses: list[dict[str, list[float]]] = []
        for index, item in enumerate(runtime, 1):
            workfront = item["workfront"]
            record = item["record"]
            plan = record["plan"]
            target = [float(value) for value in plan.center_xyz]
            print(
                f"[top-down placement {index}/3] {workfront.equipment_id}: "
                f"short handling pipe -> trench",
                flush=True,
            )
            follow = _follow_pipe(record, plan.direction_xyz)
            facing = bridge.face_equipment_toward(
                workfront.equipment_prim_path,
                target[:2],
                motion_frame_callback=follow,
            )
            carrier_poses.append(_carrier_pipe_pose(
                _frame_from_result(facing),
                plan.direction_xyz,
            ))
            target_poses.append({
                "position": target,
                "direction": list(plan.direction_xyz),
            })
            item["target_facing"] = facing

        placement_hover_poses = [
            {
                "position": [
                    float(target["position"][0]),
                    float(target["position"][1]),
                    max(
                        float(carrier["position"][2]),
                        float(target["position"][2]) + 1.8,
                    ),
                ],
                "direction": list(target["direction"]),
            }
            for carrier, target in zip(carrier_poses, target_poses)
        ]
        _animate_pipe_poses(
            world,
            records,
            carrier_poses,
            placement_hover_poses,
            max(0.45, animation_seconds * 0.45),
            render=not args.headless,
        )
        _animate_pipe_poses(
            world,
            records,
            placement_hover_poses,
            target_poses,
            max(0.55, animation_seconds * 0.55),
            render=not args.headless,
        )

        # The short pieces are only handling props. Once all three operators
        # release them, replace them in one frame with the full drawing route.
        for record in records:
            record["prim"].SetActive(False)
        final_records = [
            create_pipe_prim(stage, plan, material) for plan in final_plans
        ]
        for record in final_records:
            _set_pipe_collision(record, True)
        for _ in range(30):
            world.step(render=not args.headless)

        handling: list[dict[str, Any]] = []
        for index, item in enumerate(runtime):
            handling.append(
                {
                    **item["record"]["plan"].to_dict(),
                    "equipment_id": item["workfront"].equipment_id,
                    "equipment_prim_path": item["workfront"].equipment_prim_path,
                    "workfront_id": item["workfront"].workfront_id,
                    "spoil_bank_staging_xyz": staging_poses[index]["position"],
                    "release_xyz": target_poses[index]["position"],
                    "status": "replaced_by_complete_pipeline",
                    "controller_initialization": item["controller_initialization"],
                    "carrier_drove_into_trench": False,
                    "target_facing": item["target_facing"],
                    "animation_paths": item["animation_paths"],
                }
            )

        installed: list[dict[str, Any]] = []
        for plan in final_plans:
            midpoint = (plan.station_start_m + plan.station_end_m) * 0.5
            owner_index = next(
                (
                    index
                    for index, workfront in enumerate(raw_workfronts)
                    if float(workfront["station_start_m"])
                    <= midpoint
                    <= float(workfront["station_end_m"])
                ),
                len(runtime) - 1,
            )
            owner = runtime[owner_index]
            installed.append(
                {
                    **plan.to_dict(),
                    "equipment_id": owner["workfront"].equipment_id,
                    "equipment_prim_path": owner["workfront"].equipment_prim_path,
                    "workfront_id": owner["workfront"].workfront_id,
                    "installed_xyz": list(plan.center_xyz),
                    "status": "demo_installed",
                }
            )

        timeline.pause()
        _set_viewport_camera(stage)
        saved_stage = (
            Path(args.save_usd).expanduser().resolve()
            if args.save_usd
            else output_root / "pipeline-installed-stage.usda"
        )
        saved_stage.parent.mkdir(parents=True, exist_ok=True)
        stage.GetRootLayer().Export(saved_stage.as_posix())
        installed_chainage = total_station_length(final_plans)
        design_length = installed_chainage
        report = {
            "schema_version": "1.1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "isaac-sim-only",
            "phase_id": "pipe_installation",
            "zone_id": "B",
            "execution_mode": "three-short-handling-pipes-to-complete-route",
            "web_connected": False,
            "source_stage": str(source_stage) if source_stage else None,
            "prepared_excavation_fallback": prepared_excavation,
            "site": site_info,
            "collision": collision,
            "equipment_asset": str(equipment_asset) if equipment_asset else "restored-from-stage",
            "equipment_physics": physics_reports,
            "installation": {
                "method": "short-pickup-top-down-lower-then-full-route-reveal",
                "segment_count": len(installed),
                "handling_pipe_count": len(handling),
                "handling_pipe_length_m": round(
                    max((plan.length_m for plan in plans), default=0.0), 6
                ),
                "design_length_m": design_length,
                "source_corridor_length_m": float(
                    work_area.get("total_length_m") or design_length
                ),
                "installation_station_start_m": float(
                    pipe_spec.get("installation_station_start_m") or 0.0
                ),
                "installation_station_end_m": float(
                    pipe_spec.get("installation_station_end_m")
                    or work_area["centerline"][-1]["station_m"]
                ),
                "terminal_grade_start_m": float(
                    pipe_spec.get("terminal_grade_start_m")
                    or pipe_spec.get("installation_station_start_m")
                    or 0.0
                ),
                "terminal_grade_end_m": float(
                    pipe_spec.get("terminal_grade_end_m")
                    or pipe_spec.get("installation_station_end_m")
                    or work_area["centerline"][-1]["station_m"]
                ),
                "installed_length_m": round(installed_chainage, 6),
                "installed_geometry_length_m": round(total_pipe_length(final_plans), 6),
                "coverage_percent": round(
                    installed_chainage / design_length * 100.0 if design_length else 0.0,
                    3,
                ),
                "handling": handling,
                "segments": installed,
            },
            "terrain_height_cache": {
                "path": str(visual_height_cache),
                "cache_hit": visual_height_cache_hit,
                "valid_cell_count": visual_height_data["valid_cell_count"],
            },
            "acceptance": {
                "result": "demo_complete",
                "reason": "three short handling pipes reveal the complete drawing route",
                "measurement_source": "design-authored-demo-geometry",
            },
            "saved_stage": str(saved_stage),
        }
        report_path = _write_report(output_root, report)
        (output_root / "failure.txt").unlink(missing_ok=True)
        print("=" * 68, flush=True)
        print("Simplified three-excavator pipe placement demo complete", flush=True)
        for segment in handling:
            print(
                f"{segment['equipment_id']}: short pipe lowered at "
                f"{segment['workfront_id']}",
                flush=True,
            )
        print(
            f"Complete route: {len(installed)} pieces / {installed_chainage:.1f} m",
            flush=True,
        )
        print(f"Stage : {saved_stage}", flush=True)
        print(f"Report: {report_path}", flush=True)
        print("=" * 68, flush=True)
        if not args.headless and not args.close_on_finish:
            print("The Stage is paused. Close the Isaac Sim window to finish.", flush=True)
            while app.is_running():
                app.update()
    except Exception:
        if output_root is None:
            output_root = REPO_ROOT / "runtime" / "pipeline-installation-demo"
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close(wait_for_replicator=False, skip_cleanup=True)


if __name__ == "__main__":
    main()
