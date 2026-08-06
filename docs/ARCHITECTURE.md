# SiteGit v0.2 아키텍처

```text
팀원 브라우저
    ↓ 고정 URL
Cloudflare Named Tunnel
    ↓
FastAPI Backend
    ├─ 로그인·권한
    ├─ 7단계 도메인
    ├─ 정책 JSON
    ├─ SQLite → 외장 SSD
    └─ Isaac API 경계
             ↕
       Isaac Adapter
             ↕
         Isaac Sim
```

## 7단계 위치

1. `backend/app/domains/site_data`
2. `backend/app/domains/work_packages`
3. `backend/app/domains/equipment`
4. `backend/app/domains/executions` + `isaac_adapter`
5. `backend/app/domains/evidence`
6. `backend/app/domains/trust_gate` + `policies`
7. `backend/app/domains/versioning`

현재 v0.2는 기존 v2 UI와 공동 JSON 저장을 그대로 실행하면서, 앞으로 기능을 옮길 고정 폴더를 만든 구조입니다. 즉, 폴더는 최종 책임 구조이고 전체 DB 정규화는 다음 개발 단계입니다.
