"""6단계 Trust & Human Gate — Isaac 실행 결과의 승인 판정.

시스템은 "승인 가능"까지만 계산하고 최종 결정은 사람이 합니다. 맵에 반영되는
유일한 경로가 이 Gate이므로, 승인되지 않은 Commit은 어떤 화면에도 실제
작업 결과로 나타나지 않습니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models.audit_log import AuditLog
from ...models.isaac import (
    INSTRUCTION_APPROVED,
    INSTRUCTION_COMMITTED,
    INSTRUCTION_REJECTED,
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    ExecutionCommit,
    KIND_EXCAVATE_PRIM,
    KIND_GENERATED_SCRIPT,
    WorkInstruction,
)
from ...models.user import User
from ...schemas.isaac import MAX_EXCAVATION_TARGET_SPAN_M
from ..executions.stage_versions import promote_stage_snapshot

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
    def submit_supplemental_evidence(
        db: Session,
        *,
        commit: ExecutionCommit,
        files: list[dict],
        note: str | None,
        user: User,
    ) -> ExecutionCommit:
        """Record demo Evidence metadata and reopen a rejected Commit.

        The browser intentionally sends file metadata only.  Binary evidence
        storage can be added later without changing the review state machine.
        For the current judge demo, selecting any file is sufficient to make
        the Commit reviewable again.
        """

        if commit.review_status != REVIEW_REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Only a rejected Commit can receive supplemental Evidence",
                    "review_status": commit.review_status,
                },
            )
        if not files:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one supplemental Evidence file is required",
            )

        submitted_at = datetime.now(timezone.utc)
        evidence = dict(commit.evidence or {})
        review_history = list(evidence.get("review_history") or [])
        review_history.append(
            {
                "decision": "rejected",
                "note": commit.review_note,
                "reviewed_by": commit.reviewed_by,
                "reviewed_at": (
                    commit.reviewed_at.isoformat() if commit.reviewed_at else None
                ),
            }
        )
        submissions = list(evidence.get("supplemental_evidence") or [])
        submissions.append(
            {
                "submitted_at": submitted_at.isoformat(),
                "submitted_by": user.username,
                "note": note,
                "files": files,
            }
        )
        commit.evidence = {
            **evidence,
            "review_history": review_history,
            "supplemental_evidence": submissions,
            # Explicit demo gate: supplemental metadata lets the manager make
            # a new human decision even when the original automated metric
            # still says remediation is required.
            "supplemental_review_override": True,
        }

        result = dict(commit.result or {})
        stage_snapshot = result.get("stage_snapshot")
        if isinstance(stage_snapshot, dict):
            result["stage_snapshot"] = {**stage_snapshot, "status": "pending"}
            commit.result = result

        commit.review_status = REVIEW_PENDING
        commit.reviewed_by = None
        commit.reviewed_at = None
        commit.review_note = "추가 Evidence 제출 · 관리자 재검토 대기"
        commit.instruction.status = INSTRUCTION_COMMITTED
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_SUPPLEMENTAL_EVIDENCE_SUBMITTED",
                target_type="execution_commit",
                target_id=commit.id,
                details={
                    "instruction_id": commit.instruction_id,
                    "file_names": [str(item.get("name") or "") for item in files],
                    "note": note,
                },
            )
        )
        db.commit()
        db.refresh(commit)
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
        generated_operation = (commit.result or {}).get("operation")
        result = commit.result or {}
        quality_assessment = result.get("quality_assessment") or {}
        supplemental_review_override = bool(
            (commit.evidence or {}).get("supplemental_review_override")
        )
        if (
            decision == REVIEW_APPROVED
            and quality_assessment.get("status") == "needs_remediation"
            and not supplemental_review_override
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": (
                        "목표 굴착량을 만족하지 못해 바로 승인할 수 없습니다. "
                        "센서 증거를 확인한 뒤 보완 작업을 생성하세요."
                    ),
                    "code": "EXCAVATION_REMEDIATION_REQUIRED",
                    "remediation_required": True,
                    "planned_volume_m3": quality_assessment.get(
                        "planned_volume_m3"
                    ),
                    "completed_volume_m3": quality_assessment.get(
                        "completed_volume_m3"
                    ),
                    "remaining_volume_m3": quality_assessment.get(
                        "remaining_volume_m3"
                    ),
                    "measured_completion_ratio": quality_assessment.get(
                        "measured_completion_ratio"
                    ),
                    "required_completion_ratio": quality_assessment.get(
                        "required_completion_ratio"
                    ),
                },
            )
        has_terrain_deformation = bool(
            (result.get("terrain_deformation") or {}).get("available")
            and result.get("map_changes")
        )
        is_excavation = commit.instruction.kind == KIND_EXCAVATE_PRIM or (
            commit.instruction.kind == KIND_GENERATED_SCRIPT
            and generated_operation
            in {"excavate_prim", "set_prim_active", "pipeline_excavation"}
            and (
                result.get("target_active_after") is False
                or has_terrain_deformation
            )
        )
        if decision == REVIEW_APPROVED and is_excavation:
            if (
                result.get("simulator") != "isaac-sim"
                or result.get("source") != "stage-readback"
                or not (
                    result.get("target_active_after") is False
                    or has_terrain_deformation
                )
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Excavation approval requires verified sensor read-back and a "
                        "verified inactive target Prim or verified terrain deformation."
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

        reviewed_at = datetime.now(timezone.utc)
        stage_snapshot = (commit.result or {}).get("stage_snapshot")
        if decision == REVIEW_APPROVED:
            promoted = promote_stage_snapshot(
                commit,
                reviewed_by=user.username,
                reviewed_at=reviewed_at,
            )
            if promoted is not None:
                commit.result = {
                    **(commit.result or {}),
                    "stage_snapshot": {
                        **stage_snapshot,
                        **promoted,
                        "status": "approved",
                    },
                }
        elif isinstance(stage_snapshot, dict):
            commit.result = {
                **(commit.result or {}),
                "stage_snapshot": {**stage_snapshot, "status": "rejected"},
            }

        resolved_note = note
        if decision == REVIEW_APPROVED and supplemental_review_override and not note:
            history = (commit.evidence or {}).get("review_history") or []
            previous_note = str((history[-1] if history else {}).get("note") or "").strip()
            resolved_note = "추가 Evidence 재검토 승인"
            if previous_note:
                resolved_note = f"{resolved_note} · 최초 반려: {previous_note}"
            resolved_note = resolved_note[:500]

        commit.review_status = REVIEW_APPROVED if decision == REVIEW_APPROVED else REVIEW_REJECTED
        commit.reviewed_by = user.username
        commit.reviewed_at = reviewed_at
        commit.review_note = resolved_note
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
                    "note": resolved_note,
                },
            )
        )
        db.commit()
        db.refresh(commit)
        return commit

    @staticmethod
    def approve_remediation_parent(
        db: Session,
        *,
        remediation_commit: ExecutionCommit,
        user: User,
    ) -> WorkInstruction | None:
        """Close the original deficient commit after corrective work passes.

        The original result remains in history as an under-excavated state,
        but its review is completed one microsecond before the corrective
        commit so map replay always finishes on the corrected geometry.
        """

        params = remediation_commit.instruction.params or {}
        parent_commit_id = str(params.get("remediation_parent_commit_id") or "")
        if not parent_commit_id:
            return None
        parent = db.get(ExecutionCommit, parent_commit_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The remediation parent commit no longer exists",
            )
        if parent.review_status == REVIEW_APPROVED:
            return parent.instruction
        if parent.review_status != REVIEW_PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The remediation parent commit is no longer reviewable",
            )
        quality = (parent.result or {}).get("quality_assessment") or {}
        if quality.get("status") != "needs_remediation":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The parent commit does not require remediation",
            )

        corrected_at = remediation_commit.reviewed_at or datetime.now(timezone.utc)
        planned_volume = float(quality.get("planned_volume_m3") or 0.0)
        initial_completed_volume = float(quality.get("completed_volume_m3") or 0.0)
        initial_remaining_volume = float(quality.get("remaining_volume_m3") or 0.0)
        initial_measured_ratio = float(
            quality.get("measured_completion_ratio") or 0.0
        )
        parent.result = {
            **(parent.result or {}),
            "quality_assessment": {
                **quality,
                "status": "remediated",
                "initial_completed_volume_m3": initial_completed_volume,
                "initial_remaining_volume_m3": initial_remaining_volume,
                "initial_measured_completion_ratio": initial_measured_ratio,
                "completed_volume_m3": planned_volume,
                "remaining_volume_m3": 0.0,
                "measured_completion_ratio": 1.0,
                "remediation_commit_id": remediation_commit.id,
                "message": "Corrective excavation was completed and revalidated.",
            },
        }
        parent.review_status = REVIEW_APPROVED
        parent.reviewed_by = user.username
        parent.reviewed_at = corrected_at - timedelta(microseconds=1)
        parent.review_note = (
            f"보완 커밋 {remediation_commit.id[:8]} 재검증 통과로 원 작업을 완료 처리"
        )
        parent.instruction.status = INSTRUCTION_APPROVED
        db.add(
            AuditLog(
                user_id=user.id,
                username=user.username,
                action="ISAAC_REMEDIATION_PARENT_APPROVED",
                target_type="execution_commit",
                target_id=parent.id,
                details={
                    "remediation_commit_id": remediation_commit.id,
                    "instruction_id": parent.instruction_id,
                },
            )
        )
        db.commit()
        db.refresh(parent.instruction)
        return parent.instruction

    @staticmethod
    def approved_map_objects(
        db: Session,
        *,
        project_id: str,
        reviewed_after: datetime | None = None,
    ) -> list[dict]:
        """Replay every approved commit and return the latest published state."""
        timeline = TrustGateService.approved_map_timeline(
            db,
            project_id=project_id,
            reviewed_after=reviewed_after,
        )
        return TrustGateService.replay_map_timeline(timeline)

    @staticmethod
    def approved_map_timeline(
        db: Session,
        *,
        project_id: str,
        reviewed_after: datetime | None = None,
    ) -> list[dict]:
        """Return every approved commit with its map delta in review order.

        Unlike ``approved_map_objects``, this method never deduplicates commits
        that touch the same Prim. The browser can therefore replay the exact
        approved history instead of seeing only the latest Prim state.
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
        if reviewed_after is not None:
            cutoff = reviewed_after.replace(tzinfo=None)
            query = query.where(ExecutionCommit.reviewed_at >= cutoff)
        timeline: list[dict] = []
        for commit, instruction in db.execute(query).all():
            timeline.append(
                {
                    "commit_id": commit.id,
                    "instruction_id": instruction.id,
                    "approved_by": commit.reviewed_by,
                    "approved_at": commit.reviewed_at,
                    "objects": TrustGateService._map_delta_for_commit(commit, instruction),
                }
            )
        return timeline

    @staticmethod
    def replay_map_timeline(timeline: list[dict]) -> list[dict]:
        """Replay timeline deltas and return one final object per Prim."""
        objects_by_prim: dict[str, dict] = {}
        for step in timeline:
            for item in step.get("objects") or []:
                key = str(item.get("prim_path") or item.get("id"))
                objects_by_prim[key] = item
        return list(objects_by_prim.values())

    @staticmethod
    def _map_delta_for_commit(
        commit: ExecutionCommit,
        instruction: WorkInstruction,
    ) -> list[dict]:
        """Convert one approved execution result into a replayable map delta."""
        params = instruction.params or {}
        result = commit.result or {}
        objects: list[dict] = []
        seen_prim_paths: set[str] = set()

        # Parallel excavation originally recorded removals as ``active: false``
        # and kept the exact per-Prim bounds inside each scoop.  Preserve
        # compatibility with those already-approved commits so the published
        # Work/Timeline maps can be rebuilt without rerunning Isaac Sim.
        final_targets: dict[str, dict] = {}
        for scoop in reversed(result.get("scoops") or []):
            if not isinstance(scoop, dict):
                continue
            deformation = scoop.get("terrain_deformation") or {}
            for target in deformation.get("targets") or []:
                if not isinstance(target, dict):
                    continue
                target_path = str(target.get("target_prim_path") or "")
                if target_path and target_path not in final_targets:
                    final_targets[target_path] = target

        map_changes = result.get("map_changes") or []
        if map_changes:
            for index, change in enumerate(map_changes):
                if not isinstance(change, dict):
                    continue
                prim_path = str(change.get("prim_path") or f"{commit.id}:{index}")
                action = str(
                    change.get("action")
                    or ("remove" if change.get("active") is False else "upsert")
                )
                if action == "remove":
                    final_target = final_targets.get(prim_path) or {}
                    position = (
                        change.get("position")
                        or final_target.get("position")
                        or result.get("target_position")
                    )
                    size = (
                        change.get("size")
                        or final_target.get("size")
                        or result.get("target_bounds_size")
                    )
                    if not position or not size:
                        continue
                    objects.append(
                        {
                            "id": f"{commit.id}:{index}",
                            "instruction_id": instruction.id,
                            "type": "removed_prim",
                            "label": change.get("label") or params.get("target_name") or "Removed terrain",
                            "color": change.get("color") or "#d95757",
                            "position": position,
                            "size": size,
                            "approved_by": commit.reviewed_by,
                            "approved_at": commit.reviewed_at,
                            "prim_path": prim_path,
                            "geometry": None,
                        }
                    )
                    seen_prim_paths.add(prim_path)
                    continue
                position = change.get("position")
                size = change.get("size")
                if not position or not size:
                    continue
                objects.append(
                    {
                        "id": f"{commit.id}:{index}",
                        "instruction_id": instruction.id,
                        "type": change.get("type") or "terrain_patch",
                        "label": change.get("label") or params.get("label") or instruction.kind,
                        "color": change.get("color") or DEFAULT_CUBE_COLOR,
                        "position": position,
                        "size": size,
                        "approved_by": commit.reviewed_by,
                        "approved_at": commit.reviewed_at,
                        "prim_path": prim_path,
                        "geometry": change.get("geometry"),
                    }
                )
                seen_prim_paths.add(prim_path)

            # Older parallel-excavation results kept deposited soil under each
            # scoop rather than in map_changes.  Publish those authored meshes
            # as approved map overlays as well.
            deposit_index = len(map_changes)
            for scoop in result.get("scoops") or []:
                if not isinstance(scoop, dict):
                    continue
                moved_soil = scoop.get("moved_soil")
                if not isinstance(moved_soil, dict):
                    continue
                prim_path = str(moved_soil.get("prim_path") or "")
                position = moved_soil.get("position")
                size = moved_soil.get("size")
                if not prim_path or prim_path in seen_prim_paths or not position or not size:
                    continue
                objects.append(
                    {
                        "id": f"{commit.id}:{deposit_index}",
                        "instruction_id": instruction.id,
                        "type": "soil_deposit",
                        "label": moved_soil.get("label") or "굴착 토사",
                        "color": moved_soil.get("color") or "#8B6A3D",
                        "position": position,
                        "size": size,
                        "approved_by": commit.reviewed_by,
                        "approved_at": commit.reviewed_at,
                        "prim_path": prim_path,
                        "geometry": moved_soil.get("geometry"),
                    }
                )
                seen_prim_paths.add(prim_path)
                deposit_index += 1
            return objects

        is_excavation = instruction.kind == KIND_EXCAVATE_PRIM or (
            instruction.kind == KIND_GENERATED_SCRIPT
            and result.get("operation") in {"excavate_prim", "set_prim_active"}
            and result.get("target_active_after") is False
        )
        if is_excavation:
            position = result.get("target_position")
            size = result.get("target_bounds_size")
            if not position or not size:
                return objects
            prim_path = result.get("target_prim_path") or params.get("target_prim_path")
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
                    "prim_path": prim_path,
                    "geometry": None,
                }
            )
            return objects

        position = result.get("placed_position") or params.get("position")
        if not position:
            return objects
        size = result.get("placed_size") or params.get("size") or DEFAULT_CUBE_SIZE
        prim_path = result.get("prim_path") or commit.id
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
                "geometry": result.get("geometry"),
            }
        )
        return objects

    @staticmethod
    def rejected_map_conflicts(
        db: Session,
        *,
        project_id: str,
        reviewed_after: datetime | None = None,
    ) -> list[dict]:
        """Return rejected proposed map changes without mutating the published map."""
        query = (
            select(ExecutionCommit, WorkInstruction)
            .join(WorkInstruction, ExecutionCommit.instruction_id == WorkInstruction.id)
            .where(
                WorkInstruction.project_id == project_id,
                ExecutionCommit.review_status == REVIEW_REJECTED,
            )
            .order_by(ExecutionCommit.reviewed_at.desc())
        )
        if reviewed_after is not None:
            cutoff = reviewed_after.replace(tzinfo=None)
            query = query.where(ExecutionCommit.reviewed_at >= cutoff)
        conflicts: list[dict] = []
        for commit, instruction in db.execute(query).all():
            result = commit.result or {}
            params = instruction.params or {}
            proposed = result.get("map_changes") or [
                {
                    "prim_path": result.get("target_prim_path") or params.get("target_prim_path"),
                    "position": result.get("target_after_position") or result.get("target_position"),
                    "size": result.get("target_after_bounds_size") or result.get("target_bounds_size"),
                    "label": params.get("target_name") or params.get("label") or instruction.kind,
                }
            ]
            for index, change in enumerate(proposed):
                if not isinstance(change, dict):
                    continue
                conflicts.append(
                    {
                        "id": f"conflict:{commit.id}:{index}",
                        "commit_id": commit.id,
                        "instruction_id": instruction.id,
                        "label": change.get("label") or instruction.kind,
                        "reason": commit.review_note or "Manager rejected this proposed map change.",
                        "position": change.get("position"),
                        "size": change.get("size"),
                        "prim_path": change.get("prim_path"),
                        "rejected_by": commit.reviewed_by,
                        "rejected_at": commit.reviewed_at,
                    }
                )
        return conflicts
