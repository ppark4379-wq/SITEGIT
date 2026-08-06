from __future__ import annotations

from sqlalchemy import select

from .core.config import get_settings
from .core.security import hash_password
from .db.session import SessionLocal
from .models.project_state import ProjectState
from .models.user import User
from .services.state_service import load_seed_payload


def _sync_initial_user(
    db,
    *,
    username: str,
    password: str,
    full_name: str,
    role: str,
    legacy_usernames: tuple[str, ...] = (),
) -> None:
    user = db.scalar(select(User).where(User.username == username))
    if not user:
        for legacy_username in legacy_usernames:
            user = db.scalar(select(User).where(User.username == legacy_username))
            if user:
                break

    if user:
        user.username = username
        user.password_hash = hash_password(password)
        user.full_name = full_name
        user.role = role
        user.is_active = True
    else:
        db.add(User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        ))

    for legacy_username in legacy_usernames:
        if legacy_username == username:
            continue
        legacy_user = db.scalar(select(User).where(User.username == legacy_username))
        if legacy_user and legacy_user is not user:
            legacy_user.is_active = False


def seed_database() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        _sync_initial_user(
            db,
            username=settings.initial_admin_username,
            password=settings.initial_admin_password,
            full_name=settings.initial_admin_name,
            role="admin",
            legacy_usernames=("admin",),
        )
        if settings.seed_demo_users:
            _sync_initial_user(
                db,
                username=settings.initial_manager_username,
                password=settings.initial_manager_password,
                full_name=settings.initial_manager_name,
                role="manager",
                legacy_usernames=("manager",),
            )
            _sync_initial_user(
                db,
                username=settings.initial_viewer_username,
                password=settings.initial_viewer_password,
                full_name=settings.initial_viewer_name,
                role="viewer",
                legacy_usernames=("viewer",),
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
