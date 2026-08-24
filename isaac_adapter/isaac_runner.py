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
_PROCESS_ENVIRONMENT = dict(os.environ)
load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
# A portable launcher supplies SSD paths through the real process environment.
# Keep adapter/.env more specific than the root file, while giving explicit
# process values the highest priority on every machine.
os.environ.update(_PROCESS_ENVIRONMENT)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="GUI 없이 실행")
    parser.add_argument(
        "--presentation",
        action="store_true",
        help="Stage/Property/Content를 숨기고 Viewport를 이동 가능한 최대화 창으로 표시",
    )
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
            "SITEGIT_SITE_ASSET 또는 demolition 기본 USDZ를 씁니다."
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

    from presentation_mode import enable_viewport_only_mode, simulation_app_config

    simulation_app = SimulationApp(
        simulation_app_config(
            headless=bool(args.headless),
            presentation=bool(args.presentation),
        )
    )
    enable_viewport_only_mode(
        simulation_app,
        enabled=bool(args.presentation and not args.headless),
    )

    # 여기서부터 omni/pxr 사용 가능합니다.
    import omni.usd
    from isaacsim.core.api import World

    from isaac_bridge import IsaacBridge, _path_list
    from cube_task_runner import (
        PROJECT_ID,
        API_URL,
        USERNAME,
        PASSWORD,
        run_instruction,
        run_parallel_excavation_group,
        run_parallel_pipeline_backfill_group,
        run_parallel_pipeline_installation_group,
    )
    from equipment_sensors import (
        EquipmentSensorRig,
        SensorRigConfig,
        prepare_raycast_collisions,
    )
    from equipment_physics import prepare_equipment_physics, track_contact_pose
    from evidence_exporter import EvidenceExporter
    from site_stage import (
        create_diggable_soil_pile,
        default_site_asset,
        load_equipment,
        load_site,
        write_site_frame,
    )
    from pipeline_scenario import create_pipeline_backfill
    from terrain_collision_proxy import (
        collision_proxy_height_sampler,
        create_terrain_collision_proxy,
        load_or_build_collision_proxy_data,
    )
    from sitegit_client import SiteGitClient
    from stage_snapshots import load_branch_head_snapshot, save_pending_stage_snapshot

    try:
        data_root_value = Path(os.getenv("SITEGIT_DATA_ROOT", REPO_ROOT / "runtime"))
        if not data_root_value.is_absolute():
            data_root_value = REPO_ROOT / data_root_value
        data_root_value = data_root_value.resolve()
        branch_name = os.getenv("SITEGIT_BRANCH", "main").strip() or "main"
        scenario_id = os.getenv(
            "SITEGIT_STAGE_SCENARIO_ID", "pipeline-demolition-v12"
        ).strip()
        restore_head = os.getenv(
            "SITEGIT_RESTORE_BRANCH_HEAD", "true"
        ).strip().lower() not in {"0", "false", "no", "off"}
        approved_stage_path = None
        approved_head = None
        if args.usd is None and restore_head and not args.no_site:
            approved_stage_path, approved_head = load_branch_head_snapshot(
                data_root_value,
                PROJECT_ID,
                branch_name,
                scenario_id=scenario_id or None,
            )
        stage_source = Path(args.usd).resolve() if args.usd else approved_stage_path
        loaded_head_commit_id = (
            str(approved_head.get("commit_id")) if approved_head else None
        )
        collision_proxy = None
        proxy_surface_height = None
        pipeline_surface_height = None
        pipeline_base_color: str | None = None
        pipeline_normal: str | None = None
        if stage_source:
            omni.usd.get_context().open_stage(str(stage_source))
            if approved_stage_path and not args.usd:
                print(
                    "승인된 Isaac Stage HEAD 복원: "
                    f"branch={branch_name} · commit={loaded_head_commit_id[:8]}\n"
                    f"  {approved_stage_path}",
                    flush=True,
                )
        elif omni.usd.get_context().get_stage() is None:
            omni.usd.get_context().new_stage()
        # Stage와 확장 모듈이 완전히 올라올 때까지 몇 프레임 돌립니다.
        for _ in range(60):
            simulation_app.update()

        # 현장 지형은 기본으로 올립니다. --no-site로 끌 수 있습니다.
        if not stage_source and not args.no_site:
            asset = Path(args.site) if args.site else default_site_asset()
            if asset is None:
                print(
                    "현장 에셋이 없어 빈 Stage로 시작합니다.\n"
                    "  기대 경로: SITEGIT_SITE_ASSET 또는 "
                    "SITEGIT_DATA_ROOT/isaac/assets/construction_site_demolition.usdz"
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
        proxy_enabled = os.getenv(
            "SITEGIT_TERRAIN_COLLISION_PROXY", "true"
        ).strip().lower() not in {"0", "false", "no", "off"}
        if proxy_enabled and stage.GetPrimAtPath("/World/Site").IsValid():
            try:
                collision_proxy = create_terrain_collision_proxy(
                    stage,
                    data_root_value,
                    resolution_m=float(
                        os.getenv("SITEGIT_TERRAIN_COLLISION_RESOLUTION_M", "2")
                    ),
                )
                proxy_surface_height = collision_proxy_height_sampler(
                    collision_proxy["cache_path"]
                )
                pipeline_surface_height = proxy_surface_height
                print(
                    "Terrain collision proxy ready: "
                    f"{collision_proxy['triangle_count']:,} triangles · "
                    f"{collision_proxy['resolution_m']:.1f}m grid · "
                    f"cache={'hit' if collision_proxy['cache_hit'] else 'created'}",
                    flush=True,
                )
            except Exception as error:
                print(
                    "[warning] Terrain collision proxy failed; using the full site mesh: "
                    f"{error}",
                    flush=True,
                )

        create_pipeline_fill = os.getenv(
            "SITEGIT_CREATE_PIPELINE_BACKFILL", "true"
        ).strip().lower()
        if (
            create_pipeline_fill not in {"0", "false", "no", "off"}
            and stage.GetPrimAtPath("/World/Site").IsValid()
        ):
            if proxy_surface_height is None:
                raise RuntimeError(
                    "Pipeline backfill requires the terrain collision height cache"
                )
            visual_height_resolution = float(
                os.getenv("SITEGIT_PIPELINE_HEIGHT_RESOLUTION_M", "0.5")
            )
            try:
                visual_height_cache = (
                    data_root_value
                    / "isaac"
                    / "terrain_backfill_height_0_5m.npz"
                )
                visual_height_data, visual_height_cache_hit = (
                    load_or_build_collision_proxy_data(
                        data_root_value / "isaac" / "site-work-map",
                        visual_height_cache,
                        resolution_m=visual_height_resolution,
                    )
                )
                pipeline_surface_height = collision_proxy_height_sampler(
                    visual_height_cache
                )
                print(
                    "Pipeline visual height cache ready: "
                    f"{visual_height_data['valid_cell_count']:,} cells · "
                    f"{visual_height_resolution:.2f}m grid · "
                    f"cache={'hit' if visual_height_cache_hit else 'created'}",
                    flush=True,
                )
            except Exception as error:
                pipeline_surface_height = proxy_surface_height
                print(
                    "[warning] Fine pipeline height cache failed; using the "
                    f"collision grid: {error}",
                    flush=True,
                )
            material_root = data_root_value / "isaac" / "assets" / "materials"
            pipeline_base_color = os.getenv(
                "SITEGIT_PIPELINE_SOIL_BASECOLOR",
                str(material_root / "demolition_soil_tile_diffuse.jpg"),
            )
            pipeline_normal = os.getenv(
                "SITEGIT_PIPELINE_SOIL_NORMAL",
                str(material_root / "demolition_soil_tile_normal.jpg"),
            )
            fill_info = create_pipeline_backfill(
                stage,
                surface_height=pipeline_surface_height,
                base_color_texture=pipeline_base_color,
                normal_texture=pipeline_normal or None,
                update_callback=simulation_app.update,
            )
            print(
                "Pipeline 초기 복토 준비 완료: "
                f"{fill_info['section_count']}개 구간 · "
                f"{fill_info['root_prim_path']} · "
                f"material={fill_info['material_path'] or 'displayColor fallback'} · "
                f"scenario={scenario_id} · texture={pipeline_base_color} · "
                f"normal={pipeline_normal or 'none'}",
                flush=True,
            )

        create_demo_soil = os.getenv("SITEGIT_CREATE_DEMO_SOIL_PILE", "false").strip().lower()
        if (
            not args.no_demo_soil
            and create_demo_soil not in {"0", "false", "no", "off"}
            and stage.GetPrimAtPath("/World/Site").IsValid()
        ):
            pile_xy = _float_tuple(
                os.getenv("SITEGIT_DEMO_SOIL_PILE_POSITION", "-26.5,-40.5"),
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
                    "/World/Diggable/ZoneC_SoilPile_01",
                ),
                position_xy=(pile_xy[0], pile_xy[1]),
                size=(pile_size[0], pile_size[1], pile_size[2]),
                zone_id=os.getenv("SITEGIT_DEMO_SOIL_PILE_ZONE", "C"),
                simulation_app=simulation_app,
                surface_height=proxy_surface_height,
            )
            print(
                "독립 토사 Prim 준비 완료: "
                f"{pile_info['prim_path']} · "
                f"{pile_info['size'][0]:.1f}×{pile_info['size'][1]:.1f}×"
                f"{pile_info['size'][2]:.1f}m · 바닥 Z={pile_info['base_z']:.2f}m",
                flush=True,
            )

        equipment_paths = _path_list(
            "SITEGIT_EQUIPMENT_PRIMS",
            "/World/Equipment/EXC_001,/World/Equipment/EXC_002,/World/Equipment/EXC_003",
        )
        if not args.no_equipment:
            equipment_value = args.equipment or os.getenv("SITEGIT_EQUIPMENT_ASSET", "")
            if equipment_value:
                position_values = _float_tuple(
                    os.getenv("SITEGIT_EQUIPMENT_POSITION", "-26.5,-30.5,0"),
                    count=3,
                    setting_name="SITEGIT_EQUIPMENT_POSITION",
                )
                try:
                    from three_excavator_demo import load_demo_workfronts

                    planned_positions = {
                        item.equipment_prim_path: item.start_position
                        for item in load_demo_workfronts()
                    }
                except Exception as error:
                    planned_positions = {}
                    print(f"[warning] drawing equipment positions unavailable: {error}")
                equipment_info = None
                for equipment_index, equipment_prim_path in enumerate(equipment_paths):
                    if stage.GetPrimAtPath(equipment_prim_path).IsValid():
                        continue
                    position = planned_positions.get(
                        equipment_prim_path,
                        (
                            position_values[0] + equipment_index * 5.0,
                            position_values[1],
                            position_values[2],
                        ),
                    )
                    equipment_info = load_equipment(
                        omni.usd.get_context().get_stage(),
                        equipment_value,
                        prim_path=equipment_prim_path,
                        equipment_id=f"EXC-{equipment_index + 1:03d}",
                        position=position,
                        simulation_app=simulation_app,
                        surface_height=proxy_surface_height,
                    )
                if equipment_info is None:
                    equipment_info = {
                        "prim_path": ",".join(equipment_paths),
                        "asset": str(equipment_value),
                        "skeleton_paths": [],
                        "animation_paths": [],
                    }
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
        evidence_exporter = EvidenceExporter(data_root_value / "evidence")

        def save_stage_candidate(instruction: dict, execution_id: str) -> dict:
            snapshot = save_pending_stage_snapshot(
                bridge.stage,
                data_root=data_root_value,
                project_id=PROJECT_ID,
                branch=branch_name,
                instruction_id=str(instruction["id"]),
                execution_id=execution_id,
                base_commit_id=loaded_head_commit_id,
                scenario_id=scenario_id or None,
            )
            print(
                "  [stage pending] "
                f"branch={branch_name} · base="
                f"{(loaded_head_commit_id or 'baseline')[:8]} · "
                f"{snapshot['storage_key']}",
                flush=True,
            )
            return snapshot
        diggable_roots = _path_list(
            "SITEGIT_DIGGABLE_ROOTS", "/World/Diggable"
        )
        scene_object_roots = _path_list(
            "SITEGIT_SCENE_OBJECT_ROOTS", "/World/SiteGit"
        )

        default_collision_roots = (
            "/World/SiteGitTerrainCollision,/World/Diggable,/World/SiteGit"
            if collision_proxy
            else "/World/Site,/World/Diggable,/World/SiteGit"
        )
        collision_roots = _path_list(
            "SITEGIT_LIDAR_COLLISION_ROOTS",
            default_collision_roots,
        )
        if not collision_proxy and "/World/SiteGitTerrainCollision" in collision_roots:
            collision_roots = [
                "/World/Site" if path == "/World/SiteGitTerrainCollision" else path
                for path in collision_roots
            ]
        collision_report = prepare_raycast_collisions(
            bridge.stage,
            collision_roots,
            update_callback=simulation_app.update,
            cooking_frames=max(
                0, int(os.getenv("SITEGIT_COLLISION_COOKING_FRAMES", "20"))
            ),
        )
        print(
            "LiDAR collision 준비 완료: "
            f"Mesh {collision_report['mesh_count']}개 · "
            f"신규 Collision {collision_report['new_collision_count']}개",
            flush=True,
        )

        physical_equipment: dict[str, dict] = {}
        for equipment_path in equipment_paths:
            if not bridge.stage.GetPrimAtPath(equipment_path).IsValid():
                continue
            try:
                physical_equipment[equipment_path] = prepare_equipment_physics(
                    bridge.stage,
                    equipment_path,
                    surface_height=proxy_surface_height or bridge._terrain_surface_z,
                )
                report = physical_equipment[equipment_path]
                print(
                    "굴착기 물리 준비 완료: "
                    f"{equipment_path} · 좌우 궤도 Collider {len(report['collider_paths'])}개 · "
                    f"질량 {os.getenv('SITEGIT_EQUIPMENT_MASS_KG', '18000')}kg",
                    flush=True,
                )
            except Exception as error:
                raise RuntimeError(f"굴착기 물리 초기화 실패 ({equipment_path}): {error}") from error

        # Initialize a real physics/render loop before the equipment sensors.
        # The off-screen camera and PhysX scene queries both depend on this
        # context even when the normal runner window is visible.
        world = World(
            stage_units_in_meters=1.0,
            physics_prim_path="/World/PhysicsScene",
            set_defaults=False,
        )
        world.reset()

        def render_sensor_frame() -> None:
            world.step(render=True)

        motion_render_every = max(
            1,
            int(os.getenv("SITEGIT_MOTION_RENDER_EVERY_N", "2")),
        )
        motion_frame = 0

        def advance_motion_frame() -> None:
            """Advance physics every frame and render only the configured frames."""

            nonlocal motion_frame
            motion_frame += 1
            world.step(render=(motion_frame % motion_render_every == 0))

        # All later equipment movement must advance the physics World, not just
        # redraw Kit.  Otherwise authored velocities never affect the body.
        bridge._update_callback = advance_motion_frame

        import omni.timeline

        timeline = omni.timeline.get_timeline_interface()
        timeline.play()
        settle_frames = max(1, int(os.getenv("SITEGIT_EQUIPMENT_SETTLE_FRAMES", "120")))
        for frame in range(settle_frames):
            world.step(render=(frame % 4 == 0 or frame == settle_frames - 1))

        sensor_rig = None
        sensor_rigs: dict[str, EquipmentSensorRig] = {}
        valid_sensor_equipment_paths = [
            path for path in equipment_paths if bridge.stage.GetPrimAtPath(path).IsValid()
        ]
        sensor_equipment_path = valid_sensor_equipment_paths[0] if valid_sensor_equipment_paths else ""
        if sensor_equipment_path:
            track_pose = track_contact_pose(bridge.stage, sensor_equipment_path)
            print(
                "굴착기 PhysX 안착 완료: "
                f"궤도 중심 XY=({track_pose['x']:.2f}, {track_pose['y']:.2f}) · "
                f"궤도 바닥 Z={track_pose['z']:.2f}m",
                flush=True,
            )
            sensor_info = None
            for path in valid_sensor_equipment_paths:
                rig = EquipmentSensorRig(
                    bridge.stage,
                    path,
                    update_callback=render_sensor_frame,
                    config=SensorRigConfig.from_environment(),
                    physics_world=world,
                )
                info = rig.initialize()
                sensor_rigs[path] = rig
                if path == sensor_equipment_path:
                    sensor_info = info
            sensor_rig = sensor_rigs[sensor_equipment_path]
            assert sensor_info is not None
            print(
                "굴착기 SensorRig 준비 완료\n"
                f"  Mount  : {sensor_info['mount_prim_path']}\n"
                f"  Camera : {sensor_info['camera_prim_path']} · "
                f"{sensor_info['camera_resolution'][0]}x{sensor_info['camera_resolution'][1]}\n"
                f"  LiDAR  : {sensor_info['lidar_ray_count']:,} rays · "
                f"{sensor_info['lidar_points_prim_path']}\n"
                f"  IMU    : {sensor_info['imu_prim_path']} · "
                f"{sensor_info['imu_frequency_hz']} Hz",
                flush=True,
            )
        else:
            print(
                "[warning] 유효한 장비 Prim이 없어 카메라/LiDAR SensorRig를 만들지 않았습니다.",
                flush=True,
            )

        # Scene queries need an active PhysX scene.  The runner's normal update
        # loop keeps the timeline advancing while work instructions are polled.
        for _ in range(5):
            world.step(render=True)

        def publish_inventory() -> None:
            inventory = bridge.stage_inventory(
                equipment_paths=equipment_paths,
                diggable_roots=diggable_roots,
                scene_object_roots=scene_object_roots,
            )
            inventory["scenario_id"] = scenario_id
            response = client.update_stage_inventory(PROJECT_ID, inventory)
            print(
                "  [inventory] "
                f"장비 {len(response['equipment'])} · 대상 {len(response['diggable_targets'])} · "
                f"Stage 객체 {len(response.get('scene_objects', []))}"
            )

        publish_inventory()
        print(f"Isaac Sim ↔ SiteGit {API_URL} · project={PROJECT_ID}")
        print("웹 맵 왼쪽에서 실제 장비와 굴착 대상 Prim을 선택할 수 있습니다.")

        elapsed = 0.0
        inventory_elapsed = 0.0
        frame_seconds = 1.0 / 60.0
        waiting_commit_id: str | None = None
        waiting_notice_printed = False
        while simulation_app.is_running():
            simulation_app.update()
            elapsed += frame_seconds
            inventory_elapsed += frame_seconds
            if inventory_elapsed >= 1.0:
                inventory_elapsed = 0.0
                try:
                    publish_inventory()
                except Exception as error:
                    print(f"  [warning] Stage inventory 전송 실패: {error}")
            if elapsed < args.interval:
                continue
            elapsed = 0.0

            if waiting_commit_id:
                try:
                    reviewed = client.get_commit(waiting_commit_id)
                except Exception as error:
                    print(f"  [warning] Commit 검토 상태 확인 실패: {error}")
                    continue
                review_status = reviewed.get("review_status")
                if review_status == "pending":
                    if not waiting_notice_printed:
                        print(
                            f"  [waiting] Commit {waiting_commit_id[:8]} 관리자 승인/반려 대기",
                            flush=True,
                        )
                        waiting_notice_printed = True
                    continue
                if review_status == "approved":
                    loaded_head_commit_id = waiting_commit_id
                    print(
                        f"  [merged] Commit {waiting_commit_id[:8]} → {branch_name} HEAD",
                        flush=True,
                    )
                    waiting_commit_id = None
                    waiting_notice_printed = False
                else:
                    print(
                        f"  [rejected] Commit {waiting_commit_id[:8]} · "
                        "승인 HEAD로 안전하게 돌아가기 위해 Isaac Runner를 종료합니다. "
                        "같은 명령으로 다시 실행하세요.",
                        flush=True,
                    )
                    break

            # A restarted Adapter must only wait for commits that actually own
            # a candidate Stage snapshot. Older demo commits contain evidence
            # but no USD snapshot; treating those as a global lock leaves every
            # newly issued scenario instruction pending forever.
            try:
                committed = client.list_instructions(
                    PROJECT_ID,
                    statuses=["committed"],
                    limit=20,
                )
                pending_reviews = [
                    commit
                    for instruction in committed
                    for commit in instruction.get("commits", [])
                    if commit.get("review_status") == "pending"
                    and bool((commit.get("result") or {}).get("stage_snapshot"))
                ]
                if pending_reviews:
                    if not waiting_notice_printed:
                        print(
                            "  [waiting] 다른 실행 Commit의 관리자 검토가 끝날 때까지 "
                            "새 Work Package를 가져오지 않습니다.",
                            flush=True,
                        )
                        waiting_notice_printed = True
                    continue
                remote_head = client.get_branch_head(PROJECT_ID, branch_name)
                remote_head_id = remote_head.get("commit_id") if remote_head else None
                if remote_head_id != loaded_head_commit_id:
                    print(
                        "  [head changed] 승인 Branch HEAD가 변경되었습니다. "
                        "최신 Stage를 복원하기 위해 Isaac Runner를 종료합니다. "
                        "같은 명령으로 다시 실행하세요.",
                        flush=True,
                    )
                    break
                waiting_notice_printed = False
            except Exception as error:
                print(f"  [warning] Branch 실행 가능 상태 확인 실패: {error}")
                continue

            try:
                instructions = client.claim_instructions(
                    PROJECT_ID,
                    limit=3,
                    prefer_execution_group=True,
                )
            except Exception as error:  # 서버가 잠깐 끊겨도 Isaac은 계속 돌아야 합니다.
                print(f"  [error] SiteGit 통신 실패: {error}")
                continue

            if instructions:
                print(f"지시 {len(instructions)}건 수신")
                group_ids = {
                    str((instruction.get("params") or {}).get("execution_group_id") or "")
                    for instruction in instructions
                }
                is_parallel_excavation = (
                    1 <= len(instructions) <= 3
                    and len(group_ids) == 1
                    and "" not in group_ids
                    and all(
                        (instruction.get("params") or {}).get("execution_group_mode")
                        == "parallel_incremental_scoops"
                        for instruction in instructions
                    )
                )
                is_parallel_pipeline_installation = (
                    len(instructions) == 3
                    and len(group_ids) == 1
                    and "" not in group_ids
                    and all(
                        (instruction.get("params") or {}).get("execution_group_mode")
                        == "parallel_pipe_installation"
                        for instruction in instructions
                    )
                )
                is_parallel_pipeline_backfill = (
                    len(instructions) == 3
                    and len(group_ids) == 1
                    and "" not in group_ids
                    and all(
                        (instruction.get("params") or {}).get("execution_group_mode")
                        == "parallel_pipeline_backfill"
                        for instruction in instructions
                    )
                )
                if is_parallel_excavation:
                    print(
                        "[Zone A · phase 1] Excavation group received; starting "
                        f"{len(instructions)}-excavator execution.",
                        flush=True,
                    )
                    commits = run_parallel_excavation_group(
                        client,
                        bridge,
                        instructions,
                        world=world,
                        evidence_exporter=evidence_exporter,
                        sensor_rigs=sensor_rigs,
                        stage_snapshot_callback=save_stage_candidate,
                        animation_seconds=float(
                            os.getenv("SITEGIT_GROUP_EXCAVATION_ANIMATION_SECONDS", "3.5")
                        ),
                        scoop_count=int(
                            os.getenv("SITEGIT_GROUP_EXCAVATION_SCOOPS", "5")
                        ),
                        render=not args.headless,
                    )
                    publish_inventory()
                    pending = [
                        commit
                        for commit in commits
                        if commit and commit.get("review_status") == "pending"
                    ]
                    if pending:
                        waiting_commit_id = str(pending[-1]["id"])
                        waiting_notice_printed = False
                elif is_parallel_pipeline_installation:
                    if pipeline_surface_height is None:
                        raise RuntimeError(
                            "Zone A phase 2 pipeline installation needs the site height sampler"
                        )
                    print(
                        "[Zone A · phase 2] Excavation approvals complete; starting "
                        "synchronized pipeline installation.",
                        flush=True,
                    )
                    commits = run_parallel_pipeline_installation_group(
                        client,
                        bridge,
                        instructions,
                        world=world,
                        floor_height=pipeline_surface_height,
                        plan_path=(
                            REPO_ROOT
                            / "contracts"
                            / "site_plans"
                            / "demolition_pipeline_v1.json"
                        ),
                        evidence_exporter=evidence_exporter,
                        sensor_rigs=sensor_rigs,
                        stage_snapshot_callback=save_stage_candidate,
                        animation_seconds=float(
                            os.getenv(
                                "SITEGIT_GROUP_PIPE_INSTALLATION_ANIMATION_SECONDS",
                                "1.6",
                            )
                        ),
                        render=not args.headless,
                    )
                    publish_inventory()
                    pending = [
                        commit
                        for commit in commits
                        if commit and commit.get("review_status") == "pending"
                    ]
                    if pending:
                        waiting_commit_id = str(pending[-1]["id"])
                        waiting_notice_printed = False
                elif is_parallel_pipeline_backfill:
                    if pipeline_surface_height is None:
                        raise RuntimeError(
                            "Zone A phase 3 backfill needs the site height sampler"
                        )
                    print(
                        "[Zone A · phase 3] Installation approvals complete; starting "
                        "synchronized pipeline backfill.",
                        flush=True,
                    )
                    commits = run_parallel_pipeline_backfill_group(
                        client,
                        bridge,
                        instructions,
                        world=world,
                        surface_height=pipeline_surface_height,
                        plan_path=(
                            REPO_ROOT
                            / "contracts"
                            / "site_plans"
                            / "demolition_pipeline_v1.json"
                        ),
                        base_color_texture=pipeline_base_color,
                        normal_texture=pipeline_normal,
                        evidence_exporter=evidence_exporter,
                        sensor_rigs=sensor_rigs,
                        stage_snapshot_callback=save_stage_candidate,
                        animation_seconds=float(
                            os.getenv(
                                "SITEGIT_GROUP_PIPELINE_BACKFILL_ANIMATION_SECONDS",
                                "3.0",
                            )
                        ),
                        scoop_count=int(
                            os.getenv("SITEGIT_GROUP_PIPELINE_BACKFILL_SCOOPS", "5")
                        ),
                        render=not args.headless,
                    )
                    publish_inventory()
                    pending = [
                        commit
                        for commit in commits
                        if commit and commit.get("review_status") == "pending"
                    ]
                    if pending:
                        waiting_commit_id = str(pending[-1]["id"])
                        waiting_notice_printed = False
                else:
                    for instruction in instructions:
                        params = instruction.get("params") or {}
                        equipment_path = str(
                            (params.get("resource_bindings") or {}).get("equipment")
                            or params.get("equipment_prim_path")
                            or ""
                        )
                        commit = run_instruction(
                            client,
                            bridge,
                            instruction,
                            evidence_exporter=evidence_exporter,
                            update_callback=render_sensor_frame,
                            sensor_rig=sensor_rigs.get(equipment_path, sensor_rig),
                            stage_snapshot_callback=save_stage_candidate,
                        )
                        publish_inventory()
                        if commit and commit.get("review_status") == "pending":
                            waiting_commit_id = str(commit["id"])
                            waiting_notice_printed = False
                if args.save_usd:
                    omni.usd.get_context().save_as_stage(str(Path(args.save_usd).resolve()))
                    print(f"  [saved] {args.save_usd}")

            if args.once:
                if not instructions:
                    print("대기 중인 지시가 없습니다.")
                break
    finally:
        try:
            timeline.stop()
        except (NameError, AttributeError):
            pass
        simulation_app.close()


if __name__ == "__main__":
    main()
