from __future__ import annotations

from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from ...models.work_package import RELEASE_LOCKED, RELEASE_OPEN, WorkPackage, WorkPackageExecutionLink
from ...schemas.work_package import ReworkCreate, WorkPackageCreate
from ..versioning.service import VersioningService
from .template import EXCAVATION_CRITERIA, EXCAVATION_REQUIRED_RESULTS
from .transition import WorkPackageTransitionService


class WorkPackagesService:
    @staticmethod
    def get(db: Session, work_package_id: str) -> WorkPackage:
        item = db.execute(select(WorkPackage).options(selectinload(WorkPackage.evaluations),
            selectinload(WorkPackage.execution_links)).where(WorkPackage.id == work_package_id)).scalar_one_or_none()
        if not item: raise HTTPException(status_code=404, detail="Work Package not found")
        return item

    @staticmethod
    def list(db: Session, project_id: str) -> list[WorkPackage]:
        return list(db.execute(select(WorkPackage).where(WorkPackage.project_id == project_id)
            .order_by(WorkPackage.created_at)).scalars())

    @staticmethod
    def create(db: Session, payload: WorkPackageCreate, *, actor: str | None, commit: bool = True) -> WorkPackage:
        if payload.id and db.get(WorkPackage, payload.id):
            raise HTTPException(status_code=409, detail="Work Package ID already exists")
        predecessor = db.get(WorkPackage, payload.predecessor_wp_id) if payload.predecessor_wp_id else None
        if payload.predecessor_wp_id and not predecessor:
            raise HTTPException(status_code=422, detail="Predecessor Work Package not found")
        unlocked = predecessor is None or predecessor.status == "RELEASED"
        item = WorkPackage(id=payload.id or f"WP-{payload.work_type[:3]}-{uuid4().hex[:10].upper()}",
            project_id=payload.project_id, work_type=payload.work_type, zone_id=payload.zone_id,
            title=payload.title, description=payload.description, target_json=payload.target,
            constraints_json=payload.constraints,
            completion_criteria_json=[c.model_dump() for c in payload.completion_criteria] or EXCAVATION_CRITERIA,
            required_results_json=payload.required_results or EXCAVATION_REQUIRED_RESULTS,
            predecessor_wp_id=payload.predecessor_wp_id, successor_wp_id=payload.successor_wp_id,
            status="READY" if unlocked else "DRAFT", release_gate=RELEASE_OPEN if unlocked else RELEASE_LOCKED,
            created_by=actor)
        db.add(item); db.flush()
        if predecessor and not predecessor.successor_wp_id: predecessor.successor_wp_id = item.id
        VersioningService.record(db, work_package_id=item.id, event_type="WP_CREATED", actor=actor,
            to_status=item.status, reason="Work Package created")
        if item.status == "READY":
            VersioningService.record(db, work_package_id=item.id, event_type="WP_READY", actor=actor,
                from_status="DRAFT", to_status="READY")
        if commit: db.commit(); db.refresh(item)
        return item

    @staticmethod
    def start(db: Session, item: WorkPackage, *, actor: str | None) -> WorkPackage:
        WorkPackageTransitionService.transition(db, work_package=item, to_status="RUNNING", actor=actor)
        db.commit(); db.refresh(item); return item

    @staticmethod
    def mark_review(db: Session, item: WorkPackage, *, actor: str | None,
                    reference_id: str | None = None) -> WorkPackage:
        WorkPackageTransitionService.transition(db, work_package=item, to_status="REVIEW", actor=actor,
            event_type="EXECUTION_FINISHED", reference_id=reference_id)
        db.commit(); db.refresh(item); return item

    @staticmethod
    def link_instruction(db: Session, *, item: WorkPackage, instruction_id: str) -> WorkPackageExecutionLink:
        link = WorkPackageExecutionLink(work_package_id=item.id, instruction_id=instruction_id)
        db.add(link); db.commit(); db.refresh(link); return link

    @staticmethod
    def create_rework(db: Session, original: WorkPackage, payload: ReworkCreate,
                      *, actor: str | None) -> WorkPackage:
        if original.status != "REWORK":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                detail="Rework can only be created after failed evaluation")
        count = len(list(db.execute(select(WorkPackage).where(WorkPackage.parent_wp_id == original.id)).scalars()))
        rework = WorkPackage(id=f"{original.id}-R{count+1}", project_id=original.project_id,
            work_type=original.work_type, zone_id=original.zone_id, title=f"{original.title} · 보완 {count+1}",
            description=payload.reason, target_json=original.target_json, constraints_json=original.constraints_json,
            completion_criteria_json=original.completion_criteria_json,
            required_results_json=original.required_results_json, status="READY", release_gate=RELEASE_OPEN,
            parent_wp_id=original.id, successor_wp_id=original.successor_wp_id, rework_reason=payload.reason,
            failed_criteria_json=original.failed_criteria_json, target_area_json=payload.target_area, created_by=actor)
        db.add(rework); db.flush()
        VersioningService.record(db, work_package_id=original.id, event_type="REWORK_CREATED", actor=actor,
            from_status="REWORK", to_status="REWORK", reason=payload.reason, reference_id=rework.id)
        VersioningService.record(db, work_package_id=rework.id, event_type="WP_CREATED", actor=actor,
            to_status="READY", reason="Corrective Work Package", reference_id=original.id)
        db.commit(); db.refresh(rework); return rework

    @staticmethod
    def release(db: Session, item: WorkPackage, *, actor: str | None) -> WorkPackage:
        WorkPackageTransitionService.transition(db, work_package=item, to_status="RELEASED", actor=actor)
        item.release_gate = RELEASE_OPEN
        successor_id = item.successor_wp_id
        if item.parent_wp_id:
            parent = db.get(WorkPackage, item.parent_wp_id)
            if parent:
                parent.status = "RELEASED"; parent.release_gate = RELEASE_OPEN; successor_id = parent.successor_wp_id
                VersioningService.record(db, work_package_id=parent.id, event_type="RELEASED", actor=actor,
                    from_status="REWORK", to_status="RELEASED", reference_id=item.id)
        if successor_id:
            successor = db.get(WorkPackage, successor_id)
            if successor and successor.release_gate == RELEASE_LOCKED:
                previous = successor.status; successor.release_gate = RELEASE_OPEN
                if successor.status == "DRAFT": successor.status = "READY"
                VersioningService.record(db, work_package_id=successor.id, event_type="SUCCESSOR_UNLOCKED", actor=actor,
                    from_status=previous, to_status=successor.status, reference_id=item.id)
        db.commit(); db.refresh(item); return item
