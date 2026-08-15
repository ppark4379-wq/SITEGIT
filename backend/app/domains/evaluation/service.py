from __future__ import annotations

from sqlalchemy.orm import Session
from ...models.work_package import WorkPackage, WorkPackageEvaluation
from ...schemas.work_package import EvaluationCreate
from ..work_packages.transition import WorkPackageTransitionService


class EvaluationService:
    @staticmethod
    def evaluate(db: Session, *, work_package: WorkPackage, payload: EvaluationCreate,
                 actor: str | None) -> WorkPackageEvaluation:
        overall = "PASS" if all(c.status == "PASS" for c in payload.criteria) else "FAIL"
        recommended = "RELEASE_READY" if overall == "PASS" else "REWORK"
        result = WorkPackageEvaluation(work_package_id=work_package.id,
            progress_json=payload.progress.model_dump(), overall=overall,
            criteria_json=[c.model_dump() for c in payload.criteria], recommended_action=recommended)
        db.add(result); db.flush()
        failed = [c.model_dump() for c in payload.criteria if c.status == "FAIL"]
        work_package.failed_criteria_json = failed
        WorkPackageTransitionService.transition(db, work_package=work_package, to_status=recommended, actor=actor,
            event_type="RECHECK_PASSED" if overall == "PASS" else "CRITERIA_FAILED",
            reason=None if overall == "PASS" else "; ".join(c.get("reason") or c["label"] for c in failed),
            reference_id=result.id)
        db.commit(); db.refresh(result); return result

    @staticmethod
    def latest(work_package: WorkPackage) -> WorkPackageEvaluation | None:
        return work_package.evaluations[-1] if work_package.evaluations else None
