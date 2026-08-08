from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Vector3(BaseModel):
    """Isaac Sim 맵 좌표. 뷰어와 동일하게 Y가 위쪽입니다."""

    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    z: float = Field(ge=-100000, le=100000)


class CubeParams(BaseModel):
    """place_cube 지시의 파라미터."""

    position: Vector3
    size: Vector3 = Field(default_factory=lambda: Vector3(x=4, y=4, z=4))
    label: str = Field(default="시험 큐브", max_length=80)
    color: str = Field(default="#f0b429", pattern=r"^#[0-9a-fA-F]{6}$")


class InstructionCreate(BaseModel):
    project_id: str = Field(max_length=80)
    kind: Literal["place_cube"] = "place_cube"
    params: CubeParams
    note: str | None = Field(default=None, max_length=500)


class CommitCreate(BaseModel):
    """Isaac Adapter가 실행을 마치고 올리는 결과."""

    status: Literal["succeeded", "failed"] = "succeeded"
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    adapter: str = Field(default="isaac-adapter", max_length=60)


class ReviewDecision(BaseModel):
    """관리자의 결과 판정. 승인해야 맵에 반영됩니다."""

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class CommitResponse(BaseModel):
    id: str
    instruction_id: str
    attempt: int
    status: str
    result: dict[str, Any]
    evidence: dict[str, Any]
    adapter: str
    committed_by: str | None
    committed_at: datetime
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class InstructionResponse(BaseModel):
    id: str
    project_id: str
    kind: str
    params: dict[str, Any]
    status: str
    note: str | None
    created_by_username: str | None
    created_at: datetime
    updated_at: datetime
    dispatched_at: datetime | None
    commits: list[CommitResponse] = Field(default_factory=list)


class MapObject(BaseModel):
    """승인된 Commit을 뷰어가 그릴 수 있는 형태로 변환한 결과."""

    id: str
    instruction_id: str
    type: str
    label: str
    color: str
    position: Vector3
    size: Vector3
    approved_by: str | None
    approved_at: datetime | None


class MapObjectsResponse(BaseModel):
    project_id: str
    objects: list[MapObject]
    revision: str
