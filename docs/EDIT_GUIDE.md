# 어디를 수정해야 하나

| 바꾸려는 것 | 수정 위치 |
|---|---|
| 화면·디자인·문구 | `frontend` |
| 기능·DB·판정 | `backend` |
| 7단계별 기능 | `backend/app/domains/<단계>` |
| Isaac Sim API·ROS·Prim | `isaac_adapter` |
| JSON 필드의 약속 | `contracts` |
| Evidence·Conflict 임계값 | `policies` |
| URL·포트·SSD·비밀번호 | 실제 `.env` |
| Cloudflare 고정 URL | `ops/cloudflare` |
| 실행·중지·백업 | `ops/scripts` |
| 초기 사상구 값 | `seed` |

## 변경 예시

- 허용오차 50 → 70: `policies` 또는 Work Package 설정
- 새로운 경사도 오차 계산: `backend/domains/evidence`, 필요 시 `contracts`, `isaac_adapter`
- 대시보드 카드 위치 변경: `frontend`
- Isaac Prim 경로 변경: `isaac_adapter/isaac_bridge.py`
