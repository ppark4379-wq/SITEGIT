"""Canonical drawing and drawing-driven scenario dispatch regression tests."""

from __future__ import annotations

import pytest

from app.domains.work_packages.code_agent import validate_restricted_code
from app.domains.work_packages.site_plan import (
    apply_pipeline_design_defaults,
    design_prompt_context,
    load_pipeline_design,
)
from app.schemas.work_package_ai import PlanningWorkPackagePlan
from isaac_adapter.pipeline_scenario import DEFAULT_TRENCH_STATIONS


def test_pipeline_drawing_matches_the_current_backfill_centerline() -> None:
    design = load_pipeline_design("SASANG-001")
    assert design is not None
    assert design.plan_id == "SASANG-PIPE-DEMO-V1"
    assert design.total_length_m == pytest.approx(79.2)
    assert len(design.centerline) == len(DEFAULT_TRENCH_STATIONS)
    assert [
        (point.x, point.y, point.width_m) for point in design.centerline
    ] == [
        (station.x, station.y, station.width) for station in DEFAULT_TRENCH_STATIONS
    ]
    assert [phase.id for phase in design.phases] == [
        "excavation",
        "pipe_installation",
        "backfill",
    ]
    assert [phase.zone_id for phase in design.phases] == ["A", "B", "C"]
    assert {front.zone_id for front in design.workfronts} == {"A"}
    assert sum(len(front.target_prim_paths) for front in design.workfronts) == 8


def test_short_pipeline_request_is_enriched_from_the_drawing() -> None:
    design = load_pipeline_design("SASANG-001")
    assert design is not None
    llm_guess = PlanningWorkPackagePlan(
        ready=False,
        zone_id="UNSPECIFIED",
        work_type="미정",
        title="미정",
        summary="추가 정보 필요",
        clarification_question="어디를 작업할까요?",
    )

    plan = apply_pipeline_design_defaults("이 구역 관로 공사 진행하자", llm_guess, design)

    assert plan.ready is True
    assert plan.target_amount == pytest.approx(79.2)
    assert plan.zone_id == "A"
    assert plan.segment == "STA 0+000 ~ 0+079.2"
    assert plan.successor_title == "터파기 → 관로 설치 → 되메우기"
    assert "SASANG-PIPE-DEMO-V1" in plan.summary
    context = design_prompt_context(design)
    assert "굴착기 3대" not in context  # exact equipment IDs are supplied instead
    assert "EXC-001" in context and "EXC-003" in context


@pytest.mark.parametrize(
    ("message", "expected_zone", "expected_work_type"),
    [
        ("터파기 진행해줘", "A", "터파기"),
        ("관로 설치 진행해줘", "B", "관로 설치"),
        ("되메우기 진행해줘", "C", "되메우기"),
    ],
)
def test_each_pipeline_phase_has_one_zone(
    message: str, expected_zone: str, expected_work_type: str
) -> None:
    design = load_pipeline_design("SASANG-001")
    assert design is not None
    llm_guess = PlanningWorkPackagePlan(
        ready=False,
        zone_id="UNSPECIFIED",
        work_type="미정",
        title="미정",
        summary="추가 정보 필요",
    )

    plan = apply_pipeline_design_defaults(message, llm_guess, design)

    assert plan.zone_id == expected_zone
    assert plan.work_type == expected_work_type


def test_site_plan_registry_returns_canonical_and_saves_revisions(manager_client) -> None:
    listed = manager_client.get("/api/v1/site-plans?project_id=SASANG-001")
    assert listed.status_code == 200, listed.text
    canonical = next(
        item for item in listed.json() if item["design"]["plan_id"] == "SASANG-PIPE-DEMO-V1"
    )
    design = canonical["design"]
    design["revision"] = "TEST-REGISTRY"
    design["title"] = "테스트 관로 도면"

    saved = manager_client.post(
        "/api/v1/site-plans",
        json={
            "project_id": "SASANG-001",
            "status": "draft",
            "source_filename": "test-plan.json",
            "design": design,
        },
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["updated_by"]

    refreshed = manager_client.get("/api/v1/site-plans?project_id=SASANG-001")
    assert refreshed.status_code == 200, refreshed.text
    assert any(
        item["design"]["revision"] == "TEST-REGISTRY" for item in refreshed.json()
    )


def _stage_prim(path: str, name: str, role: str, zone_id: str | None = None) -> dict:
    return {
        "path": path,
        "name": name,
        "type_name": "Mesh" if role == "diggable" else "Xform",
        "role": role,
        "world_position": {"x": 0, "y": 0, "z": 1},
        "bounds_size": {"x": 10, "y": 10, "z": 3},
        "active": True,
        "zone_id": zone_id,
        "capabilities": ["excavate_prim"],
    }


def test_manager_approval_issues_three_deterministic_excavation_fronts(manager_client) -> None:
    project_id = "SASANG-001"
    equipment = [
        _stage_prim(f"/World/Equipment/EXC_00{index}", f"EXC-00{index}", "equipment")
        for index in range(1, 4)
    ]
    targets = [
        _stage_prim(
            f"/World/Diggable/Pipeline/TrenchFill_{index:02d}",
            f"TrenchFill-{index:02d}",
            "diggable",
            "A",
        )
        for index in range(1, 9)
    ]
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "scenario_id": "demolition-pipeline-v1",
            "stage_identifier": "pipeline-test.usda",
            "equipment": equipment,
            "diggable_targets": targets,
            "scene_objects": [],
        },
    )
    assert inventory.status_code == 200, inventory.text

    response = manager_client.post(
        "/api/v1/work-packages/ai/planning/dispatch",
        json={
            "project_id": project_id,
            "source_text": "이 구역 관로 공사 진행하자",
            "plan_id": "SASANG-PIPE-DEMO-V1",
            "phase_id": "excavation",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert len(payload["work_packages"]) == 3
    assert {item["zone_id"] for item in payload["work_packages"]} == {"A"}
    assert {item["workfront_id"] for item in payload["work_packages"]} == {
        "EXC-FRONT-01",
        "EXC-FRONT-02",
        "EXC-FRONT-03",
    }
    assert {item["status"] for item in payload["work_packages"]} == {"pending"}
    assert len(payload["instructions"]) == 3
    for instruction in payload["instructions"]:
        code = instruction["params"]["generated_code"]
        validate_restricted_code(code)
        assert instruction["params"]["scenario_phase_id"] == "excavation"
        assert instruction["params"]["zone_id"] == "A"
        assert instruction["params"]["planned_quantity"]["source"].startswith(
            "SASANG-PIPE-DEMO-V1"
        )
