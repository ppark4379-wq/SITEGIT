"""Tests for resource-aware LLM code Work Packages."""

from __future__ import annotations

import pytest

from app.domains.work_packages.code_agent import _normalize_program, validate_restricted_code
from isaac_adapter.work_code_executor import execute_work_code, validate_work_code


def _plan(**overrides):
    payload = {
        "ready": True,
        "operation": "excavate_prim",
        "equipment_ref": "any excavator",
        "target_ref": "any soil",
        "zone_id": "A",
        "summary": "Zone A 토사 굴착",
        "clarification_question": "",
        "generated_code": (
            "def execute(ctx):\n"
            "    return ctx.excavate(\n"
            "        equipment_prim_path='/World/Equipment/EXC_001',\n"
            "        target_prim_path='/World/Diggable/ZoneA_Soil_01',\n"
            "        approach_distance_m=3.0,\n"
            "        animation_seconds=3.0,\n"
            "    )\n"
        ),
    }
    payload.update(overrides)
    return payload


def test_missing_stage_resources_are_persisted_as_blocked(manager_client):
    project_id = "CODE-BLOCKED-001"
    response = manager_client.post(
        "/api/v1/work-packages/ai/code/dispatch",
        json={
            "project_id": project_id,
            "message": "Zone A에서 아무 굴착기로 토사를 굴착해줘",
            "plan": _plan(),
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["work_package"]["status"] == "blocked"
    assert payload["instruction"]["status"] == "blocked"
    assert payload["work_package"]["generated_code"] == ""
    assert payload["work_package"]["missing_resources"]

    claimed = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={"project_id": project_id},
    )
    assert claimed.status_code == 200
    assert claimed.json() == []


def test_live_resources_generate_restricted_code_and_queue(manager_client):
    project_id = "CODE-READY-001"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "stage_identifier": "test-stage.usda",
            "equipment": [
                {
                    "path": "/World/Equipment/EXC_001",
                    "name": "EXC-001",
                    "type_name": "Xform",
                    "role": "equipment",
                    "world_position": {"x": 0, "y": 0, "z": 0},
                    "bounds_size": {"x": 6, "y": 4, "z": 4},
                    "active": True,
                    "capabilities": ["move_equipment", "excavate_prim"],
                }
            ],
            "diggable_targets": [
                {
                    "path": "/World/Diggable/ZoneA_Soil_01",
                    "name": "ZoneA-Soil-01",
                    "type_name": "Mesh",
                    "role": "diggable",
                    "world_position": {"x": 10, "y": 5, "z": 1},
                    "bounds_size": {"x": 6, "y": 5, "z": 2.5},
                    "active": True,
                    "zone_id": "A",
                    "capabilities": ["excavate_prim"],
                }
            ],
        },
    )
    assert inventory.status_code == 200, inventory.text

    response = manager_client.post(
        "/api/v1/work-packages/ai/code/dispatch",
        json={
            "project_id": project_id,
            "message": "Zone A에서 아무 굴착기로 토사를 굴착해줘",
            "plan": _plan(),
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    work_package = payload["work_package"]
    assert work_package["status"] == "pending"
    assert work_package["equipment"]["path"] == "/World/Equipment/EXC_001"
    assert work_package["target"]["path"] == "/World/Diggable/ZoneA_Soil_01"
    assert "ctx.excavate" in work_package["generated_code"]
    assert "import" not in work_package["generated_code"]
    validate_restricted_code(work_package["generated_code"])

    claimed = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={"project_id": project_id},
    )
    assert claimed.status_code == 200
    assert [item["kind"] for item in claimed.json()] == ["generated_script"]


def test_guessed_zone_path_is_rebound_to_the_live_physical_zone_target(manager_client):
    project_id = "CODE-REBIND-ZONE-C"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "stage_identifier": "test-stage.usda",
            "equipment": [
                {
                    "path": "/World/Equipment/EXC_001",
                    "name": "EXC-001",
                    "role": "equipment",
                    "world_position": {"x": -20, "y": -20, "z": 2},
                    "bounds_size": {"x": 8, "y": 15, "z": 11},
                    "active": True,
                }
            ],
            "diggable_targets": [
                {
                    "path": "/World/Diggable/Legacy_SoilPile_01",
                    "name": "현장 토사",
                    "role": "diggable",
                    "world_position": {"x": -26.5, "y": -40.5, "z": 3},
                    "bounds_size": {"x": 6.3, "y": 5.25, "z": 2.5},
                    "active": True,
                    "zone_id": "C",
                }
            ],
        },
    )
    assert inventory.status_code == 200, inventory.text
    guessed = _plan(
        zone_id="C",
        summary="Zone C 토사 굴착",
        generated_code=(
            "def execute(ctx):\n"
            "    return ctx.excavate(\n"
            "        equipment_prim_path='/World/Equipment/EXC_001',\n"
            "        target_prim_path='/World/Diggable/ZoneC_SoilPile_01',\n"
            "        approach_distance_m=3.0,\n"
            "        animation_seconds=3.0,\n"
            "    )\n"
        ),
    )

    response = manager_client.post(
        "/api/v1/work-packages/ai/code/dispatch",
        json={
            "project_id": project_id,
            "message": "Zone C에 있는 흙을 굴착해줘",
            "plan": guessed,
        },
    )

    assert response.status_code == 201, response.text
    work_package = response.json()["work_package"]
    assert work_package["status"] == "pending"
    assert work_package["target"]["path"] == "/World/Diggable/Legacy_SoilPile_01"
    assert "/World/Diggable/Legacy_SoilPile_01" in work_package["generated_code"]
    assert "/World/Diggable/ZoneC_SoilPile_01" not in work_package["generated_code"]


