"""Versioned construction drawing registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from ...core.config import get_settings
from ...domains.work_packages.site_plan_store import list_site_plans, save_site_plan
from ...models.user import User
from ...schemas.site_plan import SitePlanRecord, SitePlanSaveRequest
from ..deps import get_current_user, require_roles


router = APIRouter(prefix="/site-plans", tags=["site-plans"])


@router.get("", response_model=list[SitePlanRecord])
def read_site_plans(
    project_id: str = Query(default="SASANG-001", min_length=1, max_length=80),
    _user: User = Depends(get_current_user),
) -> list[SitePlanRecord]:
    return list_site_plans(get_settings().sitegit_data_root, project_id)


@router.post("", response_model=SitePlanRecord, status_code=status.HTTP_201_CREATED)
def write_site_plan(
    payload: SitePlanSaveRequest,
    user: User = Depends(require_roles("admin", "manager", "reviewer")),
) -> SitePlanRecord:
    return save_site_plan(
        get_settings().sitegit_data_root,
        payload,
        username=user.username,
    )

