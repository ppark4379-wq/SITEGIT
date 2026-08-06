# Git과 외장 SSD의 경계

## GitHub

코드, JSON Schema, 기본 정책, Seed, 운영 템플릿, 문서, 테스트를 저장합니다.

## 외장 SSD

```text
SiteGitData/
├─ database/sitegit.db
├─ evidence/
├─ isaac/
├─ logs/
└─ backups/
```

사용자, 실제 Work Package, 진행률, Evidence, Conflict, Release, 작업 로그, PCD, 영상은 SSD에 저장합니다.

규격 JSON은 Git, 실제 실행 결과 JSON은 SSD입니다.
