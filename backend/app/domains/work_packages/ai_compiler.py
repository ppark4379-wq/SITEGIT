"""자연어를 검증 가능한 데모 Work Package로 컴파일합니다.

LLM은 사용자의 표현을 구조화할 뿐 실행 좌표를 결정하지 않습니다. 좌표는 이
모듈이 현장 프레임과 Zone 규칙으로 계산합니다. 따라서 프롬프트가 바뀌거나 모델이
잘못된 값을 내더라도 현장 밖 좌표를 Isaac에 바로 전달하지 않습니다.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from ...core.config import Settings
from ...schemas.isaac import (
    MAX_EXCAVATION_TARGET_SPAN_M,
    StageInventoryResponse,
    StagePrimRecord,
    Vector3,
)
from ...schemas.work_package_ai import (
    AIWorkPackageDraft,
    ExcavationDraft,
    LLMExcavationPlan,
    LLMWorkPackagePlan,
    PlanningWorkPackagePlan,
    WorkPackageCheck,
    ZoneBounds,
)


def compile_planning_work_package(
    message: str,
    settings: Settings,
    drawing_context: str = "",
) -> PlanningWorkPackagePlan:
    """실행과 분리된 관리자 검토용 작업지시 초안을 만듭니다."""
    schema = PlanningWorkPackagePlan.model_json_schema()
    system_prompt = """당신은 건설 현장 관리자용 SiteGit Planning Assistant입니다.
사용자의 한국어 요청을 작업지시 초안으로 구조화하세요. 실행 좌표, Isaac Prim path,
장비 제어 명령은 절대 만들지 않습니다. 불명확한 핵심 값은 추측하지 말고
clarification_question에 질문하며 ready=false로 반환하세요. Zone은 A-D 중 하나이며,
공종, 제목, 목표량/단위, 구간, 권장 장비, 후속 작업을 간결하게 작성하세요.
target_unit은 m, m3, ea 중 하나입니다. 승인된 현장 도면 문맥이 제공되면 사용자의
짧은 지시를 그 도면에 연결하고, 수량·구간·장비·공정 순서는 반드시 도면 값을
사용하세요. 도면에 있는 값은 다시 계산하거나 추측하지 마세요."""
    if drawing_context:
        system_prompt = f"{system_prompt}\n\n{drawing_context}"
    try:
        endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
            response = client.post(endpoint, json={
                "model": settings.ollama_model,
                "messages": [{"role":"system","content":system_prompt},{"role":"user","content":message}],
                "stream": False, "think": False, "format": schema,
                "options": {"temperature": 0}, "keep_alive": "10m",
            })
        if response.status_code == 404:
            raise WorkPackageLLMUnavailable(f"Ollama 모델 '{settings.ollama_model}'을 찾지 못했습니다.")
        response.raise_for_status()
        output_text = response.json().get("message", {}).get("content", "")
        if not output_text:
            raise WorkPackageLLMError("LLM이 작업지시 초안을 반환하지 않았습니다.")
        return PlanningWorkPackagePlan.model_validate_json(output_text)
    except (WorkPackageLLMUnavailable, WorkPackageLLMError):
        raise
    except httpx.ConnectError as error:
        raise WorkPackageLLMUnavailable("로컬 Ollama에 연결할 수 없습니다.") from error
    except httpx.TimeoutException as error:
        raise WorkPackageLLMError("Ollama 응답 시간이 초과되었습니다.") from error
    except (httpx.HTTPError, ValidationError, ValueError, json.JSONDecodeError) as error:
        raise WorkPackageLLMError("LLM 작업지시 응답을 검증하지 못했습니다.") from error


DEFAULT_SITE_BOUNDS = {
    "min": [-106.0, -114.0, 0.0],
    "max": [106.0, 114.0, 12.0],
}

LOCATION_FACTORS: dict[str, tuple[float, float]] = {
    "center": (0.5, 0.5),
    "north": (0.5, 0.78),
    "south": (0.5, 0.22),
    "east": (0.78, 0.5),
    "west": (0.22, 0.5),
    "northeast": (0.78, 0.78),
    "northwest": (0.22, 0.78),
    "southeast": (0.78, 0.22),
    "southwest": (0.22, 0.22),
}


class WorkPackageLLMUnavailable(RuntimeError):
    """LLM 설정 또는 SDK가 없어 자연어 해석을 실행할 수 없습니다."""


class WorkPackageLLMError(RuntimeError):
    """LLM 호출 또는 구조화 결과 검증에 실패했습니다."""


def _structured_output_schema() -> dict[str, Any]:
    """Ollama Structured Outputs에 전달할 엄격한 JSON Schema."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ready": {"type": "boolean"},
            "operation": {"type": "string", "enum": ["place_cube", "unsupported"]},
            "zone_id": {
                "type": "string",
                "enum": ["A", "B", "C", "D", "UNSPECIFIED"],
            },
            "location": {
                "type": "string",
                "enum": [
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
                ],
            },
            "label": {"type": "string", "minLength": 1, "maxLength": 80},
            "color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
            "size": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x": {"type": "number", "minimum": 0.25, "maximum": 50},
                    "y": {"type": "number", "minimum": 0.25, "maximum": 50},
                    "z": {"type": "number", "minimum": 0.25, "maximum": 50},
                },
                "required": ["x", "y", "z"],
            },
            "summary": {"type": "string", "minLength": 1, "maxLength": 300},
            "clarification_question": {"type": "string", "maxLength": 300},
        },
        "required": [
            "ready",
            "operation",
            "zone_id",
            "location",
            "label",
            "color",
            "size",
            "summary",
            "clarification_question",
        ],
    }


