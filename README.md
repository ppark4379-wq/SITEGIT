# SiteGit v0.2 — Git-ready Modular Local Shared Platform

현재 추천 조합을 기준으로 만든 GitHub 업로드용 구조입니다.

> **Private GitHub + 대표 PC FastAPI + 외장 SSD SQLite/Evidence + Cloudflare Named Tunnel 고정 URL + Isaac Adapter**

기존 SiteGit v2 화면과 로그인·공동 저장 기능은 그대로 실행하면서, 팀원이 어디를 수정해야 하는지 바로 보이도록 최종 책임 구조를 고정했습니다.

---

## 0. 처음 실행하기

### 외장 SSD를 다른 Windows PC에서 실행

저장소, `SiteGitData`, Isaac Sim과 Ollama 모델을 같은 SSD에 둔 경우에는
먼저 루트의 환경 설정 파일을 한 번 실행합니다.

```powershell
.\start_sitegit_portable.bat
```

이 파일은 Backend나 Isaac Sim을 실행하지 않고, SSD 드라이브 문자를 자동
감지해 다음 환경만 준비합니다.

- Python 3.11 이상이 없으면 Python 3.12를 `winget`으로 설치
- Ollama 프로그램이 없으면 `winget`으로 설치
- `SiteGitData/tooling/venvs/<PC 이름>`에 PC별 Python 가상환경 생성
- Backend Python 패키지 설치
- 현재 SSD 위치를 기준으로 맵, 굴착기, LiDAR 기준 USD와 토사 재질 검색
- SSD의 `ollama/models`에서 설정된 모델 확인(없을 때만 SSD로 다운로드)
- SSD의 Isaac Sim과 NVIDIA 드라이버 확인

모델 데이터가 SSD에 있으면 다시 다운로드하지 않습니다. `ollama.exe`는 각
PC에 설치되지만, 모델은 계속 SSD의 파일을 사용합니다. 설치하지 않고 상태만
확인하려면:

```powershell
.\start_sitegit_portable.bat -CheckOnly
```

환경 준비가 끝나면 Backend와 Isaac Sim을 서로 다른 창에서 실행합니다.

```powershell
# 1번 창: Backend + Ollama + 웹
.\start_sitegit_backend.bat

# 2번 창: Isaac Sim + 현장/굴착기/센서 Adapter
.\start_sitegit_isaac.bat
```

### 심사위원 반복 시연: 매회 최초 지형으로 시작

심사위원마다 터파기 전 상태부터 다시 보여줄 때는 별도로 실행한 Backend와
Isaac Sim을 모두 닫고 아래 파일 하나만 실행합니다.

```powershell
.\start_sitegit_judge_demo.bat
```

이 런처는 직전 회차의 DB, Work Package/Commit/승인 기록, Evidence, 승인된
Isaac Branch HEAD와 웹 게시 기준 상태를 먼저
`SiteGitData/backups/demo-runs/<시각>`에 이동해 보관합니다. 그다음 새 Backend,
브라우저, 원본 지형의 Isaac Sim을 순서대로 실행합니다. 현장 USDZ, 텍스처,
WebGL 맵 번들, 충돌 캐시와 도면은 초기화하지 않습니다.

심사 시연에서는 Isaac Sim이 자동으로 **최대화된 일반 창의 Viewport 전용 모드**로
열립니다. Stage, Property, Content, 좌측 툴바와 Viewport 메뉴는 숨겨져 현장 장면만
보이지만 Windows 작업표시줄, `Alt+Tab`, 제목 표시줄은 유지됩니다. 제목 표시줄의
복원 버튼으로 창 크기를 줄여 웹과 나란히 놓을 수 있고, `F11`은 필요할 때만 진짜
전체 화면으로 전환합니다. 실행 중 `F7`은 편집 UI 표시/숨김입니다. 문제를 분석할 때
처음부터 기존 편집 화면으로 열려면 다음처럼 실행합니다.

