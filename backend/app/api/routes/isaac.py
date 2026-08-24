"""Isaac Sim 폐루프 API.

웹 지시 → Isaac 실행 → Commit → 관리자 승인 → 맵 반영.

지시 생성과 승인은 웹(관리자)이, claim과 commit은 Isaac Adapter가 씁니다.
Adapter도 일반 사용자로 로그인하므로 별도 인증 경로를 만들지 않습니다.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...domains.executions.service import ExecutionsService
from ...domains.executions.stage_inventory import (
    find_inventory_prim,
    load_published_baseline,
    published_baseline_exists,
    load_stage_inventory,
    save_stage_inventory,
)
from ...domains.executions.stage_versions import load_branch_head
from ...domains.trust_gate.service import TrustGateService
from ...domains.work_packages.ai_compiler import (
    WorkPackageLLMError,
    WorkPackageLLMUnavailable,
    compile_remediation_narrative,
)
from ...models.user import User
from ...realtime.manager import manager
from ...schemas.isaac import (
    CommitCreate,
    CommitResponse,
    InstructionCreate,
    InstructionProgressUpdate,
    InstructionResponse,
    MapObjectsResponse,
    ReviewDecision,
    StageInventoryResponse,
    StageInventoryUpdate,
    StageBranchHeadResponse,
)
from ..deps import get_current_user, get_db, require_roles

router = APIRouter(prefix="/isaac", tags=["isaac"])

# 지시 발행과 결과 승인은 관리 권한이 필요합니다. viewer는 조회만 합니다.
OPERATOR_ROLES = ("admin", "manager", "reviewer")


def _default_project_id() -> str:
    return get_settings().default_project_id


@router.get("/stage-inventory", response_model=StageInventoryResponse)
def get_stage_inventory(
    project_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
) -> StageInventoryResponse:
    """Return live equipment, diggable targets, and scene objects reported by Isaac Sim."""
    return load_stage_inventory(project_id or _default_project_id())


@router.get("/branches/{branch}/head", response_model=StageBranchHeadResponse)
def get_stage_branch_head(
    branch: str,
    project_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
) -> StageBranchHeadResponse:
    """Return the latest manager-approved Stage snapshot for one branch."""

    head = load_branch_head(project_id or _default_project_id(), branch)
    if head is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage branch HEAD does not exist yet",
        )
    return StageBranchHeadResponse.model_validate(head)


@router.post("/stage-inventory", response_model=StageInventoryResponse)
async def update_stage_inventory(
    payload: StageInventoryUpdate,
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> StageInventoryResponse:
    """Adapter heartbeat. Browser clients cannot invent executable Prim paths."""
    inventory = save_stage_inventory(payload)
    await _broadcast_map_changed(
        payload.project_id,
        "stage.inventory",
        equipment_count=len(payload.equipment),
        target_count=len(payload.diggable_targets),
        scene_object_count=len(payload.scene_objects),
    )
    return inventory


async def _broadcast_map_changed(project_id: str, reason: str, **extra: object) -> None:
    """기존 프로젝트 WebSocket으로 맵 변경을 알립니다.

    별도 소켓을 열지 않고 /state/ws/{project_id}를 재사용하므로 프론트엔드는
    이미 열려 있는 연결에서 그대로 받습니다.
    """
    await manager.broadcast(
        project_id, {"type": "isaac.map.updated", "reason": reason, **extra}
    )


@router.get("/instructions", response_model=list[InstructionResponse])
def list_instructions(
    project_id: str | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[InstructionResponse]:
    instructions = ExecutionsService.list_instructions(
        db,
        project_id=project_id or _default_project_id(),
        statuses=tuple(status) if status else None,
        limit=limit,
    )
    return [InstructionResponse.model_validate(i, from_attributes=True) for i in instructions]


@router.post("/instructions", response_model=InstructionResponse, status_code=201)
async def create_instruction(
    payload: InstructionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> InstructionResponse:
    if payload.kind == "excavate_prim":
        params = payload.params.model_dump()
        inventory, equipment = find_inventory_prim(
            payload.project_id, params["equipment_prim_path"], "equipment"
        )
        _, target = find_inventory_prim(
            payload.project_id, params["target_prim_path"], "diggable"
        )
        if not inventory.connected or equipment is None or target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Excavation paths must match the current live Isaac Stage inventory.",
            )
    instruction = ExecutionsService.create_instruction(
        db,
        project_id=payload.project_id,
        kind=payload.kind,
        params=payload.params.model_dump(),
        note=payload.note,
        user=user,
    )
    await _broadcast_map_changed(
        instruction.project_id, "instruction.created", instruction_id=instruction.id
    )
    return InstructionResponse.model_validate(instruction, from_attributes=True)


@router.post("/instructions/claim", response_model=list[InstructionResponse])
def claim_instructions(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    prefer_execution_group: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> list[InstructionResponse]:
    """Adapter 전용. 대기 중인 지시를 가져가면서 dispatched로 표시합니다."""
    claimed = ExecutionsService.claim_pending(
        db,
        project_id=project_id or _default_project_id(),
        limit=limit,
        prefer_execution_group=prefer_execution_group,
    )
    return [InstructionResponse.model_validate(i, from_attributes=True) for i in claimed]


@router.post(
    "/instructions/{instruction_id}/progress",
    response_model=InstructionResponse,
)
async def update_instruction_progress(
    instruction_id: str,
    payload: InstructionProgressUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> InstructionResponse:
    """Receive a non-commit progress heartbeat from the live Isaac task."""

    instruction = ExecutionsService.get_instruction(db, instruction_id)
    updated = ExecutionsService.record_progress(
        db,
        instruction=instruction,
        progress=payload.model_dump(),
    )
    await _broadcast_map_changed(
        instruction.project_id,
        "instruction.progress",
        instruction_id=instruction.id,
        progress_ratio=payload.progress_ratio,
    )
    return InstructionResponse.model_validate(updated, from_attributes=True)


@router.post("/instructions/{instruction_id}/commit", response_model=CommitResponse, status_code=201)
async def commit_execution(
    instruction_id: str,
    payload: CommitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> CommitResponse:
    """Adapter 전용. Isaac 실행 결과를 올리고 관리자 검토 대기로 넘깁니다."""
    instruction = ExecutionsService.get_instruction(db, instruction_id)
    evidence_instruction_id = payload.evidence.get("instruction_id")
    if (
        payload.evidence.get("schema_version") is not None
        and evidence_instruction_id != instruction_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evidence Bundle instruction_id must match the commit URL.",
        )
    commit = ExecutionsService.record_commit(
        db,
        instruction=instruction,
        commit_status=payload.status,
        result=payload.result,
        evidence=payload.evidence,
        adapter=payload.adapter,
        user=user,
    )
    await _broadcast_map_changed(
        instruction.project_id,
        "commit.created",
        instruction_id=instruction.id,
        commit_id=commit.id,
    )
    return CommitResponse.model_validate(commit, from_attributes=True)


@router.post(
    "/commits/{commit_id}/remediation",
    response_model=InstructionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_remediation_instruction(
    commit_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> InstructionResponse:
    """Create an LLM-assisted, manager-gated corrective excavation draft."""

    commit = TrustGateService.get_commit(db, commit_id)
    quality = (commit.result or {}).get("quality_assessment") or {}
    if commit.review_status != "pending" or quality.get("status") != "needs_remediation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending under-excavation commit can create remediation",
        )
    existing = ExecutionsService.find_remediation_for_commit(
        db,
        project_id=commit.instruction.project_id,
        parent_commit_id=commit.id,
    )
    if existing is not None:
        return InstructionResponse.model_validate(existing, from_attributes=True)

    parent_params = dict(commit.instruction.params or {})
    equipment_path = str(
        (parent_params.get("resource_bindings") or {}).get("equipment")
        or (commit.result or {}).get("equipment_prim_path")
        or ""
    )
    target_paths = [
        str(path)
        for path in (
            parent_params.get("target_prim_paths")
            or (commit.result or {}).get("target_prim_paths")
            or []
        )
    ]
    if not equipment_path or not target_paths:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Corrective work requires the original equipment and target bindings",
        )

    planned_volume = float(quality.get("planned_volume_m3") or 0.0)
    completed_volume = float(quality.get("completed_volume_m3") or 0.0)
    remaining_volume = max(0.0, float(quality.get("remaining_volume_m3") or 0.0))
    measured_ratio = float(quality.get("measured_completion_ratio") or 0.0)
    required_ratio = float(quality.get("required_completion_ratio") or 0.98)
    equipment_id = str(
        parent_params.get("equipment_name")
        or equipment_path.rsplit("/", 1)[-1].replace("_", "-")
    )
    llm_assisted = True
    compiler_model = get_settings().ollama_model
    try:
        narrative = compile_remediation_narrative(
            settings=get_settings(),
            workfront_id=str(parent_params.get("workfront_id") or "Zone-A"),
            equipment_id=equipment_id,
            planned_volume_m3=planned_volume,
            completed_volume_m3=completed_volume,
            remaining_volume_m3=remaining_volume,
            measured_completion_ratio=measured_ratio,
            required_completion_ratio=required_ratio,
        ).model_dump()
    except (WorkPackageLLMUnavailable, WorkPackageLLMError):
        llm_assisted = False
        compiler_model = "deterministic-remediation-v1"
        narrative = {
            "title": f"{equipment_id} 굴착량 미달 보완 작업",
            "summary": (
                f"목표 {planned_volume:.1f}㎥ 중 {completed_volume:.1f}㎥ 완료, "
                f"잔여 {remaining_volume:.1f}㎥를 동일 작업전선에서 추가 굴착합니다."
            ),
            "action_steps": [
                "기존 작업전선과 잔여 토사 Prim을 재확인합니다.",
                f"{equipment_id} 한 대로 잔여 {remaining_volume:.1f}㎥를 굴착합니다.",
                "카메라·LiDAR·IMU 증거를 다시 수집하고 재커밋합니다.",
            ],
            "manager_note": "계측 수치는 규칙 엔진이 확정했으며 관리자 승인 후 실행됩니다.",
        }

    correction_group_id = f"EXG-REMEDIATION-{uuid4().hex[:10]}"
    work_package_id = f"WP-REMEDIATION-{uuid4().hex[:8].upper()}"
    remediation = ExecutionsService.create_instruction(
        db,
        project_id=commit.instruction.project_id,
        kind=commit.instruction.kind,
        params={
            **parent_params,
            "work_package_id": work_package_id,
            "execution_group_id": correction_group_id,
            "execution_group_size": 1,
            "execution_group_mode": "parallel_incremental_scoops",
            "remediation_mode": True,
            "remediation_plan_status": "draft",
            "remediation_parent_commit_id": commit.id,
            "remediation_parent_instruction_id": commit.instruction_id,
            "quality_scenario": None,
            "summary": narrative["title"],
            "planned_quantity": {
                "value": remaining_volume,
                "unit": "m3",
                "source": "Isaac Stage read-back remediation gap",
            },
            "remediation_facts": {
                "planned_volume_m3": planned_volume,
                "completed_volume_m3": completed_volume,
                "remaining_volume_m3": remaining_volume,
                "measured_completion_ratio": measured_ratio,
                "required_completion_ratio": required_ratio,
            },
            "remediation_narrative": narrative,
            "llm_assisted": llm_assisted,
            "compiler_model": compiler_model,
            "resource_bindings": {
                "equipment": equipment_path,
                "target": target_paths[0],
            },
            "target_prim_paths": target_paths,
            "checks": [
                {
                    "code": "measurement",
                    "ok": False,
                    "message": (
                        f"굴착 달성률 {measured_ratio * 100:.1f}% / "
                        f"기준 {required_ratio * 100:.1f}%"
                    ),
                },
                {
                    "code": "manager_gate",
                    "ok": False,
                    "message": "관리자 보완 계획 승인 대기",
                },
            ],
        },
        note=narrative["summary"],
        user=user,
        initial_status="blocked",
    )
    await _broadcast_map_changed(
        remediation.project_id,
        "remediation.draft.created",
        instruction_id=remediation.id,
        parent_commit_id=commit.id,
    )
    return InstructionResponse.model_validate(remediation, from_attributes=True)


@router.post(
    "/instructions/{instruction_id}/dispatch-remediation",
    response_model=InstructionResponse,
)
async def dispatch_remediation_instruction(
    instruction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> InstructionResponse:
    """Approve a corrective draft and release only its assigned excavator."""

    instruction = ExecutionsService.get_instruction(db, instruction_id)
    params = instruction.params or {}
    inventory = load_stage_inventory(instruction.project_id)
    equipment_path = str((params.get("resource_bindings") or {}).get("equipment") or "")
    target_paths = [str(path) for path in params.get("target_prim_paths") or []]
    active_equipment = {item.path for item in inventory.equipment if item.active}
    active_targets = {item.path for item in inventory.diggable_targets if item.active}
    missing = []
    if not inventory.connected:
        missing.append("Isaac Stage 연결 없음")
    if equipment_path not in active_equipment:
        missing.append(f"장비 Prim 없음: {equipment_path}")
    missing.extend(path for path in target_paths if path not in active_targets)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "보완 작업 실행 자원을 확인할 수 없습니다.",
                "missing_resources": missing,
            },
        )
    dispatched = ExecutionsService.dispatch_remediation(
        db, instruction=instruction, user=user
    )
    await _broadcast_map_changed(
        dispatched.project_id,
        "remediation.dispatched",
        instruction_id=dispatched.id,
    )
    return InstructionResponse.model_validate(dispatched, from_attributes=True)


@router.post("/commits/{commit_id}/review", response_model=CommitResponse)
async def review_commit(
    commit_id: str,
    payload: ReviewDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> CommitResponse:
    """관리자 판정. 승인하면 이 시점에 맵 오브젝트가 됩니다."""
    commit = TrustGateService.get_commit(db, commit_id)
    reviewed = TrustGateService.review(
        db, commit=commit, decision=payload.decision, note=payload.note, user=user
    )
    released = []
    if payload.decision == "approved":
        completed_instruction = reviewed.instruction
        if (reviewed.instruction.params or {}).get("remediation_mode"):
            parent_instruction = TrustGateService.approve_remediation_parent(
                db,
                remediation_commit=reviewed,
                user=user,
            )
            if parent_instruction is not None:
                completed_instruction = parent_instruction
        released = ExecutionsService.release_ready_successor_groups(
            db,
            completed_instruction=completed_instruction,
            user=user,
        )
    await _broadcast_map_changed(
        reviewed.instruction.project_id,
        f"review.{payload.decision}",
        instruction_id=reviewed.instruction_id,
        commit_id=reviewed.id,
    )
    if released:
        await _broadcast_map_changed(
            reviewed.instruction.project_id,
            "scenario.phase.approval_ready",
            instruction_id=released[0].id,
            ready_count=len(released),
            phase_id=(released[0].params or {}).get("scenario_phase_id"),
        )
    return CommitResponse.model_validate(reviewed, from_attributes=True)


@router.get("/commits/{commit_id}", response_model=CommitResponse)
def get_commit(
    commit_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CommitResponse:
    """Return one execution Commit so an Adapter can wait for its review."""

    commit = TrustGateService.get_commit(db, commit_id)
    return CommitResponse.model_validate(commit, from_attributes=True)


@router.get("/map-objects", response_model=MapObjectsResponse)
def list_map_objects(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> MapObjectsResponse:
    """뷰어가 지형 mesh 위에 그릴 승인된 작업 결과."""
    resolved_project_id = project_id or _default_project_id()
    baseline = load_published_baseline(resolved_project_id)
    reviewed_after = (
        baseline.captured_at
        if published_baseline_exists(resolved_project_id)
        else None
    )
    timeline = TrustGateService.approved_map_timeline(
        db,
        project_id=resolved_project_id,
        reviewed_after=reviewed_after,
    )
    objects = TrustGateService.replay_map_timeline(timeline)
    conflicts = TrustGateService.rejected_map_conflicts(
        db,
        project_id=resolved_project_id,
        reviewed_after=reviewed_after,
    )
    # 뷰어가 폴링할 때 내용 변화만 싸게 감지할 수 있도록 요약 값을 함께 줍니다.
    latest = max((step["approved_at"] for step in timeline if step["approved_at"]), default=None)
    revision = f"{len(timeline)}:{latest.isoformat() if latest else '-'}"
    return MapObjectsResponse(
        project_id=resolved_project_id,
        objects=objects,
        baseline_diggable_targets=baseline.diggable_targets,
        baseline_scene_objects=baseline.scene_objects,
        timeline=timeline,
        conflicts=conflicts,
        revision=revision,
    )
