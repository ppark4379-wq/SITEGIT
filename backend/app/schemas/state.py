from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StateResponse(BaseModel):
    project_id: str
    payload: dict[str, Any]
    revision: int
    updated_at: datetime
    updated_by: str | None = None


class StateUpdate(BaseModel):
    payload: dict[str, Any]
    revision: int | None = Field(default=None, ge=1)
    source: str = Field(default="web", max_length=40)