```powershell
.\start_sitegit_judge_demo.bat -EditorUi
```

Isaac Sim 창을 닫으면 이 런처가 소유한 Backend도 종료됩니다. 다음 심사위원
차례에 같은 파일을 다시 실행하면 새 회차가 시작됩니다. 자동 실행 없이 상태만
초기화하려면 다음 파일을 사용한 뒤 기존 Backend/Isaac 런처를 각각 실행합니다.

```powershell
.\reset_sitegit_demo.bat
.\start_sitegit_backend.bat
.\start_sitegit_isaac.bat
```

일반 개발 중에는 `start_sitegit_backend.bat`과 `start_sitegit_isaac.bat`을 그대로
사용합니다. 이 두 파일은 승인 기록이나 Branch HEAD를 초기화하지 않습니다.

`start_sitegit_portable.bat`에 `-SkipOllama`를 주면 Ollama 설치와 모델 확인을
건너뜁니다. Isaac Sim 본체와 호환 NVIDIA 드라이버는 크기와 GPU 호환성 때문에
자동 설치하지 않으며, SSD의 `isaacsim` 설치본과 현재 PC 드라이버를 검사합니다.

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

프로젝트 폴더에서 아래 명령 하나만 실행합니다.

```powershell
.\start_sitegit.bat
```

PowerShell 실행 정책은 이 실행에만 자동으로 우회됩니다. 처음 실행할 때는 다음 작업도 자동으로 수행하고, 이후에는 곧바로 서버를 시작합니다.

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

다음 실행부터도 같은 명령을 사용합니다.

```powershell
.\start_sitegit.bat
```

탐색기에서 `start_sitegit.bat`을 더블클릭해도 됩니다. 서버는 `Ctrl+C`를 누르거나 실행 창을 닫으면 종료됩니다.

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

실제 Isaac Runner는 각 작업 완료 Stage를 pending USD로 자동 저장합니다. 관리자가
승인하면 해당 USD가 `main` Branch의 새 HEAD가 되고, 반려하면 기존 HEAD가 유지됩니다.
Isaac Sim을 껐다 다시 실행해도 최신 승인 Stage를 자동으로 Checkout하므로 이전 작업이
누적된 상태에서 다음 Work Package를 수행합니다.

```text
isaac/pending/<project>/main/.../stage.usda       # 승인 전 후보
isaac/branches/<project>/main/commits/<id>/stage.usda
isaac/branches/<project>/main/head.json           # 다음 실행이 여는 Stage
```

기본값은 `SITEGIT_BRANCH=main`, `SITEGIT_RESTORE_BRANCH_HEAD=true`입니다. 승인 대기
중에는 다음 지시를 실행하지 않으며, 반려 시 Runner가 종료되므로 같은 명령으로 다시
실행해 승인 HEAD 상태를 복원합니다.

**⑤를 통과하지 않은 결과는 맵에 나타나지 않습니다.** 메인 맵 왼쪽의 Work Package
패널은 실행 중인 Isaac Stage가 보고한 장비 Prim과 `sitegitDiggable=true`가 지정된
독립 토사 Mesh Prim만 보여줍니다. Demolition 현장의 사진측량 Mesh는 재질별 대형 묶음이라
굴착 대상으로 사용하지 않습니다.
LLM이 임의의 Prim 경로를 만들 수 없으며, Backend가 최신 inventory와 정확히 일치하는
경로만 `excavate_prim` 지시로 발행합니다.

```powershell
Copy-Item isaac_adapter\.env.example isaac_adapter\.env

# 실제 Isaac Sim 연결 — Isaac의 Python으로 실행합니다
E:\isaacsim\python.bat E:\SITEGIT\isaac_adapter\isaac_runner.py

# 또는 SSD/Isaac 경로를 자동 탐색하는 실행 파일
.\start_sitegit_isaac.bat

# Backend 없이 굴착기 3대 동작만 확인
.\start_sitegit_excavator_demo.bat

# 편집 패널까지 보면서 독립 데모를 디버깅
.\start_sitegit_excavator_demo.bat -EditorUi

# Isaac 없이 배관만 검증 (실제 실행 아님)
.\.venv\Scripts\python.exe isaac_adapter\cube_task_runner.py --interval 3
```

