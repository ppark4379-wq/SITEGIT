"""Load the scenario drawing used by the planning assistant.

The LLM may explain the user's intent, but dimensions, quantities, work fronts,
Prim paths, dependencies and acceptance rules come from this reviewed file.
This keeps the plan deterministic and prevents a small local model from
inventing construction geometry.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from ...schemas.work_package_ai import (
    PlanningDesignPreview,
    PlanningWorkPackagePlan,
)


SITE_PLAN_DIRECTORY = Path(__file__).resolve().parents[4] / "contracts" / "site_plans"
DEFAULT_SITE_PLAN_PATH = SITE_PLAN_DIRECTORY / "demolition_pipeline_v1.json"


@lru_cache(maxsize=8)
def _load_raw_plan(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    return json.loads(path.read_text(encoding="utf-8"))


def load_pipeline_design(project_id: str) -> PlanningDesignPreview | None:
    """Return the canonical drawing preview for a matching project."""

    if not DEFAULT_SITE_PLAN_PATH.is_file():
        return None
    raw = _load_raw_plan(str(DEFAULT_SITE_PLAN_PATH))
    if str(raw.get("project_id")) != project_id:
        return None
    area = raw["work_area"]
    pipe = area["pipe"]
    return PlanningDesignPreview.model_validate(
        {
            "plan_id": raw["plan_id"],
            "revision": raw["revision"],
            "title": raw["title"],
            "source_map": raw["source_map"],
            "work_area_id": area["id"],
            "work_area_label": area["label"],
            "station_range": area["station_range"],
            "total_length_m": area["total_length_m"],
            "design_depth_m": area["design_depth_m"],
            "pipe_diameter_m": pipe["outside_diameter_m"],
            "centerline": area["centerline"],
            "workfronts": area["workfronts"],
            "phases": raw["workflow"],
            "assumptions": raw.get("planning_assumptions", []),
        }
    )


def is_pipeline_plan_request(message: str) -> bool:
    normalized = re.sub(r"\s+", "", message).casefold()
    return any(
        keyword in normalized
        for keyword in ("관로", "터파기", "되메우", "되메움", "관매설", "배관공사")
    )


def design_prompt_context(design: PlanningDesignPreview) -> str:
    """Produce a compact, authoritative drawing excerpt for the LLM prompt."""

    phase_lines = "; ".join(
        f"Zone {phase.zone_id}={phase.order}.{phase.title} "
        f"{phase.target_amount:g}{phase.target_unit}, "
        f"장비 {','.join(phase.equipment)}, 선행 {','.join(phase.depends_on) or '없음'}"
        for phase in design.phases
    )
    front_lines = "; ".join(
        f"Zone A 작업전선 {index} {front.station_start_m:g}~{front.station_end_m:g}m "
        f"{front.equipment_id} {front.target_volume_m3:g}m3"
        for index, front in enumerate(design.workfronts, start=1)
    )
    return (
        "[승인된 현장 도면 — 이 값은 추측하거나 변경하지 말 것]\n"
        f"도면 {design.plan_id} Rev.{design.revision}, 작업구역 {design.work_area_id} "
        f"({design.work_area_label}), {design.station_range}, 총연장 {design.total_length_m:g}m, "
        f"설계깊이 {design.design_depth_m:g}m, 관 외경 {design.pipe_diameter_m:g}m.\n"
        f"공정: {phase_lines}.\n작업전선: {front_lines}.\n"
        "사용자가 이 구역/현재 구역의 관로 공사를 요청하면 위 도면 전체 구간을 뜻합니다."
    )


def apply_pipeline_design_defaults(
    message: str,
    plan: PlanningWorkPackagePlan,
    design: PlanningDesignPreview,
) -> PlanningWorkPackagePlan:
    """Replace guessed plan values with reviewed drawing values."""

    if not is_pipeline_plan_request(message):
        return plan
    normalized = re.sub(r"\s+", "", message).casefold()
    if any(token in normalized for token in ("되메우", "되메움", "복토")):
        phase = next(item for item in design.phases if item.id == "backfill")
        successor = "관로 공사 완료 검측"
    elif any(token in normalized for token in ("관로설치", "관매설", "관로넣", "배관설치")):
        phase = next(item for item in design.phases if item.id == "pipe_installation")
        successor = "되메우기"
    elif any(token in normalized for token in ("터파기", "굴착", "파내")):
        phase = next(item for item in design.phases if item.id == "excavation")
        successor = "관로 설치"
    else:
        return plan.model_copy(
            update={
                "ready": True,
                "zone_id": "A",
                "work_type": "관로 공사 통합 계획",
                "title": f"{design.work_area_label} 관로 공사",
                "target_amount": design.total_length_m,
                "target_unit": "m",
                "segment": design.station_range,
                "equipment_hint": "굴착기 3대 + 관로 설치·다짐 장비",
                "successor_title": "터파기 → 관로 설치 → 되메우기",
                "summary": (
                    f"도면 {design.plan_id} Rev.{design.revision}을 기준으로 "
                    f"총 {design.total_length_m:g}m 구간을 3개 작업전선으로 나누어 "
                    "터파기, 관로 설치, 되메우기 순서로 계획했습니다."
                ),
                "clarification_question": "",
            }
        )
    return plan.model_copy(
        update={
            "ready": True,
            "zone_id": phase.zone_id,
            "work_type": phase.title,
            "title": f"{design.work_area_label} {phase.title}",
            "target_amount": phase.target_amount,
            "target_unit": phase.target_unit,
            "segment": design.station_range,
            "equipment_hint": " + ".join(phase.equipment),
            "successor_title": successor,
            "summary": (
                f"도면 {design.plan_id} Rev.{design.revision}의 {design.station_range}에서 "
                f"{phase.title} {phase.target_amount:g}{phase.target_unit}을 계획했습니다."
            ),
            "clarification_question": "",
        }
    )


def get_raw_pipeline_plan(plan_id: str, project_id: str) -> dict[str, Any]:
    """Return the validated raw plan used by deterministic dispatch."""

    raw = _load_raw_plan(str(DEFAULT_SITE_PLAN_PATH))
    if raw.get("plan_id") != plan_id or raw.get("project_id") != project_id:
        raise LookupError("요청한 프로젝트의 관로 도면을 찾지 못했습니다.")
    # Validation above is intentionally repeated at the API boundary.
    if load_pipeline_design(project_id) is None:
        raise LookupError("관로 도면을 검증하지 못했습니다.")
    return raw
