from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.security import create_access_token, verify_password
from ...models.audit_log import AuditLog
from ...models.user import User
from ...schemas.auth import LoginRequest, TokenResponse, UserResponse
from ..deps import get_current_user, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(user_id=user.id, username=user.username, role=user.role)
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="LOGIN",
            target_type="session",
            target_id=user.id,
            details={},
        )
    )
    db.commit()
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            action="LOGOUT",
            target_type="session",
            target_id=user.id,
            details={},
        )
    )
    db.commit()
    return response


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)
