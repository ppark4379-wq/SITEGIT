"""API contracts for versioned construction drawings used by SiteGit."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .work_package_ai import PlanningDesignPreview


class SitePlanSaveRequest(BaseModel):
    """A normalized drawing revision aligned to the Isaac site frame."""

    project_id: str = Field(default="SASANG-001", min_length=1, max_length=80)
    status: Literal["draft", "approved"] = "draft"
    source_filename: str = Field(default="", max_length=255)
    design: PlanningDesignPreview


class SitePlanRecord(SitePlanSaveRequest):
    """Stored drawing revision metadata returned to the web client."""

    updated_at: datetime
    updated_by: str = Field(min_length=1, max_length=120)