def compile_natural_language(message: str, settings: Settings) -> LLMWorkPackagePlan:
    """로컬 Ollama로 자연어를 실행 전 Work Package 초안으로 바꿉니다."""
    system_prompt = """당신은 SiteGit 데모 Work Package Compiler입니다.
사용자의 한국어 자연어에서 데모 큐브 배치 작업만 추출합니다.

규칙:
- 지원 작업은 place_cube 하나뿐입니다. 굴착·이동 등은 operation=unsupported, ready=false입니다.
- 문장에 '큐브'와 '배치', '놓아', '생성' 중 하나가 함께 있으면 반드시 operation=place_cube입니다.
- operation=unsupported는 큐브 배치가 아닌 작업에만 사용합니다.
- Zone은 A, B, C, D만 허용합니다. 없으면 UNSPECIFIED와 ready=false입니다.
- 위치 표현은 center/north/south/east/west/northeast/northwest/southeast/southwest로 정규화합니다.
- Zone만 있고 세부 위치가 없으면 center를 사용합니다.
- 색상은 반드시 #RRGGBB입니다. 빨간색=#FF0000, 노란색=#FFD700, 파란색=#0000FF,
  초록색=#00FF00, 흰색=#FFFFFF, 검은색=#000000으로 변환하며 임의 색상으로 바꾸지 않습니다.
- 크기 세 축이 모두 있어야 ready=true입니다. 단위는 meter입니다.
- 실행 좌표는 절대 만들지 마세요. Backend가 Zone으로부터 계산합니다.
- clarification_question은 ready=true이면 빈 문자열입니다.

정확한 예시:
입력: Zone A 중앙에 빨간색 큐브를 5m x 5m x 5m로 배치해줘
결과: {"ready":true,"operation":"place_cube","zone_id":"A","location":"center",
"label":"Zone A 빨간 큐브","color":"#FF0000","size":{"x":5,"y":5,"z":5},
"summary":"Zone A 중앙에 빨간색 5m 큐브를 배치합니다.","clarification_question":""}
"""
    try:
        endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
            response = client.post(
                endpoint,
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                    "think": False,
                    "format": _structured_output_schema(),
                    "options": {"temperature": 0},
                    "keep_alive": "10m",
                },
            )
        if response.status_code == 404:
            raise WorkPackageLLMUnavailable(
                f"Ollama 모델 '{settings.ollama_model}'을 찾지 못했습니다. "
                f"ollama pull {settings.ollama_model}을 실행하세요."
            )
        response.raise_for_status()
        payload = response.json()
        output_text = payload.get("message", {}).get("content", "")
        if not output_text:
            raise WorkPackageLLMError("LLM이 구조화된 Work Package를 반환하지 않았습니다.")
        return LLMWorkPackagePlan.model_validate_json(output_text)
    except (WorkPackageLLMUnavailable, WorkPackageLLMError):
        raise
    except httpx.ConnectError as error:
        raise WorkPackageLLMUnavailable(
            "로컬 Ollama에 연결할 수 없습니다. Ollama 앱이 실행 중인지 확인하세요."
        ) from error
    except httpx.TimeoutException as error:
        raise WorkPackageLLMError(
            "Ollama 응답 시간이 초과되었습니다. 모델 로딩 후 다시 시도하세요."
        ) from error
    except httpx.HTTPStatusError as error:
        raise WorkPackageLLMError(
            f"Ollama가 HTTP {error.response.status_code} 오류를 반환했습니다."
        ) from error
    except httpx.RequestError as error:
        raise WorkPackageLLMError("Ollama와 통신하는 중 오류가 발생했습니다.") from error
    except ValidationError as error:
        raise WorkPackageLLMError("Ollama 결과가 Work Package 스키마와 맞지 않습니다.") from error
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise WorkPackageLLMError("Ollama 응답을 해석하지 못했습니다.") from error


