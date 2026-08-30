from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    role: Literal["equipment", "diggable", "scene_object"]
    world_position: Vector3
    bounds_size: Vector3 = Field(default_factory=lambda: Vector3(x=0, y=0, z=0))
    active: bool = True
    zone_id: str | None = Field(default=None, max_length=80)
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    display_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    geometry: dict[str, Any] | None = None


class StageInventoryUpdate(BaseModel):
    project_id: str = Field(max_length=80)
    scenario_id: str | None = Field(default=None, min_length=1, max_length=120)
    stage_identifier: str = Field(default="anonymous-stage", max_length=500)
    equipment: list[StagePrimRecord] = Field(default_factory=list, max_length=100)
    diggable_targets: list[StagePrimRecord] = Field(default_factory=list, max_length=500)
    scene_objects: list[StagePrimRecord] = Field(default_factory=list, max_length=500)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageInventoryResponse(StageInventoryUpdate):
    connected: bool
    age_seconds: float


class StageBranchHeadResponse(BaseModel):
    """Latest manager-approved Isaac Stage snapshot for one branch."""

    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    branch: str
    scenario_id: str | None = Field(default=None, max_length=120)
    commit_id: str
    parent_commit_id: str | None = None
    instruction_id: str
    approved_by: str
    approved_at: datetime
    storage_key: str
    sha256: str
    size_bytes: int = Field(ge=0)


class QuantityMeasurement(BaseModel):
    """One measured work quantity with an explicit unit and calculation method."""

    value: float
    unit: str = Field(min_length=1, max_length=40)
    method: str | None = Field(default=None, max_length=120)
    estimated: bool = False


class GeometryChange(BaseModel):
    """Scenario-neutral before/after surface change calculated from sensor data."""

    available: bool = False
    method: str | None = Field(default=None, max_length=120)
    compared_cell_count: int = Field(default=0, ge=0)
    changed_cell_count: int = Field(default=0, ge=0)
    cell_size_m: float | None = Field(default=None, gt=0)
    removed_volume_m3: float | None = Field(default=None, ge=0)
    added_volume_m3: float | None = Field(default=None, ge=0)
    net_volume_change_m3: float | None = None
    mean_absolute_height_change_m: float | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=500)


class ExecutionEventRecord(BaseModel):
    """Timestamped fact emitted while one Isaac Work Package is executed."""

    sequence: int = Field(ge=1)
    timestamp: datetime
    elapsed_seconds: float = Field(ge=0)
    event_type: str = Field(min_length=1, max_length=80)
    work_state: str = Field(min_length=1, max_length=80)
    equipment_prim_path: str | None = Field(default=None, max_length=500)
    target_prim_path: str | None = Field(default=None, max_length=500)
    position: Vector3 | None = None
    performed_quantity: QuantityMeasurement | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SensorArtifact(BaseModel):
    """A stored camera, LiDAR, IMU, Stage, or manifest artifact."""

    sensor_type: Literal["camera", "lidar", "imu", "stage", "telemetry", "manifest"]
    phase: Literal["before", "during", "after", "execution"]
    available: bool
    captured_at: datetime
    storage_key: str | None = Field(default=None, max_length=1000)
    format: str | None = Field(default=None, max_length=40)
    source: str | None = Field(default=None, max_length=160)
    sample_count: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceQuality(BaseModel):
    """Completeness is reported, not used as a hidden acceptance rule."""

    required_sensor_types: list[str] = Field(default_factory=list)
    available_sensor_types: list[str] = Field(default_factory=list)
    missing_sensor_types: list[str] = Field(default_factory=list)
    completeness_ratio: float = Field(ge=0, le=1)
    timestamps_valid: bool = True
    notes: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    """Stable Adapter-to-Backend contract for a completed execution attempt."""

    schema_version: Literal["1.0"] = "1.0"
    evidence_id: str = Field(min_length=1, max_length=100)
    instruction_id: str = Field(min_length=1, max_length=100)
    execution_id: str = Field(min_length=1, max_length=100)
    work_package_id: str | None = Field(default=None, max_length=100)
    equipment_id: str | None = Field(default=None, max_length=160)
    zone_id: str | None = Field(default=None, max_length=80)
    source: str = Field(default="isaac-sim", max_length=80)
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0)
    events: list[ExecutionEventRecord] = Field(default_factory=list)
    artifacts: list[SensorArtifact] = Field(default_factory=list)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    quality: EvidenceQuality

    @model_validator(mode="after")
    def validate_time_range(self) -> "EvidenceBundle":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be earlier than started_at")
        return self


