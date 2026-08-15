# SiteGit v0.2 — Git-ready Modular Local Shared Platform

현재 추천 조합을 기준으로 만든 GitHub 업로드용 구조입니다.

> **Private GitHub + 대표 PC FastAPI + 외장 SSD SQLite/Evidence + Cloudflare Named Tunnel 고정 URL + Isaac Adapter**

기존 SiteGit v2 화면과 로그인·공동 저장 기능은 그대로 실행하면서, 팀원이 어디를 수정해야 하는지 바로 보이도록 최종 책임 구조를 고정했습니다.

---

## 0. 처음 실행하기 — 외장 SSD·Isaac Sim 없이

### 준비물

- Windows 10/11
- Python 3.11 이상
- Git
- PowerShell

저장소를 내려받고 프로젝트 폴더로 이동합니다.

```powershell
git clone https://github.com/ysj20030825-lab/SITEGIT.git
cd SITEGIT
```

PowerShell 실행 정책을 현재 창에서만 허용하고 최초 설정을 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ops\scripts\setup_windows.ps1
```

이 스크립트는 다음 작업을 자동으로 수행합니다.

- `.env`가 없으면 예시 설정을 복사해 생성
- `.venv` Python 가상환경 생성
- Backend 패키지 설치

생성된 `.env`를 엽니다.

```powershell
notepad .env
```

로컬 확인용으로 다음처럼 설정할 수 있습니다.

```env
APP_NAME=SiteGit
APP_ENV=development

PUBLIC_URL=http://localhost:8000
PUBLIC_HOSTNAME=localhost
SERVER_HOST=127.0.0.1
SERVER_PORT=8000

# 외장 SSD가 없으면 프로젝트 내부 runtime 폴더 사용
SITEGIT_DATA_ROOT=./runtime
DATABASE_URL=

# Isaac Sim 없이 실행
ISAAC_ADAPTER_ENABLED=false
ISAAC_ADAPTER_URL=http://localhost:8100

# 로컬 개발용 긴 임의 문자열. 운영 서버에서는 새 값 사용
JWT_SECRET=local-development-secret-change-me-2026-123456789
ACCESS_TOKEN_EXPIRE_MINUTES=480
AUTH_COOKIE_NAME=sitegit_access_token
COOKIE_SECURE=false

INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=admin-password-change-me
INITIAL_ADMIN_NAME=로컬 관리자

SEED_DEMO_USERS=true
INITIAL_MANAGER_USERNAME=manager
INITIAL_MANAGER_PASSWORD=manager-password-change-me
INITIAL_MANAGER_NAME=현장 관리자

INITIAL_VIEWER_USERNAME=viewer
INITIAL_VIEWER_PASSWORD=viewer-password-change-me
INITIAL_VIEWER_NAME=현장 조회자

# Cloudflare를 사용하지 않으면 비워 둠
CLOUDFLARE_TUNNEL_TOKEN=
```

`JWT_SECRET`은 로그인 토큰에 서명하는 서버 전용 비밀 키입니다. 로컬 테스트에서는 위와 같은 긴 임의 문자열로 충분하지만 `.env`는 Git에 올리지 않습니다. 더 강한 값을 만들려면 PowerShell에서 실행합니다.

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

서버를 실행합니다.

```powershell
.\ops\scripts\start_sitegit.ps1
```

또는 탐색기에서 `start_sitegit.bat`을 실행할 수 있습니다. PowerShell 창을 닫으면 서버도 종료됩니다.

브라우저 접속 주소:

- 웹 화면: <http://localhost:8000>
- 서버 상태: <http://localhost:8000/api/v1/health>
- 개발 API 문서: <http://localhost:8000/api/v1/docs>

로그인 아이디와 비밀번호는 `.env`의 `INITIAL_*_USERNAME`, `INITIAL_*_PASSWORD` 값입니다. 마지막으로 성공한 로그인 아이디만 브라우저에 기억되며 비밀번호는 항상 빈 상태로 시작합니다. 로그인 인증은 브라우저 세션 쿠키이므로 브라우저를 완전히 종료한 뒤 다시 열면 로그인 화면으로 돌아갑니다.

`.env`에서 초기 계정의 아이디·비밀번호·표시 이름을 바꾼 뒤 서버를 재시작하면 DB의 해당 초기 계정에도 동기화됩니다.

### `.env`가 GitHub에 없는 이유

`.env`에는 비밀번호, JWT 서명 키, 서버 경로가 포함되므로 `.gitignore`로 제외합니다. Git에는 변수 형식만 담은 `.env.example`이 올라갑니다. 저장소를 처음 받은 사람은 `setup_windows.ps1`을 실행하거나 다음 명령으로 자기 PC의 `.env`를 만듭니다.

```powershell
Copy-Item .env.example .env
```

확인 방법:

```powershell
git check-ignore .env
```

출력에 `.env`가 나오면 정상적으로 Git에서 제외된 상태입니다.

### 로컬 데이터 위치

위 설정에서는 사용자, 프로젝트와 작업 데이터가 다음 경로에 저장됩니다.

```text
runtime/database/sitegit.db
```

코드를 `git pull`해도 `.env`와 `runtime` 데이터는 덮어쓰지 않습니다.

---

## 1. 전체 연결

```text
팀원 브라우저
    ↓ https://sitegit.example.com