def _load_site_bounds(
    settings: Settings,
) -> tuple[dict[str, list[float]], str, bool]:
    frame_path = settings.sitegit_data_root / "isaac" / "site_frame.json"
    if frame_path.is_file():
        try:
            frame = json.loads(frame_path.read_text(encoding="utf-8"))
            bounds = frame["bounds"]
            minimum = [float(value) for value in bounds["min"]]
            maximum = [float(value) for value in bounds["max"]]
            if len(minimum) == 3 and len(maximum) == 3 and all(
                maximum[index] > minimum[index] for index in range(3)
            ):
                return {"min": minimum, "max": maximum}, str(frame_path), True
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    return DEFAULT_SITE_BOUNDS, "demo-default-site-frame", False


def _zone_bounds(site_bounds: dict[str, list[float]], zone_id: str) -> ZoneBounds:
    min_x, min_y = site_bounds["min"][0], site_bounds["min"][1]
    max_x, max_y = site_bounds["max"][0], site_bounds["max"][1]
    mid_x, mid_y = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5
    zones = {
        "A": (min_x, mid_x, mid_y, max_y),
        "B": (mid_x, max_x, mid_y, max_y),
        "C": (min_x, mid_x, min_y, mid_y),
        "D": (mid_x, max_x, min_y, mid_y),
    }
    values = zones[zone_id]
    return ZoneBounds(min_x=values[0], max_x=values[1], min_y=values[2], max_y=values[3])


def resolve_plan(
    *,
    project_id: str,
    source_text: str,
    plan: LLMWorkPackagePlan,
    settings: Settings,
) -> AIWorkPackageDraft:
    """LLM 초안을 실제 현장 Zone 안의 결정론적 좌표로 변환하고 검증합니다."""
    checks = [
        WorkPackageCheck(
            code="operation",
            ok=plan.ready and plan.operation == "place_cube",
            message=(
                "데모에서 지원하는 큐브 배치 작업입니다."
                if plan.operation == "place_cube"
                else "현재 데모는 큐브 배치만 지원합니다."
            ),
        ),
        WorkPackageCheck(
            code="zone",
            ok=plan.zone_id in {"A", "B", "C", "D"},
            message=(
                f"Zone {plan.zone_id}가 현장 좌표계에 등록되어 있습니다."
                if plan.zone_id in {"A", "B", "C", "D"}
                else "Zone A~D 중 하나를 지정해야 합니다."
            ),
        ),
    ]
    if not all(check.ok for check in checks):
        return AIWorkPackageDraft(
            project_id=project_id,
            source_text=source_text,
            plan=plan,
            checks=checks,
            model=settings.ollama_model,
        )

    site_bounds, source, has_actual_site_frame = _load_site_bounds(settings)
    zone = _zone_bounds(site_bounds, plan.zone_id)
    location = plan.location if plan.location in LOCATION_FACTORS else "center"
    fx, fy = LOCATION_FACTORS[location]
    x = zone.min_x + (zone.max_x - zone.min_x) * fx
    y = zone.min_y + (zone.max_y - zone.min_y) * fy
    # 현장 프레임의 기준 지면은 Z=0입니다. 큐브 중심을 절반 높이만큼 올립니다.
    z = plan.size.z * 0.5
    position = Vector3(x=x, y=y, z=z)
    checks.extend(
        [
            WorkPackageCheck(
                code="site_frame",
                ok=has_actual_site_frame,
                message=(
                    "Isaac에서 내보낸 실제 site_frame.json 좌표계를 확인했습니다."
                    if has_actual_site_frame
                    else "실제 site_frame.json이 없어 미리보기 좌표만 계산했습니다. "
                    "Isaac 맵을 먼저 게시해야 실행할 수 있습니다."
                ),
            ),
            WorkPackageCheck(
                code="site_bounds",
                ok=True,
                message=f"실행 좌표가 Zone {plan.zone_id} 내부로 계산되었습니다.",
            ),
            WorkPackageCheck(
                code="terrain_height",
                ok=True,
                message="이번 데모는 기준 지면 Z=0에 배치합니다. 지형 표면 스냅은 다음 단계입니다.",
            ),
        ]
    )
    normalized_plan = plan.model_copy(update={"location": location})
    return AIWorkPackageDraft(
        project_id=project_id,
        source_text=source_text,
        plan=normalized_plan,
        position=position,
        zone_bounds=zone,
        target_volume_m3=round(plan.size.x * plan.size.y * plan.size.z, 3),
        site_frame_source=source,
        checks=checks,
        model=settings.ollama_model,
    )


