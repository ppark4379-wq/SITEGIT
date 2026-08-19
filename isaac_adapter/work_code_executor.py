"""Validate and execute restricted LLM-authored SiteGit work programs."""

from __future__ import annotations

import ast
import os
from typing import Any

MAX_PROGRAM_CALLS = 8
CREATABLE_ROOTS = ("/World/SiteGit", "/World/Diggable")

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
        "prim_path", "zone_id", "location", "size_x", "size_y", "size_z", "color", "label", "reference_prim_path",
    },
    "create_soil_pile": {
        "prim_path", "zone_id", "location", "size_x", "size_y", "size_z", "color", "label", "reference_prim_path",
    },
    "move_prim_to_zone": {"prim_path", "zone_id", "location"},
    "set_prim_active": {"prim_path", "active"},
    "play_animation": {"equipment_prim_path", "animation_name", "duration_seconds"},
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


def _validate_ctx_call(value: ast.AST) -> None:
    if not isinstance(value, ast.Call) or value.args:
        raise RuntimeError("Work code calls must use keyword arguments only")
    if not isinstance(value.func, ast.Attribute) or not isinstance(value.func.value, ast.Name):
        raise RuntimeError("Work code may only call the provided ctx object")
    method = value.func.attr
    if value.func.value.id != "ctx" or method not in _ALLOWED_METHOD_KEYWORDS:
        raise RuntimeError(f"Unsupported work code method: {method}")
    allowed = _ALLOWED_METHOD_KEYWORDS[method]
    names = [keyword.arg for keyword in value.keywords]
    if any(name is None or name not in allowed for name in names):
        raise RuntimeError("Work code contains an unsupported argument")
    if len(names) != len(set(names)):
        raise RuntimeError("Work code contains duplicate arguments")
    missing = _REQUIRED_METHOD_KEYWORDS[method] - set(names)
    if missing:
        raise RuntimeError(f"Work code is missing required arguments: {', '.join(sorted(missing))}")
    if any(not isinstance(keyword.value, ast.Constant) for keyword in value.keywords):
        raise RuntimeError("Work code arguments must be literal values")


