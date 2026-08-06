from __future__ import annotations

from sqlalchemy import select

from .core.config import get_settings
from .core.security import hash_password
from .db.session import SessionLocal
from .models.project_state import ProjectState
from .models.user import User
from .services.state_service import load_seed_payload


def _ensure_user(db, *, username: str, password: str, full_name: str, role: str) -> None:
    user = db.scalar(select(User).where(User.username == username))
    if user:
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )
    )


def seed_database() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        _ensure_user(
            db,
            username=settings.initial_admin_username,
            password=settings.initial_admin_password,
            full_name=settings.initial_admin_name,
            role="admin",
        )
        if settings.seed_demo_users:
            _ensure_user(
                db,
                username="manager",
                password=settings.initial_manager_password,
                full_name="김현장",
                role="manager",
            )
            _ensure_user(
                db,
                username="viewer",
                password=settings.initial_viewer_password,
                full_name="현장 조회자",
                role="viewer",
            )
        if not db.get(ProjectState, settings.default_project_id):
            db.add(
                ProjectState(
                    project_id=settings.default_project_id,
                    payload=load_seed_payload(settings.seed_state_path),
                    revision=1,
                )
            )
        db.commit()
