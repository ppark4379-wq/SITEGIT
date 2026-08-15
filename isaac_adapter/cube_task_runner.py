"""Poll SiteGit WorkInstructions, execute them in a bridge, and commit evidence."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from dotenv import load_dotenv
import requests

from evidence_exporter import EvidenceExporter
from isaac_bridge import IsaacBridge, SimulatedCubeBridge
from sitegit_client import SiteGitClient

load_dotenv(Path(__file__).with_name(".env"))

API_URL = os.getenv("SITEGIT_API_URL", "http://localhost:8000/api/v1").removesuffix("/api/v1")
PROJECT_ID = os.getenv("SITEGIT_PROJECT_ID", "SASANG-001")
USERNAME = os.getenv("SITEGIT_USERNAME", "manager")
PASSWORD = os.getenv("SITEGIT_PASSWORD", "")


def build_bridge(name: str) -> IsaacBridge:
    if name == "isaac":
        raise SystemExit(
            "실제 Isaac Sim 연결은 Isaac Python으로 isaac_runner.py를 실행해야 합니다.\n"
            "    E:\\isaacsim\\python.bat isaac_adapter\\isaac_runner.py"
        )
    return SimulatedCubeBridge()


def _capture_viewport(
    exporter: EvidenceExporter,
    storage_key: str,
    update_callback,
) -> dict:
    """Capture the active Isaac viewport when the installed Kit API supports it."""
    try:
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

        viewport = get_active_viewport()
        if viewport is None:
            return {"available": False, "reason": "active viewport not found"}
        target = exporter.target_path(storage_key)
        capture_viewport_to_file(viewport, str(target))
        if update_callback:
            for _ in range(30):
                update_callback()
        exists = target.is_file()
        return {
            "available": exists,
            "storage_key": storage_key if exists else None,
            "reason": None if exists else "viewport capture did not produce a file",
        }
    except Exception as error:
        return {"available": False, "reason": f"viewport capture unavailable: {error}"}


def _capture_evidence(
    exporter: EvidenceExporter | None,
    bridge: IsaacBridge,
    instruction: dict,
    phase: str,
    update_callback,
) -> dict:
    if exporter is None:
        return {"available": False, "reason": "evidence exporter not configured"}
    instruction_id = str(instruction["id"])
    base = f"work-packages/{instruction_id}"
    target_path = str((instruction.get("params") or {}).get("target_prim_path") or "")
    target = bridge.stage.GetPrimAtPath(target_path) if target_path else None
    state = {
        "phase": phase,
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
    lidar_prim = os.getenv("SITEGIT_LIDAR_POINTS_PRIM", "/World/SiteGitLiveLidarPoints")
    return {
        "stage": {"available": True, "storage_key": summary_key, **state},
        "image": _capture_viewport(
            exporter, f"{base}/{phase}-viewport.png", update_callback
        ),
        "lidar": exporter.capture_lidar_points(
            bridge.stage,
            f"{base}/{phase}-lidar.ply",
            lidar_prim,
        ),
    }


def run_instruction(
    client: SiteGitClient,
    bridge: IsaacBridge,
    instruction: dict,
    *,
    evidence_exporter: EvidenceExporter | None = None,
    update_callback=None,
) -> None:
    """Execute one supported command and commit only Stage-read-back results."""
    instruction_id = instruction["id"]
    kind = instruction.get("kind")
    if kind not in {"place_cube", "excavate_prim"}:
        client.commit_execution(
            instruction_id,
            status="failed",
            result={"error": f"Unsupported instruction kind: {kind}"},
        )
        print(f"  [skip] {instruction_id} 지원하지 않는 지시: {kind}")
        return

    before = None
    try:
        if kind == "excavate_prim":
            before = _capture_evidence(
                evidence_exporter, bridge, instruction, "before", update_callback
            )
            result = bridge.excavate_prim(instruction)
            after = _capture_evidence(
                evidence_exporter, bridge, instruction, "after", update_callback
            )
            evidence = {
                "source": "isaac-sim",
                "before": before,
                "after": after,
                "sensors": ["viewport", "lidar-points"],
            }
        else:
            result = bridge.place_cube(instruction)
            evidence = {"sensors": [], "storage_keys": [], "note": "센서 미연결 단계"}
    except Exception as error:
        client.commit_execution(
            instruction_id,
            status="failed",
            result={"error": str(error), "operation": kind},
            evidence={"before": before} if before else {},
        )
        print(f"  [fail] {instruction_id} {error}")
        return

    commit = client.commit_execution(
        instruction_id,
        status="succeeded",
        result=result,
        evidence=evidence,
    )
    if kind == "excavate_prim":
        print(
            f"  [commit] {commit['id'][:8]} target={result.get('target_prim_path')} "
            "비활성화 완료 · 관리자 승인 대기"
        )
    else:
        position = result.get("placed_position", {})
        print(
            f"  [commit] {commit['id'][:8]} "
            f"({position.get('x')}, {position.get('y')}, {position.get('z')}) · 관리자 승인 대기"
        )


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
