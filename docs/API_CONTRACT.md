# API Contract — v0.2

Base URL: `/api/v1`

## Authentication

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

브라우저는 HttpOnly cookie를 사용합니다. Isaac Adapter는 `requests.Session`으로 로그인 쿠키를 유지합니다.

## Shared compatibility state

- `GET /state/{project_id}`
- `PUT /state/{project_id}`
- `WS /state/ws/{project_id}`

현재 v2 UI를 유지하기 위한 호환 API입니다. `PUT`은 `revision`을 사용하며 오래된 revision은 HTTP 409로 차단합니다.

## Policies

- `GET /policies`
- `GET /policies/evidence`
- `GET /policies/conflict`
- `GET /policies/release`

`policies/*.json`의 현재 기본값을 확인합니다. 실제 판정 계산을 Backend로 완전히 이동하는 것은 다음 단계입니다.

## Isaac 폐루프

지시 → 실행 → Commit → 승인 → 맵 반영. 자세한 흐름은 `docs/ISAAC_INTEGRATION.md`.

| Method | Path | 호출 주체 | 권한 |
|---|---|---|---|
| `GET` | `/isaac/instructions` | 웹·Adapter | 로그인 |
| `POST` | `/isaac/instructions` | 웹 | admin·manager·reviewer |
| `POST` | `/isaac/instructions/claim` | Adapter | admin·manager·reviewer |
| `POST` | `/isaac/instructions/{id}/commit` | Adapter | admin·manager·reviewer |
| `POST` | `/isaac/commits/{id}/review` | 웹 | admin·manager·reviewer |
| `GET` | `/isaac/map-objects` | 웹 뷰어 | 로그인 |

`claim`은 건네주는 시점에 지시를 `dispatched`로 바꿉니다. 폴링 주기가 실행 시간보다
짧아도 같은 작업을 두 번 수행하지 않습니다.

`review`는 한 번만 받습니다. 이미 판정된 Commit에 다시 호출하면 HTTP 409입니다.
실패한 실행(`status=failed`)은 승인할 수 없고 HTTP 422로 막힙니다.

`map-objects`는 **승인된 Commit만** 반환합니다. 별도 테이블이 아니라 조회 시점에
만들어내므로 승인을 되돌리면 즉시 사라집니다.

## Health

- `GET /health`

## 다음 단계에서 분리할 API

```text
/projects
/zones
/work-packages
/equipment
/executions
/evidence
/conflicts
/decisions
/events
```

위 API는 아직 구현된 것처럼 가장하지 않습니다. 각 도메인이 분리될 때 호환 state API에서 순차적으로 이동합니다.
