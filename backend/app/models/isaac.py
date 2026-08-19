"""Isaac Sim 작업 지시와 실행 Commit.

웹이 지시를 내리고(WorkInstruction), Isaac Sim이 실행 결과를 올리고
(ExecutionCommit), 관리자가 승인하면 맵에 반영되는 폐루프의 저장 계층입니다.

승인된 Commit이 곧 맵 오브젝트입니다. 별도 map_objects 테이블을 두지 않으므로
승인을 되돌리면 맵에서도 즉시 사라지고, 두 저장소가 어긋날 일이 없습니다.

기존 project_states.payload JSON에 넣지 않은 이유는 두 가지입니다. payload는
기존 UI 호환용 임시 저장소이고, 다음 단계에서 붙을 LiDAR/카메라 Evidence는
storage_key로 SSD를 가리켜야 하므로 상태 JSON에 통째로 담기에 부적합합니다.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# 지시 생명주기. 웹에서 만들어 Isaac이 가져가고, 결과를 올리면 관리자가 판정합니다.
INSTRUCTION_PENDING = "pending"
INSTRUCTION_DISPATCHED = "dispatched"
INSTRUCTION_COMMITTED = "committed"
INSTRUCTION_APPROVED = "approved"
INSTRUCTION_REJECTED = "rejected"
INSTRUCTION_STATUSES = (
    INSTRUCTION_PENDING,
    INSTRUCTION_DISPATCHED,
    INSTRUCTION_COMMITTED,
    INSTRUCTION_APPROVED,
    INSTRUCTION_REJECTED,
)

REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

# 지금은 큐브 배치 하나뿐입니다. 굴착(dig_depth 등)이 붙어도 params JSON만
# 바뀌도록 kind를 문자열로 열어 둡니다.
KIND_PLACE_CUBE = "place_cube"
KIND_EXCAVATE_PRIM = "excavate_prim"
KIND_GENERATED_SCRIPT = "generated_script"


class WorkInstruction(Base):
    """웹에서 Isaac Sim으로 내리는 단일 작업 지시."""

    __tablename__ = "work_instructions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default=KIND_PLACE_CUBE)
    # place_cube: {"position": {x,y,z}, "size": {x,y,z}, "label": str, "color": "#rrggbb"}
    # excavate_prim: {"equipment_prim_path": str, "target_prim_path": str, ...}
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=INSTRUCTION_PENDING, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by_username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    commits: Mapped[list["ExecutionCommit"]] = relationship(
        back_populates="instruction",
        cascade="all, delete-orphan",
        order_by="ExecutionCommit.committed_at",
    )

    @property
    def latest_commit(self) -> "ExecutionCommit | None":
        return self.commits[-1] if self.commits else None


class ExecutionCommit(Base):
    """Isaac Sim이 작업을 마치고 올리는 결과 한 건.

    한 지시가 반려되면 다시 실행할 수 있으므로 지시당 여러 Commit을 허용하고,
    맵에는 승인된 Commit만 반영합니다.
    """

    __tablename__ = "execution_commits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instruction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("work_instructions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded")

    # 실제로 배치된 결과. 지시값과 다를 수 있으므로 따로 기록합니다.
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 다음 단계에서 LiDAR/카메라/IMU가 채울 자리. 지금은 비어 있습니다.
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    adapter: Mapped[str] = mapped_column(String(60), nullable=False, default="isaac-adapter")
    committed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=REVIEW_PENDING, index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    instruction: Mapped[WorkInstruction] = relationship(back_populates="commits")


# 맵 렌더링은 "승인된 Commit"만 조회합니다. 이 조합에 인덱스를 겁니다.
Index("ix_execution_commits_review", ExecutionCommit.review_status, ExecutionCommit.committed_at)
