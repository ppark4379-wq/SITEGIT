"""4단계 Autonomous Equipment — Isaac Sim 작업 지시와 실행 Commit.

웹이 내린 지시를 Isaac Adapter가 가져가고, 실행 결과를 Commit으로 되돌리는
구간을 담당합니다. 승인 판정은 6단계 trust_gate가 맡습니다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ...models.audit_log import AuditLog
from ...models.isaac import (
    INSTRUCTION_APPROVED,
    INSTRUCTION_COMMITTED,
    INSTRUCTION_DISPATCHED,
    INSTRUCTION_PENDING,
    REVIEW_PENDING,
    ExecutionCommit,
    WorkInstruction,
)
from ...models.user import User


class ExecutionsService:
    """4단계 Autonomous Equipment 서비스 경계."""

    @staticmethod
    def list_instructions(
        db: Session,
        *,
        project_id: str,
        statuses: tuple[str, ...] | None = None,
        limit: int = 100,
    ) -> list[WorkInstruction]:
        query = (
            select(WorkInstruction)
            .options(selectinload(WorkInstruction.commits))
            .where(WorkInstruction.project_id == project_id)
            .order_by(WorkInstruction.created_at.desc())
            .limit(limit)
        )
        if statuses:
            query = query.where(WorkInstruction.status.in_(statuses))
        return list(db.execute(query).scalars())

    @staticmethod
    def get_instruction(db: Session, instruction_id: str) -> WorkInstruction:
        instruction = db.get(WorkInstruction, instruction_id)
        if not instruction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Work instruction not found"
            )
        return instruction

    @staticmethod
    def create_instruction(
        db: Session,
        *,
        project_id: str,
        kind: str,
        params: dict,
        note: str | None,
        user: User,
        initial_status: str = INSTRUCTION_PENDING,
    ) -> WorkInstruction:
        instruction = WorkInstruction(
            project_id=project_id,
            kind=kind,
            params=params,
            note=note,
            status=initial_status,
            created_by=user.id,
            created_by_username=user.username,
        )
        db.add(instruction)
        # id는 컬럼 default라 flush 전에는 None입니다. 감사 로그가 참조하므로 먼저 채웁니다.
        db.flush()
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_INSTRUCTION_CREATED",
                target_type="work_instruction",
                target_id=instruction.id,
                details={"project_id": project_id, "kind": kind, "params": params},
            )
        )
        db.commit()
        db.refresh(instruction)
        return instruction

    @staticmethod
    def claim_pending(
        db: Session, *, project_id: str, limit: int = 10
    ) -> list[WorkInstruction]:
        """Adapter가 가져갈 대기 지시를 넘기고 dispatched로 표시합니다.

        폴링 주기가 실행 시간보다 짧아도 같은 지시를 두 번 집어가지 않도록
        건네주는 시점에 상태를 바꿉니다.
        """
        query = (
            select(WorkInstruction)
            .where(
                WorkInstruction.project_id == project_id,
                WorkInstruction.status == INSTRUCTION_PENDING,
            )
            .order_by(WorkInstruction.created_at)
            .limit(limit)
        )
        claimed = list(db.execute(query).scalars())
        now = datetime.now(timezone.utc)
        for instruction in claimed:
            instruction.status = INSTRUCTION_DISPATCHED
            instruction.dispatched_at = now
        if claimed:
            db.commit()
            for instruction in claimed:
                db.refresh(instruction)
        return claimed

    @staticmethod
    def record_commit(
        db: Session,
        *,
        instruction: WorkInstruction,
        commit_status: str,
        result: dict,
        evidence: dict,
        adapter: str,
        user: User,
    ) -> ExecutionCommit:
        """Isaac 실행 결과를 기록하고 관리자 검토 대기로 넘깁니다."""
        if instruction.status == INSTRUCTION_APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approved instruction cannot accept a new commit",
            )
        commit = ExecutionCommit(
            instruction_id=instruction.id,
            attempt=len(instruction.commits) + 1,
            status=commit_status,
            result=result,
            evidence=evidence,
            adapter=adapter,
            committed_by=user.username,
            review_status=REVIEW_PENDING,
        )
        db.add(commit)
        instruction.status = INSTRUCTION_COMMITTED
        evidence_quality = evidence.get("quality") or {}
        performed_quantity = result.get("performed_quantity")
        geometry_change = result.get("geometry_change") or {}
        # 감사 로그가 commit.id를 참조하므로 컬럼 default를 먼저 확정합니다.
        db.flush()
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_EXECUTION_COMMITTED",
                target_type="execution_commit",
                target_id=commit.id,
                details={
                    "instruction_id": instruction.id,
                    "status": commit_status,
                    "attempt": commit.attempt,
                    "adapter": adapter,
                    "execution_id": result.get("execution_id"),
                    "duration_seconds": result.get("duration_seconds"),
                    "performed_quantity": performed_quantity,
                    "removed_volume_m3": geometry_change.get("removed_volume_m3"),
                    "added_volume_m3": geometry_change.get("added_volume_m3"),
                    "evidence_completeness_ratio": evidence_quality.get(
                        "completeness_ratio"
                    ),
                    "missing_sensor_types": evidence_quality.get(
                        "missing_sensor_types", []
                    ),
                },
            )
        )
        db.commit()
        db.refresh(commit)
        return commit
