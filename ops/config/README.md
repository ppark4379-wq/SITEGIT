# 운영 설정

실제 실행에서는 저장소 루트의 `.env` 한 파일만 수정합니다.

```powershell
Copy-Item ops/config/sitegit.env.example .env
notepad .env
```

주요 값:

- `PUBLIC_URL`: 팀원이 접속할 고정 주소
- `SERVER_HOST`, `SERVER_PORT`: 로컬 FastAPI
- `SITEGIT_DATA_ROOT`: 외장 SSD 루트
- `ISAAC_ADAPTER_*`: Isaac 연결 여부와 주소
- `JWT_SECRET`, 초기 비밀번호: 로그인 보안

`.env`는 Git에 올라가지 않습니다.