def _excavation_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ready": {"type": "boolean"},
            "operation": {"type": "string", "enum": ["excavate_prim", "unsupported"]},
            "equipment_ref": {"type": "string", "maxLength": 500},
            "target_ref": {"type": "string", "maxLength": 500},
            "zone_id": {"type": "string", "maxLength": 80},
            "summary": {"type": "string", "minLength": 1, "maxLength": 300},
            "clarification_question": {"type": "string", "maxLength": 300},
        },
        "required": [
            "ready",
            "operation",
            "equipment_ref",
            "target_ref",
            "zone_id",
            "summary",
            "clarification_question",
        ],
    }


def compile_excavation_language(
    message: str,
    inventory: StageInventoryResponse,
    settings: Settings,
) -> LLMExcavationPlan:
    """Extract an excavation intent while limiting references to real Stage inventory."""
    compact_message = "".join(message.split()).casefold()
    restore_keywords = (
        "메우",
        "메워",
        "매워",
        "채우",
        "채워",
        "복구",
        "되돌",
        "원상복구",
    )
    if any(keyword in compact_message for keyword in restore_keywords):
        return LLMExcavationPlan(
            ready=False,
            operation="unsupported",
            equipment_ref="",
            target_ref="",
            zone_id="",
            summary="기존 굴착 결과 복구 요청",
            clarification_question=(
                "메우기·복구 요청은 굴착으로 실행할 수 없습니다. "
                "해당 굴착 Commit을 되돌린 뒤 실제 복구 작업 유형을 선택하세요."
            ),
        )
    equipment_lines = "\n".join(f"- {item.name}: {item.path}" for item in inventory.equipment)
    target_lines = "\n".join(
        f"- {item.name}: {item.path}" for item in inventory.diggable_targets[:100]
    )
    system_prompt = f"""당신은 SiteGit Work Package Compiler입니다.
사용자의 자연어에서 실제 Isaac Sim 굴착 작업만 구조화합니다.

규칙:
- 지원 작업은 excavate_prim 하나입니다.
- equipment_ref와 target_ref는 아래 Stage 목록의 이름 또는 전체 경로여야 합니다.
- 목록에 없는 장비나 Prim을 만들지 마세요.
- 작업 구역이 없으면 zone_id는 빈 문자열이어도 됩니다.
- 장비와 대상이 명확할 때만 ready=true입니다.
- 좌표와 Prim 경로를 추측하지 마세요.

실제 장비 Prim:
{equipment_lines or '- 없음'}

실제 굴착 대상 Prim:
{target_lines or '- 없음'}
"""
    try:
        endpoint = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
            response = client.post(
                endpoint,
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "stream": False,
                    "think": False,
                    "format": _excavation_output_schema(),
                    "options": {"temperature": 0},
                    "keep_alive": "10m",
                },
            )
        if response.status_code == 404:
            raise WorkPackageLLMUnavailable(
                f"Ollama 모델 '{settings.ollama_model}'을 찾지 못했습니다."
            )
        response.raise_for_status()
        output = response.json().get("message", {}).get("content", "")
        if not output:
            raise WorkPackageLLMError("LLM이 굴착 Work Package를 반환하지 않았습니다.")
        return LLMExcavationPlan.model_validate_json(output)
    except (WorkPackageLLMUnavailable, WorkPackageLLMError):
        raise
    except httpx.ConnectError as error:
        raise WorkPackageLLMUnavailable("로컬 Ollama에 연결할 수 없습니다.") from error
    except httpx.TimeoutException as error:
        raise WorkPackageLLMError("Ollama 응답 시간이 초과되었습니다.") from error
    except (httpx.HTTPError, ValidationError, json.JSONDecodeError) as error:
        raise WorkPackageLLMError(f"굴착 Work Package 변환 실패: {error}") from error


