"""Regression checks for the manager UI-to-Isaac workflow wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manager_workflow_dispatches_to_the_real_code_agent() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "/work-packages/ai/planning/interpret" in workflow
    assert "/work-packages/ai/code/interpret" in workflow
    assert "submitCodeWorkPackageDraft(codeDraft,display)" in workflow
    assert "/work-packages/ai/code/dispatch" in app
    assert "실제 Isaac 실행 없이 SiteGit 작업 목록에 저장했습니다." not in workflow


def test_manager_workflow_uses_real_execution_evidence_and_history() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "wfInstructionForWork" in workflow
    assert 'data-isaac-detail=' in workflow
    assert 'data-real-wp-detail=' in workflow
    assert "wfHistoryWorks()" in workflow
    assert 'data-isaac-approve=' in app
    assert 'data-isaac-reject=' in app


def test_map_zones_are_created_from_post_cutover_work_geometry() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")
    viewer_html = (ROOT / "frontend" / "isaac-map-viewer.html").read_text(
        encoding="utf-8"
    )

    assert "MAP_FEATURE_CUTOVER_AT" in app
    assert "dynamicMapInstructions" in app
    assert "dynamicInstructionGeometry" in app
    assert "sitegit.isaac-map.zones" in app
    assert "sitegit.isaac-map.zones" in viewer
    assert "uZoneCenters[16]" in viewer
    assert "uZoneHalfSizes[16]" in viewer
    assert 'data-zone="A"' not in viewer_html


def test_timeline_supports_baseline_and_zone_filtering() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert 'data-map-layer="zone"' in workflow
    assert 'data-map-layer="timeline"' in workflow
    assert "data-timeline-zone" in app
    assert "timelineZoneFilter" in app
    assert "featureStartAt:MAP_FEATURE_CUTOVER_AT" in app
    assert "timelineFeatureStartAt" in viewer
    assert "timelineInstructionIds" in viewer


def test_embedded_map_hides_duplicate_status_card_but_keeps_errors() -> None:
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert "window.self !== window.top" in viewer
    assert "state.hidden = embedded && !isError" in viewer


def test_pipeline_drawing_plan_has_flow_preview_and_map_overlay() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert "/work-packages/ai/planning/dispatch" in workflow
    assert "터파기 → 관로 설치 → 되메우기" in workflow
    assert 'data-planning-map="1"' in workflow
    assert "setIsaacPlanningOverlay" in app
    assert "sitegit.isaac-map.plan" in viewer
    assert "planningCorridorPoints" in viewer
    assert "planningCorridorSides" in viewer
    assert 'class="plan-front-area"' in viewer
    assert "ZONE A · 터파기 전체" in viewer
    assert "wfPipelineDrawing" in workflow
    assert 'data-plan-view="drawing"' in workflow
    assert "설계 깊이" in workflow
    assert "관경 Ø" in workflow


def test_pipeline_plan_only_shows_criteria_for_the_current_phase() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "wfCurrentPhaseId" in workflow
    assert "현재 하달할 공정의 도면 검측 기준만 적용됩니다." in workflow
    assert "data-criteria-phase" not in workflow
    assert "set-criteria-phase" not in workflow
    assert "phase_id:wfCurrentPhaseId(draft)" in workflow
