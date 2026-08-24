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

Backend도 실행한 뒤 웹의 도면 기반 계획에서 **계획 승인 · 터파기 3건 하달**을 누르면,
세 지시는 같은 `execution_group_id`로 묶입니다. Runner는 `EXC-001~003`과 세 작업전선을
모두 준비한 다음 작업 전 Evidence를 촬영하고, 기본 5회의 굴착 사이클을 같은
타임라인에서 실행합니다. 작업이 끝나면 작업전선마다 독립 Evidence Commit을 남깁니다.
이때 웹과 분리된 아래 데모 러너는 함께 실행하지 마세요.

관로 공사 요청 한 건은 하나의 `scenario_run_id` 아래 다음 순서로 진행됩니다.

1. Zone A 관로 공사의 1단계 터파기 3건 실행 → 작업전선별 Evidence Commit 검토
2. 세 Commit 모두 승인 → 2단계 관로 설치 계획 검토·승인 버튼 활성화
3. 2단계 계획 승인 → 관로 설치 3건 실행 및 Evidence Commit 검토
4. 세 Commit 모두 승인 → 3단계 되메우기 계획 검토·승인 버튼 활성화
5. 3단계 계획 승인 → 되메우기 3건 실행 및 Evidence Commit 검토
6. 마지막 세 Commit 승인 → 상위 관로 공사 진행률 100%, 전체 공정 완료

후속 공정은 선행 Evidence 승인만으로 즉시 실행되지 않습니다. 관리자가 작업 현황에서
해당 Zone의 **계획 검토·승인**을 눌러 작업량·장비·공정별 판정 기준을 다시 확인해야
Runner가 그 그룹을 가져갑니다. Zone A의 3단계 실행은 굴착 때 생성된 실제 `MovedSoil` Mesh를
5단계로 소모하면서 `TrenchFill_01~08`을 복원하고, 작업전선마다 카메라·LiDAR·IMU
Evidence와 Stage read-back 결과를 별도 Commit합니다.

### 웹과 분리된 굴착기 3대 데모

Backend, Work Package, Commit을 사용하지 않고 Isaac Sim 안에서만 작업 동작을 먼저
확인하려면 저장소 루트에서 다음 파일을 실행합니다.

```powershell
.\start_sitegit_excavator_demo.bat
```

독립 시나리오 실행 파일은 기본적으로 최대화된 일반 창에 Viewport만 표시합니다.
`Alt+Tab`으로 웹에 전환하거나 제목 표시줄에서 창을 복원·이동할 수 있습니다.
`F7`로 Isaac 편집 UI를 잠시 복구하고 `F11`로 선택적으로 전체 화면을 켤 수 있습니다.
처음부터 Stage·Property·Content 패널을 표시하려면 `-EditorUi`를 붙입니다.

```powershell
.\start_sitegit_excavator_demo.bat -EditorUi
```

이 데모는 `contracts/site_plans/demolition_pipeline_v1.json`의 남·중앙·북 작업전선을
읽어 `EXC-001~003`을 관로 양쪽에 엇갈려 배치합니다. 준비 이동이 끝나면 세 장비의
Arm 애니메이션을 같은 타임라인에 걸어 기본 5회의 굴착·선회·배토·정면 복귀를 동시에 실행합니다.
각 버킷 사이클 직후 토사 Mesh가 한 단계씩 낮아지고 제거 체적만큼의 토사가 옆에
나뉘어 쌓입니다. 마지막 버킷은 가장자리까지 굴착 저면으로 정리하므로 기본 실행에서는
세 구간이 모두 파입니다. `-IntentionalDefect`를 지정하면 중앙 `EXC-002`만 최종 누적
굴착률이 낮아져 미굴착 결함이 남습니다. 실행이 끝난 Stage는 일시 정지되며 Isaac 창을 닫을 때까지
확인할 수 있습니다.

```powershell
# 애니메이션을 짧게 검증
.\start_sitegit_excavator_demo.bat -Fast

# 굴착 횟수를 바꿔 단계별 지형 감소 확인
.\start_sitegit_excavator_demo.bat -Scoops 6

# 가운데 작업전선에 의도적인 미굴착을 남기는 검토 시나리오
.\start_sitegit_excavator_demo.bat -IntentionalDefect

# GUI를 닫고 결과 Stage도 따로 저장
.\start_sitegit_excavator_demo.bat -CloseOnFinish `
  -SaveUsd E:\SiteGitData\isaac\three-excavator-demo\result.usda
```

결과 요약은 `SITEGIT_DATA_ROOT/isaac/three-excavator-demo/report.json`에 기록됩니다.
이 실행 파일은 API 호출이나 웹 맵 반영을 하지 않습니다.

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

### Zone A phase 2 pipe-installation demo

The excavation demo always exports
`SITEGIT_DATA_ROOT/isaac/three-excavator-demo/excavated-stage.usda`, allowing the
next construction phase to continue from the exact excavated geometry.

```powershell
.\start_sitegit_pipeline_demo.bat

# Short animation smoke check
.\start_sitegit_pipeline_demo.bat -Fast
```

The demo places one short handling pipe beside each work front's spoil bank.
The physical excavators remain on stable upper ground, pick up one prop each,
face the trench, and lower all three from above. The props then disappear and
the complete drawing-aligned route appears in one frame. The resulting Stage
and report are stored under
`SITEGIT_DATA_ROOT/isaac/pipeline-installation-demo`.

### Authored excavator sensor mount

Keep the clean excavator asset in `SITEGIT_EQUIPMENT_ASSET`. If a separate USD
contains a LiDAR position adjusted in Isaac Sim, configure it only as a sensor
placement reference:

```dotenv
SITEGIT_SENSOR_REFERENCE_USD=E:\path\to\excavator_lidar.usd
SITEGIT_SENSOR_REFERENCE_PRIM=/World/LidarMount
SITEGIT_CAMERA_OFFSET_FROM_LIDAR=0.65,0.10,0.25
SITEGIT_CAMERA_PITCH_DEG=24
SITEGIT_CAMERA_FOCAL_LENGTH_MM=12
SITEGIT_CAMERA_LEVEL_HORIZON=true
SITEGIT_LIDAR_HORIZONTAL_FOV_DEG=130
SITEGIT_LIDAR_VERTICAL_MIN_DEG=-70
SITEGIT_LIDAR_VERTICAL_MAX_DEG=10
SITEGIT_LIDAR_HORIZONTAL_RAYS=101
SITEGIT_LIDAR_VERTICAL_RAYS=31
SITEGIT_LIDAR_MIN_RANGE_M=0.35
SITEGIT_LIDAR_MAX_RANGE_M=25
```

The adapter reads only the referenced Prim transform. It does not compose the
reference USD's old map, cubes, cameras, or other Stage content into the live
site. `/World/Equipment/EXC_001/SiteGitSensors/RaycastLidar` and its sibling
`Camera` keep their mounted offsets while following the excavator. Horizon
levelling acts like a camera gimbal and keeps roll at zero on sloped terrain,
while LiDAR is refreshed before each evidence image so the green points in the
image belong to the same before/after phase.

The standalone three-excavator demo applies this same fixed mount to all three
machines and writes clean before/after PNG images plus world-space LiDAR PLY
files under `SITEGIT_DATA_ROOT/isaac/three-excavator-demo/sensors/EXC-00X`.
The tuned 82.3 by 52.3 degree camera view includes the bucket, trench face, and
excavated floor; the LiDAR covers 130 degrees horizontally, -70 to +10 degrees
vertically, and 0.35 to 25 metres. Use `-SkipSensors` only when a fast motion-only
run is needed.

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
