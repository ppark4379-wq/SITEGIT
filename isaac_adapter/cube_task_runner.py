"""Poll SiteGit WorkInstructions, execute them in a bridge, and commit evidence."""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import time
from typing import Any, Callable

from dotenv import load_dotenv
import requests

from evidence_exporter import EvidenceExporter
from execution_evidence import (
    ExecutionTrace,
    evidence_quality,
    flatten_phase_artifacts,
    iso_timestamp,
)
from isaac_bridge import IsaacBridge, SimulatedCubeBridge
from sitegit_client import SiteGitClient
from work_code_executor import execute_work_code

load_dotenv(Path(__file__).with_name(".env"))

API_URL = os.getenv("SITEGIT_API_URL", "http://localhost:8000/api/v1").removesuffix("/api/v1")
PROJECT_ID = os.getenv("SITEGIT_PROJECT_ID", "SASANG-001")
USERNAME = os.getenv("SITEGIT_USERNAME", "manager")
PASSWORD = os.getenv("SITEGIT_PASSWORD", "")


def _json_safe(value: Any) -> Any:
    """Convert Isaac/USD values into JSON-compatible telemetry values."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    try:
        return [_json_safe(item) for item in value]
    except TypeError:
        return str(value)


def _resource_paths(instruction: dict) -> tuple[str, str]:
    params = instruction.get("params") or {}
    bindings = params.get("resource_bindings") or {}
    return (
        str(params.get("equipment_prim_path") or bindings.get("equipment") or ""),
        str(params.get("target_prim_path") or bindings.get("target") or ""),
    )


def _capture_pose_telemetry(
    exporter: EvidenceExporter,
    bridge: IsaacBridge,
    storage_key: str,
    equipment_prim_path: str,
) -> dict[str, Any]:
    """Capture equipment pose separately from true IMU readings."""

    if not equipment_prim_path:
        return {"available": False, "reason": "equipment Prim path is not bound"}
    prim = bridge.stage.GetPrimAtPath(equipment_prim_path)
    if not prim.IsValid():
        return {
            "available": False,
            "reason": f"equipment Prim not found: {equipment_prim_path}",
        }
    try:
        from pxr import Usd, UsdGeom

        matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = matrix.ExtractTranslation()
        quaternion = matrix.ExtractRotationQuat()
        imaginary = quaternion.GetImaginary()
        payload = {
            "equipment_prim_path": equipment_prim_path,
            "position_m": {
                "x": float(translation[0]),
                "y": float(translation[1]),
                "z": float(translation[2]),
            },
            "orientation_wxyz": [
                float(quaternion.GetReal()),
                float(imaginary[0]),
                float(imaginary[1]),
                float(imaginary[2]),
            ],
            "captured_at": iso_timestamp(),
            "source": "usd-world-transform",
        }
        exporter.save_summary(storage_key, payload)
        return {
            "available": True,
            "storage_key": storage_key,
            "sample_count": 1,
            **payload,
        }
    except Exception as error:
        return {"available": False, "reason": f"pose telemetry unavailable: {error}"}


def _find_imu_prim_path(bridge: IsaacBridge, equipment_prim_path: str) -> str:
    configured = os.getenv("SITEGIT_IMU_PRIM", "").strip()
    if configured:
        return configured
    if not equipment_prim_path:
        return ""
    equipment = bridge.stage.GetPrimAtPath(equipment_prim_path)
    if not equipment.IsValid():
        return ""
    for prim in bridge.stage.Traverse():
        path = str(prim.GetPath())
        if path.startswith(f"{equipment_prim_path}/") and "imu" in prim.GetName().lower():
            return path
    return ""


def _capture_imu(
    exporter: EvidenceExporter,
    bridge: IsaacBridge,
    storage_key: str,
    equipment_prim_path: str,
) -> dict[str, Any]:
    """Read a real Isaac IMU when present; never fabricate missing sensor data."""

    imu_prim_path = _find_imu_prim_path(bridge, equipment_prim_path)
    if not imu_prim_path:
        return {
            "available": False,
            "reason": "no IMU Prim is configured under the assigned equipment",
        }
    prim = bridge.stage.GetPrimAtPath(imu_prim_path)
    if not prim.IsValid():
        return {"available": False, "reason": f"IMU Prim not found: {imu_prim_path}"}

    errors: list[str] = []
    sensor_class = None
    for module_name in ("isaacsim.sensors.physics", "omni.isaac.sensor"):
        try:
            sensor_class = getattr(importlib.import_module(module_name), "IMUSensor")
            break
        except (ImportError, AttributeError) as error:
            errors.append(f"{module_name}: {error}")
    if sensor_class is None:
        return {
            "available": False,
            "prim_path": imu_prim_path,
            "reason": "Isaac IMU Python API is unavailable",
        }
    try:
        sensor = sensor_class(prim_path=imu_prim_path)
        initialize = getattr(sensor, "initialize", None)
        if callable(initialize):
            initialize()
        if bridge._update_callback:
            bridge._update_callback()
        frame = _json_safe(sensor.get_current_frame())
        if not isinstance(frame, dict) or not frame:
            return {
                "available": False,
                "prim_path": imu_prim_path,
                "reason": "IMU returned an empty frame",
            }
        payload = {
            "prim_path": imu_prim_path,
            "captured_at": iso_timestamp(),
            "frame": frame,
            "source": "isaac-imu-sensor",
        }
        exporter.save_summary(storage_key, payload)
        return {
            "available": True,
            "storage_key": storage_key,
            "sample_count": 1,
            **payload,
        }
    except Exception as error:
        return {
            "available": False,
            "prim_path": imu_prim_path,
            "reason": f"IMU read failed: {error}",
        }


def build_bridge(name: str) -> IsaacBridge:
    if name == "isaac":
        raise SystemExit(
            "실제 Isaac Sim 연결은 Isaac Python으로 isaac_runner.py를 실행해야 합니다.\n"
            "    E:\\isaacsim\\python.bat isaac_adapter\\isaac_runner.py"
        )
    return SimulatedCubeBridge()


def _capture_evidence(
    exporter: EvidenceExporter | None,
    bridge: IsaacBridge,
    instruction: dict,
    phase: str,
    update_callback,
    sensor_rig: Any = None,
) -> dict:
    if exporter is None:
        return {"available": False, "reason": "evidence exporter not configured"}
    instruction_id = str(instruction["id"])
    base = f"work-packages/{instruction_id}"
    equipment_path, target_path = _resource_paths(instruction)
    target = bridge.stage.GetPrimAtPath(target_path) if target_path else None
    captured_at = iso_timestamp()
    state = {
        "phase": phase,
        "captured_at": captured_at,
        "equipment_prim_path": equipment_path,
        "target_prim_path": target_path,
        "target_valid": bool(target and target.IsValid()),
        "target_active": bool(target and target.IsValid() and target.IsActive()),
    }
    if target and target.IsValid() and target.IsActive():
        position, size = bridge._world_bounds(target)
        state["target_position"] = position
        state["target_bounds_size"] = size
    summary_key = f"{base}/{phase}-stage.json"
    exporter.save_summary(summary_key, state)
    if sensor_rig is None:
        image = {
            "available": False,
            "reason": "no equipment-mounted camera rig is configured",
        }
        lidar = {
            "available": False,
            "reason": "no equipment-mounted LiDAR rig is configured",
        }
        imu = _capture_imu(
            exporter,
            bridge,
            f"{base}/{phase}-imu.json",
            equipment_path,
        )
    elif sensor_rig.equipment_prim_path != equipment_path:
        image = {
            "available": False,
            "reason": (
                "assigned equipment does not match the initialized sensor rig: "
                f"{equipment_path or '(unbound)'}"
            ),
        }
        lidar = dict(image)
        imu = dict(image)
    else:
        # Refresh the Stage point visualization first so each phase image shows
        # that phase's scan, rather than the previous scan left in the viewport.
        lidar = sensor_rig.capture_lidar(
            exporter,
            f"{base}/{phase}-equipment-lidar.ply",
        )
        image = sensor_rig.capture_camera(
            exporter,
            f"{base}/{phase}-equipment-camera.png",
        )
        imu = sensor_rig.capture_imu(
            exporter,
            f"{base}/{phase}-equipment-imu.json",
        )
    return {
        "captured_at": captured_at,
        "stage": {"available": True, "storage_key": summary_key, **state},
        "image": image,
        "lidar": lidar,
        "imu": imu,
        "telemetry": _capture_pose_telemetry(
            exporter,
            bridge,
            f"{base}/{phase}-pose.json",
            equipment_path,
        ),
    }


def _geometry_change(
    exporter: EvidenceExporter | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    if exporter is None:
        return {
            "available": False,
            "method": "lidar_height_grid_max_z",
            "reason": "evidence exporter not configured",
        }
    before_key = (before or {}).get("lidar", {}).get("storage_key")
    after_key = (after or {}).get("lidar", {}).get("storage_key")
    return exporter.compare_lidar_height_grids(
        before_key,
        after_key,
        cell_size_m=float(os.getenv("SITEGIT_HEIGHT_GRID_CELL_M", "0.5")),
        minimum_height_change_m=float(
            os.getenv("SITEGIT_MIN_HEIGHT_CHANGE_M", "0.05")
        ),
    )


def _performed_quantity(
    kind: str,
    result: dict[str, Any],
    geometry_change: dict[str, Any],
) -> dict[str, Any] | None:
    operation = str(result.get("operation") or kind).lower()
    terrain_deformation = result.get("terrain_deformation") or {}
    is_excavation = (
        "excavat" in operation
        or result.get("target_active_after") is False
        or bool(terrain_deformation.get("available"))
    )
    if not is_excavation:
        return None
    # The deformed USD Mesh is the authoritative operation result. LiDAR is a
    # validation sensor and can miss changed cells because of occlusion/FOV,
    # so it must not replace a known Stage-derived excavation volume with 0.
    if terrain_deformation.get("available"):
        return {
            "value": float(terrain_deformation.get("removed_volume_m3") or 0.0),
            "unit": "m3",
            "method": str(terrain_deformation.get("method") or "usd_mesh_vertex_sculpt"),
            "estimated": True,
        }
    if not geometry_change.get("available"):
        return None
    return {
        "value": float(geometry_change.get("removed_volume_m3") or 0.0),
        "unit": "m3",
        "method": str(geometry_change.get("method") or "lidar_height_grid"),
        "estimated": True,
    }


def _build_evidence_bundle(
    exporter: EvidenceExporter | None,
    instruction: dict,
    trace: ExecutionTrace,
    *,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    finished_at,
    duration_seconds: float,
) -> dict[str, Any]:
    params = instruction.get("params") or {}
    bindings = params.get("resource_bindings") or {}
    artifacts: list[dict[str, Any]] = []
    if before:
        artifacts.extend(flatten_phase_artifacts("before", before))
    if after:
        artifacts.extend(flatten_phase_artifacts("after", after))
    bundle = {
        "schema_version": "1.0",
        "evidence_id": trace.evidence_id,
        "instruction_id": str(instruction["id"]),
        "execution_id": trace.execution_id,
        "work_package_id": params.get("work_package_id"),
        "equipment_id": params.get("equipment_name") or bindings.get("equipment"),
        "zone_id": params.get("zone_id"),
        "source": "isaac-sim",
        "started_at": trace.started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": duration_seconds,
        "events": trace.events,
        "artifacts": artifacts,
        # Kept for existing web clients while artifacts[] is the canonical list.
        "before": before or {},
        "after": after or {},
        "quality": evidence_quality(artifacts),
    }
    if exporter is not None:
        manifest_key = f"work-packages/{instruction['id']}/evidence-manifest.json"
        bundle["artifacts"].append(
            {
                "sensor_type": "manifest",
                "phase": "execution",
                "available": True,
                "captured_at": finished_at.isoformat(),
                "storage_key": manifest_key,
                "format": "json",
                "source": "sitegit-adapter",
                "sample_count": 1,
                "reason": None,
                "metadata": {},
            }
        )
        exporter.save_summary(manifest_key, bundle)
    return bundle


def run_instruction(
    client: SiteGitClient,
    bridge: IsaacBridge,
    instruction: dict,
    *,
    evidence_exporter: EvidenceExporter | None = None,
    update_callback=None,
    sensor_rig: Any = None,
    stage_snapshot_callback: Callable[[dict, str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Execute one supported command and commit only Stage-read-back results."""
    instruction_id = instruction["id"]
    kind = instruction.get("kind")
    if kind not in {"place_cube", "excavate_prim", "generated_script"}:
        commit = client.commit_execution(
            instruction_id,
            status="failed",
            result={"error": f"Unsupported instruction kind: {kind}"},
        )
        print(f"  [skip] {instruction_id} 지원하지 않는 지시: {kind}")
        return commit

    trace = ExecutionTrace(str(instruction_id))
    equipment_path, target_path = _resource_paths(instruction)
    trace.add(
        "instruction_claimed",
        "preparing",
        equipment_prim_path=equipment_path or None,
        target_prim_path=target_path or None,
        details={"instruction_kind": kind},
    )
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    params = instruction.get("params") or {}
    generated_code = str(params.get("generated_code") or "")
    waits_for_excavation_pose = kind == "excavate_prim" or (
        kind == "generated_script" and "ctx.excavate" in generated_code
    )
    evidence_instruction = instruction

    def capture_before(
        prepared_details: dict[str, Any] | None = None,
    ) -> None:
        nonlocal before, evidence_instruction
        if before is not None:
            return
        capture_instruction = instruction
        if prepared_details:
            # Generated programs can create or select their target at runtime.
            # Capture against the actual Prim paths reported by the prepared
            # excavation boundary instead of a stale planning-time binding.
            capture_instruction = {
                **instruction,
                "params": {
                    **params,
                    "equipment_prim_path": str(
                        prepared_details.get("equipment_prim_path") or equipment_path
                    ),
                    "target_prim_path": str(
                        prepared_details.get("target_prim_path") or target_path
                    ),
                },
            }
        evidence_instruction = capture_instruction
        before = _capture_evidence(
            evidence_exporter,
            bridge,
            capture_instruction,
            "before",
            update_callback,
            sensor_rig,
        )
        trace.add(
            "before_evidence_captured",
            "ready",
            equipment_prim_path=equipment_path or None,
            target_prim_path=target_path or None,
            details={
                "capture_trigger": (
                    "equipment_prepared" if prepared_details else "instruction_received"
                ),
                "camera_available": bool(before.get("image", {}).get("available")),
                "lidar_available": bool(before.get("lidar", {}).get("available")),
                "imu_available": bool(before.get("imu", {}).get("available")),
                "prepared_pose": _json_safe(prepared_details or {}),
            },
        )

    try:
        if waits_for_excavation_pose:
            bridge.set_excavation_prepared_callback(capture_before)
        else:
            capture_before()
        trace.add(
            "execution_started",
            "executing",
            equipment_prim_path=equipment_path or None,
            target_prim_path=target_path or None,
        )
        try:
            if kind == "generated_script":
                result = execute_work_code(bridge, generated_code)
            elif kind == "excavate_prim":
                result = bridge.excavate_prim(instruction)
            else:
                result = bridge.place_cube(instruction)
        finally:
            # Never let a callback from a failed instruction leak into the
            # next Work Package.
            bridge.set_excavation_prepared_callback(None)

        if before is None:
            raise RuntimeError(
                "Excavation completed without reaching the prepared-evidence boundary"
            )

        for action in result.get("action_log", []):
            trace.add(
                "action_completed",
                "executing",
                equipment_prim_path=str(
                    action.get("equipment_prim_path") or equipment_path or ""
                )
                or None,
                target_prim_path=str(action.get("target_prim_path") or target_path or "")
                or None,
                details=_json_safe(action),
            )

        after = _capture_evidence(
            evidence_exporter,
            bridge,
            evidence_instruction,
            "after",
            update_callback,
            sensor_rig,
        )
        geometry_change = _geometry_change(evidence_exporter, before, after)
        performed_quantity = _performed_quantity(kind, result, geometry_change)
        trace.add(
            "after_evidence_captured",
            "verifying",
            equipment_prim_path=equipment_path or None,
            target_prim_path=target_path or None,
            details={
                "camera_available": bool(after.get("image", {}).get("available")),
                "lidar_available": bool(after.get("lidar", {}).get("available")),
                "imu_available": bool(after.get("imu", {}).get("available")),
                "geometry_change_available": bool(geometry_change.get("available")),
            },
        )
        if stage_snapshot_callback is not None:
            stage_snapshot = stage_snapshot_callback(instruction, trace.execution_id)
            result = {**result, "stage_snapshot": stage_snapshot}
            trace.add(
                "stage_snapshot_saved",
                "verifying",
                equipment_prim_path=equipment_path or None,
                target_prim_path=target_path or None,
                details={
                    "branch": stage_snapshot.get("branch"),
                    "base_commit_id": stage_snapshot.get("base_commit_id"),
                    "storage_key": stage_snapshot.get("storage_key"),
                },
            )
        trace.add(
            "execution_completed",
            "completed",
            equipment_prim_path=equipment_path or None,
            target_prim_path=target_path or None,
            performed_quantity=performed_quantity,
        )
        finished_at, duration_seconds = trace.finish()
        evidence = _build_evidence_bundle(
            evidence_exporter,
            instruction,
            trace,
            before=before,
            after=after,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )
        result = {
            **result,
            "schema_version": "1.0",
            "operation": str(result.get("operation") or kind),
            "execution_id": trace.execution_id,
            "duration_seconds": duration_seconds,
            "performed_quantity": performed_quantity,
            "geometry_change": geometry_change,
        }
    except Exception as error:
        trace.add(
            "execution_failed",
            "failed",
            equipment_prim_path=equipment_path or None,
            target_prim_path=target_path or None,
            details={"error": str(error), "instruction_kind": kind},
        )
        finished_at, duration_seconds = trace.finish()
        evidence = _build_evidence_bundle(
            evidence_exporter,
            instruction,
            trace,
            before=before,
            after=after,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )
        commit = client.commit_execution(
            instruction_id,
            status="failed",
            result={
                "schema_version": "1.0",
                "error": str(error),
                "operation": str(kind),
                "execution_id": trace.execution_id,
                "duration_seconds": duration_seconds,
                "performed_quantity": None,
                "geometry_change": {
                    "available": False,
                    "reason": "execution failed before a complete comparison",
                },
            },
            evidence=evidence,
        )
        print(f"  [fail] {instruction_id} {error}")
        return commit

    commit = client.commit_execution(
        instruction_id,
        status="succeeded",
        result=result,
        evidence=evidence,
    )
    if kind == "excavate_prim" or (
        kind == "generated_script"
        and (
            result.get("target_active_after") is False
            or bool((result.get("terrain_deformation") or {}).get("available"))
        )
    ):
        print(
            f"  [commit] {commit['id'][:8]} target={result.get('target_prim_path')} "
            "지형 변경 완료 · 관리자 승인/반려 대기"
        )
    elif kind == "generated_script":
        print(
            f"  [commit] {commit['id'][:8]} operation={result.get('operation')} "
            f"actions={result.get('action_count', 1)} · 관리자 승인 대기"
        )
    else:
        position = result.get("placed_position", {})
        print(
            f"  [commit] {commit['id'][:8]} "
            f"({position.get('x')}, {position.get('y')}, {position.get('z')}) · 관리자 승인 대기"
        )
    return commit