### 웹 계획 승인 → Zone A 터파기 실행

Backend와 `start_sitegit_isaac.bat`을 각각 켠 상태에서 작업 지시 화면의
**계획 승인 · 터파기 3건 하달**을 누르면 세 Work Package가 하나의 실행 그룹으로
발행됩니다. Live Adapter는 그룹 전체를 한 번에 가져와 `EXC-001~003`을 각 작업전선에
배치하고, 독립 데모와 같은 5회 굴착·선회·배토 사이클을 동시에 수행합니다.

```text
계획 승인
  → Zone A Work Package 3건 생성
  → 실행 그룹 1건으로 Isaac Adapter가 원자적 claim
  → 굴착기 3대 동시 터파기 및 단계별 토사 Mesh 감소
  → 작업전선별 카메라·LiDAR·IMU Evidence Commit 3건 생성
  → 관리자 검토 대기
```

Zone A는 계획을 하달하는 즉시 현장 맵에 생성되며, 실행 중에는 Work Package 상태가
진행 중으로 표시됩니다. 각 버킷 사이클이 끝날 때마다 세 작업전선의 진행률도
20% 단위로 갱신됩니다. 터파기 결과 지형은 Evidence Commit을 승인하기 전까지 공식
Work 맵에 Merge되지 않습니다. 이 경로를 시험할 때는 웹과 분리된
`start_sitegit_excavator_demo.bat`을 동시에 실행하지 마세요.

3대 데모는 관로의 남·중앙·북 작업전선에 `EXC-001~003`을 엇갈려 놓고, 준비 배치가 끝나면
세 장비가 같은 타임라인에서 5회의 퍼기·지형 감소·선회·배토·정면 복귀 사이클을 동시에 수행합니다.
토사 Mesh는 매 버킷 사이클마다 단계적으로 낮아지고 배토 Mesh가 옆에 누적됩니다. 중앙
미굴착 결함이 필요하면 `-IntentionalDefect` 옵션으로 `EXC-002`의 누적 굴착률을 낮출 수
있습니다. 기본 실행은 세 작업전선을 모두 굴착합니다. 이 데모는 웹·Backend·Commit과 완전히
분리되어 있으며 자세한 옵션은 `isaac_adapter/README.md`에 있습니다.

두 러너는 같은 지시를 두고 경쟁하므로 동시에 켜지 마세요. Commit의 `result.simulator`가 `isaac-sim`이면 Isaac Stage에서 실제로 읽어온 값이고, `simulated-cube-bridge`면 지시값을 되돌린 것뿐입니다.

Manager Action의 **Work Package** 목록에서 지시와 Commit을 확인합니다. 증거 버튼으로
작업 전·후 장비 장착 카메라 이미지, Stage 상태, LiDAR PLY, IMU 상태, 장비 Pose, 작업 시간과
형상 변화량을 검토하고 승인합니다. 승인 전에는
맵이 바뀌지 않습니다. 승인하면 Commit의 실제 변경 삼각형 Mesh를 기준 맵 위에 Merge하고,
반려하면 공식 맵은 유지한 채 반려 사유와 변경 범위를 Constraint 화면의 Conflict로
기록합니다. `/World/Diggable` 아래 독립 토사는 굴착 시 삭제하지 않고 Mesh 정점을 깎으며,
제거한 체적과 동일한 별도 성토 Mesh를 생성합니다. 실시간 Stage inventory는 장비·대상 선택과
연결 상태에만 쓰고 공식 Work 맵의 형상 원본으로 사용하지 않습니다.

