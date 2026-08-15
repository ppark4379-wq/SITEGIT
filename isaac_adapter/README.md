# Isaac Adapter

SiteGit과 Isaac Sim 사이의 유일한 연결 영역입니다.

```text
FastAPI ↔ sitegit_client.py ↔ work_package_mapper.py ↔ isaac_bridge.py ↔ Isaac Sim
                                                       ↓
                                             evidence_exporter.py
```

- Backend나 SQLite를 Isaac Sim에서 직접 열지 않습니다.
- 실제 Isaac API·ROS 2·Prim 경로 변경은 이 폴더만 수정합니다.
- Work Package/Evidence 필드 자체가 바뀌면 `contracts`도 함께 수정합니다.
- `mock_adapter.py`는 Isaac 없이 로그인·공동 상태 API를 검증합니다.

## 작업 폐루프 실행

웹에서 내린 지시를 가져와 실행하고 결과를 Commit합니다. 관리자가 승인해야 맵에
반영됩니다. 자세한 흐름은 `docs/ISAAC_INTEGRATION.md`를 보세요.

```powershell
# isaac_adapter/.env 준비 (SITEGIT_PASSWORD 필수)
Copy-Item isaac_adapter\.env.example isaac_adapter\.env
```

**실제 Isaac Sim 연결** — Isaac의 Python으로 실행합니다. `omni`/`pxr`은
SimulationApp 부팅 후에만 import되므로 프로젝트 `.venv`로는 안 됩니다.

```powershell
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py
```

현장 지형(`SITEGIT_DATA_ROOT/isaac/assets/construction_site_mud.usdz`)이 함께
올라오고, 확정된 좌표계는 `SITEGIT_DATA_ROOT/isaac/site_frame.json`에 기록됩니다.
`--no-site`로 끄거나 `--site <경로>`로 다른 에셋을 지정할 수 있습니다.

기본 실행은 `/World/Diggable/ZoneA_SoilPile_01`에 독립 토사 Mesh를 만듭니다. Mud Map의
실제 삼각형 높이를 계산해 지면에 붙이고 `sitegitDiggable=true`와 Collision을 지정하므로,
재질별 대형 `Object_*` 메시 대신 이 Prim만 굴착 목록에 나타납니다. 기본 위치·크기는
`SITEGIT_DEMO_SOIL_PILE_POSITION=-12,12`, `SITEGIT_DEMO_SOIL_PILE_SIZE=6,5,2.5`이며
`--no-demo-soil`로 끌 수 있습니다.

`SITEGIT_EQUIPMENT_ASSET`가 설정되면 굴착기도 `/World/Equipment/EXC_001`에
참조로 붙습니다. 이미 맵과 굴착기가 함께 저장된 Stage가 있다면 자동 로드 대신
다음처럼 그 Stage를 여는 편이 가장 정확합니다.

```powershell
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py `
  --usd E:\path\to\mud-with-excavator.usd `
  --save-usd E:\SiteGitData\isaac\stages\working.usda
```

Runner는 실제 Stage inventory를 5초마다 Backend에 보고합니다. 웹에서 선택 가능한
장비와 굴착 대상은 이 목록으로 제한되며, 굴착된 토사 Prim은 `active=false`로 계속
보고되어 승인 전 웹 기준 형상이 유지됩니다. `excavate_prim`은 장비 루트를 대상 앞으로
이동하면서 에셋의 Track/ArmDig/ArmDump Skeleton 애니메이션을 재생한 뒤 대상 Prim을
비활성화하고, 작업 전·후 Viewport/Stage/LiDAR Evidence를 Commit합니다. 토사의 연속
물리 변형은 아직 이 인터페이스 뒤에 연결되지 않았습니다.

DB에 저장되는 좌표는 이 현장 좌표계(Z-up · meter · 지면 Z=0)입니다. 웹 뷰어는
지형 mesh 좌표로 변환해 그립니다. 자세한 내용은 `docs/ISAAC_INTEGRATION.md`.

**배관만 검증** — Isaac 없이 지시값을 그대로 되돌립니다. 실제 실행이 아닙니다.

```powershell
.\.venv\Scripts\python.exe isaac_adapter\cube_task_runner.py --interval 3
```

두 러너는 같은 지시를 가져가려고 경쟁하므로 **동시에 켜지 마세요.**
Commit의 `result.simulator`가 `isaac-sim`이면 진짜, `simulated-cube-bridge`면
가짜입니다.

## Site Work Map 게시

Isaac Sim에서 웹용 Mesh 번들을 내보낸 뒤 다음 명령으로 현재 SiteGit
런타임에 게시합니다. 대용량 geometry와 texture는 Git이 아니라
`SITEGIT_DATA_ROOT/isaac/site-work-map`에 저장됩니다.

```powershell
.\.venv\Scripts\python.exe isaac_adapter\map_publisher.py `
  --source E:\path\to\exported-mud-map
```

번들은 `sitegit-web-mesh-v1` 형식의 `manifest.json`, float32 geometry
`.bin`, texture 이미지로 구성됩니다. Backend가 실행 중이면 Site Work Map
화면을 새로고침하는 것만으로 새 맵을 확인할 수 있습니다.
