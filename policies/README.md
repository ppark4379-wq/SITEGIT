# Policies — 자주 바뀌는 평가 기준

Evidence·Conflict·Release 기준이 아직 확정되지 않았기 때문에, 숫자와 활성화 여부를 Python 코드에 박아 넣지 않고 이 폴더로 분리합니다.

- `evidence_policy.json`: 완결성, 관측률, 신뢰도 등
- `conflict_policy.json`: 어떤 Conflict를 켜고 끌지, 등급과 해결방식
- `release_policy.json`: 관리자 Release 전 필수 조건

## 수정 원칙

- `50 → 70`, `true → false` 같은 기준 변경: **이 JSON만 수정**
- 새로운 계산식 추가: `backend/app/domains/evidence` 또는 `trust_gate` 수정
- Isaac Sim이 새 측정값을 보내야 함: `contracts`와 `isaac_adapter`도 함께 수정

현재 v0.2의 기존 화면에는 일부 임시 기준이 남아 있습니다. 이 정책 폴더는 다음 기능 분리 단계의 기준 원본이며, 백엔드의 `/api/v1/policies`에서 확인할 수 있습니다.
