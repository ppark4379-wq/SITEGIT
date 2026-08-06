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
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        response.raise_for_status()

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
