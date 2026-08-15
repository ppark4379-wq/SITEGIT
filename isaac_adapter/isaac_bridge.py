"""Isaac Sim 실행 계층.

중요한 제약: `pxr`과 `omni`는 SimulationApp이 부팅된 뒤에만 import됩니다.
그래서 이 파일은 모듈 최상단에서 USD를 import하지 않고 메서드 안에서 합니다.
실행 진입점은 `isaac_runner.py`이며, SimulationApp을 먼저 띄운 뒤 이 클래스를
사용합니다.
"""

from __future__ import annotations

import os
from typing import Any, Callable

# Isaac Stage에서 SiteGit이 만든 오브젝트가 모이는 위치.
SITEGIT_ROOT_PATH = "/World/SiteGit"


class IsaacBridge:
    """실제 Isaac Sim Stage에 작업을 반영합니다.

    핵심 원칙은 **지시값을 그대로 되돌려주지 않는다**는 것입니다. Prim을 만든 뒤
    Stage에서 월드 변환을 다시 읽어 그 값을 반환합니다. 웹 맵은 이 값을 그리므로,
    Isaac 쪽에서 위치가 보정되면 웹도 보정된 위치를 보여줍니다.
    """

    def __init__(self, stage: Any = None, update_callback: Callable[[], None] | None = None):
        self._stage = stage
        self._update_callback = update_callback
        self._known_diggable_records: dict[str, dict[str, Any]] = {}

    @property
    def stage(self) -> Any:
        if self._stage is None:
            import omni.usd

            self._stage = omni.usd.get_context().get_stage()
            if self._stage is None:
                raise RuntimeError(
                    "USD Stage를 찾을 수 없습니다. SimulationApp이 먼저 부팅되어야 합니다."
                )
        return self._stage

    def dispatch(self, command: dict[str, Any]) -> str:
        raise NotImplementedError("Connect this method to the actual Isaac Sim execution layer.")

    def read_progress(self, execution_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _ensure_scope(self) -> None:
        """/World/SiteGit 계층이 없으면 만듭니다."""
        from pxr import UsdGeom

        stage = self.stage
        for path in ("/World", SITEGIT_ROOT_PATH):
            if not stage.GetPrimAtPath(path).IsValid():
                UsdGeom.Xform.Define(stage, path)

    def _read_world_transform(self, prim_path: str) -> tuple[dict, dict]:
        """Stage에서 실제 월드 위치와 크기를 다시 읽습니다.

        지시값을 신뢰하지 않고 Stage를 진실의 원본으로 삼습니다.
        """
        from pxr import Gf, Usd, UsdGeom

        prim = self.stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise RuntimeError(f"Prim을 만들지 못했습니다: {prim_path}")

        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = matrix.ExtractTranslation()
        # 회전이 없는 축정렬 변환이므로 각 행의 길이가 곧 축별 배율입니다.
        axis_scale = [
            Gf.Vec3d(matrix[row][0], matrix[row][1], matrix[row][2]).GetLength()
            for row in range(3)
        ]
        # UsdGeom.Cube는 size 속성이 한 변의 길이입니다. 배율과 함께 실제 크기를 만듭니다.
        cube_size = UsdGeom.Cube(prim).GetSizeAttr().Get() or 1.0
        position = {"x": float(translation[0]), "y": float(translation[1]), "z": float(translation[2])}
        size = {
            "x": float(axis_scale[0] * cube_size),
            "y": float(axis_scale[1] * cube_size),
            "z": float(axis_scale[2] * cube_size),
        }
        return position, size

    def place_cube(self, instruction: dict[str, Any]) -> dict[str, Any]:
        """지시받은 위치에 큐브 Prim을 만들고, Stage에서 실제 값을 읽어 반환합니다."""
        from pxr import Gf, UsdGeom

        params = instruction.get("params") or {}
        position = params.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
        size = params.get("size") or {"x": 4.0, "y": 4.0, "z": 4.0}

        self._ensure_scope()
        prim_path = f"{SITEGIT_ROOT_PATH}/cube_{str(instruction.get('id', 'unknown')).replace('-', '')[:12]}"

        cube = UsdGeom.Cube.Define(self.stage, prim_path)
        cube.GetSizeAttr().Set(1.0)  # 단위 큐브로 두고 크기는 Scale로 표현합니다.
        xform = UsdGeom.XformCommonAPI(cube)
        xform.SetTranslate(
            Gf.Vec3d(float(position.get("x", 0)), float(position.get("y", 0)), float(position.get("z", 0)))
        )
        xform.SetScale(
            Gf.Vec3f(float(size.get("x", 1)), float(size.get("y", 1)), float(size.get("z", 1)))
        )

        color = params.get("color")
        if color:
            cube.GetDisplayColorAttr().Set([_hex_to_gf_color(color)])

        placed_position, placed_size = self._read_world_transform(prim_path)
        return {
            "placed_position": placed_position,
            "placed_size": placed_size,
            "prim_path": prim_path,
            "simulator": "isaac-sim",
            "source": "stage-readback",
        }

    def _world_bounds(self, prim: Any) -> tuple[dict[str, float], dict[str, float]]:
        from pxr import Usd, UsdGeom

        cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        )
        aligned = cache.ComputeWorldBound(prim).ComputeAlignedBox()
        minimum, maximum = aligned.GetMin(), aligned.GetMax()
        position = {
            "x": float((minimum[0] + maximum[0]) * 0.5),
            "y": float((minimum[1] + maximum[1]) * 0.5),
            "z": float((minimum[2] + maximum[2]) * 0.5),
        }
        size = {
            "x": max(0.0, float(maximum[0] - minimum[0])),
            "y": max(0.0, float(maximum[1] - minimum[1])),
            "z": max(0.0, float(maximum[2] - minimum[2])),
        }
        return position, size

    def stage_inventory(
        self,
        *,
        equipment_paths: list[str],
        diggable_roots: list[str],
    ) -> dict[str, Any]:
        """Read exact executable Prim paths and transforms from the live Stage."""
        from pxr import Usd, UsdGeom

        def record(prim: Any, role: str) -> dict[str, Any]:
            position, size = self._world_bounds(prim)
            custom_name = (
                prim.GetCustomDataByKey("sitegitEquipmentId")
                if role == "equipment"
                else prim.GetCustomDataByKey("sitegitDiggableId")
            )
            return {
                "path": str(prim.GetPath()),
                "name": str(custom_name or prim.GetName()),
                "type_name": prim.GetTypeName() or "Prim",
                "role": role,
                "world_position": position,
                "bounds_size": size,
                "active": bool(prim.IsActive()),
            }

        equipment: list[dict[str, Any]] = []
        for path in equipment_paths:
            prim = self.stage.GetPrimAtPath(path)
            if prim.IsValid() and prim.IsActive():
                equipment.append(record(prim, "equipment"))

        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root_path in diggable_roots:
            root = self.stage.GetPrimAtPath(root_path)
            if not root.IsValid() or not root.IsActive():
                continue
            for prim in Usd.PrimRange(root):
                path = str(prim.GetPath())
                if path in seen or not prim.IsActive() or not prim.IsA(UsdGeom.Mesh):
                    continue
                if prim.GetCustomDataByKey("sitegitDiggable") is not True:
                    continue
                seen.add(path)
                item = record(prim, "diggable")
                self._known_diggable_records[path] = item
                targets.append(item)
        # Deactivated Prim은 기본 Usd.PrimRange에서 빠집니다. 승인 전 웹은 기존
        # 지형을 유지해야 하므로 마지막 실제 bounds를 active=false로 함께 보고합니다.
        for path, cached in self._known_diggable_records.items():
            if path in seen:
                continue
            prim = self.stage.GetPrimAtPath(path)
            if prim.IsValid() and not prim.IsActive():
                inactive = dict(cached)
                inactive["active"] = False
                targets.append(inactive)
        targets.sort(key=lambda item: item["path"])
        layer = self.stage.GetRootLayer()
        return {
            "stage_identifier": layer.realPath or layer.identifier or "anonymous-stage",
            "equipment": equipment,
            "diggable_targets": targets,
        }

    def _set_world_translation(self, prim: Any, world_position: list[float]) -> None:
        """Move a root equipment Prim while preserving its existing rotation/scale ops."""
        from pxr import Gf, UsdGeom

        current_center, _ = self._world_bounds(prim)
        delta = Gf.Vec3d(
            world_position[0] - current_center["x"],
            world_position[1] - current_center["y"],
            world_position[2] - current_center["z"],
        )
        parent = prim.GetParent()
        if parent and parent.IsValid() and str(parent.GetPath()) != "/":
            parent_matrix = UsdGeom.Xformable(parent).ComputeLocalToWorldTransform(0)
            delta = parent_matrix.GetInverse().TransformDir(delta)

        xformable = UsdGeom.Xformable(prim)
        translate_op = next(
            (
                op
                for op in xformable.GetOrderedXformOps()
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate
            ),
            None,
        )
        if translate_op is None:
            translate_op = xformable.AddTranslateOp(opSuffix="sitegit")
        current_value = translate_op.Get() or Gf.Vec3d(0.0, 0.0, 0.0)
        translate_op.Set(Gf.Vec3d(current_value) + delta)

    def _play_skeletal_animation(
        self,
        equipment: Any,
        animation_name: str,
        *,
        duration_seconds: float,
    ) -> str | None:
        """Bind and play one authored animation below an equipment root.

        The PBR excavator stores its clips as ``SkelAnimation`` siblings and
        switches them through ``Skeleton.skel:animationSource``. The Kit
        timeline is driven explicitly so referenced clips also play while the
        main simulation timeline is paused.
        """
        from pxr import Usd
        import omni.timeline

        skeleton = None
        animation = None
        wanted = animation_name.lower()
        for prim in Usd.PrimRange(equipment):
            type_name = prim.GetTypeName()
            if type_name == "Skeleton" and skeleton is None:
                skeleton = prim
            if type_name == "SkelAnimation" and wanted in prim.GetName().lower():
                animation = prim
        if skeleton is None or animation is None:
            return None

        relationship = skeleton.GetRelationship("skel:animationSource")
        if not relationship:
            relationship = skeleton.CreateRelationship("skel:animationSource")
        relationship.SetTargets([animation.GetPath()])

        samples = sorted(
            {
                sample
                for attribute in animation.GetAttributes()
                for sample in attribute.GetTimeSamples()
            }
        )
        if not samples:
            return str(animation.GetPath())

        timeline = omni.timeline.get_timeline_interface()
        timeline.pause()
        time_codes_per_second = float(self.stage.GetTimeCodesPerSecond() or 24.0)
        frames = max(2, min(180, round(max(0.25, duration_seconds) * 30.0)))
        first, last = float(samples[0]), float(samples[-1])
        if self.stage.GetStartTimeCode() > first:
            self.stage.SetStartTimeCode(first)
        if self.stage.GetEndTimeCode() < last:
            self.stage.SetEndTimeCode(last)
        for index in range(frames):
            ratio = index / (frames - 1)
            timeline.set_current_time((first + (last - first) * ratio) / time_codes_per_second)
            if self._update_callback:
                self._update_callback()
        return str(animation.GetPath())

    def excavate_prim(self, instruction: dict[str, Any]) -> dict[str, Any]:
        """Move the real excavator, play authored clips, and deactivate a target Prim."""
        from pxr import UsdGeom

        params = instruction.get("params") or {}
        equipment_path = str(params.get("equipment_prim_path") or "")
        target_path = str(params.get("target_prim_path") or "")
        equipment = self.stage.GetPrimAtPath(equipment_path)
        target = self.stage.GetPrimAtPath(target_path)
        if not equipment.IsValid() or not equipment.IsActive():
            raise RuntimeError(f"장비 Prim이 Stage에 없습니다: {equipment_path}")
        if not target.IsValid() or not target.IsActive():
            raise RuntimeError(f"굴착 대상 Prim이 Stage에 없습니다: {target_path}")
        allowed_roots = _path_list(
            "SITEGIT_DIGGABLE_ROOTS", "/World/Diggable"
        )
        if not any(target_path == root or target_path.startswith(root + "/") for root in allowed_roots):
            raise RuntimeError(f"등록된 굴착 대상 루트 밖의 Prim입니다: {target_path}")

        equipment_start, equipment_size = self._world_bounds(equipment)
        target_position, target_size = self._world_bounds(target)
        max_target_span = float(os.getenv("SITEGIT_MAX_EXCAVATION_TARGET_SPAN_M", "25"))
        target_span = max(float(target_size["x"]), float(target_size["y"]))
        if target_span > max_target_span:
            raise RuntimeError(
                f"굴착 대상 Prim의 최대 폭이 {target_span:.1f}m입니다. "
                f"전체 현장 Mesh 삭제를 막기 위해 {max_target_span:.0f}m 이하의 "
                "독립된 토사 Prim만 실행할 수 있습니다."
            )
        dx = target_position["x"] - equipment_start["x"]
        dy = target_position["y"] - equipment_start["y"]
        horizontal = max((dx * dx + dy * dy) ** 0.5, 1e-9)
        meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(self.stage) or 1.0)
        offset = float(params.get("approach_distance_m", 3.0)) / meters_per_unit
        destination = [
            target_position["x"] - dx / horizontal * offset,
            target_position["y"] - dy / horizontal * offset,
            equipment_start["z"],
        ]
        seconds = float(params.get("animation_seconds", 3.0))
        animation_paths: list[str] = []
        track_animation = self._play_skeletal_animation(
            equipment,
            "TrackAnimation",
            duration_seconds=min(1.0, seconds),
        )
        if track_animation:
            animation_paths.append(track_animation)
        # Bounds read-back is intentionally used while moving, so 20 Hz keeps
        # the GUI smooth without recooking the full excavator bounds 60 times/s.
        steps = max(1, min(180, round(seconds * 20)))
        start = [equipment_start[axis] for axis in ("x", "y", "z")]
        for index in range(1, steps + 1):
            ratio = index / steps
            current = [
                start[axis] + (destination[axis] - start[axis]) * ratio
                for axis in range(3)
            ]
            self._set_world_translation(equipment, current)
            if self._update_callback:
                self._update_callback()

        dig_animation = self._play_skeletal_animation(
            equipment,
            "ArmDig",
            duration_seconds=seconds,
        )
        if dig_animation:
            animation_paths.append(dig_animation)
        target.SetActive(False)
        if self._update_callback:
            for _ in range(5):
                self._update_callback()
        dump_animation = self._play_skeletal_animation(
            equipment,
            "ArmDump",
            duration_seconds=seconds,
        )
        if dump_animation:
            animation_paths.append(dump_animation)
        equipment_end, _ = self._world_bounds(equipment)
        target_after = self.stage.GetPrimAtPath(target_path)
        return {
            "operation": "excavate_prim",
            "equipment_prim_path": equipment_path,
            "target_prim_path": target_path,
            "equipment_start_position": equipment_start,
            "equipment_end_position": equipment_end,
            "equipment_bounds_size": equipment_size,
            "target_position": target_position,
            "target_bounds_size": target_size,
            "target_active_before": True,
            "target_active_after": bool(target_after.IsActive()) if target_after.IsValid() else False,
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "animation": (
                "authored-excavator-clips" if animation_paths else "equipment-root-approach"
            ),
            "animation_prim_paths": animation_paths,
        }