class WorkResultSummary(BaseModel):
    """Common result envelope; operation-specific read-back fields remain allowed."""

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1.0"] = "1.0"
    operation: str = Field(min_length=1, max_length=120)
    execution_id: str = Field(min_length=1, max_length=100)
    duration_seconds: float = Field(ge=0)
    performed_quantity: QuantityMeasurement | None = None
    geometry_change: GeometryChange = Field(default_factory=GeometryChange)


class CommitCreate(BaseModel):
    """Isaac Adapter가 실행을 마치고 올리는 결과."""

    status: Literal["succeeded", "failed"] = "succeeded"
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    adapter: str = Field(default="isaac-adapter", max_length=60)

    @model_validator(mode="after")
    def validate_versioned_payloads(self) -> "CommitCreate":
        # Older adapters can still send their existing unversioned dicts while
        # versioned payloads are strictly checked at the API boundary.
        result_summary = None
        evidence_bundle = None
        if self.result.get("schema_version") is not None:
            result_summary = WorkResultSummary.model_validate(self.result)
        if self.evidence.get("schema_version") is not None:
            evidence_bundle = EvidenceBundle.model_validate(self.evidence)
        if (
            result_summary is not None
            and evidence_bundle is not None
            and result_summary.execution_id != evidence_bundle.execution_id
        ):
            raise ValueError("result and evidence must reference the same execution_id")
        return self


class ReviewDecision(BaseModel):
    """관리자의 결과 판정. 승인해야 맵에 반영됩니다."""

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class SupplementalEvidenceFile(BaseModel):
    """Metadata for one manager-selected supplemental Evidence file."""

    name: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(default=0, ge=0, le=2_000_000_000)
    content_type: str | None = Field(default=None, max_length=120)


class SupplementalEvidenceSubmission(BaseModel):
    """Demo submission used to reopen a rejected Commit for review."""

    files: list[SupplementalEvidenceFile] = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class InstructionProgressUpdate(BaseModel):
    """Live progress reported by the Isaac Adapter during one work front."""

    phase: str = Field(default="excavating", min_length=1, max_length=80)
    step_index: int = Field(ge=0, le=1000)
    step_count: int = Field(ge=1, le=1000)
    progress_ratio: float = Field(ge=0.0, le=1.0)
    removed_volume_m3: float = Field(default=0.0, ge=0.0)
    installed_length_m: float = Field(default=0.0, ge=0.0)
    backfilled_volume_m3: float = Field(default=0.0, ge=0.0)


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
    geometry: dict[str, Any] | None = None


class MapConflict(BaseModel):
    """A rejected execution proposal retained outside the published map."""

    id: str
    commit_id: str
    instruction_id: str
    label: str
    reason: str
    position: Vector3 | None = None
    size: Vector3 | None = None
    prim_path: str | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None


class MapTimelineStep(BaseModel):
    """One immutable approved Commit and its replayable map delta."""

    commit_id: str
    instruction_id: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    objects: list[MapObject] = Field(default_factory=list)


class MapObjectsResponse(BaseModel):
    project_id: str
    objects: list[MapObject]
    baseline_diggable_targets: list[StagePrimRecord] = Field(default_factory=list)
    baseline_scene_objects: list[StagePrimRecord] = Field(default_factory=list)
    timeline: list[MapTimelineStep] = Field(default_factory=list)
    conflicts: list[MapConflict] = Field(default_factory=list)
    revision: str