def test_generated_code_validator_rejects_arbitrary_python():
    with pytest.raises(ValueError):
        validate_restricted_code(
            "def execute(ctx):\n    import os\n    return os.system('whoami')\n"
        )


def test_connected_stage_can_queue_llm_authored_soil_creation_without_existing_target(
    manager_client,
):
    project_id = "CODE-CREATE-SOIL-001"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "stage_identifier": "test-stage.usda",
            "equipment": [],
            "diggable_targets": [],
            "scene_objects": [],
        },
    )
    assert inventory.status_code == 200, inventory.text
    code = (
        "def execute(ctx):\n"
        "    return ctx.create_soil_pile(\n"
        "        prim_path='/World/Diggable/ZoneA_SoilPile_AI01',\n"
        "        zone_id='A',\n"
        "        location='center',\n"
        "        size_x=5.0,\n"
        "        size_y=5.0,\n"
        "        size_z=2.0,\n"
        "        label='Zone A 토사',\n"
        "    )\n"
    )
    response = manager_client.post(
        "/api/v1/work-packages/ai/code/dispatch",
        json={
            "project_id": project_id,
            "message": "Zone A 중앙에 5m x 5m x 2m 토사를 만들어줘",
            "plan": _plan(
                operation="create_soil_pile",
                equipment_ref="",
                target_ref="",
                summary="Zone A 중앙에 토사 생성",
                generated_code=code,
            ),
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["work_package"]["status"] == "pending"
    assert payload["work_package"]["equipment"] is None
    assert payload["work_package"]["target"] is None
    assert payload["work_package"]["execution_target_path"] == "/World/Diggable/ZoneA_SoilPile_AI01"
    validate_restricted_code(payload["work_package"]["generated_code"])


def test_restricted_code_allows_sequential_stage_actions():
    code = (
        "def execute(ctx):\n"
        "    ctx.play_animation(equipment_prim_path='/World/Equipment/EXC_001', animation_name='ArmDig', duration_seconds=2.0)\n"
        "    return ctx.set_prim_active(prim_path='/World/Diggable/ZoneA_Soil_01', active=False)\n"
    )
    validate_restricted_code(code)
    validate_work_code(code)
    with pytest.raises(RuntimeError):
        validate_work_code(
            "def execute(ctx: __import__('os').system('whoami')):\n"
            "    return ctx.excavate()\n"
        )


def test_small_model_return_ctx_shorthand_is_safely_normalized():
    code = (
        "def execute(ctx):\n"
        "    ctx.create_soil_pile(prim_path='/World/Diggable/Soil_02', zone_id='A', location='center', size_x=5.0, size_y=5.0, size_z=2.0, color='green', label='새 토사')\n"
        "    return ctx\n"
    )
    normalized = _normalize_program(code)
    assert normalized.endswith("return ctx.finish()")
    validate_restricted_code(normalized)
    validate_work_code(normalized)


def test_restricted_generated_code_calls_the_adapter_bridge():
    class FakeBridge:
        def excavate_prim(self, instruction):
            return {
                "operation": "excavate_prim",
                "params_read_back": instruction["params"],
            }

    code = (
        "def execute(ctx):\n"
        "    return ctx.excavate(\n"
        "        equipment_prim_path='/World/Equipment/EXC_001',\n"
        "        target_prim_path='/World/Diggable/ZoneA_Soil_01',\n"
        "        approach_distance_m=3.0,\n"
        "        animation_seconds=3.0,\n"
        "    )\n"
    )
    result = execute_work_code(FakeBridge(), code)

    assert result["operation"] == "excavate_prim"
    assert result["generated_code_executed"] is True
    assert result["params_read_back"]["target_prim_path"].endswith("ZoneA_Soil_01")
