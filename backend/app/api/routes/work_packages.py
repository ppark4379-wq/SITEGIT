"""자연어 Work Package 생성과 Isaac 실행 대기열 연결 API."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...domains.executions.service import ExecutionsService
from ...domains.executions.stage_inventory import load_stage_inventory
from ...domains.work_packages.ai_compiler import (
    WorkPackageLLMError,
    WorkPackageLLMUnavailable,
    compile_natural_language,
    compile_planning_work_package,
    compile_excavation_language,
    resolve_excavation_plan,
    resolve_plan,
)
from ...domains.work_packages.code_agent import (
    compile_code_work_package,
    resolve_code_work_package,
    validate_restricted_code,
)
from ...domains.work_packages.site_plan import (
    apply_site_design_defaults,
    design_prompt_context,
    get_raw_pipeline_plan,
    load_site_design_for_request,
)
from ...models.user import User
from ...models.audit_log import AuditLog
from ...realtime.manager import manager
from ...schemas.isaac import InstructionResponse
from ...schemas.work_package_ai import (
    AIWorkPackageDispatchRequest,
    AIWorkPackageDispatchResponse,
    AIWorkPackageInterpretRequest,
    AIWorkPackageRecord,
    AIWorkPackageDraft,
    ExcavationDispatchRequest,
    ExcavationDispatchResponse,
    ExcavationInterpretRequest,
    ExcavationDraft,
    ExcavationWorkPackageRecord,
    CodeWorkPackageDispatchRequest,
    CodeWorkPackageDispatchResponse,
    CodeWorkPackageDraft,
    CodeWorkPackageInterpretRequest,
    CodeWorkPackageRecord,
    PlanningWorkPackageDraft,
    PlanningScenarioDispatchRequest,
    PlanningScenarioDispatchResponse,
    PlanningScenarioWorkPackageRecord,
)
from ..deps import get_db, require_roles


router = APIRouter(prefix="/work-packages", tags=["work-packages"])
OPERATOR_ROLES = ("admin", "manager", "reviewer")


@router.post("/ai/planning/interpret", response_model=PlanningWorkPackageDraft)
def interpret_planning_work_package(
    payload: AIWorkPackageInterpretRequest,
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> PlanningWorkPackageDraft:
    """Isaac 실행과 분리해 관리자 검토용 작업지시 초안만 생성합니다."""
    settings = get_settings()
    design = load_site_design_for_request(payload.project_id, payload.message)
    try:
        plan = compile_planning_work_package(
            payload.message,
            settings,
            design_prompt_context(design) if design else "",
        )
    except WorkPackageLLMUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_NOT_CONFIGURED", "message": str(error)},
        ) from error
    except WorkPackageLLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "LLM_REQUEST_FAILED", "message": str(error)},
        ) from error
    if design:
        plan = apply_site_design_defaults(payload.message, plan, design)
    return PlanningWorkPackageDraft(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=plan,
        design=design,
        model=settings.ollama_model,
    )


def _scenario_excavation_code(equipment_path: str, target_paths: list[str]) -> str:
    """Build one small, validated program for a drawing work front."""

    lines = ["def execute(ctx):"]
    for target_path in target_paths:
        lines.append(
            "    ctx.excavate("
            f"equipment_prim_path={equipment_path!r}, "
            f"target_prim_path={target_path!r}, "
            "approach_distance_m=3.0, animation_seconds=6.0)"
        )
    lines.append("    return ctx.finish()")
    code = "\n".join(lines)
    validate_restricted_code(code)
    return code


def _scenario_coordinated_code() -> str:
    """Return a validated placeholder for an Adapter-coordinated group task."""

    code = "def execute(ctx):\n    return ctx.finish()"
    validate_restricted_code(code)
    return code


def _dispatch_soil_relocation_phase(
    db: Session,
    *,
    payload: PlanningScenarioDispatchRequest,
    raw_plan: dict,
    user: User,
) -> PlanningScenarioDispatchResponse:
    """Confirm the drawing candidate, create Zone B, and issue its package."""

    phase = next(
        (item for item in raw_plan["workflow"] if item["id"] == payload.phase_id),
        None,
    )
    if phase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"도면에 없는 공정입니다: {payload.phase_id}",
        )

    work_area = raw_plan["work_area"]
    relocation = work_area["relocation"]
    front = work_area["workfronts"][0]
    equipment_path = str(relocation["equipment_prim_path"])
    source_path = str(relocation["source_prim_path"])
    inventory = load_stage_inventory(payload.project_id)
    equipment_paths = {item.path for item in inventory.equipment if item.active}
    target_paths = {item.path for item in inventory.diggable_targets if item.active}
    missing: list[str] = []
    if not inventory.connected:
        missing.append("현장 작업 시스템 연결 대기")
    if equipment_path not in equipment_paths:
        missing.append(f"장비 Prim 없음: {equipment_path}")
    if source_path not in target_paths:
        missing.append(f"토사 Prim 없음: {source_path}")

    work_package_id = f"WP-SOIL-B-{uuid4().hex[:8].upper()}"
    scenario_run_id = f"SCN-{uuid4().hex[:12].upper()}"
    group_id = f"EXG-{payload.plan_id}-soil-relocation-{uuid4().hex[:10]}"
    instruction_status = "blocked" if missing else "pending"
    generated_code = _scenario_coordinated_code()
    instruction = ExecutionsService.create_instruction(
        db,
        project_id=payload.project_id,
        kind="generated_script",
        params={
            "work_package_id": work_package_id,
            "scenario_plan_id": payload.plan_id,
            "scenario_run_id": scenario_run_id,
            "scenario_parent_work_package_id": work_package_id,
            "scenario_title": "Zone B 토사 적치 위치 변경",
            "scenario_phase_id": payload.phase_id,
            "scenario_phase_order": 1,
            "workfront_id": front["id"],
            "operation": "soil_relocation",
            "zone_assignment_mode": "create_on_approval",
            "zone_created_from_candidate": True,
            "zone_created_at": datetime.now(timezone.utc).isoformat(),
            "location_confirmed": True,
            "location_confirmation_prompt": work_area.get(
                "location_confirmation_prompt", ""
            ),
            "candidate_work_area_id": work_area["id"],
            "execution_group_id": group_id,
            "execution_group_size": 1,
            "execution_group_mode": "stationary_soil_relocation",
            "summary": "Zone B · 굴착기 궤도 고정 토사 이동",
            "zone_id": str(phase["zone_id"]),
            "source_text": payload.source_text,
            "generated_code": generated_code,
            "program_version": 1,
            "resource_bindings": {
                "equipment": equipment_path,
                "target": source_path,
            },
            "target_prim_paths": [source_path],
            "equipment_name": relocation["equipment_id"],
            "target_name": front["label"],
            "planned_quantity": {
                "value": float(phase["target_amount"]),
                "unit": str(phase["target_unit"]),
                "source": f"{payload.plan_id} Rev.{raw_plan['revision']}",
            },
            "station_range": work_area["station_range"],
            "relocation": relocation,
            "work_area_bounds": work_area.get("bounds"),
            "tracks_stationary": True,
            "missing_resources": missing,
            "checks": [
                {
                    "code": "drawing",
                    "ok": True,
                    "message": f"승인 도면 확인: {payload.plan_id} Rev.{raw_plan['revision']}",
                },
                {
                    "code": "stationary_tracks",
                    "ok": True,
                    "message": "궤도 고정 · 상부체 선회 방식",
                },
                {
                    "code": "resources",
                    "ok": not missing,
                    "message": "현장 자원 확인 완료" if not missing else missing[0],
                },
            ],
            "compiler_model": "site-plan-deterministic-v1",
        },
        note="Zone B 토사 적치 위치 변경 작업 하달",
        user=user,
        initial_status=instruction_status,
    )
    record = PlanningScenarioWorkPackageRecord(
        id=work_package_id,
        phase_id=payload.phase_id,
        workfront_id=front["id"],
        zone_id=str(phase["zone_id"]),
        equipment_id=str(relocation["equipment_id"]),
        target_prim_paths=[source_path],
        status=instruction_status,
        missing_resources=missing,
    )
    return PlanningScenarioDispatchResponse(
        plan_id=payload.plan_id,
        phase_id=payload.phase_id,
        work_packages=[record],
        instructions=[InstructionResponse.model_validate(instruction, from_attributes=True)],
    )


def _approve_registered_scenario_phase(
    db: Session,
    *,
    payload: PlanningScenarioDispatchRequest,
    raw_plan: dict,
    user: User,
) -> PlanningScenarioDispatchResponse:
    """Approve the latest ready successor phase without creating duplicates."""

    phase = next(
        (item for item in raw_plan["workflow"] if item["id"] == payload.phase_id),
        None,
    )
    if phase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"도면에 없는 공정입니다: {payload.phase_id}",
        )

    candidates = [
        item
        for item in ExecutionsService.list_instructions(
            db, project_id=payload.project_id, limit=500
        )
        if item.status == "blocked"
        and str((item.params or {}).get("scenario_plan_id") or "")
        == payload.plan_id
        and str((item.params or {}).get("scenario_phase_id") or "")
        == payload.phase_id
        and bool((item.params or {}).get("phase_approval_ready"))
    ]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Zone {phase['zone_id']}의 {phase['title']} 공정 계획은 아직 열리지 않았습니다. "
                "선행 공정의 모든 Evidence Commit을 먼저 승인해 주세요."
            ),
        )

    group_id = str((candidates[0].params or {}).get("execution_group_id") or "")
    members = [
        item
        for item in candidates
        if str((item.params or {}).get("execution_group_id") or "") == group_id
    ]
    expected_size = int((members[0].params or {}).get("execution_group_size") or 0)
    if not group_id or len(members) != expected_size:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="다음 공정의 Work Package 그룹이 완전하지 않습니다.",
        )

    inventory = load_stage_inventory(payload.project_id)
    active_equipment = {item.path for item in inventory.equipment if item.active}
    missing: list[str] = []
    if not inventory.connected:
        missing.append("현장 작업 시스템 연결 대기")
    for instruction in members:
        equipment_path = str(
            ((instruction.params or {}).get("resource_bindings") or {}).get(
                "equipment"
            )
            or ""
        )
        if equipment_path and equipment_path not in active_equipment:
            missing.append(f"장비 Prim 없음: {equipment_path}")
    missing = list(dict.fromkeys(missing))
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=" · ".join(missing),
        )

    approved_at = datetime.now(timezone.utc).isoformat()
    records: list[PlanningScenarioWorkPackageRecord] = []
    for instruction in members:
        params = dict(instruction.params or {})
        params["phase_plan_status"] = "approved"
        params["phase_plan_approved_at"] = approved_at
        params["phase_plan_approved_by"] = user.username
        checks = []
        for check in params.get("checks") or []:
            if check.get("code") == "predecessor":
                checks.append(
                    {
                        **check,
                        "ok": True,
                        "message": "선행 공정 승인 및 현재 공정 계획 승인 완료",
                    }
                )
            else:
                checks.append(check)
        params["checks"] = checks
        params["missing_resources"] = []
        instruction.params = params
        instruction.status = "pending"
        db.add(instruction)
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_SCENARIO_PHASE_PLAN_APPROVED",
                target_type="work_instruction",
                target_id=instruction.id,
                details={
                    "project_id": payload.project_id,
                    "scenario_plan_id": payload.plan_id,
                    "scenario_run_id": params.get("scenario_run_id"),
                    "scenario_phase_id": payload.phase_id,
                    "execution_group_id": group_id,
                },
            )
        )
    db.commit()
    for instruction in members:
        db.refresh(instruction)
        params = instruction.params or {}
        records.append(
            PlanningScenarioWorkPackageRecord(
                id=str(params.get("work_package_id")),
                phase_id=payload.phase_id,
                workfront_id=str(params.get("workfront_id")),
                zone_id=str(params.get("zone_id")),
                equipment_id=str(params.get("equipment_name")),
                target_prim_paths=[
                    str(path) for path in params.get("target_prim_paths") or []
                ],
                status="pending",
                missing_resources=[],
            )
        )
    return PlanningScenarioDispatchResponse(
        plan_id=payload.plan_id,
        phase_id=payload.phase_id,
        work_packages=records,
        instructions=[
            InstructionResponse.model_validate(item, from_attributes=True)
            for item in members
        ],
    )


@router.post(
    "/ai/planning/dispatch",
    response_model=PlanningScenarioDispatchResponse,
    status_code=201,
)
async def dispatch_planning_scenario(
    payload: PlanningScenarioDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> PlanningScenarioDispatchResponse:
    """Approve one drawing phase and issue deterministic per-front Isaac work."""

    try:
        raw_plan = get_raw_pipeline_plan(payload.plan_id, payload.project_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if raw_plan.get("scenario_type") == "soil_relocation":
        response = _dispatch_soil_relocation_phase(
            db,
            payload=payload,
            raw_plan=raw_plan,
            user=user,
        )
        await manager.broadcast(
            payload.project_id,
            {
                "type": "isaac.map.updated",
                "reason": "soil_relocation.plan_issued",
                "plan_id": payload.plan_id,
                "phase_id": payload.phase_id,
                "zone_id": "B",
                "zone_created": True,
            },
        )
        return response
    if payload.phase_id != "excavation":
        response = _approve_registered_scenario_phase(
            db,
            payload=payload,
            raw_plan=raw_plan,
            user=user,
        )
        await manager.broadcast(
            payload.project_id,
            {
                "type": "isaac.map.updated",
                "reason": "scenario.phase.plan_approved",
                "plan_id": payload.plan_id,
                "phase_id": payload.phase_id,
            },
        )
        return response

    inventory = load_stage_inventory(payload.project_id)
    equipment_by_path = {item.path: item for item in inventory.equipment if item.active}
    target_by_path = {item.path: item for item in inventory.diggable_targets if item.active}
    phase = next(
        item for item in raw_plan["workflow"] if item["id"] == payload.phase_id
    )
    phase_zone_id = str(phase["zone_id"])
    records: list[PlanningScenarioWorkPackageRecord] = []
    instructions: list[InstructionResponse] = []
    work_area = raw_plan["work_area"]
    scenario_run_id = f"SCN-{uuid4().hex[:12].upper()}"
    scenario_parent_work_package_id = f"WP-PIPELINE-{uuid4().hex[:8].upper()}"
    execution_group_id = f"EXG-{payload.plan_id}-{payload.phase_id}-{uuid4().hex[:10]}"
    execution_group_size = len(work_area["workfronts"])
    for front in work_area["workfronts"]:
        equipment_path = str(front["equipment_prim_path"])
        target_paths = [str(path) for path in front["target_prim_paths"]]
        missing: list[str] = []
        if not inventory.connected:
            missing.append("현장 작업 시스템 연결 대기")
        if equipment_path not in equipment_by_path:
            missing.append(f"장비 Prim 없음: {equipment_path}")
        missing.extend(
            f"굴착 대상 Prim 없음: {path}"
            for path in target_paths
            if path not in target_by_path
        )
        generated_code = _scenario_excavation_code(equipment_path, target_paths)
        work_package_id = f"WP-PIPE-{phase_zone_id}-{uuid4().hex[:8].upper()}"
        instruction_status = "blocked" if missing else "pending"
        instruction = ExecutionsService.create_instruction(
            db,
            project_id=payload.project_id,
            kind="generated_script",
            params={
                "work_package_id": work_package_id,
                "scenario_plan_id": payload.plan_id,
                "scenario_run_id": scenario_run_id,
                "scenario_parent_work_package_id": scenario_parent_work_package_id,
                "scenario_title": "관로 공사",
                "scenario_phase_id": payload.phase_id,
                "scenario_phase_order": 1,
                "workfront_id": front["id"],
                "operation": "pipeline_excavation",
                "execution_group_id": execution_group_id,
                "execution_group_size": execution_group_size,
                "execution_group_mode": "parallel_incremental_scoops",
                "summary": f"Zone {phase_zone_id} 관로 공사 · 1단계 {front['label']}",
                "zone_id": phase_zone_id,
                "source_text": payload.source_text,
                "generated_code": generated_code,
                "program_version": 1,
                "resource_bindings": {
                    "equipment": equipment_path,
                    "target": target_paths[0],
                },
                "target_prim_paths": target_paths,
                "equipment_name": front["equipment_id"],
                "target_name": front["label"],
                "planned_quantity": {
                    "value": front["target_volume_m3"],
                    "unit": "m3",
                    "source": f"{payload.plan_id} Rev.{raw_plan['revision']}",
                },
                "quality_scenario": front.get("demo_quality_scenario"),
                "required_completion_ratio": float(
                    (front.get("demo_quality_scenario") or {}).get(
                        "required_completion_ratio", 0.98
                    )
                ),
                "station_range": (
                    f"STA {front['station_start_m']:05.1f} ~ {front['station_end_m']:05.1f}"
                ),
                "depends_on_phase_ids": [],
                "missing_resources": missing,
                "checks": [
                    {
                        "code": "drawing",
                        "ok": True,
                        "message": f"승인 도면 확인: {payload.plan_id} Rev.{raw_plan['revision']}",
                    },
                    {
                        "code": "resources",
                        "ok": not missing,
                        "message": "현장 자원 확인 완료" if not missing else missing[0],
                    },
                ],
                "compiler_model": "site-plan-deterministic-v1",
            },
            note=f"관로 도면 작업 하달 · {front['label']}"[:500],
            user=user,
            initial_status=instruction_status,
        )
        records.append(
            PlanningScenarioWorkPackageRecord(
                id=work_package_id,
                phase_id=payload.phase_id,
                workfront_id=front["id"],
                zone_id=phase_zone_id,
                equipment_id=front["equipment_id"],
                target_prim_paths=target_paths,
                status=instruction_status,
                missing_resources=missing,
            )
        )
        instructions.append(
            InstructionResponse.model_validate(instruction, from_attributes=True)
        )

    # A pipeline request is one approved construction plan, not three unrelated
    # chat commands.  Register the next phase now, but keep it blocked until all
    # independently reviewable excavation commits in Zone A have been approved.
    # The trust gate then exposes phase 2 for a separate manager approval; only
    # that second approval changes this group to pending for the Adapter.
    installation_phase = next(
        item for item in raw_plan["workflow"] if item["id"] == "pipe_installation"
    )
    installation_zone_id = str(installation_phase["zone_id"])
    installation_group_id = (
        f"EXG-{payload.plan_id}-pipe_installation-{uuid4().hex[:10]}"
    )
    installation_group_size = len(work_area["workfronts"])
    coordinated_code = _scenario_coordinated_code()
    for front in work_area["workfronts"]:
        equipment_path = str(front["equipment_prim_path"])
        target_paths = [str(path) for path in front["target_prim_paths"]]
        missing: list[str] = []
        if not inventory.connected:
            missing.append("Field work system connection is not ready")
        if equipment_path not in equipment_by_path:
            missing.append(f"Equipment Prim is missing: {equipment_path}")
        work_package_id = (
            f"WP-PIPE-{installation_zone_id}-{uuid4().hex[:8].upper()}"
        )
        instruction = ExecutionsService.create_instruction(
            db,
            project_id=payload.project_id,
            kind="generated_script",
            params={
                "work_package_id": work_package_id,
                "scenario_plan_id": payload.plan_id,
                "scenario_run_id": scenario_run_id,
                "scenario_parent_work_package_id": scenario_parent_work_package_id,
                "scenario_title": "관로 공사",
                "scenario_phase_id": "pipe_installation",
                "scenario_phase_order": 2,
                "workfront_id": front["id"],
                "operation": "pipeline_installation",
                "execution_group_id": installation_group_id,
                "execution_group_size": installation_group_size,
                "execution_group_mode": "parallel_pipe_installation",
                "predecessor_execution_group_id": execution_group_id,
                "summary": f"Zone {installation_zone_id} 관로 공사 · 2단계 관로 설치 · {front['label']}",
                "zone_id": installation_zone_id,
                "source_text": payload.source_text,
                "generated_code": coordinated_code,
                "program_version": 1,
                "resource_bindings": {
                    "equipment": equipment_path,
                    "target": target_paths[0],
                },
                "target_prim_paths": target_paths,
                "equipment_name": front["equipment_id"],
                "target_name": f"Pipeline segment · {front['id']}",
                "planned_quantity": {
                    "value": float(front["station_end_m"])
                    - float(front["station_start_m"]),
                    "unit": "m",
                    "source": f"{payload.plan_id} Rev.{raw_plan['revision']}",
                },
                "station_range": (
                    f"STA {front['station_start_m']:05.1f} ~ "
                    f"{front['station_end_m']:05.1f}"
                ),
                "depends_on_phase_ids": ["excavation"],
                "phase_approval_ready": False,
                "phase_plan_status": "locked",
                "missing_resources": missing,
                "checks": [
                    {
                        "code": "predecessor",
                        "ok": False,
                        "message": "Waiting for all Zone A phase 1 excavation commits to be approved",
                    },
                    {
                        "code": "resources",
                        "ok": not missing,
                        "message": "Stage resources are ready" if not missing else missing[0],
                    },
                ],
                "compiler_model": "site-plan-deterministic-v1",
            },
            note=f"Pipeline drawing successor · {front['label']}"[:500],
            user=user,
            initial_status="blocked",
        )
        records.append(
            PlanningScenarioWorkPackageRecord(
                id=work_package_id,
                phase_id="pipe_installation",
                workfront_id=front["id"],
                zone_id=installation_zone_id,
                equipment_id=front["equipment_id"],
                target_prim_paths=target_paths,
                status="blocked",
                missing_resources=missing,
            )
        )
        instructions.append(
            InstructionResponse.model_validate(instruction, from_attributes=True)
        )

    # Phase 3 is part of the same Zone A construction job.  It remains locked
    # while phase 2 is being installed/reviewed, then uses the same explicit
    # phase-plan approval gate before the Adapter may claim it.
    backfill_phase = next(
        item for item in raw_plan["workflow"] if item["id"] == "backfill"
    )
    backfill_zone_id = str(backfill_phase["zone_id"])
    backfill_group_id = f"EXG-{payload.plan_id}-backfill-{uuid4().hex[:10]}"
    backfill_group_size = len(work_area["workfronts"])
    for front in work_area["workfronts"]:
        equipment_path = str(front["equipment_prim_path"])
        target_paths = [str(path) for path in front["target_prim_paths"]]
        missing: list[str] = []
        if not inventory.connected:
            missing.append("Field work system connection is not ready")
        if equipment_path not in equipment_by_path:
            missing.append(f"Equipment Prim is missing: {equipment_path}")
        work_package_id = f"WP-PIPE-{backfill_zone_id}-{uuid4().hex[:8].upper()}"
        instruction = ExecutionsService.create_instruction(
            db,
            project_id=payload.project_id,
            kind="generated_script",
            params={
                "work_package_id": work_package_id,
                "scenario_plan_id": payload.plan_id,
                "scenario_run_id": scenario_run_id,
                "scenario_parent_work_package_id": scenario_parent_work_package_id,
                "scenario_title": "관로 공사",
                "scenario_phase_id": "backfill",
                "scenario_phase_order": 3,
                "workfront_id": front["id"],
                "operation": "pipeline_backfill",
                "execution_group_id": backfill_group_id,
                "execution_group_size": backfill_group_size,
                "execution_group_mode": "parallel_pipeline_backfill",
                "predecessor_execution_group_id": installation_group_id,
                "summary": f"Zone {backfill_zone_id} 관로 공사 · 3단계 되메우기 · {front['label']}",
                "zone_id": backfill_zone_id,
                "source_text": payload.source_text,
                "generated_code": coordinated_code,
                "program_version": 1,
                "resource_bindings": {
                    "equipment": equipment_path,
                    "target": target_paths[0],
                },
                "target_prim_paths": target_paths,
                "equipment_name": front["equipment_id"],
                "target_name": f"Backfill section · {front['id']}",
                "planned_quantity": {
                    "value": float(front["target_volume_m3"]),
                    "unit": "m3",
                    "source": f"{payload.plan_id} Rev.{raw_plan['revision']}",
                },
                "station_range": (
                    f"STA {front['station_start_m']:05.1f} ~ "
                    f"{front['station_end_m']:05.1f}"
                ),
                "depends_on_phase_ids": ["pipe_installation"],
                "phase_approval_ready": False,
                "phase_plan_status": "locked",
                "missing_resources": missing,
                "checks": [
                    {
                        "code": "predecessor",
                        "ok": False,
                        "message": "Waiting for all Zone A phase 2 installation commits to be approved",
                    },
                    {
                        "code": "resources",
                        "ok": not missing,
                        "message": "Stage resources are ready" if not missing else missing[0],
                    },
                ],
                "compiler_model": "site-plan-deterministic-v1",
            },
            note=f"Pipeline drawing successor · backfill · {front['label']}"[:500],
            user=user,
            initial_status="blocked",
        )
        records.append(
            PlanningScenarioWorkPackageRecord(
                id=work_package_id,
                phase_id="backfill",
                workfront_id=front["id"],
                zone_id=backfill_zone_id,
                equipment_id=front["equipment_id"],
                target_prim_paths=target_paths,
                status="blocked",
                missing_resources=missing,
            )
        )
        instructions.append(
            InstructionResponse.model_validate(instruction, from_attributes=True)
        )

    await manager.broadcast(
        payload.project_id,
        {
            "type": "isaac.map.updated",
            "reason": "work_package.scenario.issued",
            "plan_id": payload.plan_id,
            "phase_id": payload.phase_id,
        },
    )
    return PlanningScenarioDispatchResponse(
        plan_id=payload.plan_id,
        phase_id=payload.phase_id,
        work_packages=records,
        instructions=instructions,
    )


@router.post("/ai/code/interpret", response_model=CodeWorkPackageDraft)
def interpret_code_work_package(
    payload: CodeWorkPackageInterpretRequest,
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> CodeWorkPackageDraft:
    """Compile a request, resolve live Stage resources, and preview safe code."""
    settings = get_settings()
    inventory = load_stage_inventory(payload.project_id)
    try:
        plan = compile_code_work_package(payload.message, inventory, settings)
    except WorkPackageLLMUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_NOT_CONFIGURED", "message": str(error)},
        ) from error
    except WorkPackageLLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "LLM_REQUEST_FAILED", "message": str(error)},
        ) from error
    return resolve_code_work_package(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=plan,
        inventory=inventory,
        settings=settings,
    )


@router.post(
    "/ai/code/dispatch",
    response_model=CodeWorkPackageDispatchResponse,
    status_code=201,
)
async def dispatch_code_work_package(
    payload: CodeWorkPackageDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> CodeWorkPackageDispatchResponse:
    """Persist every request; executable programs are queued and others are blocked."""
    settings = get_settings()
    inventory = load_stage_inventory(payload.project_id)
    draft = resolve_code_work_package(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=payload.plan,
        inventory=inventory,
        settings=settings,
    )
    work_package_id = f"WP-CODE-{uuid4().hex[:10].upper()}"
    bindings = {
        "equipment": draft.equipment.path if draft.equipment else "",
        "target": (
            draft.execution_target_path
            or (draft.target.path if draft.target else "")
        ),
    }
    instruction_status = "pending" if draft.executable else "blocked"
    instruction = ExecutionsService.create_instruction(
        db,
        project_id=payload.project_id,
        kind="generated_script",
        params={
            "work_package_id": work_package_id,
            "operation": draft.plan.operation,
            "summary": draft.plan.summary,
            "zone_id": draft.plan.zone_id or None,
            "source_text": payload.message,
            "generated_code": draft.generated_code,
            "program_version": 1,
            "resource_bindings": bindings,
            "equipment_name": draft.equipment.name if draft.equipment else None,
            "target_name": draft.target.name if draft.target else draft.plan.summary,
            "missing_resources": draft.missing_resources,
            "checks": [check.model_dump() for check in draft.checks],
            "compiler_model": draft.model,
        },
        note=f"AI code Work Package · {payload.message}"[:500],
        user=user,
        initial_status=instruction_status,
    )
    await manager.broadcast(
        payload.project_id,
        {
            "type": "isaac.map.updated",
            "reason": (
                "work_package.code.queued"
                if draft.executable
                else "work_package.code.blocked"
            ),
            "instruction_id": instruction.id,
            "work_package_id": work_package_id,
        },
    )
    record = CodeWorkPackageRecord(
        id=work_package_id,
        project_id=payload.project_id,
        operation=draft.plan.operation,
        summary=draft.plan.summary,
        zone_id=draft.plan.zone_id,
        status=instruction_status,
        source_text=payload.message,
        equipment=draft.equipment,
        target=draft.target,
        execution_target_path=draft.execution_target_path,
        checks=draft.checks,
        missing_resources=draft.missing_resources,
        generated_code=draft.generated_code,
    )
    return CodeWorkPackageDispatchResponse(
        work_package=record,
        instruction=InstructionResponse.model_validate(instruction, from_attributes=True),
    )


@router.post("/ai/excavation/interpret", response_model=ExcavationDraft)
def interpret_excavation_work_package(
    payload: ExcavationInterpretRequest,
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> ExcavationDraft:
    """Compile natural language and bind it to exact live Isaac Stage Prim paths."""
    settings = get_settings()
    inventory = load_stage_inventory(payload.project_id)
    compiler_message = payload.message
    if payload.equipment_prim_path or payload.target_prim_path:
        compiler_message += (
            "\n선택된 실제 장비 Prim: "
            f"{payload.equipment_prim_path or '없음'}"
            "\n선택된 실제 굴착 대상 Prim: "
            f"{payload.target_prim_path or '없음'}"
        )
    try:
        plan = compile_excavation_language(compiler_message, inventory, settings)
    except WorkPackageLLMUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_NOT_CONFIGURED", "message": str(error)},
        ) from error
    except WorkPackageLLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "LLM_REQUEST_FAILED", "message": str(error)},
        ) from error
    return resolve_excavation_plan(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=plan,
        inventory=inventory,
        settings=settings,
        equipment_prim_path=payload.equipment_prim_path,
        target_prim_path=payload.target_prim_path,
    )


@router.post(
    "/ai/excavation/dispatch",
    response_model=ExcavationDispatchResponse,
    status_code=201,
)
async def dispatch_excavation_work_package(
    payload: ExcavationDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> ExcavationDispatchResponse:
    """Queue a validated real-Prim excavation instruction for Isaac Sim."""
    settings = get_settings()
    inventory = load_stage_inventory(payload.project_id)
    draft = resolve_excavation_plan(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=payload.plan,
        inventory=inventory,
        settings=settings,
        equipment_prim_path=payload.equipment_prim_path,
        target_prim_path=payload.target_prim_path,
    )
    if not draft.equipment or not draft.target or any(not check.ok for check in draft.checks):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WORK_PACKAGE_NOT_EXECUTABLE",
                "message": payload.plan.clarification_question
                or "연결된 현장 시스템의 장비와 작업 대상 검증이 필요합니다.",
                "checks": [check.model_dump() for check in draft.checks],
            },
        )

    work_package_id = f"WP-EXC-{uuid4().hex[:10].upper()}"
    instruction = ExecutionsService.create_instruction(
        db,
        project_id=payload.project_id,
        kind="excavate_prim",
        params={
            "equipment_prim_path": draft.equipment.path,
            "target_prim_path": draft.target.path,
            "equipment_name": draft.equipment.name,
            "target_name": draft.target.name,
            "label": payload.plan.summary,
            "work_package_id": work_package_id,
            "zone_id": payload.plan.zone_id or None,
            "approach_distance_m": 3.0,
            "animation_seconds": 3.0,
            "source_text": payload.message,
        },
        note=f"AI excavation Work Package · {payload.message}"[:500],
        user=user,
    )
    await manager.broadcast(
        payload.project_id,
        {
            "type": "isaac.map.updated",
            "reason": "work_package.excavation.created",
            "instruction_id": instruction.id,
            "work_package_id": work_package_id,
        },
    )
    record = ExcavationWorkPackageRecord(
        id=work_package_id,
        project_id=payload.project_id,
        equipment=draft.equipment,
        target=draft.target,
        zone_id=payload.plan.zone_id,
        status="pending",
        source_text=payload.message,
    )
    return ExcavationDispatchResponse(
        work_package=record,
        instruction=InstructionResponse.model_validate(instruction, from_attributes=True),
    )


@router.post("/ai/interpret", response_model=AIWorkPackageDraft)
def interpret_work_package(
    payload: AIWorkPackageInterpretRequest,
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> AIWorkPackageDraft:
    """자연어를 구조화하고 현장 Zone 안의 실행 좌표를 미리 검증합니다."""
    settings = get_settings()
    try:
        plan = compile_natural_language(payload.message, settings)
    except WorkPackageLLMUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_NOT_CONFIGURED", "message": str(error)},
        ) from error
    except WorkPackageLLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "LLM_REQUEST_FAILED", "message": str(error)},
        ) from error
    return resolve_plan(
        project_id=payload.project_id,
        source_text=payload.message,
        plan=plan,
        settings=settings,
    )


@router.post("/ai/dispatch", response_model=AIWorkPackageDispatchResponse, status_code=201)
async def dispatch_work_package(
    payload: AIWorkPackageDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> AIWorkPackageDispatchResponse:
    """검토한 초안을 기존 Isaac 지시 대기열에 넣습니다."""
    settings = get_settings()
    draft = resolve_plan(
        project_id=payload.project_id,
        source_text=payload.source_text,
        plan=payload.plan,
        settings=settings,
    )
    if not payload.plan.ready or draft.position is None or any(
        not check.ok for check in draft.checks
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WORK_PACKAGE_NOT_EXECUTABLE",
                "message": payload.plan.clarification_question
                or "Work Package 검증 조건을 충족하지 못했습니다.",
            },
        )

    work_package_id = f"WP-AI-{payload.plan.zone_id}-{uuid4().hex[:8].upper()}"
    size = payload.plan.size.model_dump()
    instruction = ExecutionsService.create_instruction(
        db,
        project_id=payload.project_id,
        kind="place_cube",
        params={
            "position": draft.position.model_dump(),
            "size": size,
            "label": draft.plan.label,
            "color": draft.plan.color,
            "work_package_id": work_package_id,
            "zone_id": draft.plan.zone_id,
            "zone_location": draft.plan.location,
        },
        note=f"AI Work Package · {payload.source_text}"[:500],
        user=user,
    )
    await manager.broadcast(
        payload.project_id,
        {
            "type": "isaac.map.updated",
            "reason": "work_package.created",
            "instruction_id": instruction.id,
            "work_package_id": work_package_id,
        },
    )
    record = AIWorkPackageRecord(
        id=work_package_id,
        project_id=payload.project_id,
        zone_id=payload.plan.zone_id,
        zone_location=draft.plan.location,
        operation=payload.plan.operation,
        label=payload.plan.label,
        color=payload.plan.color,
        size=payload.plan.size,
        position=draft.position,
        target_volume_m3=draft.target_volume_m3 or 0.0,
        status="pending",
        source_text=payload.source_text,
    )
    return AIWorkPackageDispatchResponse(
        work_package=record,
        instruction=InstructionResponse.model_validate(instruction, from_attributes=True),
    )
