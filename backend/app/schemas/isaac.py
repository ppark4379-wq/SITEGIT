from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

USD_PRIM_PATH_PATTERN = r"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$"
MAX_EXCAVATION_TARGET_SPAN_M = 25.0


class Vector3(BaseModel):
    """Isaac Sim 현장 좌표. Z가 높이이고 지면 기준은 Z=0입니다."""

    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    z: float = Field(ge=-100000, le=100000)


class CubeParams(BaseModel):
    """place_cube 지시의 파라미터."""

    position: Vector3
    size: Vector3 = Field(default_factory=lambda: Vector3(x=4, y=4, z=4))
    label: str = Field(default="시험 큐브", max_length=80)
    color: str = Field(default="#f0b429", pattern=r"^#[0-9a-fA-F]{6}$")
    work_package_id: str | None = Field(default=None, max_length=80)
    zone_id: str | None = Field(default=None, max_length=20)
    zone_location: str | None = Field(default=None, max_length=30)


class ExcavationParams(BaseModel):
    """실제 Isaac Stage의 장비 Prim과 굴착 대상 Prim을 연결하는 지시입니다."""

    equipment_prim_path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    target_prim_path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    equipment_name: str = Field(min_length=1, max_length=120)
    target_name: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=160)
    work_package_id: str = Field(max_length=80)
    zone_id: str | None = Field(default=None, max_length=40)
    approach_distance_m: float = Field(default=3.0, ge=0.5, le=20.0)
    animation_seconds: float = Field(default=3.0, ge=0.5, le=30.0)
    source_text: str | None = Field(default=None, max_length=1000)


class InstructionCreate(BaseModel):
    project_id: str = Field(max_length=80)
    kind: Literal["place_cube", "excavate_prim"] = "place_cube"
    params: CubeParams | ExcavationParams
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_params_for_kind(self) -> "InstructionCreate":
        expected = CubeParams if self.kind == "place_cube" else ExcavationParams
        if not isinstance(self.params, expected):
            raise ValueError(f"{self.kind} requires {expected.__name__}")
        return self


class StagePrimRecord(BaseModel):
    """Isaac Adapter가 실제 Stage에서 읽어 등록한 Prim 한 개입니다."""

    path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    name: str = Field(min_length=1, max_length=160)
    type_name: str = Field(default="Xform", max_length=80)
    role: Literal["equipment", "diggable"]
    world_position: Vector3
    bounds_size: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    active: bool = True


class StageInventoryUpdate(BaseModel):
    project_id: str = Field(max_length=80)
    stage_identifier: str = Field(default="anonymous-stage", max_length=500)
    equipment: list[StagePrimRecord] = Field(default_factory=list, max_length=100)
    diggable_targets: list[StagePrimRecord] = Field(default_factory=list, max_length=500)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageInventoryResponse(StageInventoryUpdate):
    connected: bool
    age_seconds: float


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
    prim_path: str | None = None


class MapObjectsResponse(BaseModel):
    project_id: str
    objects: list[MapObject]
    revision: str
