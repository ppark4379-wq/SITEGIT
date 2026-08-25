# SiteGit 홍보 랜딩 페이지

기존 SiteGit 랜딩의 입체적인 제품 소개 스타일을 유지하면서 포스터의 핵심 스토리를 반영한 정적 홍보 페이지입니다. 운영 애플리케이션과 분리되어 있으며 HTML, CSS, Vanilla JavaScript만 사용합니다.

## 로컬 실행

저장소 루트에서 다음 명령을 실행합니다.

```powershell
python -m http.server 4173 --directory landing
```

브라우저에서 `http://localhost:4173`으로 접속합니다.

## 페이지 구성

- Hero: 노트북·태블릿·휴대폰으로 보는 실제 제품 화면
- Why SiteGit: 사람과 장비가 대화하는 방식의 변화
- Difference: 일반 장비·현장 솔루션과 SiteGit의 차이
- Site + Git: 관리자 → SiteGit → 자율화 장비와 Conflict·Commit·History
- How SiteGit Works: 오늘의 작업 → Work Package → 장비 실행 → Evidence → 승인 → Commit
- Product Tour: 로그인부터 현장 운영까지 주요 제품 화면을 확인하는 갤러리

Product Tour는 로그인부터 현장 대시보드, 작업 지시와 장비관리까지 주요 업무 흐름을 화면별로 소개합니다. Isaac Sim 미연동 상태에서는 임의의 실행 화면을 만들지 않고 OFFLINE 상태와 빈 작업 영역을 그대로 보여줍니다.

## 최신 화면 이미지

`assets/screenshots/`의 다음 파일을 랜딩 페이지에서 사용합니다.

- `ui-dashboard.png`
- `ui-work-instruction.png`
- `ui-work-status.png`
- `ui-equipment.png`
- `ui-settings.png`
- `ui-login.png`

모든 캡처는 `1920 × 1200` 비율이며 CSS에서 전체 화면이 잘리지 않도록 표시합니다.

## Cloudflare Workers Static Assets

`wrangler.jsonc`가 `landing` 폴더 전체를 정적 파일로 배포하도록 설정되어 있습니다. Worker JavaScript와 빌드 과정은 필요하지 않습니다.

## 파일 구조

```text
landing/
├─ index.html
├─ styles.css
├─ script.js
├─ wrangler.jsonc
├─ README.md
└─ assets/
   ├─ icons/
   ├─ images/
   └─ screenshots/
```

Cloudflare Web Analytics 스니펫은 `index.html`의 `</body>` 바로 앞에 있으며 중복해서 추가하지 않습니다.
