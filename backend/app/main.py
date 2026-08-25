from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request, status
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


@app.middleware("http")
async def prevent_stale_frontend_cache(request: Request, call_next):
    """Serve the current working-tree UI instead of a cached older bundle."""

    response = await call_next(request)
    path = request.url.path
    if (
        path in {"/", "/login", "/favicon.ico", settings.api_prefix}
        or path.startswith("/static/")
        or path.startswith(f"{settings.api_prefix}/")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

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


@app.get("/isaac-data/{storage_path:path}", include_in_schema=False)
def isaac_data(storage_path: str, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    """Isaac 지형 Mesh 번들. 로그인한 사용자에게만 내보냅니다.

    StaticFiles 마운트로 두면 FastAPI 의존성이 걸리지 않아 무인증으로 공개됩니다.
    고정 URL로 외부에 노출하는 순간 현장 지형 전체가 무인증 다운로드 대상이 되므로
    직접 라우트로 받아 쿠키를 검사합니다.
    """
    if not _request_user(request, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    root = (settings.sitegit_data_root / "isaac").resolve()
    target = (root / storage_path).resolve()
    # 경로 탈출 차단. resolve() 뒤에 비교해야 ../ 를 확실히 걸러냅니다.
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(target)


@app.get("/evidence/{storage_path:path}", include_in_schema=False)
def evidence_data(storage_path: str, request: Request, db: Session = Depends(get_db)) -> FileResponse:
    """Serve authenticated before/after images, Stage summaries, and LiDAR PLY files."""
    if not _request_user(request, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    root = (settings.sitegit_data_root / "evidence").resolve()
    target = (root / storage_path).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(target)
