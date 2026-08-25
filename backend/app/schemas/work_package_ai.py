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


class PlanningCoordinate(BaseModel):
    """One drawing station in the normalized Isaac site frame."""

    station_m: float = Field(ge=0, le=100_000)
    x: float = Field(ge=-100_000, le=100_000)
    y: float = Field(ge=-100_000, le=100_000)
    z: float = Field(default=0, ge=-100_000, le=100_000)
    width_m: float = Field(gt=0, le=1_000)


class PlanningBounds(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class PlanningWorkfrontPreview(BaseModel):
    """One independently assignable excavation front from the scenario drawing."""

    id: str = Field(min_length=1, max_length=80)
    zone_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    station_start_m: float = Field(ge=0)
    station_end_m: float = Field(gt=0)
    equipment_id: str = Field(min_length=1, max_length=80)
    equipment_prim_path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    target_volume_m3: float = Field(ge=0)
    target_prim_paths: list[str] = Field(default_factory=list, max_length=8)
    bounds: PlanningBounds


class PlanningPhasePreview(BaseModel):
    """A manager-visible phase in the drawing-derived construction workflow."""

    id: str = Field(min_length=1, max_length=80)
    zone_id: str = Field(min_length=1, max_length=80)
    order: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=120)
    work_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    target_amount: float = Field(ge=0, le=1_000_000)
    target_unit: Literal["m", "m3", "ea"]
    estimated_hours: float = Field(ge=0, le=100_000)
    equipment: list[str] = Field(default_factory=list, max_length=20)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)


class PlanningRelocationPreview(BaseModel):
    """Reviewed geometry for one stationary excavator soil-relocation job."""

    source_prim_path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    source_position: PlanningCoordinate
    source_size_m: list[float] = Field(min_length=3, max_length=3)
    destination_position: PlanningCoordinate
    equipment_id: str = Field(min_length=1, max_length=80)
    equipment_prim_path: str = Field(pattern=USD_PRIM_PATH_PATTERN, max_length=500)
    equipment_position: PlanningCoordinate
    swing_degrees: float = Field(ge=-180, le=180)
    tracks_stationary: bool = True
    scoop_count: int = Field(default=5, ge=1, le=12)


class PlanningDesignPreview(BaseModel):
    """Canonical site drawing context returned alongside an LLM planning draft."""

    plan_id: str = Field(min_length=1, max_length=120)
    scenario_type: Literal["pipeline", "soil_relocation"] = "pipeline"
    revision: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=160)
    source_map: str = Field(min_length=1, max_length=160)
    work_area_id: str = Field(min_length=1, max_length=120)
    zone_id: str = Field(min_length=1, max_length=80)
    zone_assignment_mode: Literal["existing", "create_on_approval"] = "existing"
    location_confirmation_required: bool = False
    location_confirmation_prompt: str = Field(default="", max_length=300)
    zone_title: str = Field(min_length=1, max_length=120)
    work_area_label: str = Field(min_length=1, max_length=160)
    station_range: str = Field(min_length=1, max_length=120)
    total_length_m: float = Field(gt=0)
    design_depth_m: float = Field(gt=0)
    pipe_diameter_m: float = Field(gt=0)
    centerline: list[PlanningCoordinate] = Field(min_length=2, max_length=200)
    workfronts: list[PlanningWorkfrontPreview] = Field(default_factory=list, max_length=20)
    phases: list[PlanningPhasePreview] = Field(min_length=1, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    relocation: PlanningRelocationPreview | None = None


class PlanningWorkPackagePlan(BaseModel):
    """관리자 검토용 작업지시 초안. 실행 좌표나 Isaac Prim은 포함하지 않습니다."""

    ready: bool
    zone_id: ZoneId
    work_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    target_amount: float = Field(default=0, ge=0, le=1_000_000)
    target_unit: Literal["m", "m3", "ea"] = "m"
    segment: str = Field(default="관리자 확인 필요", max_length=120)
    equipment_hint: str = Field(default="관리자 배정 필요", max_length=120)
    successor_title: str = Field(default="후속 작업 미지정", max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    clarification_question: str = Field(default="", max_length=300)


class RemediationNarrative(BaseModel):
    """LLM-authored wording around Backend-owned corrective-work facts."""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    action_steps: list[str] = Field(min_length=2, max_length=6)
    manager_note: str = Field(min_length=1, max_length=300)


class PlanningWorkPackageDraft(BaseModel):
    project_id: str
    source_text: str
    plan: PlanningWorkPackagePlan
    design: PlanningDesignPreview | None = None
    model: str


class PlanningScenarioDispatchRequest(BaseModel):
    project_id: str = Field(default="SASANG-001", max_length=80)
    source_text: str = Field(min_length=3, max_length=1500)
    plan_id: str = Field(min_length=1, max_length=120)
    phase_id: str = Field(default="excavation", min_length=1, max_length=80)


class PlanningScenarioWorkPackageRecord(BaseModel):
    id: str
    phase_id: str
    workfront_id: str
    zone_id: str
    equipment_id: str
    target_prim_paths: list[str]
    status: Literal["pending", "blocked"]
    missing_resources: list[str] = Field(default_factory=list)


class PlanningScenarioDispatchResponse(BaseModel):
    plan_id: str
    phase_id: str
    work_packages: list[PlanningScenarioWorkPackageRecord]
    instructions: list[InstructionResponse]


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
