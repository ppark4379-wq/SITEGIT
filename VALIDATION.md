# Validation

생성 시 다음을 확인했습니다.

- Python `compileall`: 통과
- Policies, Contracts, Seed JSON 파싱: 통과
- FastAPI TestClient: health, login, policies, shared state 조회 통과
- Git staging 검사: `.env`, DB, PCD, USD, 영상, 로그 미포함

실제 Cloudflare 고정 URL과 Isaac Sim 연결은 사용자 도메인·Tunnel credentials·Isaac 환경이 필요하므로 템플릿과 연결 경계까지만 포함합니다.
