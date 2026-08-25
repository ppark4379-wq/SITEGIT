"""Load reviewed site plans used by the planning assistant.

The language model explains intent. Exact coordinates, quantities, equipment
bindings, dependencies, and acceptance rules come from versioned plan files.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from ...schemas.work_package_ai import PlanningDesignPreview, PlanningWorkPackagePlan


SITE_PLAN_DIRECTORY = Path(__file__).resolve().parents[4] / "contracts" / "site_plans"
DEFAULT_SITE_PLAN_PATH = SITE_PLAN_DIRECTORY / "demolition_pipeline_v1.json"
SOIL_RELOCATION_PLAN_PATH = SITE_PLAN_DIRECTORY / "demolition_soil_relocation_v1.json"


@lru_cache(maxsize=16)
def _load_raw_plan(path_text: str) -> dict[str, Any]:
    return json.loads(Path(path_text).read_text(encoding="utf-8"))


def _design_from_raw(raw: dict[str, Any]) -> PlanningDesignPreview:
    area = raw["work_area"]
    pipe = area.get("pipe") or {}
    return PlanningDesignPreview.model_validate(
        {
            "plan_id": raw["plan_id"],
            "scenario_type": raw.get("scenario_type", "pipeline"),
            "revision": raw["revision"],
            "title": raw["title"],
            "source_map": raw["source_map"],
            "work_area_id": area["id"],
            "zone_id": area["zone_id"],
            "zone_assignment_mode": area.get("zone_assignment_mode", "existing"),
            "location_confirmation_required": area.get(
                "location_confirmation_required", False
            ),
            "location_confirmation_prompt": area.get(
                "location_confirmation_prompt", ""
            ),
            "zone_title": area["zone_title"],
            "work_area_label": area["label"],
            "station_range": area["station_range"],
            "total_length_m": area["total_length_m"],
            "design_depth_m": area.get("design_depth_m", 1.0),
            "pipe_diameter_m": pipe.get("outside_diameter_m", 1.0),
            "centerline": area["centerline"],
            "workfronts": area.get("workfronts", []),
            "phases": raw["workflow"],
            "assumptions": raw.get("planning_assumptions", []),
            "relocation": area.get("relocation"),
        }
    )


def _load_design(path: Path, project_id: str) -> PlanningDesignPreview | None:
    if not path.is_file():
        return None
    raw = _load_raw_plan(str(path))
    if str(raw.get("project_id")) != project_id:
        return None
    return _design_from_raw(raw)


def load_pipeline_design(project_id: str) -> PlanningDesignPreview | None:
    """Return the reviewed Zone A pipeline construction plan."""

    return _load_design(DEFAULT_SITE_PLAN_PATH, project_id)


def load_soil_relocation_design(project_id: str) -> PlanningDesignPreview | None:
    """Return the drawing-derived candidate for a stationary relocation job."""

    return _load_design(SOIL_RELOCATION_PLAN_PATH, project_id)


def _normalized(message: str) -> str:
    return re.sub(r"\s+", "", message).casefold()


def is_soil_relocation_request(message: str) -> bool:
    """Recognize a natural-language pile-to-pile relocation request."""

    normalized = _normalized(message)
    explicit = any(
        keyword in normalized
        for keyword in (
            "토사이동",
            "토사옮기",
            "흙더미옮기",
            "흙옮기",
            "적치위치변경",
            "zoneb",
            "b구역",
            "동측토사",
        )
    )
    soil_noun = any(token in normalized for token in ("토사", "흙더미", "흙"))
    relocation_verb = any(
        token in normalized for token in ("옮겨", "옮기", "이동", "적치", "쌓아")
    )
    return explicit or (soil_noun and relocation_verb)


def is_pipeline_plan_request(message: str) -> bool:
    """Recognize the existing Zone A pipeline workflow."""

    normalized = _normalized(message)
    return any(
        keyword in normalized
        for keyword in ("관로", "터파기", "되메우기", "되메움", "관매설", "배관공사")
    )


def load_site_design_for_request(
    project_id: str,
    message: str,
) -> PlanningDesignPreview | None:
    """Select the authoritative plan matching the manager's request."""

    if is_soil_relocation_request(message):
        return load_soil_relocation_design(project_id)
    if is_pipeline_plan_request(message):
        return load_pipeline_design(project_id)
    return None


