# Frontend

사용자가 보는 웹페이지입니다.

## 현재 동작 파일

- `index.html`: 메인 화면 뼈대
- `styles.css`: 전체 디자인
- `app.js`: 기존 v2 화면과 상호작용을 보존한 통합 호환 파일
- `login.*`: 로그인 화면

기존 프로토타입을 깨지 않기 위해 v0.2에서도 `app.js`가 실제 실행 진입점입니다. 새 기능을 추가할 때는 `pages/`와 `services/`에 먼저 작성하고, 안정화된 뒤 `app.js`에서 호출하도록 이동합니다.

## 수정 기준

- 색상·배치·문구: `index.html`, `styles.css`, 해당 `pages/`
- Backend API 호출: `services/api.js`
- 실시간 알림: `services/realtime.js`
- Conflict 계산 자체: Frontend가 아니라 `backend/app/domains/trust_gate`
