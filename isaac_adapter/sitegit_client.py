from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class SiteGitClient:
    base_url: str
    session: requests.Session

    @classmethod
    def create(cls, base_url: str) -> "SiteGitClient":
        return cls(base_url=base_url.rstrip("/"), session=requests.Session())

    def login(self, username: str, password: str) -> None:
        """로그인 후 Bearer 토큰을 세션에 고정합니다.

        쿠키에 의존하지 않는 이유는 운영 설정에서 COOKIE_SECURE=true이기 때문입니다.
        그러면 Secure 쿠키가 되어 http://localhost 로 붙는 Adapter에는 전송되지
        않습니다. Backend가 Authorization 헤더도 받으므로 토큰을 직접 씁니다.
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("로그인 응답에 access_token이 없습니다.")
        self.session.headers["Authorization"] = f"Bearer {token}"

    def get_shared_state(self, project_id: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}/api/v1/state/{project_id}", timeout=15)
        response.raise_for_status()
        return response.json()

    def submit_shared_state(self, project_id: str, payload: dict[str, Any], revision: int) -> dict[str, Any]:
        response = self.session.put(
            f"{self.base_url}/api/v1/state/{project_id}",
            json={"payload": payload, "revision": revision, "source": "isaac-adapter"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # --- Isaac 폐루프: 지시 수신과 결과 Commit -------------------------------

    def claim_instructions(self, project_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """대기 중인 작업 지시를 가져옵니다.

        서버가 건네주는 시점에 dispatched로 표시하므로, 폴링 주기가 실행
        시간보다 짧아도 같은 지시를 두 번 집어가지 않습니다.
        """
        response = self.session.post(
            f"{self.base_url}/api/v1/isaac/instructions/claim",
            params={"project_id": project_id, "limit": limit},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def list_instructions(
        self,
        project_id: str,
        *,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List work instructions without mutating their dispatch state."""

        params: list[tuple[str, Any]] = [("project_id", project_id), ("limit", limit)]
        params.extend(("status", value) for value in (statuses or []))
        response = self.session.get(
            f"{self.base_url}/api/v1/isaac/instructions",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_commit(self, commit_id: str) -> dict[str, Any]:
        """Read the manager review status for one pending execution Commit."""

        response = self.session.get(
            f"{self.base_url}/api/v1/isaac/commits/{commit_id}",
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def get_branch_head(self, project_id: str, branch: str = "main") -> dict[str, Any] | None:
        """Return the latest approved Stage snapshot manifest for a branch."""

        response = self.session.get(
            f"{self.base_url}/api/v1/isaac/branches/{branch}/head",
            params={"project_id": project_id},
            timeout=15,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def commit_execution(
        self,
        instruction_id: str,
        *,
        status: str = "succeeded",
        result: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        adapter: str = "isaac-adapter",
    ) -> dict[str, Any]:
        """실행 결과를 올립니다. 관리자가 승인해야 맵에 반영됩니다."""
        response = self.session.post(
            f"{self.base_url}/api/v1/isaac/instructions/{instruction_id}/commit",
            json={
                "status": status,
                "result": result or {},
                "evidence": evidence or {},
                "adapter": adapter,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_map_objects(self, project_id: str) -> dict[str, Any]:
        """승인되어 맵에 반영된 오브젝트 목록."""
        response = self.session.get(
            f"{self.base_url}/api/v1/isaac/map-objects",
            params={"project_id": project_id},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def update_stage_inventory(
        self,
        project_id: str,
        inventory: dict[str, Any],
    ) -> dict[str, Any]:
        """Publish exact Prim paths from the currently running Isaac Stage."""
        response = self.session.post(
            f"{self.base_url}/api/v1/isaac/stage-inventory",
            json={"project_id": project_id, **inventory},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
