"""Compile natural-language requests into restricted Isaac execution programs.

The LLM describes intent and resource references.  Exact Prim paths always come
from the live Stage inventory, and executable Python is emitted from a small
allow-listed context API.  This keeps generated work inspectable without
granting the model filesystem, network, import, or raw ``omni`` access.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from ...core.config import Settings
from ...schemas.isaac import (
    MAX_EXCAVATION_TARGET_SPAN_M,
    StageInventoryResponse,
    StagePrimRecord,
)
from ...schemas.work_package_ai import (
    CodeWorkPackageDraft,
    LLMCodeWorkPackagePlan,
    WorkPackageCheck,
)
from .ai_compiler import WorkPackageLLMError, WorkPackageLLMUnavailable


MAX_PROGRAM_CALLS = 8
CREATABLE_ROOTS = ("/World/SiteGit", "/World/Diggable")
ZONE_LOCATIONS = {
    "center",
    "north",
    "south",
    "east",
    "west",
    "northeast",
    "northwest",
    "southeast",
    "southwest",
}
_GENERIC_REFERENCES = {
    "",
    "any",
    "any equipment",
    "any excavator",
    "equipment",
    "excavator",
    "굴착기",
    "아무 굴착기",
    "어떤 굴착기",
    "target",
    "any target",
    "soil",
    "any soil",
    "soil pile",
    "토사",
    "흙",
    "흙더미",
    "선택 대상",
}


def _output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ready": {"type": "boolean"},
            "operation": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_]*$",
                "minLength": 1,
                "maxLength": 80,
            },
            "equipment_ref": {"type": "string", "maxLength": 500},
            "target_ref": {"type": "string", "maxLength": 500},
            "zone_id": {"type": "string", "maxLength": 80},
            "summary": {"type": "string", "minLength": 1, "maxLength": 300},
            "clarification_question": {"type": "string", "maxLength": 300},
            "generated_code": {"type": "string", "maxLength": 12000},
        },
        "required": [
            "ready",
            "operation",
            "equipment_ref",
            "target_ref",
            "zone_id",
            "summary",
            "clarification_question",
            "generated_code",
        ],
    }


def compile_code_work_package(
    message: str,
    inventory: StageInventoryResponse,
    settings: Settings,
) -> LLMCodeWorkPackagePlan:
    """Ask the configured local model for a restricted, composable Isaac program."""
    equipment_lines = "\n".join(
        f"- {item.name} (zone={item.zone_id or 'unknown'}): {item.path}"
        for item in inventory.equipment
    )
    target_lines = "\n".join(
        f"- {item.name} (zone={item.zone_id or 'unknown'}, active={item.active}): {item.path}"
        for item in inventory.diggable_targets[:100]
    )
    scene_lines = "\n".join(
        f"- {item.name} (zone={item.zone_id or 'unknown'}, active={item.active}): {item.path}"
        for item in inventory.scene_objects[:100]
    )
    system_prompt = f"""당신은 SiteGit의 현장 작업 코드 에이전트입니다.
사용자의 자연어를 아래의 안전한 ctx API만 사용하는 Python 프로그램으로 변환하세요.
작업 종류를 하나로 분류하는 것이 아니라 필요한 ctx 호출을 최대 8개까지 순서대로 조합합니다.

사용 가능한 API:
- ctx.create_box(prim_path, zone_id, location, size_x, size_y, size_z, color, label, reference_prim_path)
- ctx.create_soil_pile(prim_path, zone_id, location, size_x, size_y, size_z, color, label, reference_prim_path)
- ctx.move_prim_to_zone(prim_path, zone_id, location)
- ctx.set_prim_active(prim_path, active)
- ctx.play_animation(equipment_prim_path, animation_name, duration_seconds)
- ctx.move_equipment(equipment_prim_path, target_prim_path, approach_distance_m)
- ctx.excavate(equipment_prim_path, target_prim_path, approach_distance_m, animation_seconds)
- ctx.finish()

