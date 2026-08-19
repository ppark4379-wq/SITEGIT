"""자연어 Work Package Compiler의 API 계약."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .isaac import InstructionResponse, StagePrimRecord, USD_PRIM_PATH_PATTERN, Vector3


ZoneId = Literal["A", "B", "C", "D", "UNSPECIFIED"]
ZoneLocation = Literal[
    "center",
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
    "unspecified",
]


class CubeDimensions(BaseModel):
    """데모 큐브 크기. 실제 시나리오에서는 작업 체적·깊이 스키마로 교체됩니다."""

    x: float = Field(ge=0.25, le=50)
    y: float = Field(ge=0.25, le=50)
    z: float = Field(ge=0.25, le=50)


class LLMWorkPackagePlan(BaseModel):
    """LLM이 자연어에서 추출하는 값. 실행 좌표는 포함하지 않습니다."""

    ready: bool
    operation: Literal["place_cube", "unsupported"]
    zone_id: ZoneId
    location: ZoneLocation
    label: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    size: CubeDimensions
    summary: str = Field(min_length=1, max_length=300)
    clarification_question: str = Field(default="", max_length=300)


class AIWorkPackageInterpretRequest(BaseModel):
    project_id: str = Field(default="SASANG-001", max_length=80)
    message: str = Field(min_length=3, max_length=1000)


class ZoneBounds(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class WorkPackageCheck(BaseModel):
    code: str
    ok: bool
    message: str


class AIWorkPackageDraft(BaseModel):
    """LLM 결과와 Backend의 결정론적 현장 검증을 합친 실행 전 초안."""

    project_id: str
    source_text: str
    plan: LLMWorkPackagePlan
    position: Vector3 | None = None
    zone_bounds: ZoneBounds | None = None
    target_volume_m3: float | None = None
    site_frame_source: str | None = None
    checks: list[WorkPackageCheck] = Field(default_factory=list)
    model: str


class AIWorkPackageDispatchRequest(BaseModel):
    project_id: str = Field(default="SASANG-001", max_length=80)
    source_text: str = Field(min_length=3, max_length=1000)
    plan: LLMWorkPackagePlan


class AIWorkPackageRecord(BaseModel):
    id: str
    project_id: str
    zone_id: str
    zone_location: str
    operation: str
    label: str
    color: str
    size: CubeDimensions
    position: Vector3
    target_volume_m3: float
    status: str
    source_text: str


class AIWorkPackageDispatchResponse(BaseModel):
    work_package: AIWorkPackageRecord
    instruction: InstructionResponse


class LLMExcavationPlan(BaseModel):
    """LLM output for a real-Stage excavation request.

    The references are descriptive only. Exact executable paths are resolved
    against the latest Stage inventory by the Backend.
    """

    ready: bool
    operation: Literal["excavate_prim", "unsupported"]
    equipment_ref: str = Field(default="", max_length=500)
    target_ref: str = Field(default="", max_length=500)
    zone_id: str = Field(default="", max_length=80)
    summary: str = Field(min_length=1, max_length=300)
    clarification_question: str = Field(default="", max_length=300)


class ExcavationInterpretRequest(BaseModel):
    project_id: str = Field(default="SASANG-001", max_length=80)
    message: str = Field(min_length=3, max_length=1000)
    equipment_prim_path: str | None = Field(
        default=None, pattern=USD_PRIM_PATH_PATTERN, max_length=500
    )
    target_prim_path: str | None = Field(
        default=None, pattern=USD_PRIM_PATH_PATTERN, max_length=500
    )


class ExcavationDraft(BaseModel):
    project_id: str
    source_text: str
    plan: LLMExcavationPlan
    equipment: StagePrimRecord | None = None
    target: StagePrimRecord | None = None
    checks: list[WorkPackageCheck] = Field(default_factory=list)
    model: str


class ExcavationDispatchRequest(ExcavationInterpretRequest):
    plan: LLMExcavationPlan


class ExcavationWorkPackageRecord(BaseModel):
    id: str
    project_id: str
    operation: Literal["excavate_prim"] = "excavate_prim"
    equipment: StagePrimRecord
    target: StagePrimRecord
    zone_id: str
    status: str
    source_text: str


class ExcavationDispatchResponse(BaseModel):
    work_package: ExcavationWorkPackageRecord
    instruction: InstructionResponse


class LLMCodeWorkPackagePlan(BaseModel):
    """Natural-language intent plus an LLM-authored restricted Isaac program."""

    ready: bool
    operation: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    equipment_ref: str = Field(default="", max_length=500)
    target_ref: str = Field(default="", max_length=500)
    zone_id: str = Field(default="", max_length=80)
    summary: str = Field(min_length=1, max_length=300)
    clarification_question: str = Field(default="", max_length=300)
    generated_code: str = Field(default="", max_length=12000)


class CodeWorkPackageInterpretRequest(BaseModel):
    project_id: str = Field(default="SASANG-001", max_length=80)
    message: str = Field(min_length=3, max_length=1500)


class CodeWorkPackageDraft(BaseModel):
    project_id: str
    source_text: str
    plan: LLMCodeWorkPackagePlan
    equipment: StagePrimRecord | None = None
    target: StagePrimRecord | None = None
    execution_target_path: str | None = Field(
        default=None, pattern=USD_PRIM_PATH_PATTERN, max_length=500
    )
    checks: list[WorkPackageCheck] = Field(default_factory=list)
    missing_resources: list[str] = Field(default_factory=list)
    generated_code: str = Field(default="", max_length=12000)
    executable: bool = False
    model: str


class CodeWorkPackageDispatchRequest(CodeWorkPackageInterpretRequest):
    plan: LLMCodeWorkPackagePlan


class CodeWorkPackageRecord(BaseModel):
    id: str
    project_id: str
    operation: str
    summary: str
    zone_id: str
    status: Literal["pending", "blocked"]
    source_text: str
    equipment: StagePrimRecord | None = None
    target: StagePrimRecord | None = None
    execution_target_path: str | None = Field(
        default=None, pattern=USD_PRIM_PATH_PATTERN, max_length=500
    )
    checks: list[WorkPackageCheck] = Field(default_factory=list)
    missing_resources: list[str] = Field(default_factory=list)
    generated_code: str = ""


class CodeWorkPackageDispatchResponse(BaseModel):
    work_package: CodeWorkPackageRecord
    instruction: InstructionResponse
