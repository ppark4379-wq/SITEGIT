"""자연어 Work Package 생성과 Isaac 실행 대기열 연결 API."""

from __future__ import annotations

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
    compile_excavation_language,
    resolve_excavation_plan,
    resolve_plan,
)
from ...models.user import User
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
)
from ..deps import get_db, require_roles


router = APIRouter(prefix="/work-packages", tags=["work-packages"])
OPERATOR_ROLES = ("admin", "manager", "reviewer")


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
                or "실행 중인 Isaac Stage의 장비와 대상 Prim 검증이 필요합니다.",
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
