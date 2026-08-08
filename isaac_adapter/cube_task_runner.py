"""Isaac 폐루프 러너 — 지시를 받아 큐브를 배치하고 Commit합니다.

전체 흐름에서 이 파일이 담당하는 구간:

    웹 지시 → [claim → place_cube → commit] → 관리자 승인 → 맵 반영
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

지금은 굴착기도 센서도 없이 `SimulatedCubeBridge`가 지시받은 위치를 그대로
돌려줍니다. Isaac Sim을 붙일 때는 `isaac_bridge.IsaacBridge.place_cube`만
구현하고 `--bridge isaac`으로 실행하면 나머지 배관은 그대로 씁니다.

실행:

    python isaac_adapter/cube_task_runner.py --once
    python isaac_adapter/cube_task_runner.py --interval 3
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from dotenv import load_dotenv
import requests

from isaac_bridge import IsaacBridge, SimulatedCubeBridge
from sitegit_client import SiteGitClient

load_dotenv(Path(__file__).with_name(".env"))

API_URL = os.getenv("SITEGIT_API_URL", "http://localhost:8000/api/v1").removesuffix("/api/v1")
PROJECT_ID = os.getenv("SITEGIT_PROJECT_ID", "SASANG-001")
USERNAME = os.getenv("SITEGIT_USERNAME", "manager")
PASSWORD = os.getenv("SITEGIT_PASSWORD", "")


def build_bridge(name: str) -> IsaacBridge:
    if name == "isaac":
        # omni/pxr은 SimulationApp이 부팅된 뒤에만 import되므로 일반 .venv에서는
        # 실제 Stage에 접근할 수 없습니다.
        raise SystemExit(
            "실제 Isaac Sim 연결은 Isaac의 Python으로 isaac_runner.py를 실행해야 합니다.\n"
            "    E:\\isaacsim\\python.bat isaac_adapter\\isaac_runner.py"
        )
    return SimulatedCubeBridge()


def run_instruction(client: SiteGitClient, bridge: IsaacBridge, instruction: dict) -> None:
    """지시 하나를 실행하고 결과를 Commit합니다."""
    instruction_id = instruction["id"]
    kind = instruction.get("kind")
    if kind != "place_cube":
        client.commit_execution(
            instruction_id,
            status="failed",
            result={"error": f"Unsupported instruction kind: {kind}"},
        )
        print(f"  [skip] {instruction_id} 지원하지 않는 지시 종류: {kind}")
        return

    try:
        result = bridge.place_cube(instruction)
    except NotImplementedError as error:
        # Isaac Bridge가 아직 비어 있으면 실패로 남겨 관리자가 알 수 있게 합니다.
        client.commit_execution(instruction_id, status="failed", result={"error": str(error)})
        print(f"  [fail] {instruction_id} {error}")
        return

    commit = client.commit_execution(
        instruction_id,
        status="succeeded",
        result=result,
        # 다음 단계에서 LiDAR point cloud, 카메라 이미지, 버킷 IMU가 채울 자리입니다.
        # 대용량 파일은 여기에 담지 않고 SSD에 저장한 뒤 storage_keys로 가리킵니다.
        evidence={"sensors": [], "storage_keys": [], "note": "센서 미연결 단계"},
    )
    position = result.get("placed_position", {})
    print(
        f"  [commit] {commit['id'][:8]} "
        f"({position.get('x')}, {position.get('y')}, {position.get('z')}) → 관리자 승인 대기"
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
    parser.add_argument("--interval", type=float, default=3.0, help="폴링 간격(초)")
    parser.add_argument(
        "--bridge",
        choices=("simulated", "isaac"),
        default="simulated",
        help="simulated=Isaac 없이 배관만 검증. 실제 연결은 isaac_runner.py를 쓰세요.",
    )
    args = parser.parse_args()

    if not PASSWORD:
        raise SystemExit(
            "SITEGIT_PASSWORD가 비어 있습니다. isaac_adapter/.env를 설정하세요."
        )

    client = SiteGitClient.create(API_URL)
    try:
        client.login(USERNAME, PASSWORD)
    except Exception as error:
        raise SystemExit(
            f"SiteGit 로그인 실패: {error}\n"
            f"  API      : {API_URL}\n"
            f"  사용자   : {USERNAME}\n"
            "  isaac_adapter/.env의 SITEGIT_PASSWORD가 루트 .env의\n"
            "  INITIAL_MANAGER_PASSWORD와 같은지 확인하세요."
        ) from error
    bridge = build_bridge(args.bridge)
    print(f"SiteGit {API_URL} 연결 · project={PROJECT_ID} · bridge={args.bridge}")

    if args.once:
        if poll_once(client, bridge) == 0:
            print("대기 중인 지시가 없습니다.")
        return

    print(f"{args.interval}초마다 지시를 확인합니다. Ctrl+C로 종료.")
    while True:
        try:
            poll_once(client, bridge)
        except requests.HTTPError as error:
            print(f"  [error] {error}")
        except requests.RequestException as error:
            print(f"  [error] SiteGit 연결 실패: {error}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
