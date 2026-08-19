"""Run a small headless Isaac check for the equipment-mounted sensor rig.

This diagnostic does not contact the SiteGit backend.  It creates a flat test
mesh and a mock equipment root, then verifies that the real Isaac camera writes
a PNG and the PhysX scanner writes a non-empty PLY.
"""

from __future__ import annotations

import os
from pathlib import Path
import traceback


def main() -> None:
    from isaacsim.simulation_app import SimulationApp

    output = Path(
        os.getenv(
            "SITEGIT_SENSOR_SMOKE_OUTPUT",
            Path(__file__).resolve().parents[1] / "runtime" / "sensor-smoke",
        )
    ).resolve()
    app = SimulationApp({"headless": True})
    timeline = None
    try:
        import omni.timeline
        import omni.usd
        import numpy as np
        from isaacsim.core.api import World
        from pxr import Gf, Sdf, UsdGeom, UsdLux, UsdPhysics

        from equipment_sensors import (
            EquipmentSensorRig,
            SensorRigConfig,
            prepare_raycast_collisions,
        )
        from evidence_exporter import EvidenceExporter

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdGeom.Xform.Define(stage, Sdf.Path("/World"))

        ground = UsdGeom.Mesh.Define(stage, Sdf.Path("/World/TestSite/Ground"))
        ground.CreatePointsAttr().Set(
            [
                Gf.Vec3f(-20.0, -5.0, 0.0),
                Gf.Vec3f(20.0, -5.0, 0.0),
                Gf.Vec3f(20.0, 25.0, 0.0),
                Gf.Vec3f(-20.0, 25.0, 0.0),
            ]
        )
        ground.CreateFaceVertexCountsAttr().Set([3, 3])
        ground.CreateFaceVertexIndicesAttr().Set([0, 1, 2, 0, 2, 3])

        # Give the camera a lit, unambiguous target in its forward (+Y) view.
        light = UsdLux.DomeLight.Define(stage, Sdf.Path("/World/TestLight"))
        light.CreateIntensityAttr().Set(1500.0)
        marker = UsdGeom.Cube.Define(stage, Sdf.Path("/World/TestSite/CameraTarget"))
        marker.CreateSizeAttr().Set(2.0)
        marker.CreateDisplayColorAttr().Set([Gf.Vec3f(0.9, 0.05, 0.02)])
        marker_xform = UsdGeom.Xformable(marker)
        marker_xform.AddTranslateOp().Set(Gf.Vec3d(2.75, -8.0, 1.0))
        UsdPhysics.CollisionAPI.Apply(marker.GetPrim())

        equipment = UsdGeom.Xform.Define(stage, Sdf.Path("/World/Equipment/EXC_001"))
        equipment.GetPrim().SetCustomDataByKey(
            "sitegitEquipmentAnchor", {"x": 0.0, "y": 0.0, "z": 0.0}
        )

        collision = prepare_raycast_collisions(
            stage,
            ["/World/TestSite"],
            update_callback=app.update,
            cooking_frames=60,
        )
        world = World(
            stage_units_in_meters=1.0,
            physics_prim_path="/World/PhysicsScene",
            set_defaults=False,
        )
        world.reset()
        config = SensorRigConfig.from_environment()
        rig = EquipmentSensorRig(
            stage,
            "/World/Equipment/EXC_001",
            update_callback=lambda: world.step(render=True),
            config=config,
            physics_world=world,
        )
        info = rig.initialize()
        print("Camera USD pose:", rig._camera.get_world_pose(camera_axes="usd"))
        print(
            "Camera target pixel:",
            rig._camera.get_image_coords_from_world_points(
                np.asarray([[2.75, -8.0, 1.0]], dtype=np.float32)
            ),
        )
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(100):
            world.step(render=True)

        exporter = EvidenceExporter(output)
        image = rig.capture_camera(exporter, "camera.png")
        camera_rgb = np.asarray(rig._camera.get_rgb(device="cpu"))
        print(
            "Camera RGB stats:",
            camera_rgb.shape,
            camera_rgb.dtype,
            float(camera_rgb.min(initial=0)),
            float(camera_rgb.max(initial=0)),
            float(camera_rgb.mean()),
        )
        lidar = rig.capture_lidar(exporter, "lidar.ply")
        print(f"SensorRig: {info}")
        print(f"Collision: {collision}")
        print(f"Camera: {image}")
        print(f"LiDAR: {lidar}")
        if not image.get("available"):
            raise RuntimeError(image.get("reason") or "camera smoke check failed")
        if not lidar.get("available") or int(lidar.get("point_count") or 0) < 1:
            raise RuntimeError(lidar.get("reason") or "LiDAR smoke check returned no points")
        (output / "success.txt").write_text("camera and lidar passed\n", encoding="utf-8")
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
