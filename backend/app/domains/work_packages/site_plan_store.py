"""Persist normalized site-plan revisions outside the Git working tree."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from ...schemas.site_plan import SitePlanRecord, SitePlanSaveRequest
from .site_plan import load_pipeline_design


def _safe_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    if not key:
        raise ValueError("도면 식별자가 올바르지 않습니다.")
    return key[:160]


def _plan_directory(storage_root: Path, project_id: str) -> Path:
    directory = storage_root / "site_plans" / _safe_key(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _record_path(storage_root: Path, request: SitePlanSaveRequest) -> Path:
    name = f"{_safe_key(request.design.plan_id)}--{_safe_key(request.design.revision)}.json"
    return _plan_directory(storage_root, request.project_id) / name


def save_site_plan(
    storage_root: Path,
    request: SitePlanSaveRequest,
    *,
    username: str,
) -> SitePlanRecord:
    """Validate and atomically save one drawing revision."""

    record = SitePlanRecord(
        **request.model_dump(),
        updated_at=datetime.now(timezone.utc),
        updated_by=username,
    )
    target = _record_path(storage_root, request)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return record


def list_site_plans(storage_root: Path, project_id: str) -> list[SitePlanRecord]:
    """Return saved revisions plus the repository's canonical demo drawing."""

    records: list[SitePlanRecord] = []
    directory = _plan_directory(storage_root, project_id)
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(SitePlanRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue

    canonical = load_pipeline_design(project_id)
    canonical_key = (canonical.plan_id, canonical.revision) if canonical else None
    stored_keys = {(item.design.plan_id, item.design.revision) for item in records}
    if canonical and canonical_key not in stored_keys:
        records.append(
            SitePlanRecord(
                project_id=project_id,
                status="approved",
                source_filename="contracts/site_plans/demolition_pipeline_v1.json",
                design=canonical,
                updated_at=datetime.fromtimestamp(0, tz=timezone.utc),
                updated_by="SiteGit scenario",
            )
        )
    return sorted(
        records,
        key=lambda item: (item.status == "approved", item.updated_at),
        reverse=True,
    )

