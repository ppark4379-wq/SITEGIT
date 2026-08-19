"""Save pending Isaac USD snapshots and resolve approved branch HEAD files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe(value: str, *, field: str) -> str:
    safe = _SAFE_COMPONENT.sub("_", str(value)).strip("._")
    if not safe:
        raise ValueError(f"Invalid Stage snapshot {field}")
    return safe


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_storage_key(data_root: Path, storage_key: str) -> Path:
    root = data_root.resolve()
    candidate = (root / Path(str(storage_key).replace("\\", "/"))).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Stage snapshot storage_key escapes SITEGIT_DATA_ROOT")
    return candidate


def load_branch_head_snapshot(
    data_root: Path,
    project_id: str,
    branch: str = "main",
    scenario_id: str | None = None,
) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve the approved USD referenced by a local branch HEAD manifest."""

    head_path = (
        data_root.resolve()
        / "isaac"
        / "branches"
        / _safe(project_id, field="project_id")
        / _safe(branch, field="branch")
        / "head.json"
    )
    if not head_path.is_file():
        return None, None
    head = json.loads(head_path.read_text(encoding="utf-8"))
    if scenario_id and str(head.get("scenario_id") or "") != str(scenario_id):
        return None, None
    snapshot = _resolve_storage_key(data_root, str(head.get("storage_key") or ""))
    if not snapshot.is_file():
        raise FileNotFoundError(f"Approved Stage snapshot is missing: {snapshot}")
    expected_hash = str(head.get("sha256") or "")
    if expected_hash and _sha256(snapshot) != expected_hash:
        raise RuntimeError(f"Approved Stage snapshot hash mismatch: {snapshot}")
    return snapshot, head


def save_pending_stage_snapshot(
    stage: Any,
    *,
    data_root: Path,
    project_id: str,
    branch: str,
    instruction_id: str,
    execution_id: str,
    base_commit_id: str | None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Export the current Stage without changing its active root layer."""

    root = data_root.resolve()
    target = (
        root
        / "isaac"
        / "pending"
        / _safe(project_id, field="project_id")
        / _safe(branch, field="branch")
        / _safe(instruction_id, field="instruction_id")
        / _safe(execution_id, field="execution_id")
        / "stage.usda"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    # USD chooses the file format from the final extension, so the temporary
    # export must still end in .usda rather than .tmp.
    temporary = target.with_name("stage.tmp.usda")
    root_layer = stage.GetRootLayer()
    if not root_layer.Export(str(temporary)):
        raise RuntimeError(f"Isaac Stage snapshot export failed: {temporary}")
    temporary.replace(target)
    result = {
        "schema_version": "1.0",
        "status": "pending",
        "project_id": project_id,
        "branch": branch,
        "base_commit_id": base_commit_id,
        "storage_key": target.relative_to(root).as_posix(),
        "format": "usda",
        "sha256": _sha256(target),
        "size_bytes": target.stat().st_size,
    }
    if scenario_id:
        result["scenario_id"] = str(scenario_id)
    return result
