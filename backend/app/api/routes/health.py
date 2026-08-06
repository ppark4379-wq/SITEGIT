from fastapi import APIRouter

from ...core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": "sqlite" if settings.resolved_database_url.startswith("sqlite") else "external",
    }
