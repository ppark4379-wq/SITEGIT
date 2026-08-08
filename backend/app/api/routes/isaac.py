"""Isaac Sim 폐루프 API.

웹 지시 → Isaac 실행 → Commit → 관리자 승인 → 맵 반영.

지시 생성과 승인은 웹(관리자)이, claim과 commit은 Isaac Adapter가 씁니다.
Adapter도 일반 사용자로 로그인하므로 별도 인증 경로를 만들지 않습니다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...domains.executions.service import ExecutionsService
from ...domains.trust_gate.service import TrustGateService
from ...models.user import User
from ...realtime.manager import manager
from ...schemas.isaac import (
    CommitCreate,
    CommitResponse,
    InstructionCreate,
    InstructionResponse,
    MapObjectsResponse,
    ReviewDecision,
)
from ..deps import get_current_user, get_db, require_roles

router = APIRouter(prefix="/isaac", tags=["isaac"])

# 지시 발행과 결과 승인은 관리 권한이 필요합니다. viewer는 조회만 합니다.
OPERATOR_ROLES = ("admin", "manager", "reviewer")


def _default_project_id() -> str:
    return get_settings().default_project_id


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
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> list[InstructionResponse]:
    """Adapter 전용. 대기 중인 지시를 가져가면서 dispatched로 표시합니다."""
    claimed = ExecutionsService.claim_pending(
        db, project_id=project_id or _default_project_id(), limit=limit
    )
    return [InstructionResponse.model_validate(i, from_attributes=True) for i in claimed]


@router.post("/instructions/{instruction_id}/commit", response_model=CommitResponse, status_code=201)
async def commit_execution(
    instruction_id: str,
    payload: CommitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OPERATOR_ROLES)),
) -> CommitResponse:
    """Adapter 전용. Isaac 실행 결과를 올리고 관리자 검토 대기로 넘깁니다."""
    instruction = ExecutionsService.get_instruction(db, instruction_id)
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
    await _broadcast_map_changed(
        reviewed.instruction.project_id,
        f"review.{payload.decision}",
        instruction_id=reviewed.instruction_id,
        commit_id=reviewed.id,
    )
    return CommitResponse.model_validate(reviewed, from_attributes=True)


@router.get("/map-objects", response_model=MapObjectsResponse)
def list_map_objects(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> MapObjectsResponse:
    """뷰어가 지형 mesh 위에 그릴 승인된 작업 결과."""
    resolved_project_id = project_id or _default_project_id()
    objects = TrustGateService.approved_map_objects(db, project_id=resolved_project_id)
    # 뷰어가 폴링할 때 내용 변화만 싸게 감지할 수 있도록 요약 값을 함께 줍니다.
    latest = max((o["approved_at"] for o in objects if o["approved_at"]), default=None)
    revision = f"{len(objects)}:{latest.isoformat() if latest else '-'}"
    return MapObjectsResponse(
        project_id=resolved_project_id,
        objects=objects,
        revision=revision,
    )
