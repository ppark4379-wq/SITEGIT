"""Isaac Sim 안에서 SiteGit 작업 지시를 실행하는 진입점.

**반드시 Isaac Sim의 Python으로 실행해야 합니다.** 일반 .venv에는 omni/pxr이
없습니다.

    E:\\isaacsim\\python.bat E:\\SITEGIT\\isaac_adapter\\isaac_runner.py

동작:

    ① SimulationApp 부팅 (이때서야 omni/pxr을 import할 수 있습니다)
    ② SiteGit 로그인
    ③ 대기 지시 claim → Stage에 Prim 생성 → Stage에서 실제 값 read-back
    ④ read-back 값으로 Commit
    ⑤ 관리자가 웹에서 승인하면 웹 맵에 반영

`SimulatedCubeBridge`와 달리 지시값을 그대로 돌려주지 않습니다. Prim을 만든 뒤
Stage에서 월드 변환을 다시 읽어 보고하므로, Isaac 쪽에서 위치가 바뀌면 웹도
바뀐 값을 봅니다.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="GUI 없이 실행")
    parser.add_argument("--interval", type=float, default=2.0, help="지시 확인 간격(초)")
    parser.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    parser.add_argument(
        "--usd",
        default=None,
        help="열어 둘 현장 USD 파일. 생략하면 빈 Stage에서 시작합니다.",
    )
    parser.add_argument(
        "--site",
        nargs="?",
        const="",
        default=None,
        metavar="ASSET",
        help=(
            "현장 지형을 올립니다. 경로를 생략하면 "
            "SITEGIT_DATA_ROOT/isaac/assets/construction_site_mud.usdz 를 씁니다."
        ),
    )
    parser.add_argument(
        "--no-site",
        action="store_true",
        help="현장 지형 없이 빈 Stage로 실행합니다.",
    )
    parser.add_argument(
        "--save-usd",
        default=None,
        help="작업 후 Stage를 저장할 경로. Isaac이 수정한 맵을 남겨 둡니다.",
    )
    parser.add_argument(
        "--equipment",
        default=None,
        help="함께 불러올 굴착기 USD. 생략하면 SITEGIT_EQUIPMENT_ASSET를 사용합니다.",
    )
    parser.add_argument(
        "--no-equipment",
        action="store_true",
        help="SITEGIT_EQUIPMENT_ASSET가 있어도 굴착기를 자동 로드하지 않습니다.",
    )
    parser.add_argument(
        "--no-demo-soil",
        action="store_true",
        help="기본 독립 토사 더미 Prim을 만들지 않습니다.",
    )
    return parser.parse_args()


def _float_tuple(raw: str, *, count: int, setting_name: str) -> tuple[float, ...]:
    """Parse one comma-separated numeric adapter setting."""

    try:
        values = tuple(float(value.strip()) for value in raw.split(","))
    except ValueError as error:
        raise SystemExit(f"{setting_name}은 쉼표로 구분한 숫자 {count}개여야 합니다.") from error
    if len(values) != count:
        raise SystemExit(f"{setting_name}은 쉼표로 구분한 숫자 {count}개여야 합니다.")
    return values


def main() -> None:
    args = parse_args()

    # SimulationApp이 가장 먼저 부팅되어야 omni/pxr을 import할 수 있습니다.
    from isaacsim.simulation_app import SimulationApp

    simulation_app = SimulationApp({"headless": bool(args.headless)})

    # 여기서부터 omni/pxr 사용 가능합니다.
    import omni.usd

    from isaac_bridge import IsaacBridge, _path_list
    from cube_task_runner import PROJECT_ID, API_URL, USERNAME, PASSWORD, run_instruction
    from evidence_exporter import EvidenceExporter
    from site_stage import (
        create_diggable_soil_pile,
        default_site_asset,
        load_equipment,
        load_site,
        write_site_frame,
    )
    from sitegit_client import SiteGitClient

    try:
        if args.usd:
            omni.usd.get_context().open_stage(str(Path(args.usd).resolve()))
        elif omni.usd.get_context().get_stage() is None:
            omni.usd.get_context().new_stage()
        # Stage와 확장 모듈이 완전히 올라올 때까지 몇 프레임 돌립니다.
        for _ in range(60):
            simulation_app.update()

        # 현장 지형은 기본으로 올립니다. --no-site로 끌 수 있습니다.
        if not args.usd and not args.no_site:
            asset = Path(args.site) if args.site else default_site_asset()
            if asset is None:
                print(
                    "현장 에셋이 없어 빈 Stage로 시작합니다.\n"
                    "  기대 경로: SITEGIT_DATA_ROOT/isaac/assets/construction_site_mud.usdz"
                )
            else:
                print(f"현장 지형 로딩 중... {asset}")
                info = load_site(
                    omni.usd.get_context().get_stage(),
                    asset,
                    simulation_app=simulation_app,
                )
                low, high = info["bounds"]["min"], info["bounds"]["max"]
                report = write_site_frame(info)
                print(
                    "현장 좌표계 (Z-up · meter · 지면 Z=0)\n"
                    f"  X {low[0]:8.1f} ~ {high[0]:8.1f} m\n"
                    f"  Y {low[1]:8.1f} ~ {high[1]:8.1f} m\n"
                    f"  Z {low[2]:8.1f} ~ {high[2]:8.1f} m\n"
                    f"  → {report}",
                    flush=True,
                )

        stage = omni.usd.get_context().get_stage()
        create_demo_soil = os.getenv("SITEGIT_CREATE_DEMO_SOIL_PILE", "true").strip().lower()
        if (
            not args.no_demo_soil
            and create_demo_soil not in {"0", "false", "no", "off"}
            and stage.GetPrimAtPath("/World/Site").IsValid()
        ):
            pile_xy = _float_tuple(
                os.getenv("SITEGIT_DEMO_SOIL_PILE_POSITION", "-12,12"),
                count=2,
                setting_name="SITEGIT_DEMO_SOIL_PILE_POSITION",
            )
            pile_size = _float_tuple(
                os.getenv("SITEGIT_DEMO_SOIL_PILE_SIZE", "6,5,2.5"),
                count=3,
                setting_name="SITEGIT_DEMO_SOIL_PILE_SIZE",
            )
            pile_info = create_diggable_soil_pile(
                stage,
                prim_path=os.getenv(
                    "SITEGIT_DEMO_SOIL_PILE_PRIM",
                    "/World/Diggable/ZoneA_SoilPile_01",
                ),
                position_xy=(pile_xy[0], pile_xy[1]),
                size=(pile_size[0], pile_size[1], pile_size[2]),
                zone_id=os.getenv("SITEGIT_DEMO_SOIL_PILE_ZONE", "A"),
                simulation_app=simulation_app,
            )
            print(
                "독립 토사 Prim 준비 완료: "
                f"{pile_info['prim_path']} · "
                f"{pile_info['size'][0]:.1f}×{pile_info['size'][1]:.1f}×"
                f"{pile_info['size'][2]:.1f}m · 바닥 Z={pile_info['base_z']:.2f}m",
                flush=True,
            )

        if not args.usd and not args.no_equipment:
            equipment_value = args.equipment or os.getenv("SITEGIT_EQUIPMENT_ASSET", "")
            if equipment_value:
                position_values = _float_tuple(
                    os.getenv("SITEGIT_EQUIPMENT_POSITION", "0,0,0"),
                    count=3,
                    setting_name="SITEGIT_EQUIPMENT_POSITION",
                )
                equipment_prim_path = os.getenv(
                    "SITEGIT_EQUIPMENT_PRIMS", "/World/Equipment/EXC_001"
                ).split(",")[0].strip()
                equipment_info = load_equipment(
                    omni.usd.get_context().get_stage(),
                    equipment_value,
                    prim_path=equipment_prim_path,
                    position=position_values,
                    simulation_app=simulation_app,
                )
                print(
                    f"굴착기 로드 완료: {equipment_info['prim_path']} · "
                    f"{equipment_info['asset']}"
                )
                print(
                    "  실제 Skeleton: "
                    + (", ".join(equipment_info["skeleton_paths"]) or "없음")
                )
                print(f"  애니메이션 Prim: {len(equipment_info['animation_paths'])}개")

        if not PASSWORD:
            raise SystemExit("SITEGIT_PASSWORD가 비어 있습니다. isaac_adapter/.env를 설정하세요.")

        client = SiteGitClient.create(API_URL)
        try:
            client.login(USERNAME, PASSWORD)
        except Exception as error:
            # 여기서 그냥 예외를 던지면 Isaac 창이 이유 없이 닫힌 것처럼 보입니다.
            raise SystemExit(
                f"SiteGit 로그인 실패: {error}\n"
                f"  API      : {API_URL}\n"
                f"  사용자   : {USERNAME}\n"
                "  isaac_adapter/.env의 SITEGIT_PASSWORD가 루트 .env의\n"
                "  INITIAL_MANAGER_PASSWORD와 같은지 확인하세요."
            ) from error
        bridge = IsaacBridge(update_callback=simulation_app.update)
        data_root_value = Path(os.getenv("SITEGIT_DATA_ROOT", REPO_ROOT / "runtime"))
        if not data_root_value.is_absolute():
            data_root_value = REPO_ROOT / data_root_value
        evidence_exporter = EvidenceExporter(data_root_value.resolve() / "evidence")
        equipment_paths = _path_list(
            "SITEGIT_EQUIPMENT_PRIMS", "/World/Equipment/EXC_001,/World/Armature"
        )
        diggable_roots = _path_list(
            "SITEGIT_DIGGABLE_ROOTS", "/World/Diggable"
        )

        def publish_inventory() -> None:
            inventory = bridge.stage_inventory(
                equipment_paths=equipment_paths,
                diggable_roots=diggable_roots,
            )
            response = client.update_stage_inventory(PROJECT_ID, inventory)
            print(
                "  [inventory] "
                f"장비 {len(response['equipment'])} · 대상 {len(response['diggable_targets'])}"
            )

        publish_inventory()
        print(f"Isaac Sim ↔ SiteGit {API_URL} · project={PROJECT_ID}")
        print("웹 맵 왼쪽에서 실제 장비와 굴착 대상 Prim을 선택할 수 있습니다.")

        elapsed = 0.0
        inventory_elapsed = 0.0
        frame_seconds = 1.0 / 60.0
        while simulation_app.is_running():
            simulation_app.update()
            elapsed += frame_seconds
            inventory_elapsed += frame_seconds
            if inventory_elapsed >= 5.0:
                inventory_elapsed = 0.0
                try:
                    publish_inventory()
                except Exception as error:
                    print(f"  [warning] Stage inventory 전송 실패: {error}")
            if elapsed < args.interval:
                continue
            elapsed = 0.0

            try:
                instructions = client.claim_instructions(PROJECT_ID)
            except Exception as error:  # 서버가 잠깐 끊겨도 Isaac은 계속 돌아야 합니다.
                print(f"  [error] SiteGit 통신 실패: {error}")
                continue

            if instructions:
                print(f"지시 {len(instructions)}건 수신")
                for instruction in instructions:
                    run_instruction(
                        client,
                        bridge,
                        instruction,
                        evidence_exporter=evidence_exporter,
                        update_callback=simulation_app.update,
                    )
                    publish_inventory()
                if args.save_usd:
                    omni.usd.get_context().save_as_stage(str(Path(args.save_usd).resolve()))
                    print(f"  [saved] {args.save_usd}")

            if args.once:
                if not instructions:
                    print("대기 중인 지시가 없습니다.")
                break
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
