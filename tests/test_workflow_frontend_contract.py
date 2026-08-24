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


def test_live_instruction_progress_uses_raw_execution_progress() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "instruction?.status==='dispatched'" in workflow
    assert "['dispatched','executing'].includes(w?.status)" in workflow
    assert "Number(w?.raw??0)" in workflow


def test_map_zones_are_created_from_post_cutover_work_geometry() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")
    viewer_html = (ROOT / "frontend" / "isaac-map-viewer.html").read_text(
        encoding="utf-8"
    )

    assert "MAP_FEATURE_CUTOVER_AT" in app
    assert "dynamicMapInstructions" in app
    assert "activeDynamicZoneInstructions" in app
    assert "SCENARIO_PHASE_ORDER" in app
    assert "phaseMembers.every(item=>item.status==='approved')" in app
    assert "const instructions=activeDynamicZoneInstructions()" in app
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


def test_map_reloads_published_baseline_when_isaac_connects() -> None:
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert "var wasConnected = stageConnected" in viewer
    assert "if (stageConnected && !wasConnected) loadMapObjects()" in viewer
    assert "diggableTargetsRaw = data.baseline_diggable_targets || []" in viewer


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
    assert "ZONE A · 관로 공사" in viewer
    assert "Zone=대형 공사 구역" in workflow
    assert "Phase=내부 공정" in workflow
    assert "Front=장비별 구간" in workflow
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


def test_pipeline_execution_is_grouped_and_next_phase_needs_plan_approval() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "wfScenarioRuns" in workflow
    assert "wfScenarioExecutionMarkup" in workflow
    assert "wfScenarioZoneId(design)" in workflow
    assert "내부 공정 흐름" in workflow
    assert "하나의 Zone에서 선행 Evidence 승인 후 순차적으로 열립니다" in workflow
    assert "data-open-scenario-phase" in workflow
    assert "wfOpenReadyScenarioPhasePlan" in workflow
    assert "phase_approval_ready" in workflow
    assert "계획 검토·승인" in workflow
    assert "const scenarioZoneId=reviewedInstruction?.params?.zone_id||'A'" in app
    assert "Zone ${scenarioZoneId}의 다음 공정 단계 작업량·장비·판정 기준" in app
    assert "parallel_pipeline_backfill" not in workflow
    assert "const allDone=completed===phases.length" in workflow
    assert "allDone?100" in workflow
    assert "전체 공정 완료" in workflow


def test_pipeline_parent_opens_a_real_construction_detail_view() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "data-open-scenario-run" in workflow
    assert "data-scenario-back" in workflow
    assert "wfScenarioDetailMarkup" in workflow
    assert "작업전선·장비 상태" in workflow
    assert "공사 타임라인" in workflow
    assert "관리자 게이트" in workflow
    assert "문제·차단 항목" in workflow
    assert "isaacLatestCommit(instruction)" in workflow
    assert "wfMapFrame({controls:false})" in workflow
    assert ".scenario-detail-layout" in styles
    assert ".scenario-detail-workfront" in styles
    assert ".scenario-parent-button" in styles
    assert "wfScenarioCompletionSummaryMarkup" in workflow
    assert "Zone ${esc(zoneId)} 관로 공사가 완료되었습니다" in workflow
    assert "FINAL PHASE RECORD" in workflow
    assert "공정별 완료 요약" in workflow
    assert ".scenario-completion-panel" in styles
    assert ".scenario-completion-summary-grid" in styles


def test_workflow_allows_seed_work_without_an_isaac_instruction() -> None:
    """A local/seed work row must not abort the latest workflow renderer."""

    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "function isaacLatestCommit(instruction){return (instruction?.commits||[])" in app


def test_under_excavation_uses_a_manager_gated_remediation_flow() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "quality_assessment?.status==='needs_remediation'" in app
    assert "목표 굴착량 미달 · 검토 필요" in app
    assert "/remediation`" in app
    assert "/dispatch-remediation`" in app
    assert "AI 보완 작업 초안" in app
    assert "장비·대상 Prim·부족 작업량" in app
    assert "목표량 미달 · 검토 필요" in workflow
    assert "data-open-remediation" in workflow
    assert "부족량 Evidence 검토" in workflow
    assert ".excavation-quality-panel" in styles
    assert ".remediation-plan-modal" in styles