Cloudflare Named Tunnel
    ↓
대표 PC FastAPI
    ├─ Frontend 제공
    ├─ 로그인·권한
    ├─ 7단계 SiteGit 기능
    ├─ 외장 SSD SQLite/Evidence
    └─ Isaac Adapter API
              ↕
          Isaac Sim
```

Cloudflare는 DB가 아니라 외부 접속 통로입니다. GitHub는 코드 저장소이고, 외장 SSD는 실제 프로젝트 데이터 저장소입니다.

---

## 2. 폴더 구조

```text
sitegit/
├─ frontend/                    # 사용자가 보는 웹
│  ├─ index.html, styles.css
│  ├─ app.js                    # 현재 실행되는 v2 호환 UI
│  ├─ pages/                    # 화면별 분리 위치
│  └─ services/                 # API·실시간 통신
│
├─ backend/app/                 # 기능·DB·로그인·판정
│  ├─ domains/                  # 7단계
│  │  ├─ site_data/             # 1
│  │  ├─ work_packages/         # 2
│  │  ├─ equipment/             # 3
│  │  ├─ executions/            # 4
│  │  ├─ evidence/              # 5
│  │  ├─ trust_gate/            # 6
│  │  └─ versioning/            # 7
│  ├─ api/, db/, models/
│  ├─ policies/                 # 정책 JSON 로더
│  ├─ storage/                  # SSD 경로 처리
│  └─ main.py
│
├─ isaac_adapter/               # SiteGit ↔ Isaac Sim
├─ contracts/                   # 공통 JSON Schema·예시
├─ policies/                    # 쉽게 바꾸는 평가 기준
├─ ops/                         # URL·서버·SSD·실행 관리
├─ seed/                        # 사상구 초기 데이터
├─ tests/
├─ docs/
├─ .env.example
└─ start_sitegit.bat
```

---

## 3. 딱 어디를 수정하면 되는가

| 작업 | 수정 폴더 |
|---|---|
| 웹 화면·디자인 | `frontend` |
| 기능·DB·Conflict 계산 | `backend` |
| Isaac Sim 연동 | `isaac_adapter` |
| 주고받는 JSON 필드 | `contracts` |
| Evidence·Conflict·Release 기준값 | `policies` |
| 고정 URL·포트·SSD 경로·비밀번호 | 실제 `.env`, `ops` |
| 초기 데모값 | `seed` |

새 기능이 여러 영역을 통과하면 관련 폴더를 함께 수정합니다. 예를 들어 새로운 `slope_error_degree` 값을 추가하면 `contracts` → `isaac_adapter` → `backend` → 필요 시 `frontend` 순서입니다.

---

## 4. 현재 동작 범위와 한계

### 동작

- 기존 SiteGit v2 UI
- `admin`, `manager`, `viewer` 로그인
- 외장 SSD의 SQLite 공동 상태 저장
- 여러 브라우저의 동일 프로젝트 조회·수정
- Revision 충돌 감지와 WebSocket 변경 알림
- 감사 로그
- Cloudflare 고정 URL 설정 템플릿
- Mock Isaac Adapter
- 정책 조회 API: `/api/v1/policies`
- Isaac 작업 폐루프: 웹 지시 → 실행 → Commit → 관리자 승인 → 3D 맵 반영

### 아직 구조만 만든 부분

기존 UI를 깨지 않기 위해 현재 프로젝트·Work Package·Evidence는 호환용 `project_states.payload` JSON에도 함께 저장됩니다. `backend/app/domains/*`는 최종 책임 위치이지만, 각 항목을 독립 DB 테이블과 API로 완전히 분리하는 작업은 다음 단계입니다.

또한 기존 `frontend/app.js`에는 컨셉 UI의 임시 Conflict 기준이 일부 남아 있습니다. 새 기준의 원본은 `policies/`이며, 다음 단계에서 판정 계산을 `backend/domains/trust_gate`로 옮깁니다.

---

## 5. 외장 SSD 준비 — 선택 사항

로컬 기능 확인에는 외장 SSD가 필요하지 않습니다. `.env`에서 다음처럼 프로젝트 내부 저장소를 사용할 수 있습니다.

```env
SITEGIT_DATA_ROOT=./runtime
```

운영용 대표 PC에서 외장 SSD를 사용하려면 다음 구조를 권장합니다.

```text
E:/SiteGitData/
├─ database/
├─ evidence/
├─ isaac/
├─ logs/
└─ backups/
```

실행하면 없는 폴더는 자동 생성됩니다. DB에는 절대 파일 경로 대신 `sasang/WP-C01/...` 같은 상대 `storage_key`를 저장하는 방향으로 구성합니다.

### 외장 SSD를 들고 다니며 개발할 때

저장소와 데이터를 같은 SSD에 두고 여러 PC에 번갈아 꽂는다면 **상대경로**를 사용합니다. PC마다 드라이브 문자가 `E:`에서 `F:`로 바뀌어도 그대로 동작합니다.

```text
(SSD 루트)
├─ SITEGIT/          ← 저장소
└─ SiteGitData/      ← 데이터
```

```env
SITEGIT_DATA_ROOT=../SiteGitData
```

상대경로는 실행 위치가 아니라 **저장소 루트**를 기준으로 해석됩니다. 따라서 `start_sitegit.ps1`, IDE, 수동 `uvicorn` 중 무엇으로 띄우든 같은 폴더를 가리킵니다. Backend, `ops` 스크립트, `isaac_adapter/map_publisher.py`가 모두 같은 규칙을 씁니다.

절대경로(`E:/SiteGitData`)는 SSD를 상시 운영 PC에 고정할 때만 쓰세요. 드라이브 문자가 바뀌면 서버가 오류 없이 **빈 DB를 새로 만들기** 때문에 이동용으로는 위험합니다.

주의할 점 두 가지입니다.

- **안전 제거.** 서버 실행 중 SSD를 뽑으면 SQLite가 손상됩니다. `stop_sitegit.ps1`로 서버를 끈 뒤 안전하게 제거하세요.
- **백업.** `backup_database.ps1`은 같은 SSD의 `backups/`에 복사합니다. SSD 분실·고장에 대비해 다른 물리 디스크에도 주기적으로 복사하세요.

---

## 6. Windows 운영 PC 첫 실행

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ops\scripts\setup_windows.ps1
notepad .env
```

`.env`에서 최소한 다음을 수정합니다.

```env
PUBLIC_URL=https://sitegit.example.com
PUBLIC_HOSTNAME=sitegit.example.com
SITEGIT_DATA_ROOT=E:/SiteGitData
JWT_SECRET=<충분히 긴 임의 문자열>
INITIAL_ADMIN_PASSWORD=<관리자 비밀번호>
INITIAL_ADMIN_NAME=<관리자 표시 이름>
INITIAL_MANAGER_USERNAME=<팀원 아이디>
INITIAL_MANAGER_PASSWORD=<팀원 비밀번호>
INITIAL_MANAGER_NAME=<팀원 표시 이름>
INITIAL_VIEWER_USERNAME=<조회자 아이디>
INITIAL_VIEWER_PASSWORD=<조회자 비밀번호>
INITIAL_VIEWER_NAME=<조회자 표시 이름>
COOKIE_SECURE=false
```

서버 실행:

```powershell
.\ops\scripts\start_sitegit.ps1
```

브라우저:

```text
http://localhost:8000
```

상태 확인:

```text
http://localhost:8000/api/v1/health
```

개발 API 문서:

```text
http://localhost:8000/api/v1/docs
```

---

## 7. 고정 URL

`ops/cloudflare/SETUP_FIXED_URL.md`를 따라 Named Tunnel을 설정합니다.

```text
https://sitegit.example.com
        ↓
Cloudflare Tunnel
        ↓
http://localhost:8000
```

실행:

```powershell
.\ops\scripts\start_tunnel.ps1
```

공개 전 `.env`를 다음처럼 바꿉니다.

```env
APP_ENV=production
COOKIE_SECURE=true
```

Cloudflare 인증 JSON, 실제 `config.yml`, Tunnel token은 Git에 올리지 않습니다.

---

## 8. Isaac Sim 연결

```text
FastAPI
  ↕ isaac_adapter/sitegit_client.py
Work Package Mapper
  ↕
isaac_bridge.py
  ↕
Isaac Sim
  ↓
evidence_exporter.py → 외장 SSD + FastAPI
```

처음에는 다음으로 API 경계만 검증합니다.

```powershell
python isaac_adapter/mock_adapter.py
```

실제 Stage·Prim·로봇·ROS 2 코드는 `isaac_adapter/isaac_bridge.py`에 추가합니다. Isaac Sim이 SQLite를 직접 수정해서는 안 됩니다.

### 작업 폐루프

웹에서 지시를 내리면 Isaac이 실행하고, 관리자가 승인해야 맵이 바뀝니다.

```text
① 웹      작업 지시 발행          → pending
② Adapter 지시 수신               → dispatched
③ Isaac   실제 작업 수행
④ Adapter 결과 Commit             → committed
⑤ 웹      관리자 승인 / 반려      → approved / rejected
⑥ 맵      승인된 결과만 렌더링
```

**⑤를 통과하지 않은 결과는 맵에 나타나지 않습니다.** 메인 맵 왼쪽의 Work Package
패널은 실행 중인 Isaac Stage가 보고한 장비 Prim과 `sitegitDiggable=true`가 지정된
독립 토사 Mesh Prim만 보여줍니다. Mud Map의 `Object_*`는 재질별 대형 메시 묶음이라
굴착 대상으로 사용하지 않습니다.
LLM이 임의의 Prim 경로를 만들 수 없으며, Backend가 최신 inventory와 정확히 일치하는
경로만 `excavate_prim` 지시로 발행합니다.

```powershell
Copy-Item isaac_adapter\.env.example isaac_adapter\.env

# 실제 Isaac Sim 연결 — Isaac의 Python으로 실행합니다
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py

# Isaac 없이 배관만 검증 (실제 실행 아님)
.\.venv\Scripts\python.exe isaac_adapter\cube_task_runner.py --interval 3
```

두 러너는 같은 지시를 두고 경쟁하므로 동시에 켜지 마세요. Commit의 `result.simulator`가 `isaac-sim`이면 Isaac Stage에서 실제로 읽어온 값이고, `simulated-cube-bridge`면 지시값을 되돌린 것뿐입니다.

메인 맵 왼쪽 **Work Package** 패널에서 지시와 Commit을 확인합니다. 증거 버튼으로
작업 전·후 Viewport 이미지, Stage 상태, LiDAR PLY를 검토하고 승인합니다. 승인 전에는
맵이 바뀌지 않으며, 승인 후에는 실제 Target Prim의 Stage bounds가 브라우저 지형에서
반영됩니다. `/World/Diggable` 아래의 독립 토사 Prim은 정적 Mud Map을 잘라내지 않고,
웹의 토사 overlay가 승인 후 사라지는 방식으로 반영됩니다.

지형 Mesh와 작업 결과는 저장 위치가 다릅니다. 승인 직후에는 Target Prim의 실제
bounds로 정적 Mesh를 잘라 결과를 표시합니다. 구멍의 새 단면까지 포함한 완전한 지형
Mesh가 필요하면 Isaac에서 후보 번들을 다시 내보내 `map_publisher.py`로 재게시해야
합니다. 자세한 내용은 `docs/ISAAC_INTEGRATION.md`를 확인합니다.

Runner는 작업 전·후 Viewport PNG와 Stage JSON을 Evidence 폴더에 저장합니다.
`SITEGIT_LIDAR_POINTS_PRIM`에 실제 `UsdGeom.Points` Prim이 있으면 각 시점의 Point
Cloud도 PLY로 저장합니다. 센서가 없으면 Evidence에 누락 이유가 명시됩니다.

### 자연어 실제 Prim 굴착 Work Package

메인 맵 왼쪽의 **작업 지시 생성** 버튼은 로컬 Ollama의 JSON Schema Structured
Outputs로 자연어를 구조화합니다. LLM은 굴착 의도와 참조 이름만 추출하고, 실행할
장비와 대상은 Adapter가 보고한 실제 Stage Prim 목록에서 사용자가 선택합니다.

Ollama 앱에서 모델 위치를 SSD로 지정하고 `qwen3:8b`를 내려받습니다. 로컬 API라
OpenAI API 키와 크레딧은 필요하지 않습니다.

```powershell
ollama pull qwen3:8b
```

루트 `.env`에는 로컬 Ollama 연결 정보를 둡니다.

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT_SECONDS=90
```

Ollama 앱을 실행한 상태에서 Backend와 실제 Isaac Runner를 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\ops\scripts\start_sitegit.ps1

# 별도 PowerShell
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py
```

`isaac_adapter/.env`에서 장비 에셋과 Stage 경계를 설정합니다.

```dotenv
SITEGIT_EQUIPMENT_ASSET=E:\sitegit1\assets\construction_machinery\pbr-excavator-animated\source\Excavator\Excavator.usd
SITEGIT_EQUIPMENT_POSITION=0,0,0
SITEGIT_EQUIPMENT_PRIMS=/World/Equipment/EXC_001,/World/Armature
SITEGIT_DIGGABLE_ROOTS=/World/Diggable
SITEGIT_LIDAR_POINTS_PRIM=/World/SiteGitLiveLidarPoints
SITEGIT_MAX_EXCAVATION_TARGET_SPAN_M=25
SITEGIT_CREATE_DEMO_SOIL_PILE=true
SITEGIT_DEMO_SOIL_PILE_PRIM=/World/Diggable/ZoneA_SoilPile_01
SITEGIT_DEMO_SOIL_PILE_POSITION=-12,12
SITEGIT_DEMO_SOIL_PILE_SIZE=6,5,2.5
SITEGIT_DEMO_SOIL_PILE_ZONE=A
```

기본 데모 설정은 실제 Mud Map 삼각형에서 `(-12m, 12m)`의 표면 높이를 계산하고,
그 위에 `6×5×2.5m` 토사 Mesh와 Collision을 생성합니다. 위치와 크기는 위 환경변수로
바꿀 수 있으며 `--no-demo-soil`로 자동 생성을 끌 수 있습니다. 가로·세로 최대 폭이
25m를 넘는 Prim은 웹·Backend·승인 Gate·Isaac Adapter 모든 단계에서 거부됩니다.

예시 입력은 `선택한 굴착기로 Zone A의 선택한 Prim을 굴착해줘`입니다. Runner는
장비 루트를 대상 앞으로 이동시키고, 에셋에 포함된 `TrackAnimation` → `ArmDig` →
`ArmDump` 클립을 실제 Skeleton에 연결해 재생합니다. 정확한 Target Prim을 비활성화한
뒤 Stage read-back 결과를 Commit합니다. 현재는 독립 토사 Mesh Prim 단위 제거이며, 버킷과
토사의 연속 물리 변형은 최종 articulation/soil 시나리오에서 연결합니다.

---

## 9. GitHub 업로드

비공개 저장소를 만든 뒤:

```powershell
.\ops\scripts\init_git.ps1
git commit -m "chore: initialize SiteGit modular local shared platform"
git branch -M main
git remote add origin <PRIVATE_REPOSITORY_URL>
git push -u origin main

git checkout -b develop
git push -u origin develop
```

`.gitignore`는 `.env`, DB, PCD, USD, 영상, 로그, Evidence, Cloudflare 인증정보를 제외합니다.

---

## 10. Git과 SSD 경계

### GitHub

- Frontend·Backend·Isaac Adapter 코드
- JSON Schema와 예시
- 기본 Policies
- Seed
- 운영 템플릿과 스크립트
- 문서·테스트

### 외장 SSD

- 실제 사용자·권한
- 실제 Work Package와 장비 배정
- 진행률·Evidence·Conflict·Release 이력
- PCD·이미지·영상·Isaac 결과
- 실행 로그와 DB 백업

> JSON의 **형식과 기본값**은 Git, 그 형식으로 생성된 **실제 실행 데이터**는 SSD입니다.

---

## 11. 다음 개발 순서

1. 이 v0.2를 Private GitHub에 업로드
2. 대표 PC와 외장 SSD에서 로그인·공동 저장 확인
3. Cloudflare 고정 URL 연결
4. Work Package와 장비 배정을 독립 API/테이블로 이동
5. Mock Adapter 연결 후 실제 Isaac Bridge 구현
6. Evidence 등록 API 분리
7. `policies`를 읽는 Backend Conflict/Release 판정으로 전환
8. Version·Audit 흐름 정리

더 자세한 문서는 `docs/EDIT_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DATA_BOUNDARY.md`, `docs/ISAAC_INTEGRATION.md`, `ops/OPERATIONS.md`를 확인합니다.
