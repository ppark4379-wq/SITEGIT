"""Isaac Sim 실행 계층.

중요한 제약: `pxr`과 `omni`는 SimulationApp이 부팅된 뒤에만 import됩니다.
그래서 이 파일은 모듈 최상단에서 USD를 import하지 않고 메서드 안에서 합니다.
실행 진입점은 `isaac_runner.py`이며, SimulationApp을 먼저 띄운 뒤 이 클래스를
사용합니다.
"""

from __future__ import annotations

from typing import Any

# Isaac Stage에서 SiteGit이 만든 오브젝트가 모이는 위치.
SITEGIT_ROOT_PATH = "/World/SiteGit"


class IsaacBridge:
    """실제 Isaac Sim Stage에 작업을 반영합니다.

    핵심 원칙은 **지시값을 그대로 되돌려주지 않는다**는 것입니다. Prim을 만든 뒤
    Stage에서 월드 변환을 다시 읽어 그 값을 반환합니다. 웹 맵은 이 값을 그리므로,
    Isaac 쪽에서 위치가 보정되면 웹도 보정된 위치를 보여줍니다.
    """

    def __init__(self, stage: Any = None):
        self._stage = stage

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
