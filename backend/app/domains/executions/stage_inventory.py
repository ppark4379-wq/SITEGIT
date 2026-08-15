"""Persist the latest inventory reported by the running Isaac Sim Stage.

The LLM is never allowed to invent executable Prim paths.  It may describe a
requested asset, but dispatch resolves that description against this inventory
and stores the exact Stage paths in the WorkInstruction.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ...core.config import get_settings
from ...schemas.isaac import StageInventoryResponse, StageInventoryUpdate


INVENTORY_MAX_AGE_SECONDS = 20.0


def _inventory_path(project_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", project_id).strip("._")
    if not safe_id:
        raise ValueError("Invalid project_id")
    return get_settings().sitegit_data_root / "isaac" / f"stage_inventory_{safe_id}.json"


def save_stage_inventory(payload: StageInventoryUpdate) -> StageInventoryResponse:
    """Atomically store one adapter heartbeat/inventory snapshot."""
    target = _inventory_path(payload.project_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return to_response(payload)


def load_stage_inventory(project_id: str) -> StageInventoryResponse:
    """Return the last inventory and whether its adapter heartbeat is fresh."""
    target = _inventory_path(project_id)
    if not target.is_file():
        empty = StageInventoryUpdate(project_id=project_id)
        return StageInventoryResponse(**empty.model_dump(), connected=False, age_seconds=0)
    payload = StageInventoryUpdate.model_validate_json(target.read_text(encoding="utf-8"))
    return to_response(payload)


def to_response(payload: StageInventoryUpdate) -> StageInventoryResponse:
    captured_at = payload.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    age = max(0.0, (datetime.now(timezone.utc) - captured_at).total_seconds())
    return StageInventoryResponse(
        **payload.model_dump(),
        connected=age <= INVENTORY_MAX_AGE_SECONDS,
        age_seconds=round(age, 3),
    )


def find_inventory_prim(project_id: str, path: str, role: str):
    """Resolve an exact, currently reported Prim path for dispatch validation."""
    inventory = load_stage_inventory(project_id)
    items = inventory.equipment if role == "equipment" else inventory.diggable_targets
    return inventory, next((item for item in items if item.path == path and item.active), None)
