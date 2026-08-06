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
