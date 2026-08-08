# Isaac Sim 연결

Isaac Sim은 Frontend와 SQLite에 직접 연결하지 않습니다. 반드시 HTTP API를 통합니다.

```text
FastAPI ↔ isaac_adapter/sitegit_client.py
        ↔ work_package_mapper.py
        ↔ isaac_bridge.py
        ↔ Isaac Sim
                ↓
          evidence_exporter.py → SSD + FastAPI
```

## 폐루프 — 지시부터 맵 반영까지

목표는 "웹에서 지시하면 Isaac이 작업하고, 관리자가 승인해야 맵이 바뀐다"입니다.

```text
① 웹        관리자가 작업 지시 발행            POST /isaac/instructions      → pending
② Adapter   대기 지시를 가져감                 POST /isaac/instructions/claim → dispatched
③ Isaac     실제 작업 수행                     isaac_bridge.place_cube()
④ Adapter   결과 Commit                        POST /isaac/instructions/{id}/commit → committed
⑤ 웹        관리자가 승인 또는 반려            POST /isaac/commits/{id}/review → approved / rejected
⑥ 맵        승인된 결과만 렌더링               GET  /isaac/map-objects
```

**⑤를 통과하지 않은 결과는 어떤 화면에도 작업 결과로 나타나지 않습니다.** 이것이 이
구조의 유일한 불변식이고, `tests/test_isaac_loop.py`가 이를 고정합니다.

### 맵 오브젝트 테이블이 없는 이유

승인된 Commit이 곧 맵 오브젝트입니다. 별도 테이블에 복사해 두면 승인을 되돌렸을 때
두 저장소가 어긋나므로, `GET /isaac/map-objects`는 조회할 때마다 승인된 Commit에서
만들어냅니다.

## 현장 좌표계 — 단 하나의 기준

DB에 저장되는 모든 좌표는 **Isaac 현장 좌표계**입니다.

```text
Z-up · meter · XY 중심이 원점 · 지면이 Z = 0

  X  ±106 m   좌우
  Y  ±114 m   앞뒤
  Z  0~12 m   높이
```

`isaac_adapter/site_stage.py`가 현장 USD를 올리면서 이 기준을 만들고,
결과를 `SITEGIT_DATA_ROOT/isaac/site_frame.json`에 기록합니다.

### 왜 변환이 필요한가

현장 에셋(usdz)은 **centimeter · Y-up**이고, 웹 뷰어가 그리는 지형 mesh는
**원본 OBJ 좌표(Y-up, 중심 정렬 안 됨)** 입니다. USD는 참조를 붙일 때 단위와
업축을 자동 변환하지 않으므로 그대로 두면 21 km 크기로 옆으로 누워 들어옵니다.

| 단계 | 보정 |
|---|---|
| usdz → Isaac Stage | scale 0.01 (cm→m), X축 +90° 회전 (Y-up→Z-up), XY 중심·지면 정렬 |
| 현장 좌표 → 웹 mesh | `webX = siteX + centerX`, `webY = siteZ + minY`, `webZ = -siteY + centerZ` |

웹 변환 상수는 mesh manifest의 `bounds`에서 그대로 유도하므로 하드코딩이
없습니다(`frontend/isaac-map-viewer.js`의 `siteToMesh`). 두 계가 어긋나면
큐브가 지형 밖이나 엉뚱한 자리에 그려지므로, 정렬 규칙을 바꿀 때는 반드시
양쪽을 함께 고쳐야 합니다.

### 지형과 작업 결과의 분리

| 레이어 | 저장 위치 | 갱신 방법 |
|---|---|---|
| 지형 Mesh | `SITEGIT_DATA_ROOT/isaac/site-work-map` (SSD) | `map_publisher.py`로 수동 재게시 |
| 작업 결과 | SQLite `execution_commits` | 승인 즉시 WebSocket으로 반영 |

지형은 60MB짜리 정적 번들이라 실시간으로 흘려보내지 않습니다. 굴착으로 지형 자체가
변하면 그때 재게시합니다. 반면 작업 결과는 가볍고 자주 바뀌므로 DB에 두고 실시간으로
반영합니다.

### 실시간 알림

승인이 일어나면 기존 `/state/ws/{project_id}` 소켓으로 아래 메시지가 나갑니다. 별도
소켓을 열지 않습니다.