Runner는 작업마다 Evidence Bundle 1.0을 만들고 작업 전·후 장비 장착 카메라 PNG,
Stage JSON, 장비 Pose JSON과 장착형 3D Raycast LiDAR의 월드 좌표 PLY를 Evidence 폴더에
저장합니다. 각 시점의 Point Cloud는 동일 XY 높이 격자로 비교하여 절토·성토 체적을
**추정값**으로 계산합니다. 격자 크기와 최소 높이
변화는 `SITEGIT_HEIGHT_GRID_CELL_M`, `SITEGIT_MIN_HEIGHT_CHANGE_M`으로 조정합니다.

`SITEGIT_IMU_PRIM`에 실제 Isaac IMU Prim을 지정하면 해당 센서 프레임을 저장합니다.
IMU가 없을 때는 Pose를 IMU처럼 위장하지 않고 Evidence에 `미수집`으로 기록합니다.
센서 완결성은 검토 정보이며 그 자체로 승인/반려를 자동 결정하지 않습니다. 각 Bundle은
실행 시작·작업 전 수집·실행·작업 후 수집·완료/실패 이벤트와 실제 걸린 시간을 함께
`work-packages/<instruction-id>/evidence-manifest.json`에 남깁니다.

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
SITEGIT_EQUIPMENT_POSITION=-26.5,-30.5,0
SITEGIT_STAGE_SCENARIO_ID=pipeline-demolition-v12
SITEGIT_SITE_ASSET=isaac/assets/construction_site_demolition.usdz
SITEGIT_CREATE_PIPELINE_BACKFILL=true
SITEGIT_PIPELINE_SOIL_BASECOLOR=E:\SiteGitData\isaac\assets\materials\demolition_soil_tile_diffuse.jpg
SITEGIT_PIPELINE_SOIL_NORMAL=E:\SiteGitData\isaac\assets\materials\demolition_soil_tile_normal.jpg
SITEGIT_EQUIPMENT_GROUND_CLEARANCE_M=0.03
SITEGIT_EQUIPMENT_PRIMS=/World/Equipment/EXC_001,/World/Armature
SITEGIT_DIGGABLE_ROOTS=/World/Diggable
SITEGIT_SCENE_OBJECT_ROOTS=/World/SiteGit
SITEGIT_SENSOR_MOUNT_OFFSET=0,1.64,1.93
SITEGIT_CAMERA_RESOLUTION=960,540
SITEGIT_CAMERA_PITCH_DEG=18
SITEGIT_CAMERA_WARMUP_FRAMES=60
SITEGIT_LIDAR_COLLISION_ROOTS=/World/Site,/World/Diggable,/World/SiteGit
SITEGIT_LIDAR_HORIZONTAL_FOV_DEG=120
SITEGIT_LIDAR_VERTICAL_MIN_DEG=-75
SITEGIT_LIDAR_VERTICAL_MAX_DEG=15
SITEGIT_LIDAR_HORIZONTAL_RAYS=81
SITEGIT_LIDAR_VERTICAL_RAYS=25
SITEGIT_LIDAR_MIN_RANGE_M=0.2
SITEGIT_LIDAR_MAX_RANGE_M=20
SITEGIT_MAX_EXCAVATION_TARGET_SPAN_M=25
SITEGIT_CREATE_DEMO_SOIL_PILE=false
SITEGIT_TERRAIN_COLLISION_PROXY=true
SITEGIT_TERRAIN_COLLISION_RESOLUTION_M=2
SITEGIT_PIPELINE_HEIGHT_RESOLUTION_M=0.5
SITEGIT_COLLISION_COOKING_FRAMES=20
```

The v12 backfill surface uses a 640x512 dirt-only crop from the purchased map's
original `tex_u2_v2_diffuse.jpg` and `tex_u2_v2_normal.jpg` pair. The crop is
centred at source UV `(0.38, 0.67)` and contains only nearby compacted soil;
pixels are neither generated nor colour-corrected. Keeping the crop as a
standalone texture prevents a flipped texture-V convention from exposing a
building, road or debris atlas island. Isaac uses an sRGB diffuse connection
with a Stage-light attenuation multiplier and leaves the normal map
disconnected. This avoids both the overexposed diffuse+normal result and the
black converter-specific emissive graph; the browser keeps the unmodified tile.
The fill is a closed soil volume down
to the photographed trench floor; only its upper faces use this map-derived
tile, while buried side and bottom faces use a neutral soil material.
The route extends to intact ground at both ends and feathers its outside vertex
bands into the sampled bank height, so the closed volume fills the complete
excavation without exposing dark end walls or lateral gaps.
The 2 m PhysX collision proxy remains the fast runtime surface, while a separate
cached 0.5 m height field is used only when generating the visible backfill
boundary. This keeps startup fast and aligns the terminal caps to the detailed
photogrammetry terrain.

Runner가 시작되면 `/World/Equipment/EXC_001/SiteGitSensors`를 굴착기 자식으로
생성합니다. 이 Mount 아래의 Camera와 PhysX Raycast 3D LiDAR는 장비가 이동하거나
회전할 때 같이 움직입니다. Work Package 실행 직전과 직후에 각각 장비 시점 PNG와
월드 좌표 PLY를 저장하므로, 화면을 보기 위한 자유 카메라나 공중 Viewport는 Evidence에
사용하지 않습니다. Stage에서는 최신 LiDAR 반환점을
`/World/SiteGitSensors/EXC_001_LidarPoints`에서 확인할 수 있습니다.

기본 Mount 오프셋 `(0, 1.64, 1.93)m`은 `+Y`가 굴착기 전방이고 `+Z`가 위인 현장
좌표 기준입니다. 실제 장착 위치나 굴착기 전방축이 다르면
`SITEGIT_SENSOR_MOUNT_OFFSET`과 카메라 pitch/FOV 설정을 조정한 뒤 Runner를 다시
시작합니다. 현장 Mesh와 `/World/Diggable` 작업 대상에는 Runner가 LiDAR용 정적
Collision을 자동 적용합니다.

`SITEGIT_EQUIPMENT_POSITION`의 Z는 절대 월드 높이가 아니라 해당 XY 지표면 위 여유
높이입니다. Runner는 시작 시 굴착기 bounds 바닥을 지표면에 맞추고, 작업 이동 중에도
매 스텝 아래 방향 PhysX Raycast로 지면을 다시 읽어 Z를 갱신합니다. 현재 에셋은 트랙
구동용 RigidBody/Articulation 모델이 아니므로 완전한 차량 동역학이 아니라 **지형 추종
kinematic 이동**이지만, 고정 Z 이동으로 지형을 관통하는 현상은 방지합니다.

기본 관로 시나리오는 `construction_site_demolition.usdz`의 파인 중앙 구간을 따라
`/World/Diggable/Pipeline/TrenchFill_01`부터 `TrenchFill_08`까지 독립 토사 Mesh와
Collision을 생성합니다. 각 구간은 실제 지형 높이 캐시에 맞춰 채워지고 현장 색감에 맞춘
반복형 흙 BaseColor 재질을 공유합니다. 가로·세로 최대 폭이 25m를 넘는 Prim은
웹·Backend·승인 Gate·Isaac Adapter 모든 단계에서 거부됩니다.

예시 입력은 `선택한 굴착기로 Zone A의 선택한 Prim을 굴착해줘`입니다. Runner는
장비 루트를 대상 앞으로 이동시키고, 에셋에 포함된 `TrackAnimation` → `ArmDig` →
`ArmDump` 클립을 실제 Skeleton에 연결해 재생합니다. 정확한 Target 토사 Mesh에 굴착
형상을 만들고 계산된 제거량만큼 옆에 성토 Mesh를 생성한 뒤 Stage read-back 결과를
Commit합니다. 현재 구현은 독립 Mesh의 결정적 vertex sculpt 방식이며, 입자 기반 토질·버킷
접촉 해석은 최종 articulation/soil 시나리오에서 이 인터페이스 뒤에 교체할 수 있습니다.

### AI Code Work Package

메인 화면의 **자연어 작업 지시**는 Stage 연결 여부와 관계없이 열립니다. Backend는 로컬
LLM이 해석한 작업 의도를 최신 Stage inventory와 비교한 뒤, 정확한 Prim 경로만 사용하는
제한 실행 코드 `execute(ctx)`를 생성합니다. 현재 코드 컨텍스트는 `ctx.excavate(...)`와
`ctx.move_equipment(...)`를 지원하며 import, 파일 접근, 네트워크 호출, 임의 Python 실행은
Backend와 Isaac Adapter 양쪽에서 거부합니다.

장비, Zone 토사 또는 실행 기능이 없으면 요청을 삭제하지 않고 `blocked` 상태의 Work
Package로 저장하며 웹의 Isaac 작업 큐에 부족한 자원을 표시합니다. 모든 조건이 충족되면
`pending`으로 등록되고 Runner가 생성 코드를 실행한 뒤 기존과 동일한 Evidence → Commit →
관리자 승인 흐름으로 들어갑니다.

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

### Isaac Sim Zone B pipe-installation demo

The excavation-only demo now saves its completed Stage as
`SITEGIT_DATA_ROOT/isaac/three-excavator-demo/excavated-stage.usda`. Run the
next construction phase without the Backend or web application with:

```powershell
.\start_sitegit_pipeline_demo.bat

