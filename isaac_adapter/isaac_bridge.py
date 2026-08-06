from __future__ import annotations

from typing import Any


class IsaacBridge:
    """Isaac Sim Python API 또는 Extension을 연결할 위치.

    현재 파일은 인터페이스 골격이며 실제 Stage/Prim/로봇 제어 코드는
    팀의 Isaac Sim 시나리오가 확정된 뒤 이 파일에만 추가합니다.
    """

    def dispatch(self, command: dict[str, Any]) -> str:
        raise NotImplementedError("Connect this method to the actual Isaac Sim execution layer.")

    def read_progress(self, execution_id: str) -> dict[str, Any]:
        raise NotImplementedError
