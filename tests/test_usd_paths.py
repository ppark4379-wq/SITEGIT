"""Regression tests for executable USD Prim path validation."""

import pytest
from pydantic import ValidationError

from app.schemas.isaac import ExcavationParams, StageInventoryUpdate, StagePrimRecord, Vector3
from isaac_adapter.isaac_bridge import zone_id_for_world_position


def _position() -> Vector3:
    return Vector3(x=0, y=0, z=0)


def test_stage_inventory_accepts_valid_equipment_prim_path():
    record = StagePrimRecord(
        path="/World/Equipment/EXC_001",
        name="EXC-001",
        role="equipment",
        world_position=_position(),
    )
    assert record.path == "/World/Equipment/EXC_001"


def test_stage_inventory_accepts_live_scene_objects():
    record = StagePrimRecord(
        path="/World/SiteGit/cube_demo",
        name="demo cube",
        role="scene_object",
        world_position=_position(),
        bounds_size=Vector3(x=5, y=5, z=5),
        display_color="#FF0000",
    )
    inventory = StageInventoryUpdate(project_id="SASANG-001", scene_objects=[record])
    assert inventory.scene_objects[0].role == "scene_object"


def test_excavation_rejects_hyphenated_usd_prim_path():
    with pytest.raises(ValidationError):
        ExcavationParams(
            equipment_prim_path="/World/Equipment/EXC-001",
            target_prim_path="/World/Site/soil_pile_A",
            equipment_name="EXC-001",
            target_name="soil_pile_A",
            label="시험 굴착",
            work_package_id="WP-001",
        )


def test_physical_position_overrides_stale_authored_zone_metadata():
    center = {"x": 0.0, "y": 0.0, "z": 0.0}
    size = {"x": 200.0, "y": 200.0, "z": 20.0}

    assert zone_id_for_world_position(
        {"x": -26.5, "y": -40.5, "z": 3.0},
        center,
        size,
        fallback="A",
    ) == "C"
