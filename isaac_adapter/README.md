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

### 승인 Stage 저장과 다음 작업 복원

Runner는 작업이 끝나면 현재 Stage를 자동으로
`SITEGIT_DATA_ROOT/isaac/pending/<project>/<branch>/.../stage.usda`에 저장합니다.
이 파일은 아직 공식 맵이 아닙니다. 관리자가 Commit을 승인할 때 Backend가 이를
`isaac/branches/<project>/<branch>/commits/<commit>/stage.usda`로 승격하고
`head.json`을 갱신합니다. 다음 Runner 실행은 `head.json`이 가리키는 승인 Stage를
자동으로 열기 때문에 이전 굴착·성토 작업이 누적된 상태에서 계속 작업합니다.

```dotenv
SITEGIT_BRANCH=main
SITEGIT_RESTORE_BRANCH_HEAD=true
```

Commit 검토 중에는 다음 Work Package를 가져오지 않습니다. 승인되면 현재 Stage에서
계속 작업하고, 반려되면 승인 HEAD를 다시 불러와야 하므로 Runner가 안전하게 종료됩니다.
같은 실행 명령을 다시 입력하면 반려 작업을 제외한 마지막 승인 Stage로 돌아갑니다.
`--usd`를 직접 지정하면 자동 HEAD보다 해당 파일이 우선하며, `--no-site`는 자동 복원을
비활성화합니다.

### Authored excavator sensor mount

Keep the clean excavator asset in `SITEGIT_EQUIPMENT_ASSET`. If a separate USD
contains a LiDAR position adjusted in Isaac Sim, configure it only as a sensor
placement reference:

```dotenv
SITEGIT_SENSOR_REFERENCE_USD=E:\path\to\excavator_lidar.usd
SITEGIT_SENSOR_REFERENCE_PRIM=/World/LidarMount
SITEGIT_CAMERA_OFFSET_FROM_LIDAR=0.35,0,0.15
SITEGIT_CAMERA_LEVEL_HORIZON=true
```

The adapter reads only the referenced Prim transform. It does not compose the
reference USD's old map, cubes, cameras, or other Stage content into the live
site. `/World/Equipment/EXC_001/SiteGitSensors/RaycastLidar` and its sibling
`Camera` keep their mounted offsets while following the excavator. Horizon
levelling acts like a camera gimbal and keeps roll at zero on sloped terrain,
while LiDAR is refreshed before each evidence image so the green points in the
image belong to the same before/after phase.

현장 지형(`SITEGIT_DATA_ROOT/isaac/assets/construction_site_demolition.usdz`)이 함께
올라오고, 확정된 좌표계는 `SITEGIT_DATA_ROOT/isaac/site_frame.json`에 기록됩니다.
`--no-site`로 끄거나 `--site <경로>`로 다른 에셋을 지정할 수 있습니다.

기본 실행은 demolition 현장의 중앙 굴착 구간을 따라
`/World/Diggable/Pipeline/TrenchFill_01`부터 `TrenchFill_08`까지 독립 토사 Mesh를
만듭니다. 각 구간은 실제 지형 높이에 맞고 `sitegitDiggable=true`와 Collision을 가지므로
Work Package에서 순서대로 굴착할 수 있습니다. 원본 사진측량 Mesh는 변경하지 않습니다.

`SITEGIT_EQUIPMENT_ASSET`가 설정되면 굴착기도 `/World/Equipment/EXC_001`에
참조로 붙습니다. 이미 맵과 굴착기가 함께 저장된 Stage가 있다면 자동 로드 대신
다음처럼 그 Stage를 여는 편이 가장 정확합니다.

```powershell
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py `
  --usd E:\path\to\pipeline-site-with-excavator.usd `
  --save-usd E:\SiteGitData\isaac\stages\working.usda
```

Runner는 실제 Stage inventory를 5초마다 Backend에 보고합니다. 웹에서 선택 가능한
장비와 굴착 대상은 이 목록으로 제한됩니다. `excavate_prim`은 장비를 대상 앞으로 물리
이동·정렬하고 Track/ArmDig/ArmDump Skeleton 애니메이션을 재생합니다. 작업 시 독립 토사
Mesh의 정점을 실제로 낮춰 굴착면을 만들고, 제거 체적과 같은 체적의 새 토사 Mesh를 장비
옆에 생성합니다. 작업 전·후 장착 카메라/Stage/LiDAR Evidence와 정확한 변경 Mesh를
Commit하며, 승인 전에는 이 live Stage 변경이 공식 Work 맵에 노출되지 않습니다.

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
E:\isaacsim\python.bat isaac_adapter\build_web_usd_map.py `
  --source E:\SiteGitData\isaac\assets\construction_site_demolition.usdz `
  --output E:\SiteGitData\isaac\demolition-usd-web-bundle

.\.venv\Scripts\python.exe isaac_adapter\map_publisher.py `
  --source E:\SiteGitData\isaac\demolition-usd-web-bundle
```

첫 명령은 OBJ를 다시 조립하지 않고 Isaac Sim이 실제 렌더링하는 USDZ의 Mesh,
`st0` UV, material binding을 그대로 웹 번들로 내보냅니다. 따라서 RealityCapture
타일 텍스처가 서로 뒤섞이는 문제를 피합니다.

번들은 `sitegit-web-mesh-v1` 형식의 `manifest.json`, float32 geometry
`.bin`, texture 이미지로 구성됩니다. Backend가 실행 중이면 Site Work Map
화면을 새로고침하는 것만으로 새 맵을 확인할 수 있습니다.