def design_prompt_context(design: PlanningDesignPreview) -> str:
    """Produce a compact authoritative plan excerpt for the LLM prompt."""

    phase_lines = "; ".join(
        f"{phase.order}단계={phase.title} {phase.target_amount:g}{phase.target_unit}, "
        f"장비 {','.join(phase.equipment)}, 선행 {','.join(phase.depends_on) or '없음'}"
        for phase in design.phases
    )
    front_lines = "; ".join(
        f"{front.label}: {front.equipment_id}, {front.target_volume_m3:g}m3"
        for front in design.workfronts
    )
    relocation_line = ""
    if design.relocation:
        item = design.relocation
        relocation_line = (
            f" 토사 이동: {item.source_prim_path}에서 "
            f"({item.destination_position.x:g},{item.destination_position.y:g})m로 이동, "
            f"장비 {item.equipment_id}, 궤도 고정={item.tracks_stationary}, "
            f"상부 선회 {item.swing_degrees:g}도, {item.scoop_count}회 적재."
        )
    zone_context = (
        f"승인 후보 Zone {design.zone_id}(관리자 승인 전 미생성)"
        if design.zone_assignment_mode == "create_on_approval"
        else f"Zone {design.zone_id}"
    )
    return (
        "[승인된 현장 도면: 아래 값은 추측하거나 변경하지 말 것]\n"
        f"도면 {design.plan_id} Rev.{design.revision}, {zone_context} "
        f"{design.zone_title}, 작업구역 {design.work_area_id} "
        f"({design.work_area_label}), {design.station_range}.\n"
        f"공정: {phase_lines}. 작업전선: {front_lines or '단일 작업전선'}."
        f"{relocation_line}\n"
        "사용자가 해당 구역 작업을 요청하면 이 도면을 기준으로 계획한다."
    )


def apply_pipeline_design_defaults(
    message: str,
    plan: PlanningWorkPackagePlan,
    design: PlanningDesignPreview,
) -> PlanningWorkPackagePlan:
    """Replace guessed pipeline values with reviewed drawing values."""

    normalized = _normalized(message)
    if any(token in normalized for token in ("되메우기", "되메움", "복토")):
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
                "zone_id": design.zone_id,
                "work_type": "관로 공사 통합 계획",
                "title": f"{design.work_area_label} 관로 공사",
                "target_amount": design.total_length_m,
                "target_unit": "m",
                "segment": design.station_range,
                "equipment_hint": "굴착기 3대 + 관로 설치·다짐 장비",
                "successor_title": "터파기 → 관로 설치 → 되메우기",
                "summary": (
                    f"도면 {design.plan_id} Rev.{design.revision} 기준 총 "
                    f"{design.total_length_m:g}m 관로 공사를 3개 작업전선으로 계획합니다."
                ),
                "clarification_question": "",
            }
        )
    return plan.model_copy(
        update={
            "ready": True,
            "zone_id": design.zone_id,
            "work_type": phase.title,
            "title": f"{design.work_area_label} {phase.title}",
            "target_amount": phase.target_amount,
            "target_unit": phase.target_unit,
            "segment": design.station_range,
            "equipment_hint": " + ".join(phase.equipment),
            "successor_title": successor,
            "summary": (
                f"도면 {design.plan_id} Rev.{design.revision}의 {design.station_range}에서 "
                f"{phase.title} {phase.target_amount:g}{phase.target_unit}를 계획합니다."
            ),
            "clarification_question": "",
        }
    )


def apply_soil_relocation_design_defaults(
    plan: PlanningWorkPackagePlan,
    design: PlanningDesignPreview,
) -> PlanningWorkPackagePlan:
    """Apply drawing candidate values without activating its future Zone yet."""

    phase = design.phases[0]
    relocation = design.relocation
    if relocation is None:
        return plan
    return plan.model_copy(
        update={
            "ready": True,
            "zone_id": design.zone_id,
            "work_type": phase.title,
            "title": design.work_area_label,
            "target_amount": phase.target_amount,
            "target_unit": phase.target_unit,
            "segment": design.station_range,
            "equipment_hint": relocation.equipment_id,
            "successor_title": "토사 이동 완료 검측",
            "summary": (
                f"현장 도면에서 동측 공터의 기존 흙더미와 인접 적치 위치를 작업 후보로 "
                f"찾았습니다. 표시된 위치가 맞다면 승인 시 Zone {design.zone_id}를 만들고, "
                f"{relocation.equipment_id}의 궤도를 고정한 채 상부체만 "
                f"{relocation.swing_degrees:g}도 선회해 {relocation.scoop_count}회에 나누어 "
                "토사를 옮깁니다."
            ),
            "clarification_question": "",
        }
    )


def apply_site_design_defaults(
    message: str,
    plan: PlanningWorkPackagePlan,
    design: PlanningDesignPreview,
) -> PlanningWorkPackagePlan:
    """Apply deterministic values from the selected scenario plan."""

    if design.scenario_type == "soil_relocation":
        return apply_soil_relocation_design_defaults(plan, design)
    return apply_pipeline_design_defaults(message, plan, design)


def get_raw_pipeline_plan(plan_id: str, project_id: str) -> dict[str, Any]:
    """Return an authoritative plan at the deterministic dispatch boundary."""

    for path in (DEFAULT_SITE_PLAN_PATH, SOIL_RELOCATION_PLAN_PATH):
        if not path.is_file():
            continue
        raw = _load_raw_plan(str(path))
        if raw.get("plan_id") == plan_id and raw.get("project_id") == project_id:
            _design_from_raw(raw)
            return raw
    raise LookupError("요청한 프로젝트의 승인된 도면을 찾지 못했습니다.")
