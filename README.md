# SiteGit v0.2 — Git-ready Modular Local Shared Platform

현재 추천 조합을 기준으로 만든 GitHub 업로드용 구조입니다.

> **Private GitHub + 대표 PC FastAPI + 외장 SSD SQLite/Evidence + Cloudflare Named Tunnel 고정 URL + Isaac Adapter**

기존 SiteGit v2 화면과 로그인·공동 저장 기능은 그대로 실행하면서, 팀원이 어디를 수정해야 하는지 바로 보이도록 최종 책임 구조를 고정했습니다.

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

### 아직 구조만 만든 부분

기존 UI를 깨지 않기 위해 현재 프로젝트·Work Package·Evidence는 호환용 `project_states.payload` JSON에도 함께 저장됩니다. `backend/app/domains/*`는 최종 책임 위치이지만, 각 항목을 독립 DB 테이블과 API로 완전히 분리하는 작업은 다음 단계입니다.

또한 기존 `frontend/app.js`에는 컨셉 UI의 임시 Conflict 기준이 일부 남아 있습니다. 새 기준의 원본은 `policies/`이며, 다음 단계에서 판정 계산을 `backend/domains/trust_gate`로 옮깁니다.

---

## 5. 외장 SSD 준비

```text
E:/SiteGitData/
├─ database/
├─ evidence/
├─ isaac/
├─ logs/
└─ backups/
```

실행하면 없는 폴더는 자동 생성됩니다. DB에는 절대 파일 경로 대신 `sasang/WP-C01/...` 같은 상대 `storage_key`를 저장하는 방향으로 구성합니다.

---

## 6. Windows 첫 실행

PowerShell에서 프로젝트 폴더로 이동합니다.

```powershell
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
INITIAL_MANAGER_PASSWORD=<팀원 비밀번호>
INITIAL_VIEWER_PASSWORD=<조회자 비밀번호>
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
