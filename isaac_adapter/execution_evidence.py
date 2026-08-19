"""Build versioned, scenario-neutral execution and evidence records for SiteGit."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def iso_timestamp(value: datetime | None = None) -> str:
    """Serialize timestamps consistently for the Backend contract."""

    return (value or utc_now()).isoformat()


class ExecutionTrace:
    """Collect ordered execution events using wall-clock and monotonic time."""

    def __init__(self, instruction_id: str) -> None:
        self.instruction_id = instruction_id
        self.execution_id = f"exec-{uuid4().hex}"
        self.evidence_id = f"ev-{uuid4().hex}"
        self.started_at = utc_now()
        self._started_monotonic = time.perf_counter()
        self.events: list[dict[str, Any]] = []

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, time.perf_counter() - self._started_monotonic)

    def add(
        self,
        event_type: str,
        work_state: str,
        *,
        equipment_prim_path: str | None = None,
        target_prim_path: str | None = None,
        position: dict[str, float] | None = None,
        performed_quantity: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "sequence": len(self.events) + 1,
            "timestamp": iso_timestamp(),
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "event_type": event_type,
            "work_state": work_state,
            "equipment_prim_path": equipment_prim_path,
            "target_prim_path": target_prim_path,
            "position": position,
            "performed_quantity": performed_quantity,
            "details": details or {},
        }
        self.events.append(event)
        return event

    def finish(self) -> tuple[datetime, float]:
        finished_at = utc_now()
        return finished_at, round(self.elapsed_seconds, 6)


def flatten_phase_artifacts(phase: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate the adapter's phase capture into typed artifact records."""

    captured_at = data.get("captured_at") or iso_timestamp()
    mapping = {
        "stage": ("stage", "json", "usd-stage-readback"),
        "image": ("camera", "png", "equipment-mounted-camera"),
        "lidar": ("lidar", "ply", "equipment-mounted-physx-raycast-lidar"),
        "imu": ("imu", "json", "isaac-imu-sensor"),
        "telemetry": ("telemetry", "json", "usd-world-transform"),
    }
    artifacts: list[dict[str, Any]] = []
    for key, (sensor_type, file_format, source) in mapping.items():
        payload = data.get(key) or {}
        sample_count = payload.get("sample_count")
        if key == "lidar":
            sample_count = payload.get("point_count")
        metadata = {
            item_key: item_value
            for item_key, item_value in payload.items()
            if item_key
            not in {"available", "storage_key", "reason", "sample_count", "point_count"}
        }
        artifacts.append(
            {
                "sensor_type": sensor_type,
                "phase": phase,
                "available": bool(payload.get("available")),
                "captured_at": captured_at,
                "storage_key": payload.get("storage_key"),
                "format": file_format,
                "source": payload.get("source") or source,
                "sample_count": sample_count,
                "reason": payload.get("reason"),
                "metadata": metadata,
            }
        )
    return artifacts


def evidence_quality(
    artifacts: list[dict[str, Any]],
    *,
    required_sensor_types: tuple[str, ...] = ("camera", "lidar", "imu"),
) -> dict[str, Any]:
    """Report sensor completeness without turning it into an acceptance decision."""

    available = {
        str(artifact["sensor_type"])
        for artifact in artifacts
        if artifact.get("available")
    }
    missing = [sensor for sensor in required_sensor_types if sensor not in available]
    ratio = (len(required_sensor_types) - len(missing)) / max(len(required_sensor_types), 1)
    notes = []
    if "imu" in missing:
        notes.append("No live IMU reading was available; pose telemetry is kept separately.")
    return {
        "required_sensor_types": list(required_sensor_types),
        "available_sensor_types": sorted(available),
        "missing_sensor_types": missing,
        "completeness_ratio": round(ratio, 6),
        "timestamps_valid": True,
        "notes": notes,
    }