def poll_once(client: SiteGitClient, bridge: IsaacBridge) -> int:
    instructions = client.claim_instructions(PROJECT_ID)
    if not instructions:
        return 0
    print(f"지시 {len(instructions)}건 수신")
    for instruction in instructions:
        run_instruction(client, bridge, instruction)
    return len(instructions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    parser.add_argument("--interval", type=float, default=3.0, help="poll 간격(초)")
    parser.add_argument(
        "--bridge",
        choices=("simulated", "isaac"),
        default="simulated",
        help="simulated는 기존 큐브 배관 테스트 전용입니다.",
    )
    args = parser.parse_args()
    if not PASSWORD:
        raise SystemExit("SITEGIT_PASSWORD가 비어 있습니다. isaac_adapter/.env를 설정하세요.")

    client = SiteGitClient.create(API_URL)
    client.login(USERNAME, PASSWORD)
    bridge = build_bridge(args.bridge)
    print(f"SiteGit {API_URL} 연결 · project={PROJECT_ID} · bridge={args.bridge}")
    if args.once:
        if poll_once(client, bridge) == 0:
            print("대기 중인 지시가 없습니다.")
        return
    while True:
        try:
            poll_once(client, bridge)
        except (requests.HTTPError, requests.RequestException) as error:
            print(f"  [error] SiteGit 연결 실패: {error}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
