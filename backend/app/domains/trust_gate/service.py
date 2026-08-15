"""6단계 Trust & Human Gate — Isaac 실행 결과의 승인 판정.

시스템은 "승인 가능"까지만 계산하고 최종 결정은 사람이 합니다. 맵에 반영되는
유일한 경로가 이 Gate이므로, 승인되지 않은 Commit은 어떤 화면에도 실제
작업 결과로 나타나지 않습니다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models.audit_log import AuditLog
from ...models.isaac import (
    INSTRUCTION_APPROVED,
    INSTRUCTION_REJECTED,
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    ExecutionCommit,
    KIND_EXCAVATE_PRIM,
    WorkInstruction,
)
from ...models.user import User
from ...schemas.isaac import MAX_EXCAVATION_TARGET_SPAN_M

# 뷰어 기본값. 지시에 색·라벨이 없으면 이 값으로 그립니다.
DEFAULT_CUBE_COLOR = "#f0b429"
DEFAULT_CUBE_SIZE = {"x": 4.0, "y": 4.0, "z": 4.0}


class TrustGateService:
    """6단계 Trust & Human Gate 서비스 경계."""

    @staticmethod
    def get_commit(db: Session, commit_id: str) -> ExecutionCommit:
        commit = db.get(ExecutionCommit, commit_id)
        if not commit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Execution commit not found"
            )
        return commit

    @staticmethod
    def review(
        db: Session,
        *,
        commit: ExecutionCommit,
        decision: str,
        note: str | None,
        user: User,
    ) -> ExecutionCommit:
        """관리자 판정을 기록합니다. 승인해야 맵 오브젝트가 됩니다."""
        if commit.review_status != REVIEW_PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Commit has already been reviewed",
                    "review_status": commit.review_status,
                    "reviewed_by": commit.reviewed_by,
                },
            )
        if decision == REVIEW_APPROVED and commit.status != "succeeded":
            raise HTTPException(
                status_code=422,
                detail="Failed execution cannot be approved. Re-run the instruction instead.",
            )
        if decision == REVIEW_APPROVED and commit.instruction.kind == KIND_EXCAVATE_PRIM:
            result = commit.result or {}
            if (
                result.get("simulator") != "isaac-sim"
                or result.get("source") != "stage-readback"
                or result.get("target_active_after") is not False
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Excavation approval requires real Isaac Stage read-back and a "
                        "verified inactive target Prim."
                    ),
                )
            target_size = result.get("target_bounds_size") or {}
            target_span = max(
                float(target_size.get("x", 0.0)),
                float(target_size.get("y", 0.0)),
            )
            if target_span > MAX_EXCAVATION_TARGET_SPAN_M:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Excavation target span is {target_span:.1f}m. "
                        f"Targets larger than {MAX_EXCAVATION_TARGET_SPAN_M:.0f}m "
                        "cannot be approved because they may represent the full site mesh."
                    ),
                )

        commit.review_status = REVIEW_APPROVED if decision == REVIEW_APPROVED else REVIEW_REJECTED
        commit.reviewed_by = user.username
        commit.reviewed_at = datetime.now(timezone.utc)
        commit.review_note = note
        commit.instruction.status = (
            INSTRUCTION_APPROVED if decision == REVIEW_APPROVED else INSTRUCTION_REJECTED
        )
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action=(
                    "ISAAC_RESULT_APPROVED"
                    if decision == REVIEW_APPROVED
                    else "ISAAC_RESULT_REJECTED"
                ),
                target_type="execution_commit",
                target_id=commit.id,
                details={
                    "instruction_id": commit.instruction_id,
                    "attempt": commit.attempt,
                    "note": note,
                },
            )
        )
        db.commit()
        db.refresh(commit)
        return commit

    @staticmethod
    def approved_map_objects(db: Session, *, project_id: str) -> list[dict]:
        """맵에 그릴 오브젝트 목록.

        별도 테이블이 아니라 승인된 Commit에서 그때그때 만들어냅니다. 승인을
        되돌리면 맵에서도 즉시 사라지므로 두 저장소가 어긋날 수 없습니다.
        """
        query = (
            select(ExecutionCommit, WorkInstruction)
            .join(WorkInstruction, ExecutionCommit.instruction_id == WorkInstruction.id)
            .where(
                WorkInstruction.project_id == project_id,
                ExecutionCommit.review_status == REVIEW_APPROVED,
            )
            .order_by(ExecutionCommit.reviewed_at)
        )
        objects: list[dict] = []
        for commit, instruction in db.execute(query).all():
            params = instruction.params or {}
            result = commit.result or {}
            if instruction.kind == KIND_EXCAVATE_PRIM:
                position = result.get("target_position")
                size = result.get("target_bounds_size")
                if not position or not size:
                    continue
                objects.append(
                    {
                        "id": commit.id,
                        "instruction_id": instruction.id,
                        "type": "removed_prim",
                        "label": params.get("target_name") or params.get("label") or "굴착 대상",
                        "color": "#d95757",
                        "position": position,
                        "size": size,
                        "approved_by": commit.reviewed_by,
                        "approved_at": commit.reviewed_at,
                        "prim_path": result.get("target_prim_path") or params.get("target_prim_path"),
                    }
                )
                continue
            # 실제로 배치된 값이 있으면 그것을 쓰고, 없으면 지시값으로 그립니다.
            position = result.get("placed_position") or params.get("position")
            if not position:
                continue
            size = result.get("placed_size") or params.get("size") or DEFAULT_CUBE_SIZE
            objects.append(
                {
                    "id": commit.id,
                    "instruction_id": instruction.id,
                    "type": "cube",
                    "label": params.get("label") or instruction.kind,
                    "color": params.get("color") or DEFAULT_CUBE_COLOR,
                    "position": position,
                    "size": size,
                    "approved_by": commit.reviewed_by,
                    "approved_at": commit.reviewed_at,
                    "prim_path": result.get("prim_path"),
                }
            )
        return objects
