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
    def find_remediation_for_commit(
        db: Session,
        *,
        project_id: str,
        parent_commit_id: str,
    ) -> WorkInstruction | None:
        """Return an existing corrective instruction for an undercut commit."""

        instructions = list(
            db.execute(
                select(WorkInstruction).where(
                    WorkInstruction.project_id == project_id
                )
            ).scalars()
        )
        return next(
            (
                item
                for item in instructions
                if str(
                    (item.params or {}).get("remediation_parent_commit_id") or ""
                )
                == parent_commit_id
            ),
            None,
        )

    @staticmethod
    def dispatch_remediation(
        db: Session,
        *,
        instruction: WorkInstruction,
        user: User,
    ) -> WorkInstruction:
        """Manager approval that releases one corrective task to Isaac."""

        params = dict(instruction.params or {})
        if instruction.status != "blocked" or not params.get("remediation_mode"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a blocked remediation draft can be dispatched",
            )
        if params.get("remediation_plan_status") != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Remediation plan has already been dispatched",
            )
        params["remediation_plan_status"] = "approved"
        params["remediation_approved_by"] = user.username
        params["remediation_approved_at"] = datetime.now(timezone.utc).isoformat()
        instruction.params = params
        instruction.status = INSTRUCTION_PENDING
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_REMEDIATION_DISPATCHED",
                target_type="work_instruction",
                target_id=instruction.id,
                details={
                    "parent_commit_id": params.get("remediation_parent_commit_id"),
                    "equipment": (params.get("resource_bindings") or {}).get(
                        "equipment"
                    ),
                    "remaining_volume_m3": (
                        params.get("planned_quantity") or {}
                    ).get("value"),
                },
            )
        )
        db.commit()
        db.refresh(instruction)
        return instruction

    @staticmethod
    def claim_pending(
        db: Session,
        *,
        project_id: str,
        limit: int = 10,
        prefer_execution_group: bool = False,
    ) -> list[WorkInstruction]:
        """Adapter가 가져갈 대기 지시를 넘기고 dispatched로 표시합니다.

        폴링 주기가 실행 시간보다 짧아도 같은 지시를 두 번 집어가지 않도록
        건네주는 시점에 상태를 바꿉니다.
        """
        # Drawing-approved work fronts share one execution_group_id.  The live
        # Adapter asks for the complete group so no excavator is stranded in a
        # later simulation cycle.  Legacy callers retain the original limit.
        candidate_limit = max(limit, 50) if prefer_execution_group else limit
        query = (
            select(WorkInstruction)
            .where(
                WorkInstruction.project_id == project_id,
                WorkInstruction.status == INSTRUCTION_PENDING,
            )
            .order_by(WorkInstruction.created_at)
            .limit(candidate_limit)
        )
        candidates = list(db.execute(query).scalars())
        claimed: list[WorkInstruction] = []
        if candidates:
            grouped_candidate = next(
                (
                    instruction
                    for instruction in candidates
                    if str(
                        (instruction.params or {}).get("execution_group_id") or ""
                    )
                ),
                None,
            ) if prefer_execution_group else None
            first = grouped_candidate or candidates[0]
            first_group_id = str((first.params or {}).get("execution_group_id") or "")
            if first_group_id:
                claimed = [
                    instruction
                    for instruction in candidates
                    if str((instruction.params or {}).get("execution_group_id") or "")
                    == first_group_id
                ]
                expected_size = int(
                    (first.params or {}).get("execution_group_size")
                    or len(claimed)
                )
                if len(claimed) != expected_size:
                    # Keep the incomplete group pending. Dispatch writes all
                    # members in one request, so this mainly protects against
                    # partial legacy/test data.
                    return []
            else:
                claimed = candidates[:1] if prefer_execution_group else candidates[:limit]
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
    def record_progress(
        db: Session,
        *,
        instruction: WorkInstruction,
        progress: dict,
    ) -> WorkInstruction:
        """Persist one live Isaac step without creating an Evidence Commit."""

        if instruction.status != INSTRUCTION_DISPATCHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only a dispatched instruction can report live progress",
            )
        params = dict(instruction.params or {})
        params["execution_progress"] = {
            **progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        instruction.params = params
        db.commit()
        db.refresh(instruction)
        return instruction

    @staticmethod
    def release_ready_successor_groups(
        db: Session,
        *,
        completed_instruction: WorkInstruction,
        user: User,
    ) -> list[WorkInstruction]:
        """Mark blocked scenario groups ready for the next manager approval.

        Drawing phases are registered together at initial dispatch.  This
        method keeps the transition deterministic and idempotent: a successor
        becomes *plan-approval ready* only when every instruction in its exact
        predecessor execution group has reached the manager-approved state.

        Readiness deliberately does not change the instruction status to
        ``pending``.  The next construction phase is a separate manager gate:
        Phase 1 evidence approval opens the Phase 2 plan screen inside Zone A,
        and only a second explicit plan approval allows Isaac to claim Phase 2.
        """

        params = completed_instruction.params or {}
        plan_id = str(params.get("scenario_plan_id") or "")
        phase_id = str(params.get("scenario_phase_id") or "")
        if not plan_id or not phase_id:
            return []
        project_instructions = list(
            db.execute(
                select(WorkInstruction).where(
                    WorkInstruction.project_id == completed_instruction.project_id
                )
            ).scalars()
        )
        scenario_instructions = [
            item
            for item in project_instructions
            if str((item.params or {}).get("scenario_plan_id") or "") == plan_id
        ]

        def predecessor_group_is_approved(successor: WorkInstruction) -> bool:
            """Check only the predecessor from the same dispatch/run.

            A plan can be demonstrated repeatedly.  Looking at every historic
            ``excavation`` instruction for that plan would make a rejected or
            unfinished old run block a new run forever.  Dispatch therefore
            stores the exact predecessor execution-group id on its successor.
            """

            successor_params = successor.params or {}
            predecessor_group_id = str(
                successor_params.get("predecessor_execution_group_id") or ""
            )
            if not predecessor_group_id:
                return False
            members = [
                item
                for item in scenario_instructions
                if str((item.params or {}).get("execution_group_id") or "")
                == predecessor_group_id
            ]
            expected_size = int(
                successor_params.get("execution_group_size") or len(members)
            )
            return len(members) == expected_size and all(
                item.status == INSTRUCTION_APPROVED for item in members
            )

        released: list[WorkInstruction] = []
        for instruction in scenario_instructions:
            if instruction.status != "blocked":
                continue
            successor_params = dict(instruction.params or {})
            dependencies = {
                str(value)
                for value in successor_params.get("depends_on_phase_ids") or []
            }
            if phase_id not in dependencies:
                continue
            if not predecessor_group_is_approved(instruction):
                continue
            checks = []
            for check in successor_params.get("checks") or []:
                if check.get("code") == "predecessor":
                    checks.append(
                        {
                            **check,
                            "ok": True,
                            "message": (
                                "Predecessor phase approved; waiting for manager "
                                "approval of the next phase plan"
                            ),
                        }
                    )
                else:
                    checks.append(check)
            successor_params["checks"] = checks
            successor_params["phase_approval_ready"] = True
            successor_params["phase_plan_status"] = "approval_ready"
            successor_params["ready_by_phase_id"] = phase_id
            successor_params["ready_at"] = datetime.now(timezone.utc).isoformat()
            instruction.params = successor_params
            released.append(instruction)

        if released:
            db.add_all(released)
            for instruction in released:
                db.add(
                    AuditLog(
                        user_id=user.id,
                        username=user.username,
                        action="ISAAC_SUCCESSOR_PHASE_APPROVAL_READY",
                        target_type="work_instruction",
                        target_id=instruction.id,
                        details={
                            "project_id": instruction.project_id,
                            "scenario_plan_id": plan_id,
                            "scenario_phase_id": (
                                instruction.params or {}
                            ).get("scenario_phase_id"),
                            "ready_by_phase_id": phase_id,
                        },
                    )
                )
            db.commit()
            for instruction in released:
                db.refresh(instruction)
        return released

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
