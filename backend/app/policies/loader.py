from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.config import get_settings

POLICY_FILES = {
    "evidence": "evidence_policy.json",
    "conflict": "conflict_policy.json",
    "release": "release_policy.json",
}


def load_policy(name: str) -> dict[str, Any]:
    try:
        filename = POLICY_FILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown policy: {name}") from exc
    path: Path = get_settings().policy_dir / filename
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_all_policies() -> dict[str, dict[str, Any]]:
    return {name: load_policy(name) for name in POLICY_FILES}
