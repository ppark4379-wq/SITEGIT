"""Run a standalone three-excavator pipeline excavation demo in Isaac Sim.

This entry point intentionally does not import the SiteGit API client and does
not create commits.  It builds a fresh demolition-site Stage, places three
physical excavators on alternating sides of the pipeline corridor, and runs
several synchronized scoop-and-dump cycles on all three work fronts. The soil
mesh is lowered after every scoop so excavation progress remains visible. The
optional defect mode makes the centre excavator under-excavate so its
incomplete result can be compared with the two normally excavated sections.

Run this module with Isaac Sim's Python, not the project's normal virtualenv.
The root ``start_sitegit_excavator_demo.bat`` launcher resolves the portable
SSD paths automatically.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

from dotenv import load_dotenv


ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
DEFAULT_PLAN_PATH = REPO_ROOT / "contracts" / "site_plans" / "demolition_pipeline_v1.json"
DEFAULT_TARGET_INDEXES = (1, 1, 0)
DEFAULT_START_SIDES = (-1, 1, -1)
DEFAULT_CUT_RATIOS = (0.92, 0.32, 0.92)
# ``Rotate90`` turns every imported excavator toward the same local side.  The
# dump mound must therefore use the same local side for all three machines;
# their alternating world headings naturally place the mounds on opposite
# sides of the trench where appropriate.
DEFAULT_DUMP_SIDES = (1, 1, 1)
# The southern work front curves under the first spoil bank. Moving only that
# bank three metres farther behind EXC-001 keeps the mound footprint completely
# off the pipeline corridor. The centre and northern placements already have
# safe clearances and must remain unchanged.
DEFAULT_DUMP_BANK_INSETS_M = (3.0, 0.0, 0.0)
DEFAULT_SCOOP_COUNT = 1

load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


@dataclass(frozen=True)
class DemoWorkfront:
    """Validated execution settings for one excavator and one work front."""

    workfront_id: str
    equipment_id: str
    equipment_prim_path: str
    target_prim_path: str
    target_prim_paths: tuple[str, ...]
    target_center_xy: tuple[float, float]
    start_position: tuple[float, float, float]
    excavation_cut_ratio: float
    dump_side: float
    dump_bank_inset_m: float
    intentional_under_excavation: bool


def load_demo_workfronts(plan_path: str | Path = DEFAULT_PLAN_PATH) -> list[DemoWorkfront]:
    """Load the canonical plan and derive staggered positions for three machines."""

    source = Path(plan_path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    workfronts = list((payload.get("work_area") or {}).get("workfronts") or [])
    if len(workfronts) != 3:
        raise ValueError("the Isaac demo requires exactly three plan work fronts")

    results: list[DemoWorkfront] = []
    for index, raw in enumerate(workfronts):
        bounds = raw.get("bounds") or {}
        target_paths = [str(value) for value in raw.get("target_prim_paths") or []]
        target_index = DEFAULT_TARGET_INDEXES[index]
        required_bounds = ("min_x", "max_x", "min_y", "max_y")
        if any(name not in bounds for name in required_bounds):
            raise ValueError(f"work front {index + 1} has incomplete bounds")
        if target_index >= len(target_paths):
            raise ValueError(f"work front {index + 1} has no representative target")

        side = DEFAULT_START_SIDES[index]
        start_x = (
            float(bounds["min_x"]) - 4.0
            if side < 0
            else float(bounds["max_x"]) + 4.0
        )
        start_y = (float(bounds["min_y"]) + float(bounds["max_y"])) * 0.5
        results.append(
            DemoWorkfront(
                workfront_id=str(raw.get("id") or f"EXC-FRONT-{index + 1:02d}"),
                equipment_id=str(raw.get("equipment_id") or f"EXC-{index + 1:03d}"),
                equipment_prim_path=str(raw.get("equipment_prim_path") or ""),
                target_prim_path=target_paths[target_index],
                target_prim_paths=tuple(target_paths),
                target_center_xy=(
                    (float(bounds["min_x"]) + float(bounds["max_x"])) * 0.5,
                    (float(bounds["min_y"]) + float(bounds["max_y"])) * 0.5,
                ),
                start_position=(start_x, start_y, 0.0),
                excavation_cut_ratio=DEFAULT_CUT_RATIOS[index],
                dump_side=float(DEFAULT_DUMP_SIDES[index]),
                dump_bank_inset_m=float(DEFAULT_DUMP_BANK_INSETS_M[index]),
                intentional_under_excavation=index == 1,
            )
        )

    equipment_paths = {item.equipment_prim_path for item in results}
    target_paths = [path for item in results for path in item.target_prim_paths]
    if "" in equipment_paths or len(equipment_paths) != 3:
        raise ValueError("the three work fronts need unique equipment Prim paths")
    if not target_paths or len(set(target_paths)) != len(target_paths):
        raise ValueError("the three work fronts need unique excavation targets")
    return results


def parse_args() -> argparse.Namespace:
    """Parse standalone demo arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="run without the Isaac GUI")
    parser.add_argument(
        "--presentation",
        action="store_true",
        help="show only the construction viewport in a maximized movable window",
    )
    parser.add_argument("--close-on-finish", action="store_true", help="close the GUI after the demo")
    parser.add_argument("--site", default=None, help="demolition-site USD/USDZ path")
    parser.add_argument("--equipment", default=None, help="animated excavator USD path")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="pipeline site plan JSON")
    parser.add_argument(
        "--animation-seconds",
        type=float,
        default=3.5,
        help="nominal duration used by each authored arm animation",
    )
    parser.add_argument(
        "--scoops",
        type=int,
        default=DEFAULT_SCOOP_COUNT,
        help="number of synchronized incremental scoop cycles",
    )
    parser.add_argument(
        "--intentional-defect",
        action="store_true",
        help="leave the centre work front intentionally under-excavated",
    )
    parser.add_argument(
        "--skip-sensors",
        action="store_true",
        help="skip the three mounted camera/LiDAR coverage captures",
    )
    parser.add_argument("--save-usd", default=None, help="optional path for the final demo Stage")
    return parser.parse_args()


