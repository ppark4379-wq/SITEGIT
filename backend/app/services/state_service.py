from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.audit_log import AuditLog
from ..models.project_state import ProjectState
from ..models.user import User


def load_seed_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def get_or_create_state(db: Session, *, project_id: str, seed_path: Path) -> ProjectState:
    state = db.get(ProjectState, project_id)
    if state:
        return state
    state = ProjectState(project_id=project_id, payload=load_seed_payload(seed_path), revision=1)
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def update_state(
    db: Session,
    *,
    state: ProjectState,
    payload: dict,
    expected_revision: int | None,
    source: str,
    user: User,
) -> ProjectState:
    if expected_revision is not None and expected_revision != state.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "State revision conflict", "current_revision": state.revision},
        )
    previous_revision = state.revision
    state.payload = payload
    state.revision += 1
    state.updated_by = user.id
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="PROJECT_STATE_UPDATED",
            target_type="project_state",
            target_id=state.project_id,
            details={"from_revision": previous_revision, "to_revision": state.revision, "source": source},
        )
    )
    db.commit()
    db.refresh(state)
    return state
