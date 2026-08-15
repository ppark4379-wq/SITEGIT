from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from ...models.work_package import WorkPackage
from ..versioning.service import VersioningService

ALLOWED_TRANSITIONS = {
    "DRAFT":{"READY","HOLD"}, "READY":{"RUNNING","HOLD"},
    "RUNNING":{"REVIEW","HOLD"}, "REVIEW":{"REWORK","RELEASE_READY","HOLD"},
    "REWORK":{"RELEASE_READY","HOLD"}, "HOLD":{"READY","RUNNING","REVIEW"},
    "RELEASE_READY":{"RELEASED","REWORK","HOLD"}, "RELEASED":set(),
}
EVENT_BY_STATUS = {"READY":"WP_READY","RUNNING":"EXECUTION_STARTED","REVIEW":"REVIEW_STARTED",
    "REWORK":"CRITERIA_FAILED","HOLD":"HOLD","RELEASE_READY":"RELEASE_READY","RELEASED":"RELEASED"}


class WorkPackageTransitionService:
    @staticmethod
    def transition(db: Session, *, work_package: WorkPackage, to_status: str,
                   actor: str | None, reason: str | None = None,
                   event_type: str | None = None, reference_id: str | None = None) -> WorkPackage:
        if to_status not in ALLOWED_TRANSITIONS.get(work_package.status, set()):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "message":"Invalid Work Package transition","from_status":work_package.status,"to_status":to_status})
        previous = work_package.status
        work_package.status = to_status
        VersioningService.record(db, work_package_id=work_package.id,
            event_type=event_type or EVENT_BY_STATUS[to_status], actor=actor,
            from_status=previous, to_status=to_status, reason=reason, reference_id=reference_id)
        return work_package
