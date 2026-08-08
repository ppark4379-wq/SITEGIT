# SiteGit 홍보 랜딩 페이지

기존 SiteGit 애플리케이션과 분리된 공개 홍보·멘토링용 정적 페이지입니다. 실제 SiteGit은 로그인과 API가 있는 업무 프로토타입이고, 이 페이지는 제품의 문제·가치·화면·흐름을 소개합니다. HTML, CSS, Vanilla JavaScript만 사용하며 백엔드와 빌드 과정이 필요하지 않습니다.

## 페이지 구성

`Header → Hero → Problem/Value → 6개 Feature → Product Preview → Flow → Closing → Footer` 순서입니다. Hero 문구는 `index.html`의 `section.hero`, HDMI 문구는 같은 섹션의 `.hero-brand`에서 수정합니다. 기능 제목과 설명은 `section.features` 안의 여섯 `article.feature`에 있습니다.

Product Preview는 실제 SiteGit을 페이지 안에 삽입한 조작형 데모가 아니라, 구현 화면을 기능별 탭으로 비교하는 스크린샷 갤러리입니다. 실제 SiteGit 배포 주소가 준비되면 별도의 CTA로 연결할 수 있습니다.

## 로컬 실행

프로젝트 루트에서 아래 명령을 실행합니다.

```powershell
python -m http.server 4173 --directory landing
```

브라우저에서 `http://localhost:4173`으로 접속합니다. `index.html`을 직접 열 수도 있지만, 상대 경로와 배포 환경을 동일하게 확인하려면 로컬 서버 방식을 권장합니다.

## Cloudflare Pages 배포

- Framework preset: `None`
- Build command: 비워 둠
- Build output directory: `landing`
- Root directory를 별도로 묻는 설정에서는 저장소 루트를 유지하고 출력 디렉터리만 `landing`으로 지정

Git 저장소를 Cloudflare Pages에 연결한 뒤 위 값으로 배포하면 됩니다. 별도의 환경 변수는 필요하지 않습니다.

## 화면 캡처 교체

실제 제품 화면은 `assets/screenshots/`에 있습니다. 새 캡처로 바꿀 때 아래 파일명을 유지하면 HTML 수정 없이 반영됩니다.

- `dashboard.png` — 실제 통합 관리자 대시보드
- `control-center-mobile.png` — Hero 휴대폰 화면
- `control-center-tablet.png` — Hero 태블릿 화면
- `plan-compiler.png` — 첫 번째 기능의 Work Package Compiler 화면
- `equipment-registry.png` — 두 번째 기능의 장비 Registry 화면
- `evidence-acceptance.png` — 네 번째 기능의 Evidence 화면
- `version-audit.png` — 여섯 번째 기능의 Version 이력 화면
- `work-packages.svg`
- `equipment.svg`
- `evidence.svg`
- `readiness.svg`
- `versions.svg`

`dashboard.png`는 Hero laptop, 실행 모니터링 기능, Product Preview 첫 화면에서 사용합니다. Hero의 휴대폰과 태블릿에는 각각 `control-center-mobile.png`, `control-center-tablet.png`를 사용합니다. 기능 섹션은 플랜 컴파일, 장비 Registry, Evidence, Version 화면을 각각 연결했으며 5번 Manager Action은 가운데 `구현 중` 오버레이가 표시됩니다.

## 스타일과 동작 수정

- 색상·간격·그림자: `styles.css` 상단의 `:root`
- Hero와 디바이스 프레임: `.hero`, `.device-stage`, `.device`
- 기능 교차 배치: `.feature`, `.feature.reverse`
- 반응형: 파일 하단의 `@media(max-width:1100px)`와 `@media(max-width:760px)`
- 등장 애니메이션: `script.js`의 `IntersectionObserver`
- Hero 패럴랙스: `script.js`의 `[data-parallax]` 처리
- 제품 화면 탭: `script.js`의 `[data-preview]` 처리
- 동작 줄이기: CSS와 JS의 `prefers-reduced-motion`

실제 SiteGit 배포 URL이 생기면 `index.html`의 헤더 `.nav-cta`와 원하는 CTA 버튼의 `href="#preview"`를 해당 URL로 바꾸고, 외부 링크라면 `target="_blank" rel="noopener"`를 추가합니다.

## 구조

```text
landing/
├─ index.html
├─ styles.css
├─ script.js
├─ README.md
└─ assets/
   ├─ icons/
   ├─ images/
   └─ screenshots/
```

접근성 설정에서 동작 줄이기를 활성화한 사용자는 플로팅, 패럴랙스, 등장 애니메이션 없이 콘텐츠를 확인할 수 있습니다.