def _required_asset(raw_value: str | None, fallback: Path | None, label: str) -> Path:
    candidate = Path(raw_value).expanduser() if raw_value else fallback
    if candidate is None or not candidate.resolve().is_file():
        raise FileNotFoundError(f"{label} was not found: {candidate}")
    return candidate.resolve()


def _set_viewport_camera(stage: Any, target_path: str | None = None) -> None:
    """Frame the pipeline corridor or one work target in the active viewport."""

    try:
        from omni.kit.viewport.utility import get_active_viewport
        from omni.kit.viewport.utility.camera_state import ViewportCameraState
        from pxr import Gf, Usd, UsdGeom

        if target_path:
            prim = stage.GetPrimAtPath(target_path)
            cache = UsdGeom.BBoxCache(
                Usd.TimeCode.Default(),
                [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
                useExtentsHint=True,
            )
            bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            minimum, maximum = bounds.GetMin(), bounds.GetMax()
            target = tuple(float((minimum[i] + maximum[i]) * 0.5) for i in range(3))
            position = (target[0] + 18.0, target[1] - 22.0, target[2] + 13.0)
        else:
            target = (-11.0, -7.0, 1.0)
            position = (42.0, -72.0, 48.0)

        viewport = get_active_viewport()
        if viewport is None:
            return
        camera = ViewportCameraState(viewport=viewport)
        camera.set_position_world(Gf.Vec3d(*position), True)
        camera.set_target_world(Gf.Vec3d(*target), True)
    except Exception as error:
        print(f"[demo] viewport camera setup skipped: {error}", flush=True)


def _write_report(output_root: Path, report: dict[str, Any]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / "report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _capture_sensor_phase(
    sensor_rigs: list[tuple[DemoWorkfront, Any]],
    exporter: Any,
    phase: str,
) -> dict[str, Any]:
    """Capture clean RGB and optional runtime LiDAR evidence for every machine."""

    for _, rig in sensor_rigs:
        rig.clear_lidar_visualization()

    results: dict[str, Any] = {}
    for workfront, rig in sensor_rigs:
        camera = rig.capture_camera(
            exporter,
            f"sensors/{workfront.equipment_id}/{phase}-camera.png",
        )
        results[workfront.equipment_id] = {"camera": camera}

    for workfront, rig in sensor_rigs:
        lidar = rig.capture_lidar(
            exporter,
            f"sensors/{workfront.equipment_id}/{phase}-lidar.ply",
        )
        results[workfront.equipment_id]["lidar"] = lidar
        camera_state = (
            "ok"
            if results[workfront.equipment_id]["camera"].get("available")
            else "failed"
        )
        if lidar.get("capture_mode") == "declared-only":
            lidar_state = "configured (runtime scan skipped)"
        elif lidar.get("available"):
            lidar_state = (
                f"{int(lidar.get('point_count') or 0):,}/"
                f"{int(lidar.get('ray_count') or 0):,} hits"
            )
        else:
            lidar_state = "failed"
        print(
            f"[sensor {phase}] {workfront.equipment_id}: camera={camera_state} · "
            f"LiDAR={lidar_state}",
            flush=True,
        )
    return results


def main() -> None:
    """Build and execute the three-work-front excavation scene."""

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
    timeline = None
    output_root: Path | None = None
    report: dict[str, Any] = {}
    try:
        import omni.timeline
        import omni.usd
        from isaacsim.core.api import World

        from equipment_physics import (
            prepare_equipment_physics,
            track_contact_pose,
            track_visual_bounds,
        )
        from equipment_sensors import (
            EquipmentSensorRig,
            SensorRigConfig,
            prepare_raycast_collisions,
        )
        from evidence_exporter import EvidenceExporter
        from isaac_bridge import (
            IsaacBridge,
            excavation_approach_plan,
            per_scoop_cut_ratio,
        )
        from pipeline_scenario import create_pipeline_backfill
        from site_stage import add_lighting, default_site_asset, load_equipment, load_site, resolved_data_root
        from terrain_collision_proxy import (
            collision_proxy_height_sampler,
            create_terrain_collision_proxy,
            load_or_build_collision_proxy_data,
        )

        data_root = resolved_data_root()
        output_root = data_root / "isaac" / "three-excavator-demo"
        workfronts = load_demo_workfronts(args.plan)
        site_asset = _required_asset(
            args.site or os.getenv("SITEGIT_SITE_ASSET"),
            default_site_asset(data_root),
            "demolition-site asset",
        )
        equipment_asset = _required_asset(
            args.equipment or os.getenv("SITEGIT_EQUIPMENT_ASSET"),
            None,
            "animated excavator asset",
        )

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        print("=" * 68, flush=True)
        print("SiteGit standalone three-excavator demo", flush=True)
        print("No Backend, API, commit, or web map is used by this process.", flush=True)
        print(f"Site : {site_asset}", flush=True)
        print(f"Asset: {equipment_asset}", flush=True)
        print("=" * 68, flush=True)

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
        visual_surface = collision_proxy_height_sampler(visual_height_cache)
        material_root = data_root / "isaac" / "assets" / "materials"
        base_color = Path(
            os.getenv(
                "SITEGIT_PIPELINE_SOIL_BASECOLOR",
                str(material_root / "demolition_soil_tile_diffuse.jpg"),
            )
        )
        normal = Path(
            os.getenv(
                "SITEGIT_PIPELINE_SOIL_NORMAL",
                str(material_root / "demolition_soil_tile_normal.jpg"),
            )
        )
        pipeline = create_pipeline_backfill(
            stage,
            surface_height=visual_surface,
            base_color_texture=base_color if base_color.is_file() else None,
            normal_texture=normal if normal.is_file() else None,
            update_callback=app.update,
        )

        sensor_collision_report: dict[str, Any] | None = None
        sensor_config = (
            SensorRigConfig.from_environment() if not args.skip_sensors else None
        )
        if sensor_config is not None and sensor_config.lidar_runtime_enabled:
            sensor_collision_roots = [
                value.strip()
                for value in os.getenv(
                    "SITEGIT_LIDAR_COLLISION_ROOTS",
                    "/World/SiteGitTerrainCollision,/World/Diggable,/World/SiteGit",
                ).split(",")
                if value.strip()
            ]
            sensor_collision_report = prepare_raycast_collisions(
                stage,
                sensor_collision_roots,
                update_callback=app.update,
                cooking_frames=max(
                    0,
                    int(os.getenv("SITEGIT_COLLISION_COOKING_FRAMES", "20")),
                ),
            )
            print(
                "[sensors] raycast collision ready: "
                f"{sensor_collision_report['mesh_count']} meshes",
                flush=True,
            )
        elif sensor_config is not None:
            print(
                "[sensors] LiDAR capability declared; runtime raycast scan disabled",
                flush=True,
            )

        equipment_reports: list[dict[str, Any]] = []
        for workfront in workfronts:
            loaded = load_equipment(
                stage,
                equipment_asset,
                prim_path=workfront.equipment_prim_path,
                equipment_id=workfront.equipment_id,
                position=workfront.start_position,
                simulation_app=app,
                settle_frames=120,
                surface_height=physics_surface,
            )
            equipment_reports.append({"workfront": asdict(workfront), "loaded": loaded})
            print(
                f"[placed] {workfront.equipment_id} -> {workfront.workfront_id} "
                f"at ({workfront.start_position[0]:.1f}, {workfront.start_position[1]:.1f})",
                flush=True,
            )

        physics_reports = [
            prepare_equipment_physics(
                stage,
                workfront.equipment_prim_path,
                surface_height=physics_surface,
            )
            for workfront in workfronts
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
        _set_viewport_camera(stage)
        scoop_count = max(1, min(12, int(args.scoops)))
        runtime_workfronts: list[dict[str, Any]] = []
        sensor_rigs: list[tuple[DemoWorkfront, Any]] = []
        sensor_setups: list[dict[str, Any]] = []
        sensor_captures: dict[str, Any] = {}

        # First bring every machine into working range. Excavation starts only
        # after all three are ready, and all arm clips below share one timeline.
        for index, workfront in enumerate(workfronts, 1):
            _set_viewport_camera(stage, workfront.target_prim_path)
            print("-" * 68, flush=True)
            print(
                f"[positioning {index}/3] {workfront.equipment_id} -> "
                f"{workfront.target_prim_path}",
                flush=True,
            )
            equipment = stage.GetPrimAtPath(workfront.equipment_prim_path)
            target = stage.GetPrimAtPath(workfront.target_prim_path)
            targets = [stage.GetPrimAtPath(path) for path in workfront.target_prim_paths]
            if (
                not equipment.IsValid()
                or not target.IsValid()
                or any(not item.IsValid() for item in targets)
            ):
                raise RuntimeError(
                    f"invalid demo Prim: {workfront.equipment_prim_path} / "
                    f"{', '.join(workfront.target_prim_paths)}"
                )
            equipment_start = track_contact_pose(stage, workfront.equipment_prim_path)
            bounds = track_visual_bounds(stage, workfront.equipment_prim_path)
            track_size = {
                axis: float(bounds["max"][axis_index] - bounds["min"][axis_index])
                for axis_index, axis in enumerate(("x", "y", "z"))
            }
            target_position, target_size = bridge._world_bounds(target)
            approach_plan = excavation_approach_plan(
                equipment_start,
                target_position,
                target_size,
                track_size,
                3.0,
            )
            drive = bridge.drive_equipment_to(
                workfront.equipment_prim_path,
                list(approach_plan["destination_xy"]),
                requested_seconds=max(0.5, float(args.animation_seconds)),
            )
            facing = bridge.face_equipment_toward(
                workfront.equipment_prim_path,
                list(approach_plan["target_xy"]),
            )
            leave_defect = bool(
                args.intentional_defect and workfront.intentional_under_excavation
            )
            requested_total_cut = (
                workfront.excavation_cut_ratio if leave_defect else 0.995
            )
            runtime_workfronts.append(
                {
                    "workfront": asdict(workfront),
                    "equipment": equipment,
                    "target": target,
                    "target_size": target_size,
                    "targets": targets,
                    "approach_plan": approach_plan,
                    "equipment_pose": dict(facing["end_track_pose"]),
                    "preparation": {"drive": drive, "facing": facing},
                    "per_scoop_cut_ratio": per_scoop_cut_ratio(
                        requested_total_cut,
                        scoop_count,
                    ),
                    "requested_total_cut_ratio": requested_total_cut,
                    "finish_clear": not leave_defect,
                    "animation_paths": [],
                    "scoops": [],
                }
            )

        if sensor_config is not None:
            for workfront in workfronts:
                rig = EquipmentSensorRig(
                    stage,
                    workfront.equipment_prim_path,
                    update_callback=lambda: world.step(render=True),
                    config=sensor_config,
                )
                setup = rig.initialize(include_imu=False)
                sensor_rigs.append((workfront, rig))
                sensor_setups.append(setup)
                print(
                    f"[sensor mount] {workfront.equipment_id}: "
                    f"camera {setup['camera_horizontal_fov_degrees']:.1f}° x "
                    f"{setup['camera_vertical_fov_degrees']:.1f}° · "
                    f"pitch {setup['camera_pitch_degrees']:.1f}° down · "
                    f"LiDAR {setup['lidar_horizontal_fov_degrees']:.1f}° / "
                    f"{setup['lidar_ray_count']:,} rays",
                    flush=True,
                )
            evidence_exporter = EvidenceExporter(output_root)
            sensor_captures["before"] = _capture_sensor_phase(
                sensor_rigs,
                evidence_exporter,
                "before",
            )

        _set_viewport_camera(stage)
        equipment_prims = [state["equipment"] for state in runtime_workfronts]
        phase_seconds = max(1.2, float(args.animation_seconds) * 0.55)
        dig_seconds = max(2.0, float(args.animation_seconds))
        swing_seconds = max(1.5, float(args.animation_seconds) * 0.75)
        dump_seconds = max(1.2, float(args.animation_seconds) * 0.6)
        print("=" * 68, flush=True)
        print(
            f"Parallel excavation begins: 3 machines x {scoop_count} scoop cycles",
            flush=True,
        )
        print("All three arm animations now share the same timeline.", flush=True)
        print("=" * 68, flush=True)

        for scoop_index in range(scoop_count):
            print("-" * 68, flush=True)
            print(
                f"[parallel scoop {scoop_index + 1}/{scoop_count}] "
                "EXC-001 + EXC-002 + EXC-003",
                flush=True,
            )
            for animation_name, duration in (
                ("ArmOut", phase_seconds),
                ("ArmDig", dig_seconds),
                ("ArmInDig", phase_seconds),
            ):
                paths = bridge.play_skeletal_animations_parallel(
                    equipment_prims,
                    animation_name,
                    duration_seconds=duration,
                )
                for state in runtime_workfronts:
                    equipment_path = state["workfront"]["equipment_prim_path"]
                    state["animation_paths"].extend(
                        path for path in paths if path.startswith(equipment_path + "/")
                    )

            # USD edits happen during the same rendered moment directly after
            # the shared dig clip. Each pass visibly lowers the remaining soil.
            progress = float(scoop_index + 1) / float(scoop_count)
            minimum_cut_influence = min(1.0, 0.12 + 0.88 * progress**1.35)
            for state in runtime_workfronts:
                applied_cut_ratio = float(state["per_scoop_cut_ratio"])
                if scoop_index == scoop_count - 1 and state["finish_clear"]:
                    # The final bucket cleans the complete work-front footprint
                    # down to the trench base instead of leaving a raised rim.
                    applied_cut_ratio = max(0.95, applied_cut_ratio)
                target_deformations: list[dict[str, Any]] = []
                for target in state["targets"]:
                    target_deformations.append(
                        {
                            "target_prim_path": str(target.GetPath()),
                            **bridge._deform_diggable_mesh(
                                target,
                                cut_ratio=applied_cut_ratio,
                                minimum_cut_influence=minimum_cut_influence,
                            ),
                        }
                    )
                deformation = {
                    "available": any(
                        bool(item.get("available")) for item in target_deformations
                    ),
                    "method": "multi_prim_usd_mesh_vertex_sculpt",
                    "target_count": len(target_deformations),
                    "targets": target_deformations,
                    "before_volume_m3": sum(
                        float(item.get("before_volume_m3") or 0.0)
                        for item in target_deformations
                    ),
                    "after_volume_m3": sum(
                        float(item.get("after_volume_m3") or 0.0)
                        for item in target_deformations
                    ),
                    "removed_volume_m3": sum(
                        float(item.get("removed_volume_m3") or 0.0)
                        for item in target_deformations
                    ),
                    "cut_ratio": applied_cut_ratio,
                    "minimum_cut_influence": minimum_cut_influence,
                }
                state["scoops"].append(
                    {
                        "index": scoop_index + 1,
                        "terrain_deformation": deformation,
                        "moved_soil": None,
                    }
                )
                print(
                    f"  {state['workfront']['equipment_id']}: removed "
                    f"{float(deformation.get('removed_volume_m3') or 0.0):.2f} m3 "
                    f"from {len(target_deformations)} soil sections",
                    flush=True,
                )
            for _ in range(18):
                world.step(render=not args.headless)

            paths = bridge.play_skeletal_animations_parallel(
                equipment_prims,
                "Rotate90",
                duration_seconds=swing_seconds,
            )
            for state in runtime_workfronts:
                equipment_path = state["workfront"]["equipment_prim_path"]
                state["animation_paths"].extend(
                    path for path in paths if path.startswith(equipment_path + "/")
                )
            for _ in range(18):
                world.step(render=not args.headless)

            paths = bridge.play_skeletal_animations_parallel(
                equipment_prims,
                "ArmDump",
                duration_seconds=dump_seconds,
                pose_overlay_animation_name="Rotate90",
                pose_overlay_joint_suffixes=("/Rotator",),
            )
            for state in runtime_workfronts:
                equipment_path = state["workfront"]["equipment_prim_path"]
                state["animation_paths"].extend(
                    path for path in paths if path.startswith(equipment_path + "/")
                )
                deformation = state["scoops"][-1]["terrain_deformation"]
                state["scoops"][-1]["moved_soil"] = bridge._create_moved_soil_pile(
                    target=state["target"],
                    target_size=state["target_size"],
                    equipment_position=state["equipment_pose"],
                    approach_plan=state["approach_plan"],
                    removed_volume_m3=float(
                        deformation.get("removed_volume_m3") or 0.0
                    ),
                    dump_side=float(state["workfront"]["dump_side"]),
                    dump_sequence_index=scoop_index,
                    dump_bank_inset_m=float(
                        state["workfront"]["dump_bank_inset_m"]
                    ),
                )
                if scoop_index == scoop_count - 1 and state["finish_clear"]:
                    # The plan assigns several fill Prim sections to each
                    # machine. Once its final bucket is dumped, remove every
                    # assigned section so the complete trench is exposed.
                    cleared_paths: list[str] = []
                    for target in state["targets"]:
                        cleared_paths.append(str(target.GetPath()))
                        target.SetActive(False)
                    state["scoops"][-1]["cleared_target_prim_paths"] = cleared_paths
            for _ in range(24):
                world.step(render=not args.headless)

            paths = bridge.play_skeletal_animations_parallel(
                equipment_prims,
                "Rotate90",
                duration_seconds=swing_seconds,
                reverse=True,
            )
            for state in runtime_workfronts:
                equipment_path = state["workfront"]["equipment_prim_path"]
                state["animation_paths"].extend(
                    path for path in paths if path.startswith(equipment_path + "/")
                )
            for _ in range(24):
                world.step(render=not args.headless)

        for _ in range(60):
            world.step(render=not args.headless)

        if sensor_rigs:
            sensor_captures["after"] = _capture_sensor_phase(
                sensor_rigs,
                evidence_exporter,
                "after",
            )

        excavation_results: list[dict[str, Any]] = []
        for state in runtime_workfronts:
            removed = sum(
                float(item["terrain_deformation"].get("removed_volume_m3") or 0.0)
                for item in state["scoops"]
            )
            deposited = sum(
                float((item.get("moved_soil") or {}).get("deposited_volume_m3") or 0.0)
                for item in state["scoops"]
            )
            excavation_results.append(
                {
                    "workfront": state["workfront"],
                    "preparation": state["preparation"],
                    "scoop_count": scoop_count,
                    "per_scoop_cut_ratio": state["per_scoop_cut_ratio"],
                    "requested_total_cut_ratio": state["requested_total_cut_ratio"],
                    "finish_clear": state["finish_clear"],
                    "scoops": state["scoops"],
                    "animation_paths": state["animation_paths"],
                    "total_removed_volume_m3": removed,
                    "total_deposited_volume_m3": deposited,
                    "final_track_pose": track_contact_pose(
                        stage, state["workfront"]["equipment_prim_path"]
                    ),
                }
            )
            print(
                f"[complete] {state['workfront']['equipment_id']} "
                f"removed={removed:.2f} m3 · deposited={deposited:.2f} m3 · "
                f"scoops={scoop_count}",
                flush=True,
            )

        timeline.pause()
        _set_viewport_camera(stage)
        report = {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "isaac-sim-only",
            "execution_mode": "parallel-incremental-scoops",
            "intentional_defect_enabled": bool(args.intentional_defect),
            "web_connected": False,
            "site": site_info,
            "collision": collision,
            "pipeline": pipeline,
            "pipeline_height_cache": {
                "path": str(visual_height_cache),
                "cache_hit": visual_height_cache_hit,
                "valid_cell_count": visual_height_data["valid_cell_count"],
            },
            "equipment": equipment_reports,
            "physics": physics_reports,
            "excavations": excavation_results,
            "sensors": {
                "enabled": bool(sensor_rigs),
                "collision": sensor_collision_report,
                "setups": sensor_setups,
                "captures": sensor_captures,
            },
        }
        report_path = _write_report(output_root, report)
        (output_root / "failure.txt").unlink(missing_ok=True)
        # Always persist the completed excavation so the Phase 2 pipe-install
        # demo and later Phase 3 backfill can continue from this exact Stage.
        save_path = (
            Path(args.save_usd).expanduser().resolve()
            if args.save_usd
            else output_root / "excavated-stage.usda"
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        stage.GetRootLayer().Export(save_path.as_posix())
        report["saved_stage"] = str(save_path)
        report_path = _write_report(output_root, report)

        print("=" * 68, flush=True)
        print("Three-excavator demo complete", flush=True)
        if args.intentional_defect:
            print("EXC-001: complete excavation + side dump", flush=True)
            print("EXC-002: intentionally incomplete excavation + side dump", flush=True)
            print("EXC-003: complete excavation + side dump", flush=True)
        else:
            print("EXC-001/002/003: complete excavation + side dump", flush=True)
        print(f"Report: {report_path}", flush=True)
        if sensor_rigs:
            print(f"Sensor evidence: {output_root / 'sensors'}", flush=True)
        print("=" * 68, flush=True)

        if not args.headless and not args.close_on_finish:
            print("The Stage is paused. Close the Isaac Sim window to finish.", flush=True)
            while app.is_running():
                app.update()
    except Exception:
        if output_root is None:
            output_root = REPO_ROOT / "runtime" / "three-excavator-demo"
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if timeline is not None:
            try:
                timeline.stop()
            except Exception:
                pass
        app.close(wait_for_replicator=False, skip_cleanup=True)


if __name__ == "__main__":
    main()