```json
{"type": "isaac.map.updated", "reason": "review.approved", "commit_id": "..."}
```

브라우저는 이 메시지를 받아 3D 뷰어 iframe에 `postMessage`로 다시 읽으라고 알립니다.

## 실행 — 실제 Isaac Sim 연결

**반드시 Isaac Sim의 Python으로 실행합니다.** `omni`와 `pxr`은 `SimulationApp`이
부팅된 뒤에만 import되므로 프로젝트 `.venv`에서는 Stage에 접근할 수 없습니다.
`isaac_bridge.py`가 USD를 모듈 최상단이 아니라 메서드 안에서 import하는 이유도
이 제약 때문입니다.

현장 지형은 기본으로 함께 올라옵니다. 에셋은 대용량이라 Git이 아니라 SSD에 둡니다.

```text
SITEGIT_DATA_ROOT/isaac/assets/construction_site_mud.usdz   (302 MB)
```

```powershell
# GUI로 큐브가 생기는 것을 보면서
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py

# 지형 없이 빈 Stage로
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py --no-site

# 다른 현장 에셋으로
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py --site D:\other\site.usdz

# 화면 없이
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py --headless

# 현장 USD를 열어 둔 채로, 작업 결과를 USD로 남기며
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py `
  --usd E:\SiteGitData\isaac\site.usd --save-usd E:\SiteGitData\isaac\site_after.usd
```

> **가짜 러너와 동시에 돌리지 마세요.** `cube_task_runner.py`도 같은 지시를
> claim하므로 둘을 함께 켜 두면 어느 쪽이 가져갈지 알 수 없습니다. 실제 연동을
> 확인할 때는 `cube_task_runner.py`를 Ctrl+C로 끄세요.

### 무엇이 진짜인지 구분하는 법

Commit의 `result.simulator` 필드를 보면 됩니다.

| 값 | 의미 |
|---|---|
| `isaac-sim` + `source: stage-readback` | Isaac Stage에 Prim이 실제로 생겼고, 그 값을 다시 읽었습니다 |
| `simulated-cube-bridge` + `source: echo` | Isaac이 돌지 않았습니다. 지시값을 그대로 되돌린 것뿐입니다 |

`isaac_bridge.SimulatedCubeBridge`는 Isaac 없이 **배관만** 검증하는 용도입니다.
이 브릿지가 만든 결과는 "Isaac이 확인한 값"이 아닙니다.

### 지시값이 아니라 Stage를 읽습니다

`IsaacBridge.place_cube`는 Prim을 만든 뒤
`UsdGeom.Xformable.ComputeLocalToWorldTransform()`으로 월드 변환을 **다시 읽어**
`placed_position`으로 보고합니다. 웹 맵은 지시값이 아니라 이 값을 그리므로,
나중에 지형 스냅이나 충돌 회피로 Isaac 쪽 위치가 보정되면 웹도 보정된 위치를
보여줍니다. `tests/test_isaac_loop.py`가 이 동작을 고정합니다.

### 아직 남은 간극

웹 3D 뷰는 Isaac의 화면을 스트리밍하는 것이 아니라, 보고받은 좌표로 큐브를
**다시 그리는** 것입니다. 형상이 단순한 지금은 차이가 없지만, 굴착으로 지형
자체가 변하면 좌표만으로는 표현할 수 없습니다. 그때는 Isaac에서 변형된 Mesh를
내보내 `map_publisher.py`로 재게시하는 경로를 써야 합니다.

## 다음 단계 — 센서 Evidence

`ExecutionCommit.evidence`가 그 자리입니다. 지금은 비어 있습니다.

```json
{
  "sensors": ["lidar_point_cloud", "camera_rgb", "bucket_imu"],
  "storage_keys": ["sasang/WP-C01/exec-001/after.pcd"],
  "metrics": {"bucket_angle_deg": 32.4, "depth_mm": 1004}
}
```

LiDAR point cloud, 카메라 이미지 같은 대용량 파일은 JSON에 담지 않습니다.
`evidence_exporter.py`로 SSD에 저장한 뒤 상대 `storage_key`만 기록합니다. 형식이
바뀌면 `contracts/schemas/execution_commit.schema.json`을 먼저 수정합니다.
