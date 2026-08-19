"""Versioned Isaac Stage snapshots for approved SiteGit branches.

The adapter writes a candidate USD below ``isaac/pending``.  The backend is
the only component allowed to promote that file into an approved branch HEAD.
This keeps a live, unreviewed Stage from silently becoming the official map.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from fastapi import HTTPException, status

from ...core.config import get_settings
from ...models.isaac import ExecutionCommit


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")
_USD_SUFFIXES = {".usd", ".usda", ".usdc"}


def _safe_component(value: str, *, field: str) -> str:
    safe = _SAFE_COMPONENT.sub("_", str(value)).strip("._")
    if not safe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid Stage snapshot {field}",
        )
    return safe


def _branch_root(project_id: str, branch: str) -> Path:
    settings = get_settings()
    return (
        settings.sitegit_data_root
        / "isaac"
        / "branches"
        / _safe_component(project_id, field="project_id")
        / _safe_component(branch, field="branch")
    )


def _storage_path(storage_key: str) -> Path:
    root = get_settings().sitegit_data_root.resolve()
    candidate = (root / Path(str(storage_key).replace("\\", "/"))).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stage snapshot storage_key escapes SITEGIT_DATA_ROOT",
        )
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_branch_head(project_id: str, branch: str = "main") -> dict[str, Any] | None:
    """Load one approved branch HEAD manifest, if it exists."""

    path = _branch_root(project_id, branch) / "head.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid Stage branch HEAD: {error}",
        ) from error
    return payload


def promote_stage_snapshot(
    commit: ExecutionCommit,
    *,
    reviewed_by: str,
    reviewed_at: datetime,
) -> dict[str, Any] | None:
    """Copy a pending USD into immutable commit storage and advance HEAD."""

    result = commit.result or {}
    snapshot = result.get("stage_snapshot")
    if not isinstance(snapshot, dict):
        return None
    storage_key = str(snapshot.get("storage_key") or "").strip()
    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stage snapshot storage_key is required",
        )
    source = _storage_path(storage_key)
    if not source.is_file() or source.suffix.lower() not in _USD_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pending Stage snapshot not found: {storage_key}",
        )

    project_id = commit.instruction.project_id
    branch = str(snapshot.get("branch") or "main")
    expected_pending_root = (
        get_settings().sitegit_data_root.resolve()
        / "isaac"
        / "pending"
        / _safe_component(project_id, field="project_id")
        / _safe_component(branch, field="branch")
    ).resolve()
    if source != expected_pending_root and expected_pending_root not in source.parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stage snapshot is outside this project and branch pending area",
        )
    scenario_id = str(snapshot.get("scenario_id") or "").strip() or None
    previous_head = load_branch_head(project_id, branch)
    if previous_head and scenario_id:
        if str(previous_head.get("scenario_id") or "") != scenario_id:
            previous_head = None
    actual_parent = previous_head.get("commit_id") if previous_head else None
    expected_parent = snapshot.get("base_commit_id")
    if expected_parent != actual_parent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Stage snapshot was produced from a stale branch HEAD",
                "expected_base_commit_id": expected_parent,
                "current_head_commit_id": actual_parent,
            },
        )

    actual_hash = _sha256(source)
    expected_hash = str(snapshot.get("sha256") or "").strip()
    if expected_hash and expected_hash != actual_hash:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stage snapshot SHA-256 does not match the adapter manifest",
        )

    commit_root = _branch_root(project_id, branch) / "commits" / _safe_component(
        commit.id, field="commit_id"
    )
    commit_root.mkdir(parents=True, exist_ok=True)
    destination = commit_root / f"stage{source.suffix.lower()}"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)

    data_root = get_settings().sitegit_data_root.resolve()
    approved_storage_key = destination.resolve().relative_to(data_root).as_posix()
    head = {
        "schema_version": "1.0",
        "project_id": project_id,
        "branch": branch,
        "commit_id": commit.id,
        "parent_commit_id": actual_parent,
        "instruction_id": commit.instruction_id,
        "approved_by": reviewed_by,
        "approved_at": reviewed_at.isoformat(),
        "storage_key": approved_storage_key,
        "sha256": actual_hash,
        "size_bytes": destination.stat().st_size,
    }
    if scenario_id:
        head["scenario_id"] = scenario_id
    head_path = _branch_root(project_id, branch) / "head.json"
    head_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_head = head_path.with_suffix(".json.tmp")
    temporary_head.write_text(
        json.dumps(head, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_head.replace(head_path)
    return head
