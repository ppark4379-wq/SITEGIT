from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .api.deps import get_db
from .api.router import api_router
from .core.config import get_settings
from .core.security import decode_access_token
from .db.base import Base
from .db.session import engine
from .models.user import User
from .seed import seed_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sitegit")
settings = get_settings()

app = FastAPI(
    title="SiteGit Modular Local Shared API",
    version="0.2.0",
    docs_url=f"{settings.api_prefix}/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.include_router(api_router, prefix=settings.api_prefix)
app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_database()
    if settings.jwt_secret.startswith("CHANGE-ME"):
        logger.warning("JWT_SECRET is using the development default. Change it before exposing the fixed URL.")


def _request_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    user = db.get(User, payload.get("sub"))
    return user if user and user.is_active else None


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    return FileResponse(settings.frontend_dir / "login.html")


@app.get("/", include_in_schema=False)
def app_page(request: Request, db: Session = Depends(get_db)):
    if not _request_user(request, db):
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(settings.frontend_dir / "favicon.svg", media_type="image/svg+xml")
