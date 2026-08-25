from __future__ import annotations

from pathlib import Path

import pytest

from isaac_adapter.evidence_exporter import EvidenceExporter
from isaac_adapter.equipment_sensors import (
    EquipmentSensorRig,
    SensorRigConfig,
    generate_lidar_directions,
)
from isaac_adapter.execution_evidence import ExecutionTrace, evidence_quality
from isaac_adapter.isaac_bridge import IsaacBridge, excavation_approach_plan, grounded_equipment_center_z


def _write_ply(path: Path, points: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "end_header",
    ]
    rows = [f"{x} {y} {z}" for x, y, z in points]
    path.write_text("\n".join(header + rows) + "\n", encoding="ascii")


def test_lidar_height_grid_reports_removed_and_added_volume(tmp_path):
    exporter = EvidenceExporter(tmp_path)
    _write_ply(
        exporter.target_path("wp/before.ply"),
        [(0.1, 0.1, 2.0), (1.1, 0.1, 1.0)],
    )
    _write_ply(
        exporter.target_path("wp/after.ply"),
        [(0.1, 0.1, 1.0), (1.1, 0.1, 2.0)],
    )

    result = exporter.compare_lidar_height_grids(
        "wp/before.ply",
        "wp/after.ply",
        cell_size_m=1.0,
        minimum_height_change_m=0.01,
    )

    assert result["available"] is True
    assert result["changed_cell_count"] == 2
    assert result["removed_volume_m3"] == pytest.approx(1.0)
    assert result["added_volume_m3"] == pytest.approx(1.0)
    assert result["net_volume_change_m3"] == pytest.approx(0.0)


def test_evidence_quality_does_not_treat_pose_as_real_imu():
    artifacts = [
        {"sensor_type": "camera", "available": True},
        {"sensor_type": "lidar", "available": True},
        {"sensor_type": "telemetry", "available": True},
        {"sensor_type": "imu", "available": False},
    ]

    quality = evidence_quality(artifacts)

    assert quality["completeness_ratio"] == pytest.approx(2 / 3)
    assert quality["missing_sensor_types"] == ["imu"]
    assert "telemetry" in quality["available_sensor_types"]


def test_execution_trace_produces_ordered_events():
    trace = ExecutionTrace("ins-1")
    first = trace.add("execution_started", "executing")
    second = trace.add("execution_completed", "completed")

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert second["elapsed_seconds"] >= first["elapsed_seconds"]
    assert trace.execution_id.startswith("exec-")


def test_equipment_lidar_generates_forward_unit_rays():
    directions = generate_lidar_directions(120.0, -30.0, 10.0, 3, 3)

    assert len(directions) == 9
    center = directions[4]
    assert center[0] == pytest.approx(0.0)
    assert center[1] > 0.0
    assert sum(value * value for value in center) == pytest.approx(1.0)


def test_equipment_center_is_placed_above_terrain_surface():
    assert grounded_equipment_center_z(5.2, 4.0, 0.03) == pytest.approx(7.23)


def test_excavation_approach_stays_outside_soil_and_track_footprints():
    plan = excavation_approach_plan(
        {"x": 0.0, "y": 10.0},
        {"x": 0.0, "y": 0.0},
        {"x": 6.0, "y": 5.0},
        {"x": 3.0, "y": 5.0},
        requested_clearance_m=3.0,
        safety_margin_m=0.75,
    )

    assert plan["destination_xy"] == pytest.approx([0.0, 5.75])
    assert plan["target_radius_m"] == pytest.approx(2.5)
    assert plan["track_radius_m"] == pytest.approx(2.5)
    assert plan["edge_clearance_m"] == pytest.approx(3.25)
    assert plan["center_standoff_m"] == pytest.approx(5.75)


def test_excavation_prepared_callback_is_consumed_once():
    bridge = IsaacBridge(stage=object())
    captured: list[dict] = []
    bridge.set_excavation_prepared_callback(captured.append)

    bridge._notify_excavation_prepared({"phase": "working-pose"})
    bridge._notify_excavation_prepared({"phase": "must-not-repeat"})

    assert captured == [{"phase": "working-pose"}]


def test_sensor_rig_configuration_reads_environment(monkeypatch):
    monkeypatch.delenv("SITEGIT_RUNTIME_LIDAR_ENABLED", raising=False)
    monkeypatch.setenv("SITEGIT_SENSOR_MOUNT_OFFSET", "1,2,3")
    monkeypatch.setenv("SITEGIT_SENSOR_REFERENCE_USD", "E:/fixtures/excavator_lidar.usd")
    monkeypatch.setenv("SITEGIT_SENSOR_REFERENCE_PRIM", "/World/CustomLidarMount")
    monkeypatch.setenv("SITEGIT_CAMERA_OFFSET_FROM_LIDAR", "0.4,0.1,0.2")
    monkeypatch.setenv("SITEGIT_CAMERA_LEVEL_HORIZON", "true")
    monkeypatch.setenv("SITEGIT_CAMERA_RESOLUTION", "640,360")
    monkeypatch.setenv("SITEGIT_LIDAR_HORIZONTAL_RAYS", "11")
    monkeypatch.setenv("SITEGIT_LIDAR_VERTICAL_RAYS", "7")
    monkeypatch.setenv("SITEGIT_IMU_HEIGHT_ABOVE_TRACKS_M", "0.55")
    monkeypatch.setenv("SITEGIT_IMU_FREQUENCY_HZ", "120")

    config = SensorRigConfig.from_environment()

    assert config.mount_offset_m == (1.0, 2.0, 3.0)
    assert config.sensor_reference_usd == "E:/fixtures/excavator_lidar.usd"
    assert config.sensor_reference_prim_path == "/World/CustomLidarMount"
    assert config.camera_offset_from_lidar_m == (0.4, 0.1, 0.2)
    assert config.camera_level_horizon is True
    assert config.camera_resolution == (640, 360)
    assert config.lidar_runtime_enabled is False
    assert config.lidar_horizontal_rays * config.lidar_vertical_rays == 77
    assert config.imu_height_above_tracks_m == pytest.approx(0.55)
    assert config.imu_frequency_hz == 120


def test_sensor_rig_runtime_lidar_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("SITEGIT_RUNTIME_LIDAR_ENABLED", "true")

    config = SensorRigConfig.from_environment()

    assert config.lidar_runtime_enabled is True


def test_disabled_runtime_lidar_returns_declared_evidence_without_rays():
    config = SensorRigConfig(lidar_runtime_enabled=False)
    rig = EquipmentSensorRig(None, "/World/Equipment/EXC_001", config=config)

    evidence = rig.capture_lidar(None, "unused.ply")

    assert rig._directions == ()
    assert evidence["available"] is True
    assert evidence["capture_mode"] == "declared-only"
    assert evidence["point_count"] is None


def test_sensor_rig_shutdown_releases_camera_and_imu_registry():
    calls: list[object] = []

    class FakeCamera:
        def pause(self):
            calls.append("camera-pause")

        def destroy(self):
            calls.append("camera-destroy")

    class FakeImu:
        name = "sitegit_exc_004_imu"

        def pause(self):
            calls.append("imu-pause")

    class FakeScene:
        def object_exists(self, name):
            calls.append(("exists", name))
            return True

        def remove_object(self, name, *, registry_only):
            calls.append(("remove", name, registry_only))

    class FakeWorld:
        scene = FakeScene()

    rig = EquipmentSensorRig(
        None,
        "/World/Equipment/EXC_004",
        update_callback=lambda: calls.append("frame-drain"),
        physics_world=FakeWorld(),
    )
    rig._camera = FakeCamera()
    rig._imu = FakeImu()

    warnings = rig.shutdown()

    assert warnings == []
    assert calls == [
        "camera-pause",
        "frame-drain",
        "frame-drain",
        "camera-destroy",
        "imu-pause",
        ("exists", "sitegit_exc_004_imu"),
        ("remove", "sitegit_exc_004_imu", True),
    ]
    assert rig._camera is None
    assert rig._imu is None


def test_exporter_saves_world_point_cloud(tmp_path):
    exporter = EvidenceExporter(tmp_path)

    result = exporter.save_point_cloud("wp/scan.ply", [(1.0, 2.0, 3.0)])

    assert result["available"] is True
    assert result["coordinate_frame"] == "world-z-up-metres"
    assert "1.0 2.0 3.0" in (tmp_path / "wp" / "scan.ply").read_text(encoding="ascii")
