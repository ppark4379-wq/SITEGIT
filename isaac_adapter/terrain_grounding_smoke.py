"""Validate equipment grounding and mounted sensors on the real site."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import traceback

from dotenv import load_dotenv

ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def main() -> None:
    """Load the real assets, ground the excavator, and capture one sensor pair."""

    from isaacsim.simulation_app import SimulationApp

    output = REPO_ROOT / "runtime" / "terrain-grounding-smoke"
    started_at = time.perf_counter()
    app = SimulationApp({"headless": True})
    timeline = None
    try:
        import omni.timeline
        import omni.usd
        from isaacsim.core.api import World

        from equipment_physics import prepare_equipment_physics, track_contact_pose
        from equipment_sensors import (
            EquipmentSensorRig,
            SensorRigConfig,
            prepare_raycast_collisions,
        )
        from evidence_exporter import EvidenceExporter
        from site_stage import (
            default_site_asset,
            load_equipment,
            load_site,
            resolved_data_root,
        )
        from terrain_collision_proxy import (
            collision_proxy_height_sampler,
            create_terrain_collision_proxy,
        )

        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        site_asset = default_site_asset()
        if site_asset is None:
            raise FileNotFoundError("real site asset is unavailable")
        equipment_asset = Path(os.environ["SITEGIT_EQUIPMENT_ASSET"])
        load_site(stage, site_asset, simulation_app=app)
        collision_proxy = create_terrain_collision_proxy(
            stage,
            resolved_data_root(),
            resolution_m=float(
                os.getenv("SITEGIT_TERRAIN_COLLISION_RESOLUTION_M", "2")
            ),
        )
        surface_height = collision_proxy_height_sampler(collision_proxy["cache_path"])
        load_equipment(
            stage,
            equipment_asset,
            position=(-26.5, -30.5, 0.0),
            simulation_app=app,
            surface_height=surface_height,
        )
        prepare_raycast_collisions(
            stage,
            [collision_proxy["prim_path"], "/World/Diggable", "/World/SiteGit"],
            update_callback=app.update,
            cooking_frames=int(os.getenv("SITEGIT_COLLISION_COOKING_FRAMES", "20")),
        )

        physics = prepare_equipment_physics(
            stage,
            "/World/Equipment/EXC_001",
            surface_height=surface_height,
        )

        world = World(
            stage_units_in_meters=1.0,
            physics_prim_path="/World/PhysicsScene",
            set_defaults=False,
        )
        world.reset()
        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        for _ in range(120):
            world.step(render=False)
        settled_pose = track_contact_pose(stage, "/World/Equipment/EXC_001")
        rig = EquipmentSensorRig(
            stage,
            "/World/Equipment/EXC_001",
            update_callback=lambda: world.step(render=True),
            config=SensorRigConfig.from_environment(),
            physics_world=world,
        )
        sensor = rig.initialize()
        for _ in range(30):
            world.step(render=True)

        exporter = EvidenceExporter(output)
        camera = rig.capture_camera(exporter, "camera.png")
        lidar = rig.capture_lidar(exporter, "lidar.ply")
        report = {
            "physics": physics,
            "collision_proxy": collision_proxy,
            "settled_track_pose": settled_pose,
            "sensor": sensor,
            "camera": camera,
            "lidar": lidar,
            "startup_and_capture_seconds": round(
                time.perf_counter() - started_at, 3
            ),
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "failure.txt").unlink(missing_ok=True)
        if not camera.get("available") or int(lidar.get("point_count") or 0) < 1:
            raise RuntimeError("real-site camera or LiDAR capture failed")
        print(json.dumps(report, ensure_ascii=False, indent=2))
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