def _hex_to_gf_color(value: str):
    from pxr import Gf

    text = str(value).lstrip("#")
    if len(text) != 6:
        return Gf.Vec3f(0.94, 0.71, 0.16)
    return Gf.Vec3f(
        int(text[0:2], 16) / 255.0, int(text[2:4], 16) / 255.0, int(text[4:6], 16) / 255.0
    )


class SimulatedCubeBridge(IsaacBridge):
    """Isaac Sim 없이 배관만 검증하기 위한 대체 구현.

    Stage를 만들지 않고 지시값을 그대로 되돌려줍니다. 실제 Isaac 실행이 아니므로
    이 브릿지로 만든 결과는 "Isaac이 확인한 값"이 아닙니다.
    """

    def __init__(self):
        super().__init__(stage=None)

    def place_cube(self, instruction: dict[str, Any]) -> dict[str, Any]:
        params = instruction.get("params") or {}
        position = params.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
        size = params.get("size") or {"x": 4.0, "y": 4.0, "z": 4.0}
        return {
            "placed_position": position,
            "placed_size": size,
            "prim_path": f"{SITEGIT_ROOT_PATH}/cube_{str(instruction.get('id', 'unknown'))[:8]}",
            "simulator": "simulated-cube-bridge",
            "source": "echo",
        }

    def excavate_prim(self, instruction: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("실제 Prim 굴착은 Isaac Sim Stage에서만 실행할 수 있습니다.")


def _path_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