def _resolve_inventory_ref(
    items: list[StagePrimRecord], reference: str | None
) -> StagePrimRecord | None:
    if not reference:
        return None
    exact = [item for item in items if item.path == reference]
    if len(exact) == 1:
        return exact[0]
    needle = reference.casefold().strip()
    matches = [
        item
        for item in items
        if needle == item.name.casefold()
        or needle in item.path.casefold()
        or needle in item.name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def resolve_excavation_plan(
    *,
    project_id: str,
    source_text: str,
    plan: LLMExcavationPlan,
    inventory: StageInventoryResponse,
    settings: Settings,
    equipment_prim_path: str | None = None,
    target_prim_path: str | None = None,
) -> ExcavationDraft:
    """Bind descriptive LLM output to exact paths from the latest live Stage."""
    equipment = _resolve_inventory_ref(
        inventory.equipment, equipment_prim_path or plan.equipment_ref
    )
    target = _resolve_inventory_ref(
        inventory.diggable_targets, target_prim_path or plan.target_ref
    )
    target_span = (
        max(float(target.bounds_size.x), float(target.bounds_size.y)) if target else 0.0
    )
    target_scope_ok = bool(target and target_span <= MAX_EXCAVATION_TARGET_SPAN_M)
    target_active_ok = bool(target and target.active)
    checks = [
        WorkPackageCheck(
            code="stage_connected",
            ok=inventory.connected,
            message=(
                "Isaac Adapter의 Stage inventory가 연결되어 있습니다."
                if inventory.connected
                else "Isaac Adapter heartbeat가 오래되었습니다. Isaac Sim을 실행하세요."
            ),
        ),
        WorkPackageCheck(
            code="operation",
            ok=plan.ready and plan.operation == "excavate_prim",
            message="실제 Prim 굴착 작업입니다." if plan.ready else "굴착 지시가 명확하지 않습니다.",
        ),
        WorkPackageCheck(
            code="equipment_prim",
            ok=equipment is not None,
            message=(
                f"장비 Prim 확인: {equipment.path}"
                if equipment
                else "실제 Stage 장비 Prim을 하나 선택해야 합니다."
            ),
        ),
        WorkPackageCheck(
            code="target_prim",
            ok=target is not None,
            message=(
                f"굴착 대상 Prim 확인: {target.path}"
                if target
                else "실제 Stage 굴착 대상 Prim을 하나 선택해야 합니다."
            ),
        ),
        WorkPackageCheck(
            code="target_active",
            ok=target_active_ok,
            message=(
                "선택한 토사 Prim이 현재 Stage에서 활성 상태입니다."
                if target_active_ok
                else "선택한 토사 Prim은 이미 굴착되어 비활성 상태입니다."
            ),
        ),
        WorkPackageCheck(
            code="target_scope",
            ok=target_scope_ok,
            message=(
                f"굴착 대상 범위 확인: 최대 폭 {target_span:.1f}m"
                if target_scope_ok
                else (
                    f"선택한 Prim의 최대 폭이 {target_span:.1f}m라 전체 맵 Mesh에 가깝습니다. "
                    f"{MAX_EXCAVATION_TARGET_SPAN_M:.0f}m 이하의 독립된 토사 Prim만 굴착할 수 있습니다."
                )
            ),
        ),
    ]
    return ExcavationDraft(
        project_id=project_id,
        source_text=source_text,
        plan=plan,
        equipment=equipment,
        target=target,
        checks=checks,
        model=settings.ollama_model,
    )