generated_code 규칙:
- 정확히 `def execute(ctx):` 함수 하나만 작성합니다.
- 각 줄은 위 ctx 메서드의 직접 호출이어야 하고, 마지막 줄은 `return ctx...`여야 합니다.
- 모든 인자는 이름 있는 리터럴 값만 사용합니다. import, 변수, 반복문, 조건문, 속성 접근은 금지합니다.
- 기존 Prim 경로는 아래 inventory에 있는 정확한 경로만 사용합니다.
- 새 Prim은 /World/SiteGit 또는 /World/Diggable 아래에 영문/숫자/밑줄 이름으로 만듭니다.
- 새 Prim 경로는 inventory에 이미 있는 경로를 재사용하지 말고, 충돌하지 않는 번호나 설명을 붙입니다.
- 큐브/상자 생성은 create_box, 흙/토사/흙더미 생성은 create_soil_pile을 사용합니다.
- 기존 Prim의 위치를 Zone 안으로 바꾸는 요청은 move_prim_to_zone을 사용합니다.
- 제거/복원 요청은 set_prim_active를 사용하되 현장 전체 지형에는 절대 사용하지 않습니다.
- 장비가 토사를 굴착하는 요청은 excavate를 사용합니다.
- 여러 동작이면 앞 동작은 일반 호출, 마지막 동작만 return으로 작성합니다.
- 여러 동작의 마지막은 `return ctx.finish()`를 사용합니다.
- "그 위치", "같은 위치"는 생성 호출의 reference_prim_path에 앞 작업 대상 Prim 경로를 넣습니다.
- color는 반드시 #RRGGBB로 작성합니다. 초록색=#00FF00, 빨간색=#FF0000, 노란색=#FFD700입니다.

규칙:
- operation은 요청을 요약하는 snake_case 이름이며 미리 정해진 목록에 제한되지 않습니다.
- "어떤 굴착기"처럼 특정 장비가 없으면 equipment_ref=any excavator 로 작성하세요.
- 특정 토사를 지정하지 않고 Zone만 지정하면 target_ref=any soil 로 작성하세요.
- Zone A는 zone_id=A처럼 핵심 식별자만 작성하세요.
- 생성 작업은 기존 장비나 대상이 필요하지 않으므로 equipment_ref와 target_ref를 빈 문자열로 둡니다.
- 의도가 명확하고 유효한 코드를 만들 수 있으면 ready=true입니다.
- 필요한 장비/대상이 inventory에 없으면 코드는 가능한 형태로 작성하되 ready=true로 두세요. Backend가 자원 대기로 표시합니다.
- 요청을 안전 API로 표현할 수 없거나 필수 정보가 없으면 ready=false, generated_code=""로 둡니다.

예시:
입력: Zone A 중앙에 5m x 5m x 2m 토사를 만들어줘
generated_code:
def execute(ctx):
    return ctx.create_soil_pile(prim_path='/World/Diggable/ZoneA_SoilPile_01', zone_id='A', location='center', size_x=5.0, size_y=5.0, size_z=2.0, color='#6B4F2A', label='Zone A 토사', reference_prim_path='')

실제 장비 inventory:
{equipment_lines or '- 없음'}

실제 굴착 대상 inventory:
{target_lines or '- 없음'}

기타 실제 Stage 오브젝트 inventory:
{scene_lines or '- 없음'}
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
                    "format": _output_schema(),
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
            raise WorkPackageLLMError("LLM이 Work Package 계획을 반환하지 않았습니다.")
        return LLMCodeWorkPackagePlan.model_validate_json(output)
    except (WorkPackageLLMUnavailable, WorkPackageLLMError):
        raise
    except httpx.ConnectError as error:
        raise WorkPackageLLMUnavailable("로컬 Ollama에 연결할 수 없습니다.") from error
    except httpx.TimeoutException as error:
        raise WorkPackageLLMError("Ollama 응답 시간이 초과되었습니다.") from error
    except (httpx.HTTPError, ValidationError, json.JSONDecodeError) as error:
        raise WorkPackageLLMError(f"Work Package 코드 계획 변환 실패: {error}") from error


