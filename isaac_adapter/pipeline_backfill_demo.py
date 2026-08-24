"""Run the three-excavator pipeline backfill phase in Isaac Sim only.

The demo continues from ``pipeline-installed-stage.usda``.  All three machines
work in parallel: rotate to the spoil bank, scoop, rotate back toward the
trench, dump, and repeat.  Each cycle visibly consumes the excavated spoil and
restores one fifth of the approved trench-fill surface.  The Backend and web
application are intentionally not used by this standalone scene.
"""

from __future__ import annotations

import argparse
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

load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def parse_args() -> argparse.Namespace:
    """Parse standalone backfill-demo arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--presentation",
        action="store_true",
        help="show only the construction viewport in a maximized movable window",
    )
    parser.add_argument("--close-on-finish", action="store_true")
    parser.add_argument("--site", default=None, help="reserved portable site asset path")
    parser.add_argument("--equipment", default=None, help="animated excavator USD path")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH))
    parser.add_argument("--installed-stage", default=None)
    parser.add_argument("--scoops", type=int, default=5)
    parser.add_argument("--animation-seconds", type=float, default=3.0)
    parser.add_argument("--save-usd", default=None)
    return parser.parse_args()


def _load_plan(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload.get("work_area"), dict):
        raise ValueError(f"pipeline plan has no work_area: {source}")
    return payload


def _set_viewport_camera(stage: Any) -> None:
    """Show the complete trench, spoil banks, and three machines."""

    try:
        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        if viewport is None:
            return
        camera_path = "/World/SiteGitBackfillDemoCamera"
        from pxr import Gf, Sdf, UsdGeom

        camera = UsdGeom.Camera.Define(stage, Sdf.Path(camera_path))
        camera.CreateFocalLengthAttr(28.0)
        camera.CreateHorizontalApertureAttr(23.955)
        transform = camera.AddTransformOp()
        transform.Set(
            Gf.Matrix4d().SetLookAt(
                Gf.Vec3d(64.0, -82.0, 73.0),
                Gf.Vec3d(-14.0, -1.0, 0.0),
                Gf.Vec3d(0.0, 0.0, 1.0),
            ).GetInverse()
        )
        viewport.camera_path = camera_path
    except Exception as exc:
        print(f"[viewport] camera setup skipped: {exc}", flush=True)


def _write_report(output_root: Path, payload: dict[str, Any]) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _mesh_points(prim: Any) -> list[tuple[float, float, float]]:
    from pxr import UsdGeom

    values = UsdGeom.Mesh(prim).GetPointsAttr().Get() or []
    return [(float(value[0]), float(value[1]), float(value[2])) for value in values]


def _set_mesh_points(prim: Any, points: list[tuple[float, float, float]]) -> None:
    from pxr import Gf, UsdGeom

    values = [Gf.Vec3f(*point) for point in points]
    mesh = UsdGeom.Mesh(prim)
    mesh.GetPointsAttr().Set(values)
    extent = UsdGeom.PointBased.ComputeExtent(values)
    extent_attr = mesh.GetExtentAttr()
    if not extent_attr.IsValid():
        extent_attr = mesh.CreateExtentAttr()
    extent_attr.Set(extent)


def _set_collision(prim: Any, enabled: bool) -> None:
    from pxr import UsdPhysics

    collision = UsdPhysics.CollisionAPI(prim)
    if not collision:
        collision = UsdPhysics.CollisionAPI.Apply(prim)
    attr = collision.GetCollisionEnabledAttr()
    if not attr.IsValid():
        attr = collision.CreateCollisionEnabledAttr()
    attr.Set(bool(enabled))


def _collect_spoil_groups(
    stage: Any,
    workfronts: list[Any],
) -> list[list[dict[str, Any]]]:
    """Collect the five moved-soil meshes produced by each excavation front."""

    from pxr import Sdf, Usd, UsdGeom

    from pipeline_backfill import spoil_matches_targets

    root = stage.GetPrimAtPath(Sdf.Path("/World/Diggable"))
    groups: list[list[dict[str, Any]]] = [[] for _ in workfronts]
    if not root.IsValid():
        return groups
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
        useExtentsHint=True,
    )
    for prim in Usd.PrimRange(root):
        if not prim.IsValid() or not prim.IsActive() or not prim.IsA(UsdGeom.Mesh):
            continue
        name = str(prim.GetName())
        for index, workfront in enumerate(workfronts):
            target_names = [Path(path).name for path in workfront.target_prim_paths]
            if not spoil_matches_targets(name, target_names):
                continue
            bounds = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
            if bounds.IsEmpty():
                continue
            minimum, maximum = bounds.GetMin(), bounds.GetMax()
            groups[index].append(
                {
                    "prim": prim,
                    "prim_path": str(prim.GetPath()),
                    "original_points": _mesh_points(prim),
                    "center": [
                        float((minimum[0] + maximum[0]) * 0.5),
                        float((minimum[1] + maximum[1]) * 0.5),
                        float(maximum[2]),
                    ],
                }
            )
            break
    for group in groups:
        group.sort(key=lambda item: item["prim_path"])
    return groups


def _restore_target_records(stage: Any, workfronts: list[Any]) -> list[list[dict[str, Any]]]:
    """Snapshot newly regenerated final surfaces and collapse them to trench level."""

    from pxr import Sdf

    from pipeline_backfill import blend_backfill_points

    groups: list[list[dict[str, Any]]] = []
    for workfront in workfronts:
        records: list[dict[str, Any]] = []
        for path in workfront.target_prim_paths:
            prim = stage.GetPrimAtPath(Sdf.Path(path))
            if not prim.IsValid():
                raise RuntimeError(f"regenerated backfill target is missing: {path}")
            final_points = _mesh_points(prim)
            top_count = int(prim.GetCustomDataByKey("sitegitTopVertexCount") or 0)
            if top_count <= 0:
                raise RuntimeError(f"backfill target has no top-grid metadata: {path}")
            _set_collision(prim, False)
            _set_mesh_points(prim, blend_backfill_points(final_points, top_count, 0.0))
            records.append(
                {
                    "prim": prim,
                    "prim_path": path,
                    "final_points": final_points,
                    "top_vertex_count": top_count,
                }
            )
        groups.append(records)
    return groups


def _apply_cycle_geometry(
    target_groups: list[list[dict[str, Any]]],
    spoil_groups: list[list[dict[str, Any]]],
    progress: float,
) -> None:
    """Consume spoil and restore trench sections at a shared progress ratio."""

    from pipeline_backfill import blend_backfill_points, shrink_spoil_points

    for targets, spoils in zip(target_groups, spoil_groups):
        for record in targets:
            _set_mesh_points(
                record["prim"],
                blend_backfill_points(
                    record["final_points"],
                    record["top_vertex_count"],
                    progress,
                ),
            )
        for record in spoils:
            _set_mesh_points(
                record["prim"],
                shrink_spoil_points(record["original_points"], progress),
            )


def main() -> None:
    """Execute the synchronized three-machine backfill demo."""

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
    try:
        import omni.timeline
        import omni.usd
        from isaacsim.core.api import World
        from pxr import Sdf, Usd, UsdGeom, UsdPhysics

        from equipment_physics import prepare_equipment_physics, track_contact_pose
        from isaac_bridge import IsaacBridge
        from pipeline_installation import PIPE_INSTALLATION_ROOT_PATH
        from pipeline_scenario import PIPELINE_ROOT_PATH, create_pipeline_backfill
        from site_stage import load_equipment, resolved_data_root
        from terrain_collision_proxy import (
            collision_proxy_height_sampler,
            create_terrain_collision_proxy,
            load_or_build_collision_proxy_data,
        )
        from three_excavator_demo import load_demo_workfronts

        data_root = resolved_data_root()
        output_root = data_root / "isaac" / "pipeline-backfill-demo"
        source_stage = (
            Path(args.installed_stage).expanduser().resolve()
            if args.installed_stage
            else data_root
            / "isaac"
            / "pipeline-installation-demo"
            / "pipeline-installed-stage.usda"
        )
        if not source_stage.is_file():
            raise FileNotFoundError(
                "pipeline installation Stage was not found. Run "
                "start_sitegit_excavator_demo.bat and "
                f"start_sitegit_pipeline_demo.bat first: {source_stage}"
            )

        plan = _load_plan(args.plan)
        workfronts = load_demo_workfronts(args.plan)
        context = omni.usd.get_context()
        print(f"Opening installed pipeline Stage: {source_stage}", flush=True)
        context.open_stage(str(source_stage))
        for _ in range(80):
            app.update()
        stage = context.get_stage()
        if stage is None:
            raise RuntimeError(f"failed to open pipeline Stage: {source_stage}")

        installed_root = stage.GetPrimAtPath(Sdf.Path(PIPE_INSTALLATION_ROOT_PATH))
        installed_meshes = (
            [
                prim
                for prim in Usd.PrimRange(installed_root)
                if prim.IsValid() and prim.IsActive() and prim.IsA(UsdGeom.Mesh)
            ]
            if installed_root.IsValid()
            else []
        )
        if not installed_meshes:
            raise RuntimeError(
                "backfill is blocked because the installed pipeline was not found"
            )

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

        spoil_groups = _collect_spoil_groups(stage, workfronts)
        if any(not group for group in spoil_groups):
            missing = [
                workfront.equipment_id
                for workfront, group in zip(workfronts, spoil_groups)
                if not group
            ]
            raise RuntimeError(
                "backfill spoil bank is missing for: " + ", ".join(missing)
            )

        existing_fill = stage.GetPrimAtPath(Sdf.Path(PIPELINE_ROOT_PATH))
        if existing_fill.IsValid():
            stage.RemovePrim(Sdf.Path(PIPELINE_ROOT_PATH))
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
        regenerated = create_pipeline_backfill(
            stage,
            surface_height=visual_surface,
            base_color_texture=base_color if base_color.is_file() else None,
            normal_texture=normal if normal.is_file() else None,
            update_callback=app.update,
        )
        target_groups = _restore_target_records(stage, workfronts)

        missing_equipment = [
            workfront
            for workfront in workfronts
            if not stage.GetPrimAtPath(Sdf.Path(workfront.equipment_prim_path)).IsValid()
        ]
        if missing_equipment:
            equipment_asset = Path(args.equipment).expanduser().resolve() if args.equipment else None
            if equipment_asset is None or not equipment_asset.is_file():
                raise FileNotFoundError(
                    "installed Stage has no excavators and --equipment is unavailable"
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
        for _ in range(90):
            world.step(render=not args.headless)
        bridge = IsaacBridge(
            stage=stage,
            update_callback=lambda: world.step(render=not args.headless),
        )
        _set_viewport_camera(stage)

        # Initialize the physical controller at each current track coordinate.
        equipment_prims: list[Any] = []
        for workfront in workfronts:
            pose = track_contact_pose(stage, workfront.equipment_prim_path)
            bridge.drive_equipment_to(
                workfront.equipment_prim_path,
                [float(pose["x"]), float(pose["y"])],
                requested_seconds=0.5,
            )
            equipment_prims.append(stage.GetPrimAtPath(workfront.equipment_prim_path))

        # Backfill is a stationary upper-structure operation. Pin the physical
        # carriers at their settled track poses so long arm sequences cannot
        # accumulate a slope/contact impulse and roll one machine over. Tracks
        # and chassis remain fixed; only the selected skeleton joints animate.
        for equipment in equipment_prims:
            rigid = UsdPhysics.RigidBodyAPI(equipment)
            rigid.CreateVelocityAttr().Set((0.0, 0.0, 0.0))
            rigid.CreateAngularVelocityAttr().Set((0.0, 0.0, 0.0))
            rigid.CreateKinematicEnabledAttr().Set(True)
            equipment.SetCustomDataByKey(
                "sitegitBackfillCarrierMode", "stationary-kinematic"
            )
        for _ in range(12):
            world.step(render=not args.headless)

        # Start all three imported skeletons from one known intact pose. The
        # installed-stage file may have stopped at a handling animation sample.
        animation_paths: list[str] = []
        animation_paths.extend(
            bridge.play_skeletal_animations_parallel(
                equipment_prims,
                "Default_Pose",
                duration_seconds=0.8,
            )
        )

        scoop_count = max(1, min(10, int(args.scoops)))
        nominal = max(0.75, float(args.animation_seconds))
        swing_seconds = max(1.8, nominal)
        reach_seconds = max(1.4, nominal * 0.72)
        dig_seconds = max(1.8, nominal * 0.9)
        lift_seconds = max(1.5, nominal * 0.78)
        dump_seconds = max(1.6, nominal * 0.8)

        print("=" * 68, flush=True)
        print("SiteGit synchronized three-excavator backfill demo", flush=True)
        print("No Backend, API, commit, or web map is used by this process.", flush=True)
        print(f"Input Stage : {source_stage}", flush=True)
        print(f"Pipeline    : {len(installed_meshes)} installed pieces remain in place", flush=True)
        print(
            "Spoil banks : "
            + ", ".join(
                f"{workfront.equipment_id}={len(group)}"
                for workfront, group in zip(workfronts, spoil_groups)
            ),
            flush=True,
        )
        print(f"Cycles      : {scoop_count}", flush=True)
        print("=" * 68, flush=True)

        for cycle in range(scoop_count):
            progress = float(cycle + 1) / float(scoop_count)
            print(
                f"[parallel backfill {cycle + 1}/{scoop_count}] "
                "EXC-001 + EXC-002 + EXC-003",
                flush=True,
            )
            # Exact inverse of the proven excavation cycle:
            #
            #   excavation
            #     ArmOut -> ArmDig -> ArmInDig -> Rotate90 -> ArmDump
            #     -> reverse Rotate90
            #
            #   backfill
            #     Rotate90 -> reverse ArmDump -> reverse Rotate90
            #     -> reverse ArmInDig -> reverse ArmDig -> reverse ArmOut
            #
            # Do not freeze or rebuild selected joint branches here.  Playing
            # the same complete imported clips in reverse keeps the source
            # rig intact and avoids the separated/flipped excavator seen with
            # the earlier custom backfill pose composition.
            animation_paths.extend(
                bridge.play_skeletal_animations_parallel(
                    equipment_prims,
                    "Rotate90",
                    duration_seconds=swing_seconds,
                )
            )
            animation_paths.extend(
                bridge.play_skeletal_animations_parallel(
                    equipment_prims,
                    "ArmDump",
                    duration_seconds=dump_seconds,
                    reverse=True,
                    pose_overlay_animation_name="Rotate90",
                    pose_overlay_joint_suffixes=("/Rotator",),
                )
            )

            # Reverse ArmDump closes/lifts the bucket at the spoil bank.  Only
            # after that visual pickup do the corresponding spoil meshes shrink.
            from pipeline_backfill import shrink_spoil_points

            for group in spoil_groups:
                for record in group:
                    _set_mesh_points(
                        record["prim"],
                        shrink_spoil_points(record["original_points"], progress),
                    )
            for _ in range(12):
                world.step(render=not args.headless)

            animation_paths.extend(
                bridge.play_skeletal_animations_parallel(
                    equipment_prims,
                    "Rotate90",
                    duration_seconds=swing_seconds,
                    reverse=True,
                )
            )

            # These are the first three excavation clips in the exact reverse
            # order and direction.  Their final state visually lowers/releases
            # the carried soil into the trench.
            for name, duration in (
                ("ArmInDig", lift_seconds),
                ("ArmDig", dig_seconds),
                ("ArmOut", reach_seconds),
            ):
                animation_paths.extend(
                    bridge.play_skeletal_animations_parallel(
                        equipment_prims,
                        name,
                        duration_seconds=duration,
                        reverse=True,
                    )
                )

            # All three dumps land together. The final cycle reproduces the
            # exact approved surface vertices, not an approximate mound.
            from pipeline_backfill import blend_backfill_points

            for targets in target_groups:
                for record in targets:
                    _set_mesh_points(
                        record["prim"],
                        blend_backfill_points(
                            record["final_points"],
                            record["top_vertex_count"],
                            progress,
                        ),
                    )
            for _ in range(18):
                world.step(render=not args.headless)

        for group in spoil_groups:
            for record in group:
                record["prim"].SetActive(False)
        for targets in target_groups:
            for record in targets:
                _set_mesh_points(record["prim"], record["final_points"])
                _set_collision(record["prim"], True)
                record["prim"].SetCustomDataByKey("sitegitTerrainRevision", scoop_count)
                record["prim"].SetCustomDataByKey("sitegitScenarioRole", "pipeline_backfilled")
        for _ in range(50):
            world.step(render=not args.headless)
        timeline.pause()

        save_path = (
            Path(args.save_usd).expanduser().resolve()
            if args.save_usd
            else output_root / "backfilled-stage.usda"
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        stage.GetRootLayer().Export(save_path.as_posix())
        workflow = next(
            (
                item
                for item in plan.get("workflow") or []
                if str(item.get("id")) == "backfill"
            ),
            {},
        )
        report = {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "isaac-sim-only",
            "phase_id": "backfill",
            "zone_id": "C",
            "execution_mode": "three-excavator-synchronized-reverse-excavation",
            "web_connected": False,
            "source_stage": str(source_stage),
            "saved_stage": str(save_path),
            "cycle_count": scoop_count,
            "target_amount_m3": float(workflow.get("target_amount") or 0.0),
            "backfill_progress_percent": 100.0,
            "restored_section_count": int(regenerated["section_count"]),
            "installed_pipeline_piece_count": len(installed_meshes),
            "consumed_spoil_prim_count": sum(len(group) for group in spoil_groups),
            "equipment": [
                {
                    "equipment_id": workfront.equipment_id,
                    "workfront_id": workfront.workfront_id,
                    "target_prim_paths": list(workfront.target_prim_paths),
                    "spoil_prim_paths": [item["prim_path"] for item in spoil_group],
                }
                for workfront, spoil_group in zip(workfronts, spoil_groups)
            ],
            "physics": physics_reports,
            "animation_paths": sorted(set(animation_paths)),
            "terrain_height_cache": {
                "path": str(visual_height_cache),
                "cache_hit": visual_height_cache_hit,
                "valid_cell_count": visual_height_data["valid_cell_count"],
            },
            "acceptance": {
                "result": "demo_complete",
                "reason": "all spoil banks consumed and approved surface restored",
                "measurement_source": "stage-mesh-readback",
            },
        }
        report_path = _write_report(output_root, report)
        (output_root / "failure.txt").unlink(missing_ok=True)
        print("=" * 68, flush=True)
        print("Three-excavator pipeline backfill demo complete", flush=True)
        print(f"Restored soil: {regenerated['section_count']} trench sections", flush=True)
        print(f"Consumed spoil: {sum(len(group) for group in spoil_groups)} Prim(s)", flush=True)
        print(f"Buried pipeline: {len(installed_meshes)} pieces", flush=True)
        print(f"Stage : {save_path}", flush=True)
        print(f"Report: {report_path}", flush=True)
        print("=" * 68, flush=True)

        if not args.headless and not args.close_on_finish:
            print("The Stage is paused. Close the Isaac Sim window to finish.", flush=True)
            while app.is_running():
                app.update()
    except Exception:
        if output_root is None:
            output_root = REPO_ROOT / "runtime" / "pipeline-backfill-demo"
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
