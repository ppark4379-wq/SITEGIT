"""Drawing-candidate, approval-time Zone B, and Adapter contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domains.work_packages.site_plan import (
    apply_soil_relocation_design_defaults,
    is_soil_relocation_request,
    load_site_design_for_request,
    load_soil_relocation_design,
)
from app.schemas.work_package_ai import PlanningWorkPackagePlan


REPO_ROOT = Path(__file__).resolve().parents[1]


def _stage_prim(path: str, name: str, role: str, zone_id: str | None = None) -> dict:
    return {
        "path": path,
        "name": name,
        "type_name": "Mesh" if role == "diggable" else "Xform",
        "role": role,
        "world_position": {"x": 49, "y": 10, "z": 1},
        "bounds_size": {"x": 8, "y": 7, "z": 3},
        "active": True,
        "zone_id": zone_id,
        "capabilities": ["play_animation", "excavate_prim"],
    }


@pytest.mark.parametrize(
    "message",
    [
        "오른쪽 공터 흙더미를 바로 옆으로 옮겨줘",
        "동측 흙을 옆에 적치해줘",
        "저 위치 흙 옮겨줘",
    ],
)
def test_natural_requests_select_the_relocation_candidate(message: str) -> None:
    assert is_soil_relocation_request(message) is True
    design = load_site_design_for_request("SASANG-001", message)
    assert design is not None
    assert design.scenario_type == "soil_relocation"
    assert design.zone_id == "B"


def test_relocation_drawing_is_an_unassigned_candidate() -> None:
    design = load_soil_relocation_design("SASANG-001")
    assert design is not None
    assert design.plan_id == "DEMOLITION-SOIL-RELOCATION-V1"
    assert design.zone_id == "B"
    assert design.zone_assignment_mode == "create_on_approval"
    assert design.location_confirmation_required is True
    assert "맞습니까" in design.location_confirmation_prompt
    assert len(design.workfronts) == 1
    assert [phase.id for phase in design.phases] == ["soil_relocation"]
    assert design.relocation is not None
    assert design.relocation.equipment_id == "EXC-004"
    assert design.relocation.equipment_prim_path == "/World/Equipment/EXC_004"
    assert design.relocation.source_prim_path == "/World/Diggable/SoilRelocationCandidate_01"
    assert design.relocation.tracks_stationary is True
    assert design.relocation.swing_degrees == pytest.approx(90)
    assert design.relocation.scoop_count == 5
    assert design.relocation.source_position.x == pytest.approx(30)
    assert design.relocation.source_position.y == pytest.approx(56)
    assert design.relocation.equipment_position.x == pytest.approx(30)
    assert design.relocation.equipment_position.y == pytest.approx(65)
    assert design.relocation.destination_position.x == pytest.approx(38)
    assert design.relocation.destination_position.y == pytest.approx(65)

    llm_guess = PlanningWorkPackagePlan(
        ready=False,
        zone_id="UNSPECIFIED",
        work_type="미정",
        title="미정",
        summary="추가 정보 필요",
    )
    plan = apply_soil_relocation_design_defaults(llm_guess, design)
    assert plan.ready is True
    assert plan.zone_id == "B"
    assert plan.equipment_hint == "EXC-004"
    assert "작업 후보" in plan.summary
    assert "승인 시 Zone B" in plan.summary
    assert "궤도를 고정" in plan.summary
    assert "5회" in plan.summary


def test_approval_creates_zone_b_and_uses_exact_drawing_resources(manager_client) -> None:
    project_id = "SASANG-001"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "scenario_id": "pipeline-demolition-v12",
            "stage_identifier": "zone-b-test.usda",
            "equipment": [
                _stage_prim("/World/Equipment/EXC_004", "EXC-004", "equipment")
            ],
            "diggable_targets": [
                _stage_prim(
                    "/World/Diggable/SoilRelocationCandidate_01",
                    "SoilRelocationCandidate-01",
                    "diggable",
                )
            ],
            "scene_objects": [],
        },
    )
    assert inventory.status_code == 200, inventory.text

    response = manager_client.post(
        "/api/v1/work-packages/ai/planning/dispatch",
        json={
            "project_id": project_id,
            "source_text": "오른쪽 흙더미를 바로 옆으로 옮겨줘",
            "plan_id": "DEMOLITION-SOIL-RELOCATION-V1",
            "phase_id": "soil_relocation",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert len(payload["work_packages"]) == 1
    assert payload["work_packages"][0]["zone_id"] == "B"
    assert payload["work_packages"][0]["equipment_id"] == "EXC-004"
    assert payload["work_packages"][0]["status"] == "pending"

    params = payload["instructions"][0]["params"]
    assert params["execution_group_mode"] == "stationary_soil_relocation"
    assert params["tracks_stationary"] is True
    assert params["zone_assignment_mode"] == "create_on_approval"
    assert params["zone_created_from_candidate"] is True
    assert params["location_confirmed"] is True
    assert params["candidate_work_area_id"] == "SOIL-RELOCATION-CANDIDATE-01"
    assert params["resource_bindings"] == {
        "equipment": "/World/Equipment/EXC_004",
        "target": "/World/Diggable/SoilRelocationCandidate_01",
    }
    assert params["relocation"]["scoop_count"] == 5
    assert params["relocation"]["swing_degrees"] == pytest.approx(90)
    assert params["relocation"]["destination_position"]["x"] == pytest.approx(38)
    assert params["relocation"]["destination_position"]["y"] == pytest.approx(65)

    # This suite shares its API database with later dispatch tests.  Claim the
    # one Zone B instruction so it cannot be mistaken for the next pipeline
    # execution group while still preserving the pending-dispatch assertion
    # above.
    claimed = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={"project_id": project_id, "limit": 50},
    )
    assert claimed.status_code == 200, claimed.text
    assert payload["instructions"][0]["id"] in [
        item["id"] for item in claimed.json()
    ]


def test_zone_b_web_and_adapter_keep_the_same_execution_contract() -> None:
    workflow = (REPO_ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    app = (REPO_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    map_viewer = (REPO_ROOT / "frontend" / "isaac-map-viewer.js").read_text(
        encoding="utf-8"
    )
    runner = (REPO_ROOT / "isaac_adapter" / "isaac_runner.py").read_text(
        encoding="utf-8"
    )
    task = (
        REPO_ROOT / "isaac_adapter" / "stationary_soil_relocation_task.py"
    ).read_text(encoding="utf-8")

    assert "wfSoilRelocationDrawing" in workflow
    assert "wfScenarioPhasesForRun" in workflow
    assert "wfScenarioDesignForRun" in workflow
    assert "dynamicInstructionWorkAreaBounds" in app
    assert "operation.includes('relocat')" in app
    assert "updateSoilRelocationPlanningOverlay" in map_viewer
    assert "후보 작업 구역 · 승인 시 ZONE B" in map_viewer
    assert 'zone_b_work_area.get("relocation")' in runner
    assert "stationary_soil_relocation" in runner
    assert 'zone_id=""' in runner
    assert "drive_equipment_to" not in task
    assert '"Rotate90"' in task
    assert '"ArmDump"' in task
    assert "track_displacement <= 0.15" in task
    assert 'SetCustomDataByKey("sitegitZoneId", assigned_zone_id)' in task