def _normalize_zone(value: str | None) -> str:
    text = (value or "").strip().upper()
    if text.startswith("ZONE "):
        text = text[5:].strip()
    return text


def _is_generic(reference: str | None) -> bool:
    return (reference or "").strip().casefold() in _GENERIC_REFERENCES


def _matches_zone(item: StagePrimRecord, zone_id: str) -> bool:
    if not zone_id:
        return True
    item_zone = _normalize_zone(item.zone_id)
    if item_zone:
        return item_zone == zone_id
    marker = f"zone{zone_id}".casefold()
    return marker in item.path.casefold() or marker in item.name.casefold()


def _resolve_resource(
    items: list[StagePrimRecord],
    reference: str | None,
    *,
    zone_id: str = "",
) -> StagePrimRecord | None:
    candidates = [item for item in items if item.active and _matches_zone(item, zone_id)]
    if _is_generic(reference):
        return sorted(candidates, key=lambda item: item.path)[0] if candidates else None
    needle = (reference or "").strip().casefold()
    exact = [item for item in candidates if item.path.casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    matches = [
        item
        for item in candidates
        if needle == item.name.casefold()
        or needle in item.name.casefold()
        or needle in item.path.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


_ALLOWED_METHOD_KEYWORDS = {
    "excavate": {
        "equipment_prim_path",
        "target_prim_path",
        "approach_distance_m",
        "animation_seconds",
    },
    "move_equipment": {
        "equipment_prim_path",
        "target_prim_path",
        "approach_distance_m",
    },
    "create_box": {
        "prim_path",
        "zone_id",
        "location",
        "size_x",
        "size_y",
        "size_z",
        "color",
        "label",
        "reference_prim_path",
    },
    "create_soil_pile": {
        "prim_path",
        "zone_id",
        "location",
        "size_x",
        "size_y",
        "size_z",
        "color",
        "label",
        "reference_prim_path",
    },
    "move_prim_to_zone": {"prim_path", "zone_id", "location"},
    "set_prim_active": {"prim_path", "active"},
    "play_animation": {
        "equipment_prim_path",
        "animation_name",
        "duration_seconds",
    },
    "finish": set(),
}
_REQUIRED_METHOD_KEYWORDS = {
    "excavate": {"equipment_prim_path", "target_prim_path"},
    "move_equipment": {"equipment_prim_path", "target_prim_path"},
    "create_box": {
        "prim_path", "zone_id", "location", "size_x", "size_y", "size_z", "color", "label",
    },
    "create_soil_pile": {
        "prim_path", "zone_id", "location", "size_x", "size_y", "size_z", "label",
    },
    "move_prim_to_zone": {"prim_path", "zone_id", "location"},
    "set_prim_active": {"prim_path", "active"},
    "play_animation": {"equipment_prim_path", "animation_name", "duration_seconds"},
    "finish": set(),
}


def _validate_ctx_call(call: ast.AST) -> ast.Call:
    if not isinstance(call, ast.Call) or call.args:
        raise ValueError("Generated ctx calls must use keyword arguments only")
    if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
        raise ValueError("Generated code may only call ctx methods")
    method = call.func.attr
    if call.func.value.id != "ctx" or method not in _ALLOWED_METHOD_KEYWORDS:
        raise ValueError(f"Unsupported generated context method: {ast.unparse(call.func)}")
    allowed_keywords = _ALLOWED_METHOD_KEYWORDS[method]
    keyword_names = [keyword.arg for keyword in call.keywords]
    if any(name is None or name not in allowed_keywords for name in keyword_names):
        raise ValueError("Generated context call contains an unsupported keyword")
    if len(keyword_names) != len(set(keyword_names)):
        raise ValueError("Generated context call contains duplicate keywords")
    missing = _REQUIRED_METHOD_KEYWORDS[method] - set(keyword_names)
    if missing:
        raise ValueError(f"Generated context call is missing required keywords: {', '.join(sorted(missing))}")
    if any(not isinstance(keyword.value, ast.Constant) for keyword in call.keywords):
        raise ValueError("Generated context arguments must be literal values")
    return call


def _program_calls(code: str) -> list[ast.Call]:
    """Return validated ctx calls from one small sequential program."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        raise ValueError(f"Generated code syntax error: {error}") from error
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Generated code must contain exactly one execute(ctx) function")
    function = tree.body[0]
    if function.name != "execute" or [arg.arg for arg in function.args.args] != ["ctx"]:
        raise ValueError("Generated function signature must be execute(ctx)")
    if (
        function.args.posonlyargs
        or function.args.kwonlyargs
        or function.args.vararg
        or function.args.kwarg
        or function.args.defaults
        or function.args.kw_defaults
        or function.returns
        or any(arg.annotation is not None for arg in function.args.args)
    ):
        raise ValueError("Generated function may not use annotations, defaults, or extra arguments")
    if function.decorator_list or not 1 <= len(function.body) <= MAX_PROGRAM_CALLS:
        raise ValueError(f"execute(ctx) must contain 1 to {MAX_PROGRAM_CALLS} ctx calls")
    calls: list[ast.Call] = []
    for index, statement in enumerate(function.body):
        is_last = index == len(function.body) - 1
        if is_last and isinstance(statement, ast.Return):
            calls.append(_validate_ctx_call(statement.value))
        elif not is_last and isinstance(statement, ast.Expr):
            calls.append(_validate_ctx_call(statement.value))
        else:
            raise ValueError("Only sequential ctx calls are allowed; the final call must be returned")
    return calls


def validate_restricted_code(code: str) -> None:
    """Reject imports, variables and every call outside the safe ``ctx`` API."""
    _program_calls(code)


def _call_kwargs(call: ast.Call) -> dict[str, Any]:
    return {keyword.arg: keyword.value.value for keyword in call.keywords if keyword.arg}


def _valid_new_prim_path(path: str) -> bool:
    if not any(path.startswith(root + "/") for root in CREATABLE_ROOTS):
        return False
    return all(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) is not None
        for part in path.split("/")[1:]
    )


def _normalize_program(code: str) -> str:
    """Repair one harmless small-model shorthand without broadening code access."""
    return re.sub(r"(?m)^(\s*)return\s+ctx\s*$", r"\1return ctx.finish()", code.strip())


def _bind_call_keyword(calls: list[ast.Call], keyword_name: str, value: str) -> bool:
    """Replace an LLM-guessed resource path with one verified inventory path."""

    changed = False
    for call in calls:
        for keyword in call.keywords:
            if keyword.arg != keyword_name:
                continue
            if not isinstance(keyword.value, ast.Constant) or keyword.value.value == value:
                continue
            keyword.value = ast.Constant(value=value)
            changed = True
    return changed


def _render_program(calls: list[ast.Call]) -> str:
    """Render validated calls back into the restricted sequential program form."""

    lines = ["def execute(ctx):"]
    for index, call in enumerate(calls):
        prefix = "return " if index == len(calls) - 1 else ""
        lines.append(f"    {prefix}{ast.unparse(call)}")
    return "\n".join(lines)


def resolve_code_work_package(
    *,
    project_id: str,
    source_text: str,
    plan: LLMCodeWorkPackagePlan,
    inventory: StageInventoryResponse,
    settings: Settings,
) -> CodeWorkPackageDraft:
    """Validate an LLM-authored program against the current Stage inventory."""
    zone_id = _normalize_zone(plan.zone_id)
    code = _normalize_program(plan.generated_code)
    calls: list[ast.Call] = []
    code_error = ""
    if code:
        try:
            calls = _program_calls(code)
        except ValueError as error:
            code_error = str(error)
    elif plan.ready:
        code_error = "LLM이 실행 코드를 생성하지 않았습니다."

    methods = [call.func.attr for call in calls]
    arguments = [_call_kwargs(call) for call in calls]
    equipment_path = next(
        (str(item["equipment_prim_path"]) for item in arguments if item.get("equipment_prim_path")),
        "",
    )
    target_path = next(
        (str(item["target_prim_path"]) for item in arguments if item.get("target_prim_path")),
        "",
    )
    generic_prim_path = next(
        (str(item["prim_path"]) for item in arguments if item.get("prim_path")),
        "",
    )
    requires_equipment = any(
        method in {"excavate", "move_equipment", "play_animation"} for method in methods
    )
    requires_target = any(method in {"excavate", "move_equipment"} for method in methods)

    equipment = next(
        (item for item in inventory.equipment if item.path == equipment_path and item.active),
        None,
    ) if equipment_path else (
        _resolve_resource(inventory.equipment, plan.equipment_ref) if requires_equipment else None
    )
    existing_items = [*inventory.diggable_targets, *inventory.scene_objects]
    target = next(
        (
            item
            for item in existing_items
            if item.path == target_path
            and item.active
            and _matches_zone(item, zone_id)
        ),
        None,
    ) if target_path else (
        _resolve_resource(
            inventory.diggable_targets,
            plan.target_ref,
            zone_id=zone_id,
        ) if requires_target else None
    )
    created_paths = {
        str(kwargs.get("prim_path") or "")
        for method, kwargs in zip(methods, arguments)
        if method in {"create_box", "create_soil_pile"}
    }
    if requires_equipment and equipment is None:
        equipment = _resolve_resource(inventory.equipment, plan.equipment_ref)
    if requires_target and target is None and target_path not in created_paths:
        target = _resolve_resource(
            inventory.diggable_targets,
            plan.target_ref,
            zone_id=zone_id,
        )
    rebound = False
    if equipment is not None and equipment.path != equipment_path:
        rebound = _bind_call_keyword(
            calls, "equipment_prim_path", equipment.path
        ) or rebound
        equipment_path = equipment.path
    if target is not None and target.path != target_path:
        rebound = _bind_call_keyword(calls, "target_prim_path", target.path) or rebound
        target_path = target.path
    if rebound:
        code = _render_program(calls)
        arguments = [_call_kwargs(call) for call in calls]
    generic_prim_path = next(
        (str(item["prim_path"]) for item in arguments if item.get("prim_path")),
        "",
    )
    execution_target_path = generic_prim_path or target_path or None
    target_span = (
        max(float(target.bounds_size.x), float(target.bounds_size.y)) if target else 0.0
    )
    semantic_errors: list[str] = []
    known_paths = {item.path for item in [*inventory.equipment, *existing_items]}
    for method, kwargs in zip(methods, arguments):
        method_zone = _normalize_zone(str(kwargs.get("zone_id") or ""))
        location = str(kwargs.get("location") or "").lower()
        if method in {"create_box", "create_soil_pile", "move_prim_to_zone"}:
            if method_zone not in {"A", "B", "C", "D"}:
                semantic_errors.append(f"{method}: Zone A~D가 필요합니다.")
            if location not in ZONE_LOCATIONS:
                semantic_errors.append(f"{method}: 지원하지 않는 Zone 내부 위치입니다: {location}")
        if method in {"create_box", "create_soil_pile"}:
            new_path = str(kwargs.get("prim_path") or "")
            if not _valid_new_prim_path(new_path):
                semantic_errors.append(f"생성 Prim 경로가 안전한 범위가 아닙니다: {new_path}")
            if new_path in known_paths:
                semantic_errors.append(f"같은 Prim이 이미 Stage에 있습니다: {new_path}")
            reference_path = str(kwargs.get("reference_prim_path") or "")
            if reference_path and reference_path not in known_paths:
                semantic_errors.append(f"기준 Prim이 Stage inventory에 없습니다: {reference_path}")
            raw_sizes = [kwargs.get(name) for name in ("size_x", "size_y", "size_z")]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in raw_sizes):
                semantic_errors.append("생성 크기는 숫자 리터럴이어야 합니다.")
            elif any(float(value) < 0.25 or float(value) > 50.0 for value in raw_sizes):
                semantic_errors.append("생성 크기는 각 축 0.25m~50m 범위여야 합니다.")
        if method in {"move_prim_to_zone", "set_prim_active"}:
            path = str(kwargs.get("prim_path") or "")
            if path not in known_paths:
                semantic_errors.append(f"Stage inventory에 없는 Prim입니다: {path}")
            if not any(path.startswith(root + "/") for root in (*CREATABLE_ROOTS, "/World/Equipment")):
                semantic_errors.append(f"변경할 수 없는 Prim 범위입니다: {path}")
        if method == "set_prim_active" and not isinstance(kwargs.get("active"), bool):
            semantic_errors.append("set_prim_active의 active는 true/false여야 합니다.")

    checks = [
        WorkPackageCheck(
            code="intent",
            ok=plan.ready,
            message=(
                f"작업 의도 확인: {plan.summary}"
                if plan.ready
                else plan.clarification_question or "작업 설명을 보완해야 합니다."
            ),
        ),
        WorkPackageCheck(
            code="program",
            ok=bool(calls) and not code_error and not semantic_errors,
            message=(
                f"안전 Isaac 프로그램 확인: {len(calls)}개 동작 · {', '.join(methods)}"
                if calls and not code_error and not semantic_errors
                else (code_error or semantic_errors[0] if semantic_errors else code_error or "실행 프로그램이 없습니다.")
            ),
        ),
        WorkPackageCheck(
            code="stage_connected",
            ok=inventory.connected,
            message=(
                "현장 작업 시스템이 연결되어 있습니다."
                if inventory.connected
                else "현장 작업 시스템이 연결되지 않아 자원 확인을 기다립니다."
            ),
        ),
    ]
    if requires_equipment:
        checks.append(
            WorkPackageCheck(
                code="equipment",
                ok=equipment is not None and equipment.path == equipment_path,
                message=(
                    f"장비 확인: {equipment.name} · {equipment.path}"
                    if equipment and equipment.path == equipment_path
                    else f"요청한 장비 Prim을 Stage에서 찾지 못했습니다: {equipment_path or plan.equipment_ref or '미지정'}"
                ),
            )
        )
    if requires_target:
        checks.append(
            WorkPackageCheck(
                code="target",
                ok=target is not None and target.active and target.path == target_path,
                message=(
                    f"작업 대상 확인: {target.name} · {target.path}"
                    if target and target.active and target.path == target_path
                    else f"요청한 작업 대상 Prim을 Stage에서 찾지 못했습니다: {target_path or plan.target_ref or '미지정'}"
                ),
            )
        )
    if "excavate" in methods and target is not None:
        checks.append(
            WorkPackageCheck(
                code="target_scope",
                ok=bool(target and target_span <= MAX_EXCAVATION_TARGET_SPAN_M),
                message=(
                    f"굴착 대상 범위 확인: 최대 폭 {target_span:.1f}m"
                    if target and target_span <= MAX_EXCAVATION_TARGET_SPAN_M
                    else f"독립 토사 Prim은 최대 {MAX_EXCAVATION_TARGET_SPAN_M:.0f}m 이하여야 합니다."
                ),
            )
        )
    missing = [check.message for check in checks if not check.ok]
    executable = not missing
    return CodeWorkPackageDraft(
        project_id=project_id,
        source_text=source_text,
        plan=plan,
        equipment=equipment,
        target=target,
        execution_target_path=execution_target_path,
        checks=checks,
        missing_resources=missing,
        generated_code=code if executable else "",
        executable=executable,
        model=settings.ollama_model,
    )