def test_evidence_exposes_demo_sensor_fusion_depth_option() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "LiDAR + IMU·기구학 깊이 교차검증" in app
    assert "10미터 굴착 깊이 교차검증 예시" in app
    assert "DEMO · 예시값" in app
    assert "실제 승인 판정에는 아직 사용하지 않습니다" in app
    assert ".depth-corroboration-option" in styles


def test_dashboard_has_versioned_drawing_registry_and_xray_layer() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")
    viewer_html = (ROOT / "frontend" / "isaac-map-viewer.html").read_text(
        encoding="utf-8"
    )

    assert "/site-plans" in app
    assert 'data-action="manage-drawings"' in workflow
    assert 'data-map-layer="drawing"' in workflow
    assert "sitegit.isaac-map.design" in app
    assert "sitegit.isaac-map.design" in viewer
    assert "updateDesignOverlay" in viewer
    assert "design_depth_m" in viewer
    assert 'id="designOverlay"' in viewer_html


def test_review_is_grouped_by_construction_phase_not_equipment_rows() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "wfConstructionPhaseGroups" in workflow
    assert "장비별 Commit을 공정 단계로 모아" in workflow
    assert 'data-review-group="${esc(group.key)}"' in workflow
    assert "장비별 결과를 하나의 공정 단계 승인 단위로 묶어" in workflow
    assert "작업전선 Evidence" in workflow
    assert ".construction-review-layout" in styles
    assert ".phase-review-member" in styles


def test_history_uses_construction_git_graph_and_current_run_scope() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "wfConstructionGitGraph" in workflow
    assert "GIT-LIKE CONSTRUCTION GRAPH" in workflow
    assert "Phase 브랜치, 장비별 Evidence Commit" in workflow
    assert "다른 위치의 독립 작업은 별도 Zone 공사로 분리됩니다" in workflow
    assert "공정 단계" in workflow
    assert "data-history-run" in workflow
    assert ".construction-git-root" in styles
    assert ".equipment-git-branch" in styles


def test_history_phase_branches_expand_only_when_the_header_is_clicked() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "historyBranchesOpen:new Set()" in workflow
    assert 'data-history-branch-toggle="${esc(branchKey)}"' in workflow
    assert 'aria-expanded="${expanded}"' in workflow
    assert 'class="phase-git-content"' in workflow
    assert "workflowUI.historyBranchesOpen.has(branchKey)" in workflow
    assert ".phase-git-toggle" in styles
    assert ".phase-git-content[hidden]" in styles


def test_review_and_history_link_remediation_to_the_original_workfront() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "remediation_parent_instruction_id" in workflow
    assert "최초 Commit · 목표량 미달" in workflow
    assert "보완 Work Package 하달" in workflow
    assert "재작업 Commit · 기준 충족" in workflow
    assert "원 작업과 보완 작업을 하나의 작업전선 이력으로 병합" in workflow
    assert "group.primaryMembers.map" in workflow
    assert "원 작업 ${workfronts.length} + 보완 ${group.remediationMembers.length}" in workflow
    assert ".remediation-lineage" in styles
    assert ".equipment-git-branch.has-remediation" in styles


def test_history_commit_opens_the_exact_sensor_evidence_snapshot() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "instructionId:instruction.id,commitId:commit.id" in workflow
    assert 'data-isaac-commit="${esc(event.commitId)}"' in workflow
    assert "Commit 상세·Evidence 열기" in workflow
    assert "카메라·LiDAR·IMU Evidence 상세" in workflow
    assert (
        "openIsaacEvidence(detailIsaac.dataset.isaacDetail,detailIsaac.dataset.isaacCommit)"
        in app
    )
    assert "function openIsaacEvidence(instructionId,commitId='')" in app
    assert "(instruction.commits||[]).find(item=>item.id===commitId)" in app
    assert "HISTORICAL COMMIT" in app
    assert "Commit 계보" in app
    assert ".history-evidence-entry" in styles
    assert ".commit-provenance" in styles
