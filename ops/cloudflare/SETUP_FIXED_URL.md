# Cloudflare Named Tunnel 고정 URL

목표:

```text
https://sitegit.example.com → 대표 PC http://localhost:8000
```

1. 도메인을 Cloudflare에 연결합니다.
2. 대표 PC에 `cloudflared`를 설치합니다.
3. Named Tunnel `sitegit-local`을 생성합니다.
4. `config.yml.example`을 `config.yml`로 복사하고 Tunnel ID, credentials 경로, hostname을 수정합니다.
5. DNS route를 생성합니다.
6. SiteGit 서버를 먼저 실행하고 `ops/scripts/start_tunnel.ps1`을 실행합니다.

실제 `config.yml`, 인증 JSON, `cert.pem`은 Git에 올리지 않습니다. 외부 공개 전 `.env`의 `COOKIE_SECURE=true`, 강한 `JWT_SECRET`, 초기 비밀번호 변경을 확인합니다.
