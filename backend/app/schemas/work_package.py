from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WorkPackageStatus = Literal["DRAFT", "READY", "RUNNING", "REVIEW", "REWORK", "HOLD", "RELEASE_READY", "RELEASED"]
CriterionStatus = Literal["PASS", "FAIL"]


class CompletionCriterion(BaseModel):
    code: str = Field(max_length=60)
    label: str = Field(max_length=160)


class WorkPackageCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    project_id: str = Field(default="SASANG-001", max_length=80)
    work_type: str = Field(default="EXCAVATION", max_length=40)
    zone_id: str = Field(max_length=80)
    title: str = Field(max_length=160)
    description: str | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    completion_criteria: list[CompletionCriterion] = Field(default_factory=list)
    required_results: list[str] = Field(default_factory=list)
    predecessor_wp_id: str | None = Field(default=None, max_length=80)
    successor_wp_id: str | None = Field(default=None, max_length=80)


class ProgressResult(BaseModel):
    completed: float = Field(ge=0)
    target: float = Field(gt=0)
    unit: str = Field(default="m3", max_length=20)
    percentage: float = Field(ge=0, le=100)


class CriterionResult(BaseModel):
    code: str
    label: str
    status: CriterionStatus
    reason: str | None = None


class EvaluationCreate(BaseModel):
    progress: ProgressResult
    criteria: list[CriterionResult] = Field(min_length=1)


class EvaluationResponse(EvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_package_id: str
    overall: Literal["PASS", "FAIL"]
    recommended_action: Literal["REWORK", "RELEASE_READY"]
    created_at: datetime


class ReworkCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    target_area: dict[str, Any] = Field(default_factory=dict)


class WorkPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    work_type: str
    zone_id: str
    title: str
    description: str | None
    target_json: dict[str, Any]
    constraints_json: dict[str, Any]
    completion_criteria_json: list
    required_results_json: list
    status: str
    predecessor_wp_id: str | None
    successor_wp_id: str | None
    parent_wp_id: str | None
    release_gate: str
    rework_reason: str | None
    failed_criteria_json: list
    target_area_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class VersionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    work_package_id: str
    event_type: str
    from_status: str | None
    to_status: str | None
    actor: str | None
    reason: str | None
    reference_id: str | None
    created_at: datetime


class SuccessorResponse(BaseModel):
    predecessor_id: str
    successor: WorkPackageResponse | None
    release_gate: str
