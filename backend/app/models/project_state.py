from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectState(Base):
    """Prototype compatibility store.

    The current UI is still one aggregate state object. Keeping it behind the API lets
    the team share data now, while normalized domain tables are introduced later.
    """

    __tablename__ = "project_states"

    project_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
