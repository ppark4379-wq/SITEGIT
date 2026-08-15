from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from ...models.work_package import VersionEvent


class VersioningService:
    @staticmethod
    def record(db: Session, *, work_package_id: str, event_type: str, actor: str | None,
               from_status: str | None = None, to_status: str | None = None,
               reason: str | None = None, reference_id: str | None = None) -> VersionEvent:
        event = VersionEvent(work_package_id=work_package_id, event_type=event_type,
            from_status=from_status, to_status=to_status, actor=actor, reason=reason,
            reference_id=reference_id)
        db.add(event)
        return event

    @staticmethod
    def list_for_work_package(db: Session, work_package_id: str) -> list[VersionEvent]:
        return list(db.execute(select(VersionEvent).where(
            VersionEvent.work_package_id == work_package_id
        ).order_by(VersionEvent.created_at)).scalars())
