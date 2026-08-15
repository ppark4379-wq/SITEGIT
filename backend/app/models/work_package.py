from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


WP_STATUSES = (
    "DRAFT", "READY", "RUNNING", "REVIEW", "REWORK", "HOLD",
    "RELEASE_READY", "RELEASED",
)
RELEASE_LOCKED = "LOCKED"
RELEASE_OPEN = "OPEN"


class WorkPackage(Base):
    __tablename__ = "work_packages"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    work_type: Mapped[str] = mapped_column(String(40), nullable=False, default="EXCAVATION")
    zone_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    constraints_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    completion_criteria_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_results_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", index=True)
    predecessor_wp_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("work_packages.id"))
    successor_wp_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("work_packages.id"))
    parent_wp_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("work_packages.id"))
    release_gate: Mapped[str] = mapped_column(String(16), nullable=False, default=RELEASE_LOCKED)
    rework_reason: Mapped[str | None] = mapped_column(Text)
    failed_criteria_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    target_area_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    evaluations: Mapped[list["WorkPackageEvaluation"]] = relationship(cascade="all, delete-orphan")
    execution_links: Mapped[list["WorkPackageExecutionLink"]] = relationship(cascade="all, delete-orphan")
    version_events: Mapped[list["VersionEvent"]] = relationship(cascade="all, delete-orphan")


class WorkPackageExecutionLink(Base):
    __tablename__ = "work_package_execution_links"
    __table_args__ = (UniqueConstraint("work_package_id", "instruction_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_package_id: Mapped[str] = mapped_column(String(80), ForeignKey("work_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    instruction_id: Mapped[str] = mapped_column(String(36), ForeignKey("work_instructions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_commit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_commits.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class WorkPackageEvaluation(Base):
    __tablename__ = "work_package_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_package_id: Mapped[str] = mapped_column(String(80), ForeignKey("work_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    overall: Mapped[str] = mapped_column(String(16), nullable=False)
    criteria_json: Mapped[list] = mapped_column(JSON, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class VersionEvent(Base):
    __tablename__ = "version_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    work_package_id: Mapped[str] = mapped_column(String(80), ForeignKey("work_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    actor: Mapped[str | None] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
