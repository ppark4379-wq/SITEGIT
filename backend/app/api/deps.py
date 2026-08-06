from __future__ import annotations

from collections.abc import Generator

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.security import decode_access_token
from ..db.session import SessionLocal
from ..models.user import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(authorization: str | None, cookie_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return cookie_token


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    cookie_token: str | None = Cookie(default=None, alias=get_settings().auth_cookie_name),
) -> User:
    token = _extract_token(authorization, cookie_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency
