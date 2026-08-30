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
    assert design.zone_id == "A"
    assert design.zone_title == "관로 공사"
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
    assert [phase.zone_id for phase in design.phases] == ["A", "A", "A"]
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
        ("관로 설치 진행해줘", "A", "관로 설치"),
        ("되메우기 진행해줘", "A", "되메우기"),
    ],
)
def test_all_pipeline_phases_share_the_construction_zone(
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


def test_manager_approval_issues_three_deterministic_excavation_fronts(
    manager_client, monkeypatch
) -> None:
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

    excavation_acceptance_criteria = [
        "설계 굴착 저면 대비 ±35mm",
        "미굴착 토사 체적 1.5% 이하",
        "카메라·LiDAR·IMU Evidence 완전성 95% 이상",
    ]
    response = manager_client.post(
        "/api/v1/work-packages/ai/planning/dispatch",
        json={
            "project_id": project_id,
            "source_text": "이 구역 관로 공사 진행하자",
            "plan_id": "SASANG-PIPE-DEMO-V1",
            "phase_id": "excavation",
            "acceptance_criteria": excavation_acceptance_criteria,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert len(payload["work_packages"]) == 9
    excavation_packages = [
        item for item in payload["work_packages"] if item["phase_id"] == "excavation"
    ]
    installation_packages = [
        item
        for item in payload["work_packages"]
        if item["phase_id"] == "pipe_installation"
    ]
    backfill_packages = [
        item for item in payload["work_packages"] if item["phase_id"] == "backfill"
    ]
    assert {item["zone_id"] for item in excavation_packages} == {"A"}
    assert {item["workfront_id"] for item in excavation_packages} == {
        "EXC-FRONT-01",
        "EXC-FRONT-02",
        "EXC-FRONT-03",
    }
    assert {item["status"] for item in excavation_packages} == {"pending"}
    assert {item["zone_id"] for item in installation_packages} == {"A"}
    assert {item["status"] for item in installation_packages} == {"blocked"}
    assert {item["zone_id"] for item in backfill_packages} == {"A"}
    assert {item["status"] for item in backfill_packages} == {"blocked"}
    assert len(payload["instructions"]) == 9
    excavation_instructions = [
        item
        for item in payload["instructions"]
        if item["params"]["scenario_phase_id"] == "excavation"
    ]
    installation_instructions = [
        item
        for item in payload["instructions"]
        if item["params"]["scenario_phase_id"] == "pipe_installation"
    ]
    backfill_instructions = [
        item
        for item in payload["instructions"]
        if item["params"]["scenario_phase_id"] == "backfill"
    ]
    scenario_run_ids = {
        item["params"]["scenario_run_id"] for item in payload["instructions"]
    }
    parent_work_package_ids = {
        item["params"]["scenario_parent_work_package_id"]
        for item in payload["instructions"]
    }
    assert len(scenario_run_ids) == 1
    assert len(parent_work_package_ids) == 1
    assert next(iter(parent_work_package_ids)).startswith("WP-PIPELINE-")
    group_ids = {
        instruction["params"]["execution_group_id"]
        for instruction in excavation_instructions
    }
    assert len(group_ids) == 1
    assert len({item["params"]["execution_group_id"] for item in installation_instructions}) == 1
    installation_group_ids = {
        item["params"]["execution_group_id"] for item in installation_instructions
    }
    assert len({item["params"]["execution_group_id"] for item in backfill_instructions}) == 1
    for instruction in excavation_instructions:
        code = instruction["params"]["generated_code"]
        validate_restricted_code(code)
        assert instruction["params"]["scenario_phase_id"] == "excavation"
        assert instruction["params"]["zone_id"] == "A"
        assert instruction["params"]["execution_group_size"] == 3
        assert (
            instruction["params"]["acceptance_criteria"]
            == excavation_acceptance_criteria
        )
        assert (
            instruction["params"]["execution_group_mode"]
            == "parallel_incremental_scoops"
        )
        assert instruction["params"]["planned_quantity"]["source"].startswith(
            "SASANG-PIPE-DEMO-V1"
        )
    centre_instruction = next(
        item
        for item in excavation_instructions
        if item["params"]["workfront_id"] == "EXC-FRONT-02"
    )
    assert centre_instruction["params"]["quality_scenario"] == {
        "type": "intentional_under_excavation",
        "requested_completion_ratio": 0.68,
        "required_completion_ratio": 0.98,
        "description": (
            "Demo defect: the center excavator leaves measurable residual soil "
            "for a corrective-work review."
        ),
    }
    for instruction in installation_instructions:
        assert instruction["status"] == "blocked"
        assert instruction["params"]["scenario_phase_id"] == "pipe_installation"
        assert instruction["params"]["zone_id"] == "A"
        assert instruction["params"]["execution_group_mode"] == "parallel_pipe_installation"
        assert instruction["params"]["predecessor_execution_group_id"] in group_ids
    for instruction in backfill_instructions:
        assert instruction["status"] == "blocked"
        assert instruction["params"]["scenario_phase_id"] == "backfill"
        assert instruction["params"]["zone_id"] == "A"
        assert instruction["params"]["execution_group_mode"] == "parallel_pipeline_backfill"
        assert (
            instruction["params"]["predecessor_execution_group_id"]
            in installation_group_ids
        )

    claimed = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={
            "project_id": project_id,
            "limit": 3,
            "prefer_execution_group": True,
        },
    )
    assert claimed.status_code == 200, claimed.text
    claimed_payload = claimed.json()
    assert len(claimed_payload) == 3
    assert {
        item["params"]["execution_group_id"] for item in claimed_payload
    } == group_ids

    progress = manager_client.post(
        f"/api/v1/isaac/instructions/{claimed_payload[0]['id']}/progress",
        json={
            "phase": "excavating",
            "step_index": 1,
            "step_count": 5,
            "progress_ratio": 0.2,
            "removed_volume_m3": 4.5,
        },
    )
    assert progress.status_code == 200, progress.text
    live = progress.json()["params"]["execution_progress"]
    assert live["step_index"] == 1
    assert live["step_count"] == 5
    assert live["progress_ratio"] == 0.2
    assert live["removed_volume_m3"] == 4.5

    # The three independently reviewed excavation commits gate the next phase.
    # Approving only two leaves Phase 2 locked. The third approval makes its
    # plan reviewable, but does not put it in Isaac's queue until the manager
    # separately approves the Zone A Phase 2 plan.
    excavation_commits = []
    for item in claimed_payload:
        is_centre = item["params"]["workfront_id"] == "EXC-FRONT-02"
        planned_volume = float(item["params"]["planned_quantity"]["value"])
        committed = manager_client.post(
            f"/api/v1/isaac/instructions/{item['id']}/commit",
            json={
                "status": "succeeded",
                    "result": {
                        "operation": "pipeline_excavation",
                        "simulator": "isaac-sim",
                        "source": "stage-readback",
                        "target_active_after": is_centre,
                        "terrain_deformation": {
                            "available": True,
                            "method": "test-stage-readback",
                            "removed_volume_m3": 1.0,
                        },
                        "quality_assessment": {
                            "status": "needs_remediation" if is_centre else "pass",
                            "rule": "planned_excavation_completion",
                            "method": "usd_mesh_volume_stage_readback",
                            "intentional_demo_defect": is_centre,
                            "required_completion_ratio": 0.98,
                            "measured_completion_ratio": 0.68 if is_centre else 1.0,
                            "planned_volume_m3": planned_volume,
                            "completed_volume_m3": planned_volume * (0.68 if is_centre else 1.0),
                            "remaining_volume_m3": planned_volume * (0.32 if is_centre else 0.0),
                            "equipment_prim_path": item["params"]["resource_bindings"]["equipment"],
                            "workfront_id": item["params"]["workfront_id"],
                        },
                        "map_changes": [],
                    },
                "evidence": {"sensors": [], "storage_keys": []},
            },
        )
        assert committed.status_code == 201, committed.text
        excavation_commits.append(committed.json())

    normal_commits = [
        commit
        for commit in excavation_commits
        if commit["result"]["quality_assessment"]["status"] == "pass"
    ]
    deficient_commit = next(
        commit
        for commit in excavation_commits
        if commit["result"]["quality_assessment"]["status"]
        == "needs_remediation"
    )
    for commit in normal_commits:
        reviewed = manager_client.post(
            f"/api/v1/isaac/commits/{commit['id']}/review",
            json={"decision": "approved", "note": "excavation front approved"},
        )
        assert reviewed.status_code == 200, reviewed.text
    premature = manager_client.get(
        "/api/v1/isaac/instructions",
        params={"project_id": project_id, "limit": 100},
    )
    assert premature.status_code == 200, premature.text
    premature_installation = [
        item
        for item in premature.json()
        if item["params"].get("execution_group_mode")
        == "parallel_pipe_installation"
    ]
    assert len(premature_installation) == 3
    assert {item["status"] for item in premature_installation} == {"blocked"}

    # The centre excavator claims completion, but Stage read-back prevents the
    # manager from approving it and Phase 2 stays locked.
    blocked_review = manager_client.post(
        f"/api/v1/isaac/commits/{deficient_commit['id']}/review",
        json={"decision": "approved", "note": "굴착 완료 확인"},
    )
    assert blocked_review.status_code == 422, blocked_review.text
    assert blocked_review.json()["detail"]["code"] == "EXCAVATION_REMEDIATION_REQUIRED"

    class _Narrative:
        def model_dump(self):
            return {
                "title": "EXC-002 중앙 구간 부족 굴착 보완",
                "summary": "실측 부족량만 동일 장비로 추가 굴착합니다.",
                "action_steps": [
                    "원 작업전선과 잔여 토사 Prim을 확인합니다.",
                    "EXC-002로 부족량을 추가 굴착합니다.",
                    "센서 Evidence를 재수집합니다.",
                ],
                "manager_note": "실측 수치와 대상을 확인하고 하달하세요.",
            }

    monkeypatch.setattr(
        "app.api.routes.isaac.compile_remediation_narrative",
        lambda **_kwargs: _Narrative(),
    )
    remediation_response = manager_client.post(
        f"/api/v1/isaac/commits/{deficient_commit['id']}/remediation",
        json={},
    )
    assert remediation_response.status_code == 201, remediation_response.text
    remediation = remediation_response.json()
    assert remediation["status"] == "blocked"
    assert remediation["params"]["remediation_mode"] is True
    assert remediation["params"]["execution_group_size"] == 1
    assert remediation["params"]["resource_bindings"]["equipment"].endswith(
        "/EXC_002"
    )
    assert remediation["params"]["planned_quantity"]["value"] > 0

    dispatched = manager_client.post(
        f"/api/v1/isaac/instructions/{remediation['id']}/dispatch-remediation",
        json={},
    )
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["status"] == "pending"

    corrective_claim = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={
            "project_id": project_id,
            "limit": 3,
            "prefer_execution_group": True,
        },
    )
    assert corrective_claim.status_code == 200, corrective_claim.text
    assert [item["id"] for item in corrective_claim.json()] == [remediation["id"]]
    correction = corrective_claim.json()[0]
    correction_commit_response = manager_client.post(
        f"/api/v1/isaac/instructions/{correction['id']}/commit",
        json={
            "status": "succeeded",
            "result": {
                "operation": "pipeline_excavation",
                "simulator": "isaac-sim",
                "source": "stage-readback",
                "target_active_after": False,
                "target_bounds_size": {"x": 8, "y": 8, "z": 3},
                "terrain_deformation": {
                    "available": True,
                    "method": "test-stage-readback",
                    "removed_volume_m3": correction["params"]["planned_quantity"]["value"],
                },
                "quality_assessment": {
                    "status": "pass",
                    "required_completion_ratio": 0.98,
                    "measured_completion_ratio": 1.0,
                    "planned_volume_m3": correction["params"]["planned_quantity"]["value"],
                    "completed_volume_m3": correction["params"]["planned_quantity"]["value"],
                    "remaining_volume_m3": 0.0,
                },
                "map_changes": [],
            },
            "evidence": {"sensors": [], "storage_keys": []},
        },
    )
    assert correction_commit_response.status_code == 201, correction_commit_response.text
    correction_commit = correction_commit_response.json()
    correction_review = manager_client.post(
        f"/api/v1/isaac/commits/{correction_commit['id']}/review",
        json={"decision": "approved", "note": "부족분 재굴착 확인"},
    )
    assert correction_review.status_code == 200, correction_review.text
    original_after_correction = manager_client.get(
        f"/api/v1/isaac/commits/{deficient_commit['id']}"
    )
    assert original_after_correction.status_code == 200
    assert original_after_correction.json()["review_status"] == "approved"
    assert (
        original_after_correction.json()["result"]["quality_assessment"]["status"]
        == "remediated"
    )

    ready = manager_client.get(
        "/api/v1/isaac/instructions",
        params={"project_id": project_id, "limit": 100},
    )
    assert ready.status_code == 200, ready.text
    ready_installation = [
        item
        for item in ready.json()
        if item["params"].get("scenario_phase_id") == "pipe_installation"
        and item["params"].get("scenario_run_id") in scenario_run_ids
    ]
    assert len(ready_installation) == 3
    assert {item["status"] for item in ready_installation} == {"blocked"}
    assert {
        item["params"].get("phase_approval_ready")
        for item in ready_installation
    } == {True}
    assert {
        item["params"].get("phase_plan_status") for item in ready_installation
    } == {"approval_ready"}

    installation_acceptance_criteria = [
        "관 중심선 수평 편차 ±80mm",
        "관저고 설계 대비 ±30mm",
        "카메라·LiDAR·IMU Evidence 완전성 96% 이상",
    ]
    phase_approval = manager_client.post(
        "/api/v1/work-packages/ai/planning/dispatch",
        json={
            "project_id": project_id,
            "source_text": "Zone A 2단계 관로 설치 계획 승인",
            "plan_id": "SASANG-PIPE-DEMO-V1",
            "phase_id": "pipe_installation",
            "acceptance_criteria": installation_acceptance_criteria,
        },
    )
    assert phase_approval.status_code == 201, phase_approval.text
    assert {item["status"] for item in phase_approval.json()["work_packages"]} == {
        "pending"
    }
    assert {
        tuple(item["params"]["acceptance_criteria"])
        for item in phase_approval.json()["instructions"]
    } == {tuple(installation_acceptance_criteria)}

    installation_claim = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={
            "project_id": project_id,
            "limit": 3,
            "prefer_execution_group": True,
        },
    )
    assert installation_claim.status_code == 200, installation_claim.text
    claimed_installation = installation_claim.json()
    assert len(claimed_installation) == 3
    assert {
        item["params"]["execution_group_mode"] for item in claimed_installation
    } == {"parallel_pipe_installation"}
    assert {
        item["params"].get("phase_plan_status") for item in claimed_installation
    } == {"approved"}

    # Phase 2 also produces three independently reviewed Evidence commits. The
    # third approval exposes (but does not dispatch) the Phase 3 plan.
    installation_commits = []
    for item in claimed_installation:
        committed = manager_client.post(
            f"/api/v1/isaac/instructions/{item['id']}/commit",
            json={
                "status": "succeeded",
                "result": {
                    "operation": "pipeline_installation",
                    "simulator": "isaac-sim",
                    "source": "stage-readback",
                    "installed_length_m": 1.0,
                    "map_changes": [],
                },
                "evidence": {"sensors": [], "storage_keys": []},
            },
        )
        assert committed.status_code == 201, committed.text
        installation_commits.append(committed.json())

    for commit in installation_commits:
        reviewed = manager_client.post(
            f"/api/v1/isaac/commits/{commit['id']}/review",
            json={"decision": "approved", "note": "Zone A Phase 2 approved"},
        )
        assert reviewed.status_code == 200, reviewed.text

    ready = manager_client.get(
        "/api/v1/isaac/instructions",
        params={"project_id": project_id, "limit": 100},
    )
    assert ready.status_code == 200, ready.text
    ready_backfill = [
        item
        for item in ready.json()
        if item["params"].get("scenario_phase_id") == "backfill"
        and item["params"].get("scenario_run_id") in scenario_run_ids
    ]
    assert len(ready_backfill) == 3
    assert {item["status"] for item in ready_backfill} == {"blocked"}
    assert {item["params"].get("phase_approval_ready") for item in ready_backfill} == {
        True
    }
    assert {item["params"].get("phase_plan_status") for item in ready_backfill} == {
        "approval_ready"
    }

    phase_approval = manager_client.post(
        "/api/v1/work-packages/ai/planning/dispatch",
        json={
            "project_id": project_id,
            "source_text": "Zone A 3단계 되메우기 계획 승인",
            "plan_id": "SASANG-PIPE-DEMO-V1",
            "phase_id": "backfill",
        },
    )
    assert phase_approval.status_code == 201, phase_approval.text
    assert {item["status"] for item in phase_approval.json()["work_packages"]} == {
        "pending"
    }

    backfill_claim = manager_client.post(
        "/api/v1/isaac/instructions/claim",
        params={
            "project_id": project_id,
            "limit": 3,
            "prefer_execution_group": True,
        },
    )
    assert backfill_claim.status_code == 200, backfill_claim.text
    claimed_backfill = backfill_claim.json()
    assert len(claimed_backfill) == 3
    assert {item["params"]["execution_group_mode"] for item in claimed_backfill} == {
        "parallel_pipeline_backfill"
    }
    assert {item["params"].get("phase_plan_status") for item in claimed_backfill} == {
        "approved"
    }

    progress = manager_client.post(
        f"/api/v1/isaac/instructions/{claimed_backfill[0]['id']}/progress",
        json={
            "phase": "backfilling",
            "step_index": 3,
            "step_count": 5,
            "progress_ratio": 0.6,
            "backfilled_volume_m3": 12.5,
        },
    )
    assert progress.status_code == 200, progress.text
    live = progress.json()["params"]["execution_progress"]
    assert live["progress_ratio"] == 0.6
    assert live["backfilled_volume_m3"] == 12.5

    # Phase 3 is the terminal phase. Its three Evidence approvals complete the
    # one parent pipeline job and must not create another successor group.
    backfill_commits = []
    for item in claimed_backfill:
        committed = manager_client.post(
            f"/api/v1/isaac/instructions/{item['id']}/commit",
            json={
                "status": "succeeded",
                "result": {
                    "operation": "pipeline_backfill",
                    "simulator": "isaac-sim",
                    "source": "stage-readback",
                    "backfilled_volume_m3": 1.0,
                    "map_changes": [],
                },
                "evidence": {"sensors": [], "storage_keys": []},
            },
        )
        assert committed.status_code == 201, committed.text
        backfill_commits.append(committed.json())

    for commit in backfill_commits:
        reviewed = manager_client.post(
            f"/api/v1/isaac/commits/{commit['id']}/review",
            json={"decision": "approved", "note": "Zone A Phase 3 approved"},
        )
        assert reviewed.status_code == 200, reviewed.text

    completed = manager_client.get(
        "/api/v1/isaac/instructions",
        params={"project_id": project_id, "limit": 100},
    )
    assert completed.status_code == 200, completed.text
    scenario_instructions = [
        item
        for item in completed.json()
        if item["params"].get("scenario_run_id") in scenario_run_ids
    ]
    # Nine drawing-derived instructions plus one corrective instruction for
    # the intentionally deficient centre excavation front.
    assert len(scenario_instructions) == 10
    assert {item["status"] for item in scenario_instructions} == {"approved"}
    assert not any(
        item["status"] == "blocked"
        and item["params"].get("phase_approval_ready")
        for item in scenario_instructions
    )