# Faster animation for a smoke check
.\start_sitegit_pipeline_demo.bat -Fast

# Stage/Property/Content가 필요한 디버깅 화면
.\start_sitegit_pipeline_demo.bat -EditorUi
```

The runner restores the saved excavation Stage when it exists. Otherwise it
prepares the same drawing's approved excavation state. Three short handling
pipes start beside the spoil banks left by excavation. `EXC-001~003` remain on
stable upper ground and lower one short pipe each from above. At release, those
props are replaced in one frame by the complete drawing-aligned route. It saves
`pipeline-installed-stage.usda` plus `report.json` under
`SITEGIT_DATA_ROOT/isaac/pipeline-installation-demo`.

### Isaac Sim Zone C backfill demo

Continue from the installed-pipeline Stage with the final construction phase:

```powershell
.\start_sitegit_backfill_demo.bat

# Shorter animation for a smoke check
.\start_sitegit_backfill_demo.bat -Fast

# Stage/Property/Content가 필요한 디버깅 화면
.\start_sitegit_backfill_demo.bat -EditorUi
```

The three excavators run five synchronized reverse-excavation cycles. They turn
to the side spoil banks, scoop, return toward the trench, and dump together.
The normal launcher uses deliberately visible motion timing. The track carriers
stay pinned at their settled poses to prevent contact impulses from rolling a
machine, while each imported full Skeleton clip is played in the exact reverse
order of the proven excavation cycle (`Rotate90` -> reverse `ArmDump` -> reverse
`Rotate90` -> reverse `ArmInDig` -> reverse `ArmDig` -> reverse `ArmOut`).
Every cycle consumes one fifth of the real `MovedSoil` meshes and restores one
fifth of `TrenchFill_01~08`; the final cycle recovers the exact approved surface
and leaves the 79.2 m pipeline buried below it. The result is saved as
`SITEGIT_DATA_ROOT/isaac/pipeline-backfill-demo/backfilled-stage.usda` with a
standalone `report.json`. The complete local sequence is therefore:

```powershell
.\start_sitegit_excavator_demo.bat
.\start_sitegit_pipeline_demo.bat
.\start_sitegit_backfill_demo.bat
```

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
