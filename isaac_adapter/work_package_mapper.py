from __future__ import annotations

from typing import Any


def to_isaac_command(work_package: dict[str, Any]) -> dict[str, Any]:
    """SiteGit Work Package를 Isaac 측 명령 형식으로 변환하는 단일 경계."""
    return {
        "command_id": work_package.get("id") or work_package.get("work_package_id"),
        "task_type": work_package.get("task") or work_package.get("task_type"),
        "zone": work_package.get("zone") or work_package.get("zone_id"),
        "target_quantity_m3": work_package.get("target", 0),
        "tolerance_mm": work_package.get("toleranceMm", 50),
        "source_work_package": work_package,
    }