def validate_work_code(code: str) -> ast.Module:
    """Allow a short sequence of literal-only calls to the supplied ctx API."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as error:
        raise RuntimeError(f"Generated work code syntax error: {error}") from error
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise RuntimeError("Work code must contain exactly one execute(ctx) function")
    function = tree.body[0]
    if function.name != "execute" or [arg.arg for arg in function.args.args] != ["ctx"]:
        raise RuntimeError("Work code function must be execute(ctx)")
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
        raise RuntimeError("Work code may not use annotations, defaults, or extra arguments")
    if function.decorator_list or not 1 <= len(function.body) <= MAX_PROGRAM_CALLS:
        raise RuntimeError(f"execute(ctx) must contain 1 to {MAX_PROGRAM_CALLS} ctx calls")
    for index, statement in enumerate(function.body):
        is_last = index == len(function.body) - 1
        if is_last and isinstance(statement, ast.Return):
            _validate_ctx_call(statement.value)
        elif not is_last and isinstance(statement, ast.Expr):
            _validate_ctx_call(statement.value)
        else:
            raise RuntimeError("Only sequential ctx calls are allowed; the final call must be returned")
    return tree


class IsaacWorkContext:
    """Small capability surface exposed to generated work code."""

    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge
        self.action_log: list[dict[str, Any]] = []

    def _record(self, result: dict[str, Any]) -> dict[str, Any]:
        self.action_log.append(dict(result))
        return result

    def _ensure_path_scope(self, prim_path: str, roots: tuple[str, ...]) -> None:
        if not any(prim_path.startswith(root + "/") for root in roots):
            raise RuntimeError(f"Prim path is outside the allowed work scope: {prim_path}")

    def _zone_xy(self, zone_id: str, location: str) -> tuple[float, float]:
        terrain_path = os.getenv("SITEGIT_TERRAIN_PRIM_PATH", "/World/Site")
        terrain = self.bridge.stage.GetPrimAtPath(terrain_path)
        if not terrain.IsValid() or not terrain.IsActive():
            raise RuntimeError(f"Site terrain Prim is unavailable: {terrain_path}")
        center, size = self.bridge._world_bounds(terrain)
        min_x, max_x = center["x"] - size["x"] * 0.5, center["x"] + size["x"] * 0.5
        min_y, max_y = center["y"] - size["y"] * 0.5, center["y"] + size["y"] * 0.5
        mid_x, mid_y = center["x"], center["y"]
        zones = {
            "A": (min_x, mid_x, mid_y, max_y),
            "B": (mid_x, max_x, mid_y, max_y),
            "C": (min_x, mid_x, min_y, mid_y),
            "D": (mid_x, max_x, min_y, mid_y),
        }
        zone = zones.get(str(zone_id).strip().upper())
        if zone is None:
            raise RuntimeError(f"Unknown work zone: {zone_id}")
        factors = {
            "center": (0.5, 0.5), "north": (0.5, 0.78), "south": (0.5, 0.22),
            "east": (0.78, 0.5), "west": (0.22, 0.5), "northeast": (0.78, 0.78),
            "northwest": (0.22, 0.78), "southeast": (0.78, 0.22), "southwest": (0.22, 0.22),
        }
        factor = factors.get(str(location).strip().lower())
        if factor is None:
            raise RuntimeError(f"Unknown location inside zone: {location}")
        return (
            zone[0] + (zone[1] - zone[0]) * factor[0],
            zone[2] + (zone[3] - zone[2]) * factor[1],
        )

    def _reference_xy(
        self,
        reference_prim_path: str,
        zone_id: str,
        location: str,
    ) -> tuple[float, float]:
        if not reference_prim_path:
            return self._zone_xy(zone_id, location)
        for action in reversed(self.action_log):
            if action.get("target_prim_path") != reference_prim_path:
                continue
            position = action.get("target_position") or action.get("placed_position")
            if position:
                return float(position["x"]), float(position["y"])
        prim = self.bridge.stage.GetPrimAtPath(reference_prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Reference Prim is unavailable: {reference_prim_path}")
        position, _ = self.bridge._world_bounds(prim)
        return float(position["x"]), float(position["y"])

    @staticmethod
    def _hex_color(value: str, default: str = "#6B4F2A") -> str:
        names = {
            "green": "#00FF00", "red": "#FF0000", "yellow": "#FFD700",
            "blue": "#0000FF", "white": "#FFFFFF", "black": "#000000",
            "초록색": "#00FF00", "빨간색": "#FF0000", "노란색": "#FFD700",
            "파란색": "#0000FF", "흰색": "#FFFFFF", "검은색": "#000000",
        }
        text = names.get(str(value).strip().lower(), str(value).strip()).upper()
        if not text:
            text = default
        if len(text) != 7 or not text.startswith("#"):
            raise RuntimeError(f"Color must be #RRGGBB: {value}")
        try:
            int(text[1:], 16)
        except ValueError as error:
            raise RuntimeError(f"Color must be #RRGGBB: {value}") from error
        return text

    def excavate(
        self,
        *,
        equipment_prim_path: str,
        target_prim_path: str,
        approach_distance_m: float = 3.0,
        animation_seconds: float = 3.0,
    ) -> dict[str, Any]:
        return self._record(self.bridge.excavate_prim(
            {
                "params": {
                    "equipment_prim_path": equipment_prim_path,
                    "target_prim_path": target_prim_path,
                    "approach_distance_m": float(approach_distance_m),
                    "animation_seconds": float(animation_seconds),
                }
            }
        ))

    def move_equipment(
        self,
        *,
        equipment_prim_path: str,
        target_prim_path: str,
        approach_distance_m: float = 3.0,
    ) -> dict[str, Any]:
        equipment = self.bridge.stage.GetPrimAtPath(equipment_prim_path)
        target = self.bridge.stage.GetPrimAtPath(target_prim_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"Equipment Prim is unavailable: {equipment_prim_path}")
        if not target.IsValid() or not target.IsActive():
            raise RuntimeError(f"Target Prim is unavailable: {target_prim_path}")

        start, equipment_size = self.bridge._world_bounds(equipment)
        try:
            from .equipment_physics import is_physical_equipment, track_contact_pose
        except ImportError:
            from equipment_physics import is_physical_equipment, track_contact_pose

        if is_physical_equipment(self.bridge.stage, equipment_prim_path):
            start = track_contact_pose(self.bridge.stage, equipment_prim_path)
        target_position, target_size = self.bridge._world_bounds(target)
        dx = target_position["x"] - start["x"]
        dy = target_position["y"] - start["y"]
        horizontal = max((dx * dx + dy * dy) ** 0.5, 1e-9)
        offset = max(0.5, min(20.0, float(approach_distance_m)))
        destination_xy = [
            target_position["x"] - dx / horizontal * offset,
            target_position["y"] - dy / horizontal * offset,
        ]
        drive_result = self.bridge.drive_equipment_to(
            equipment_prim_path,
            destination_xy,
            requested_seconds=max(2.0, horizontal / 1.8),
        )
        end = dict(drive_result["end_track_pose"])
        return self._record({
            "operation": "move_equipment",
            "equipment_prim_path": equipment_prim_path,
            "target_prim_path": target_prim_path,
            "equipment_start_position": start,
            "equipment_end_position": end,
            "equipment_bounds_size": equipment_size,
            "target_position": target_position,
            "target_bounds_size": target_size,
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "locomotion": drive_result,
        })

    def create_box(
        self,
        *,
        prim_path: str,
        zone_id: str,
        location: str,
        size_x: float,
        size_y: float,
        size_z: float,
        color: str,
        label: str,
        reference_prim_path: str = "",
    ) -> dict[str, Any]:
        """Create one semantic box on the actual terrain at a Zone-relative location."""
        from pxr import Gf, Sdf, UsdGeom, UsdPhysics
        from isaac_adapter.site_stage import site_surface_height

        self._ensure_path_scope(prim_path, CREATABLE_ROOTS)
        sizes = [float(size_x), float(size_y), float(size_z)]
        if any(value < 0.25 or value > 50.0 for value in sizes):
            raise RuntimeError("Box dimensions must be between 0.25m and 50m")
        existing = self.bridge.stage.GetPrimAtPath(prim_path)
        if existing.IsValid() and existing.IsActive():
            raise RuntimeError(f"Prim already exists: {prim_path}")
        x, y = self._reference_xy(reference_prim_path, zone_id, location)
        base_z = float(site_surface_height(self.bridge.stage, x, y))
        cube = UsdGeom.Cube.Define(self.bridge.stage, Sdf.Path(prim_path))
        cube.GetSizeAttr().Set(1.0)
        xform = UsdGeom.XformCommonAPI(cube)
        xform.SetTranslate(Gf.Vec3d(x, y, base_z + sizes[2] * 0.5))
        xform.SetScale(Gf.Vec3f(*sizes))
        text = self._hex_color(color).lstrip("#")
        rgb = Gf.Vec3f(*(int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4)))
        cube.GetDisplayColorAttr().Set([rgb])
        prim = cube.GetPrim()
        prim.SetActive(True)
        prim.SetCustomDataByKey("sitegitSceneObject", True)
        prim.SetCustomDataByKey("sitegitObjectLabel", str(label))
        prim.SetCustomDataByKey("sitegitDisplayColor", f"#{text.upper()}")
        prim.SetCustomDataByKey("sitegitZoneId", str(zone_id).upper())
        UsdPhysics.CollisionAPI.Apply(prim)
        if self.bridge._update_callback:
            for _ in range(3):
                self.bridge._update_callback()
        position, size = self.bridge._read_world_transform(prim_path)
        return self._record({
            "operation": "create_box",
            "prim_path": prim_path,
            "target_prim_path": prim_path,
            "placed_position": position,
            "placed_size": size,
            "target_position": position,
            "target_bounds_size": size,
            "target_active_after": True,
            "simulator": "isaac-sim",
            "source": "stage-readback",
        })

    def create_soil_pile(
        self,
        *,
        prim_path: str,
        zone_id: str,
        location: str,
        size_x: float,
        size_y: float,
        size_z: float,
        label: str,
        color: str = "#6B4F2A",
        reference_prim_path: str = "",
    ) -> dict[str, Any]:
        """Create one independently diggable soil Mesh on the live terrain."""
        from isaac_adapter.site_stage import create_diggable_soil_pile

        self._ensure_path_scope(prim_path, ("/World/Diggable",))
        x, y = self._reference_xy(reference_prim_path, zone_id, location)
        display_color = self._hex_color(color)
        info = create_diggable_soil_pile(
            self.bridge.stage,
            prim_path=prim_path,
            position_xy=(x, y),
            size=(float(size_x), float(size_y), float(size_z)),
            zone_id=str(zone_id).upper(),
            diggable_id=str(label),
            display_color=display_color,
        )
        if self.bridge._update_callback:
            for _ in range(3):
                self.bridge._update_callback()
        position, size = self.bridge._world_bounds(self.bridge.stage.GetPrimAtPath(prim_path))
        return self._record({
            "operation": "create_soil_pile",
            "prim_path": prim_path,
            "target_prim_path": prim_path,
            "placed_position": position,
            "placed_size": size,
            "target_position": position,
            "target_bounds_size": size,
            "target_active_after": True,
            "zone_id": str(zone_id).upper(),
            "created": not bool(info.get("existing")),
            "simulator": "isaac-sim",
            "source": "stage-readback",
        })

    def finish(self) -> dict[str, Any]:
        """Return the last action while preserving the complete action log."""
        if not self.action_log:
            raise RuntimeError("No Isaac actions were executed")
        return dict(self.action_log[-1])

    def move_prim_to_zone(
        self,
        *,
        prim_path: str,
        zone_id: str,
        location: str,
    ) -> dict[str, Any]:
        """Move an approved work Prim to a Zone-relative XY location."""
        self._ensure_path_scope(prim_path, (*CREATABLE_ROOTS, "/World/Equipment"))
        prim = self.bridge.stage.GetPrimAtPath(prim_path)
        if not prim.IsValid() or not prim.IsActive():
            raise RuntimeError(f"Prim is unavailable: {prim_path}")
        start, size = self.bridge._world_bounds(prim)
        x, y = self._zone_xy(zone_id, location)
        self.bridge._set_world_translation(prim, [x, y, start["z"]])
        if self.bridge._update_callback:
            self.bridge._update_callback()
        end, _ = self.bridge._world_bounds(prim)
        return self._record({
            "operation": "move_prim_to_zone",
            "prim_path": prim_path,
            "target_prim_path": prim_path,
            "start_position": start,
            "placed_position": end,
            "placed_size": size,
            "target_position": end,
            "target_bounds_size": size,
            "target_active_after": True,
            "simulator": "isaac-sim",
            "source": "stage-readback",
        })

    def set_prim_active(self, *, prim_path: str, active: bool) -> dict[str, Any]:
        """Activate or deactivate only a SiteGit-created work Prim."""
        self._ensure_path_scope(prim_path, CREATABLE_ROOTS)
        prim = self.bridge.stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Prim is unavailable: {prim_path}")
        position, size = self.bridge._world_bounds(prim)
        before = bool(prim.IsActive())
        prim.SetActive(bool(active))
        if self.bridge._update_callback:
            self.bridge._update_callback()
        return self._record({
            "operation": "set_prim_active",
            "prim_path": prim_path,
            "target_prim_path": prim_path,
            "target_position": position,
            "target_bounds_size": size,
            "target_active_before": before,
            "target_active_after": bool(active),
            "simulator": "isaac-sim",
            "source": "stage-readback",
        })

    def play_animation(
        self,
        *,
        equipment_prim_path: str,
        animation_name: str,
        duration_seconds: float,
    ) -> dict[str, Any]:
        """Play one authored clip below an actual equipment Prim."""
        equipment = self.bridge.stage.GetPrimAtPath(equipment_prim_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"Equipment Prim is unavailable: {equipment_prim_path}")
        animation_path = self.bridge._play_skeletal_animation(
            equipment,
            str(animation_name),
            duration_seconds=max(0.25, min(30.0, float(duration_seconds))),
        )
        if not animation_path:
            raise RuntimeError(
                f"Animation '{animation_name}' was not found under {equipment_prim_path}"
            )
        return self._record({
            "operation": "play_animation",
            "equipment_prim_path": equipment_prim_path,
            "animation_prim_path": animation_path,
            "simulator": "isaac-sim",
            "source": "stage-readback",
        })


def execute_work_code(bridge: Any, code: str) -> dict[str, Any]:
    """Execute validated code with no Python builtins and one context object."""
    if not code.strip():
        raise RuntimeError("Generated work code is empty")
    tree = validate_work_code(code)
    namespace: dict[str, Any] = {"__builtins__": {}}
    exec(compile(tree, "<sitegit-work-package>", "exec"), namespace, namespace)
    context = IsaacWorkContext(bridge)
    result = namespace["execute"](context)
    if not isinstance(result, dict):
        raise RuntimeError("Generated work code must return a result dictionary")
    for key in (
        "prim_path",
        "target_prim_path",
        "placed_position",
        "placed_size",
        "target_position",
        "target_bounds_size",
        "target_active_before",
        "target_active_after",
        "equipment_prim_path",
    ):
        if key in result:
            continue
        for action in reversed(context.action_log):
            if key in action:
                result[key] = action[key]
                break
    result["generated_code_executed"] = True
    result["action_log"] = context.action_log
    result["action_count"] = len(context.action_log)
    return result
