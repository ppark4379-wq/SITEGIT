"""Regression tests for executable USD Prim path validation."""

import pytest
from pydantic import ValidationError

from app.schemas.isaac import ExcavationParams, StagePrimRecord, Vector3


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
