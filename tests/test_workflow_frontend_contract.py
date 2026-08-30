"""Regression checks for the manager UI-to-Isaac workflow wiring."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_demo_seed_registers_all_four_field_excavators() -> None:
    seed = json.loads(
        (ROOT / "seed" / "pipeline_demo_state.json").read_text(encoding="utf-8")
    )

    assert seed["project"]["name"] == "건설현장 관로 시공 통합 데모"
    assert [item["id"] for item in seed["equipment"]] == [
        "EXC-001",
        "EXC-002",
        "EXC-003",
        "EXC-004",
    ]
    assert all(item["primPath"].startswith("/World/Equipment/EXC_00") for item in seed["equipment"])
    assert all(item["manufacturer"] == "HD Hyundai" for item in seed["equipment"])
    assert all(item["model"] == "HX210AL" for item in seed["equipment"])
    assert all(item["operatingWeight"] == 22.15 for item in seed["equipment"])


def test_frontend_migrates_legacy_registry_and_project_copy() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "function applyCurrentDemoProfile(target)" in app
    assert "target.equipment=deepClone(CURRENT_DEMO_EQUIPMENT);" in app
    assert "applyCurrentDemoProfile(state);renderAll(true);" in app
    assert "현장에 등록된 장비의 제원, 작업 가능 범위와 운영 상태를 통합 관리합니다." in workflow
    assert "제조사 제원 보기" in workflow
    assert "Stage Prim</dt>" not in workflow
    assert "function wfPlanLabel(planId)" in workflow


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
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "wfCurrentPhaseId" in workflow
    assert "현재 하달할 공정의 추천 기준입니다. 관리자가 수치를 수정한 뒤 승인할 수 있습니다." in workflow
    assert "data-criteria-phase" in workflow
    assert "set-criteria-phase" not in workflow
    assert "phase_id:wfCurrentPhaseId(draft)" in workflow
    assert "wfCurrentAcceptanceCriteria" in workflow
    assert 'data-criteria-value' in workflow
    assert "LLM·도면 추천값 · 관리자 수정 가능" in workflow
    assert "acceptance_criteria:acceptanceCriteria" in workflow
    assert "params.acceptance_criteria" in workflow
    assert ".phase-criterion-editor input" in styles


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
    assert "createIsaacRemediation(remediateIsaac.dataset.isaacRemediation,remediateIsaac)" in app
    assert "function beginRemediationRequest" in app
    assert "overlay.dataset.remediationLoading='true'" in app
    assert "부족량을 분석하고 보완 계획을 만드는 중입니다" in app
    assert "finally{\n    finishPending();" in app
    assert "목표량 미달 · 검토 필요" in workflow
    assert "data-open-remediation" in workflow
    assert "부족량 Evidence 검토" in workflow
    assert ".excavation-quality-panel" in styles
    assert ".remediation-plan-modal" in styles
    assert ".remediation-request-overlay" in styles
    assert ".remediation-button-spinner" in styles


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
    assert "공정 브랜치, 장비별 Evidence Commit" in workflow
    assert "다른 위치의 독립 작업은 별도 Zone으로 분리 관리됩니다" in workflow
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


def test_history_uses_the_full_width_graph_without_a_duplicate_summary_panel() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    final_history_renderer = workflow[workflow.index("function wfConstructionHistoryEvents") :]

    assert "${wfHistoryDetail(selected)}" not in final_history_renderer
    assert "Evidence Commit을 누르면 해당 시점의 카메라·LiDAR·IMU Evidence 상세가 열립니다" in final_history_renderer
    assert ".construction-history-layout{display:block}" in styles


def test_review_heading_copy_is_not_limited_to_pipeline_construction() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "선택한 Zone의 장비별 Commit을 공정 단계로 모아 검토·승인하고 다음 공정으로 연결합니다" in workflow
    assert "이 화면은 선택한 Zone의 작업과 공정만 표시합니다" in workflow
    assert "Zone A 관로 공사의 장비별 Commit을 공정 단계로 모아 승인하고 다음 단계를 Release합니다" not in workflow


def test_history_and_equipment_copy_are_work_type_agnostic() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "선택한 Zone의 공정 브랜치, 장비별 Evidence Commit과 관리자 Merge 흐름을 한 그래프로 추적합니다" in workflow
    assert "Zone별 작업의 Commit과 승인 Merge 흐름을 추적합니다" in workflow
    assert "기록된 작업 없음" in workflow
    assert "작업 계획을 하달하면 Git graph 이력이 생성됩니다" in workflow
    assert "${esc(wfScenarioZoneTitle())} 계획 승인" in workflow
    assert "${esc(wfScenarioZoneTitle())} 최종 완료" in workflow
    assert "현재 관로 공사에 투입되는 현장 장비" not in workflow
    assert "Zone A 관로 공사의 Phase 브랜치" not in workflow
    assert "기록된 관로 공사 없음" not in workflow


def test_frontend_renders_only_the_active_page() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "function renderCurrentPage(force=false)" in app
    assert "(renderers[page]||renderers.dashboard)();" in app
    render_all = app[app.index("function renderAll(force=false){") : app.index("function renderHeader()")]
    assert "renderCurrentPage(force);" in render_all
    assert "renderReadiness();" not in render_all
    assert "renderWorkPackages();" not in render_all
    navigate = app[app.index("function navigate(page,force=false){") : app.index("function isaacMapFrames()")]
    assert "renderCurrentPage(force);" in navigate


def test_frontend_reuses_unchanged_pages_and_map_iframes() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert "const renderedPages = new Set();" in app
    assert "function currentRenderSignature()" in app
    assert "if(!force&&renderedPages.has(page))" in app
    assert "renderedPages.add(page);" in app
    assert "renderedPages.clear();" in app
    assert "selectedWpId:state?.selectedWpId||''" in app
    assert "renderAll(true);" in workflow


def test_remote_clients_load_shared_history_before_the_heavy_map() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "cache:'no-store'" in app
    assert "await pullRemoteState({render:false});" in app
    assert "await Promise.all([loadSitePlans(),loadStageInventory(),loadIsaacInstructions()]);" in app
    assert app.index("renderAll(true);", app.index("async function bootstrapSharedState")) < app.index(
        "await Promise.all([loadSitePlans(),loadStageInventory(),loadIsaacInstructions()]);"
    )
    initial_boot = app[app.index("/* Initial boot */") :]
    assert "공동 작업 기록을 불러오는 중입니다." in initial_boot
    assert "prepareState();\nrenderAll();" not in initial_boot


def test_map_viewer_caches_only_revisioned_base_mesh_assets() -> None:
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert 'fetch(MAP_ROOT + "/publication.json", { cache: "no-store" })' in viewer
    assert 'revision ? "force-cache" : "default"' in viewer
    assert '"?revision=" + encodeURIComponent(revision)' in viewer
    assert 'fetch(MAP_OBJECTS_URL, {' in viewer
    assert 'fetch(STAGE_INVENTORY_URL, {' in viewer
    assert viewer.count('cache: "no-store"') >= 3


def test_map_viewer_throttles_inventory_without_staling_live_data() -> None:
    viewer = (ROOT / "frontend" / "isaac-map-viewer.js").read_text(encoding="utf-8")

    assert "var stageInventoryLoading = false;" in viewer
    assert 'document.visibilityState === "hidden"' in viewer
    assert "window.setInterval(loadStageInventory, 2500);" in viewer
    assert 'document.addEventListener("visibilitychange"' in viewer


def test_heavy_frontend_images_are_deferred() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")

    assert 'decoding="async" src="${evidenceUrl(imageKey)}"' in app
    assert 'loading="lazy" decoding="async" src="${image}"' in workflow
    assert 'loading="lazy" decoding="async" src="/static/assets/review/' in workflow


def test_station_ranges_explain_datum_and_metres_consistently() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "function wfStationPoint(value)" in workflow
    assert "작업 구간 · 측점(STA)" in workflow
    assert "기준점 STA 0+000 = 관로 중심선 시작점 · 단위 m · 중심선 누적거리" in workflow
    assert "wfAnnotateStationRanges(page)" in workflow
    assert ".station-basis" in styles


def test_equipment_registry_filter_changes_the_visible_equipment_list() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "equipmentFilterOpen" not in workflow
    assert "equipmentType:'ALL'" in workflow
    assert "equipmentStatus:'ALL'" in workflow
    assert "function wfFilteredEquipment(equipment)" in workflow
    assert 'data-equipment-filter="type"' in workflow
    assert 'data-equipment-filter="status"' in workflow
    assert 'data-workflow-action="equipment-filter-reset"' in workflow
    assert 'data-workflow-action="equipment-filter"' not in workflow
    assert 'class="equipment-filter-panel"' in workflow
    assert "workflowUI.equipmentType=e.target.value" in workflow
    assert "workflowUI.equipmentStatus=e.target.value" in workflow
    assert ".equipment-filter-panel" in styles
    assert ".equipment-filter-empty" in styles


def test_settings_show_pipeline_wide_phase_specific_acceptance_criteria() -> None:
    workflow = (ROOT / "frontend" / "workflow-ui.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "관로 공사 전체 완료·승인 판정 기준" in workflow
    assert "const phases=wfScenarioPhases();" in workflow
    assert "phase.acceptance_criteria||[]" in workflow
    assert "설계 굴착 저면 대비 ±50mm" in workflow
    assert "관 중심선 수평 편차 ±100mm" in workflow
    assert "층별 다짐도 90% 이상" in workflow
    assert "기준 1건 이상 미충족 시 검토 필요" in workflow
    assert "터파기 승인 → 관로 설치 승인 → 되메우기 승인 → 관로 공사 완료" in workflow
    assert ".criteria-phase-grid" in styles
    assert ".criteria-phase-card.zone-b" in styles
    assert ".criteria-phase-card.zone-c" in styles


def test_frontend_loads_the_responsive_readability_layer_last() -> None:
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    login = (ROOT / "frontend" / "login.html").read_text(encoding="utf-8")
    readability = (ROOT / "frontend" / "readability.css").read_text(encoding="utf-8")

    assert index.index("dashboard-progress.css") < index.index("readability.css")
    assert login.index("login.css") < login.index("readability.css")
    assert "--sg-readable-micro: clamp(12px" in readability
    assert "--sg-readable-body: clamp(14px" in readability
    assert "@media (max-width: 1180px)" in readability
    assert 'span:not([class*="icon"])' in readability
    assert "overflow-wrap: anywhere" in readability


def test_scenario_detail_raises_micro_text_without_resizing_the_layout() -> None:
    readability = (ROOT / "frontend" / "readability.css").read_text(encoding="utf-8")

    assert ".app-shell .scenario-detail-page .scenario-current-panel dt {\n  font-size: 11px;" in readability
    assert ".app-shell .scenario-detail-page .scenario-current-panel dd {\n  font-size: 16px;" in readability
    assert ".app-shell .scenario-detail-page .scenario-detail-workfront > div > b {\n  font-size: 13px;" in readability
    assert ".app-shell .scenario-detail-page .scenario-criteria span {\n  font-size: 12px;" in readability
    assert ".app-shell .scenario-detail-page .scenario-activity b {\n  font-size: 13px;" in readability


def test_rejected_commit_detail_submits_supplemental_evidence_for_review() -> None:
    app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "commit.review_status==='rejected'" in app
    assert 'data-rejected-evidence-panel' in app
    assert 'id="supplementalEvidenceFiles" type="file" multiple' in app
    assert '추가 Evidence 제출 · 재검토 요청' in app
    assert '/supplemental-evidence`' in app
    assert 'supplemental_review_override' in app
    assert 'Evidence 제출 중…' in app
    assert '다시 승인할 수 있습니다.' in app
    assert 'UI PREVIEW' not in app
    assert '서버에는 저장되지 않습니다.' not in app
    assert '.supplemental-evidence-panel' in styles
    assert '.supplemental-evidence-form' in styles
