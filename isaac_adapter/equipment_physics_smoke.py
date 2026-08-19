"""Fast flat-ground smoke test for the excavator PhysX carrier."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

from dotenv import load_dotenv

ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def main() -> None:
    from isaacsim.simulation_app import SimulationApp

    output = REPO_ROOT / "runtime" / "equipment-physics-smoke"
    app = SimulationApp({"headless": True})
    timeline = None
    try:
        import omni.timeline
        import omni.usd
        from isaacsim.core.api import World
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

        from equipment_physics import prepare_equipment_physics, track_contact_pose
        from equipment_sensors import EquipmentSensorRig, SensorRigConfig
        from evidence_exporter import EvidenceExporter
        from isaac_bridge import IsaacBridge
        from site_stage import (
            add_lighting,
            create_diggable_soil_pile,
            load_equipment,
            prepare_stage,
        )

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        prepare_stage(stage)
        add_lighting(stage)
        ground = UsdGeom.Cube.Define(stage, Sdf.Path("/World/Ground"))
        ground.CreateSizeAttr(1.0)
        ground_xform = UsdGeom.XformCommonAPI(ground)
        ground_xform.SetScale(Gf.Vec3f(40.0, 40.0, 0.2))
        ground_xform.SetTranslate(Gf.Vec3d(0.0, 0.0, -0.1))
        UsdPhysics.CollisionAPI.Apply(ground.GetPrim())
        UsdGeom.Scope.Define(stage, Sdf.Path("/World/Diggable"))
        create_diggable_soil_pile(
            stage,
            prim_path="/World/Diggable/SmokeSoilPile",
            position_xy=(0.0, 0.0),
            size=(6.0, 5.0, 2.5),
            zone_id="C",
            diggable_id="SmokeSoilPile",
            simulation_app=app,
            surface_height=lambda _x, _y, _fallback: 0.0,
        )
        # Mirror the real Zone C setup: the imported excavator starts on flat
        # ground north of the pile and its authored boom/front faces site -Y.
        load_equipment(
            stage,
            Path(os.environ["SITEGIT_EQUIPMENT_ASSET"]),
            position=(0.0, 10.0, 0.0),
            simulation_app=app,
        )
        physics = prepare_equipment_physics(
            stage,
            "/World/Equipment/EXC_001",
            surface_height=lambda _x, _y, _fallback: 0.0,
        )
        world = World(
            stage_units_in_meters=1.0,
            physics_prim_path="/World/PhysicsScene",
            set_defaults=False,
        )
        world.reset()
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(90):
            world.step(render=False)
        rig = EquipmentSensorRig(
            stage,
            "/World/Equipment/EXC_001",
            update_callback=lambda: world.step(render=True),
            config=SensorRigConfig.from_environment(),
            physics_world=world,
        )
        sensor = rig.initialize()
        exporter = EvidenceExporter(output)
        bridge = IsaacBridge(stage=stage, update_callback=lambda: world.step(render=False))
        settled = track_contact_pose(stage, "/World/Equipment/EXC_001")
        prepared_capture: dict[str, object] = {}

        def capture_prepared_evidence(details: dict[str, object]) -> None:
            prepared_capture["details"] = details
            prepared_capture["track_pose"] = track_contact_pose(
                stage, "/World/Equipment/EXC_001"
            )
            prepared_capture["lidar"] = rig.capture_lidar(
                exporter, "before-lidar.ply"
            )
            prepared_capture["camera"] = rig.capture_camera(
                exporter, "before-camera.png"
            )
            prepared_capture["imu"] = rig.capture_imu(exporter, "before-imu.json")

        bridge.set_excavation_prepared_callback(capture_prepared_evidence)
        excavation = bridge.excavate_prim(
            {
                "params": {
                    "equipment_prim_path": "/World/Equipment/EXC_001",
                    "target_prim_path": "/World/Diggable/SmokeSoilPile",
                    "approach_distance_m": 3.0,
                    "animation_seconds": 0.3,
                }
            }
        )
        before_lidar = dict(prepared_capture.get("lidar") or {})
        before_camera = dict(prepared_capture.get("camera") or {})
        before_imu = dict(prepared_capture.get("imu") or {})
        lidar = rig.capture_lidar(exporter, "lidar.ply")
        camera = rig.capture_camera(exporter, "camera.png")
        imu = rig.capture_imu(exporter, "imu.json")
        point_prim = stage.GetPrimAtPath(rig.lidar_points_path)
        rendered_points = point_prim.GetAttribute("points").Get() or []
        scan_sequence = point_prim.GetCustomDataByKey("sitegitScanSequence")
        camera_world = UsdGeom.Xformable(
            stage.GetPrimAtPath(rig.camera_path)
        ).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        camera_right = camera_world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0)).GetNormalized()
        report = {
            "physics": physics,
            "settled": settled,
            "excavation": excavation,
            "sensor": sensor,
            "prepared_capture": prepared_capture,
            "before_camera": before_camera,
            "before_lidar": before_lidar,
            "before_imu": before_imu,
            "camera": camera,
            "lidar": lidar,
            "imu": imu,
            "visualization": {
                "scan_sequence": scan_sequence,
                "rendered_point_count": len(rendered_points),
                "camera_right_z": float(camera_right[2]),
            },
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "failure.txt").unlink(missing_ok=True)
        if not excavation.get("facing", {}).get("aligned"):
            raise RuntimeError("excavator did not finish facing the soil target")
        approach = excavation.get("approach_plan", {})
        if float(approach.get("edge_clearance_m") or 0.0) <= float(
            approach.get("track_radius_m") or 0.0
        ):
            raise RuntimeError("excavator did not preserve track-to-soil clearance")
        deformation = excavation.get("terrain_deformation") or {}
        moved_soil = excavation.get("moved_soil") or {}
        if not deformation.get("available"):
            raise RuntimeError(f"soil Mesh was not deformed: {deformation}")
        if excavation.get("target_active_after") is not True:
            raise RuntimeError("deformed source soil Prim must remain active")
        if not moved_soil or not stage.GetPrimAtPath(moved_soil["prim_path"]).IsValid():
            raise RuntimeError("moved soil deposit was not created")
        source_volume = float(deformation.get("removed_volume_m3") or 0.0)
        deposited_volume = float(moved_soil.get("deposited_volume_m3") or 0.0)
        if source_volume <= 0.0 or abs(source_volume - deposited_volume) > max(0.01, source_volume * 0.01):
            raise RuntimeError(
                f"soil volume is not conserved: removed={source_volume}, deposited={deposited_volume}"
            )
        if sensor.get("placement_source") != "usd-reference":
            raise RuntimeError(f"authored LiDAR mount was not used: {sensor}")
        if not before_camera.get("available") or not camera.get("available"):
            raise RuntimeError(
                f"levelled camera capture failed: before={before_camera}, after={camera}"
            )
        if not before_imu.get("available") or not imu.get("available"):
            raise RuntimeError(f"physical IMU capture failed: before={before_imu}, after={imu}")
        for capture_name, capture in (("before", before_imu), ("after", imu)):
            frame = capture.get("frame") or {}
            if len(frame.get("lin_acc") or []) != 3 or len(frame.get("ang_vel") or []) != 3:
                raise RuntimeError(f"{capture_name} IMU frame is incomplete: {frame}")
            if float(frame.get("physics_step") or 0.0) <= 0.0 or float(frame.get("time") or 0.0) <= 0.0:
                raise RuntimeError(f"{capture_name} IMU frame was not produced by PhysX: {frame}")
        if not prepared_capture.get("details"):
            raise RuntimeError("before evidence was not captured at the prepared boundary")
        before_origin = before_lidar.get("origin_m") or []
        after_origin = lidar.get("origin_m") or []
        if len(before_origin) != 3 or len(after_origin) != 3:
            raise RuntimeError("prepared before/after LiDAR origins are unavailable")
        evidence_pose_distance = sum(
            (float(after_origin[index]) - float(before_origin[index])) ** 2
            for index in range(3)
        ) ** 0.5
        if evidence_pose_distance > 0.75:
            raise RuntimeError(
                "before evidence was not captured at the working pose: "
                f"sensor moved {evidence_pose_distance:.3f}m before after-evidence"
            )
        lidar_position = sensor["mount_position_m"]
        camera_position = sensor["camera_position_m"]
        sensor_spacing = sum(
            (float(camera_position[index]) - float(lidar_position[index])) ** 2
            for index in range(3)
        ) ** 0.5
        expected_spacing = sum(
            float(value) ** 2 for value in sensor["camera_offset_from_lidar_m"]
        ) ** 0.5
        if abs(sensor_spacing - expected_spacing) > 1e-5:
            raise RuntimeError(
                f"camera is not rigidly offset from LiDAR: {sensor_spacing} != {expected_spacing}"
            )
        if int(scan_sequence or 0) < 3 or len(rendered_points) != int(lidar["point_count"]):
            raise RuntimeError(
                "Stage LiDAR visualization was not replaced by the latest scan: "
                f"sequence={scan_sequence}, rendered={len(rendered_points)}, "
                f"exported={lidar['point_count']}"
            )
        if abs(float(camera_right[2])) > 1e-4:
            raise RuntimeError(f"camera horizon is not level: right.z={camera_right[2]}")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    except Exception:
        output.mkdir(parents=True, exist_ok=True)
        (output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if timeline is not None:
            timeline.stop()
        app.close()


if __name__ == "__main__":
    main()
