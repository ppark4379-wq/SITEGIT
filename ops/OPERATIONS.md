# SiteGit 운영 가이드

`ops`는 7단계 기능과 별개로 **고정 URL, 서버, SSD 경로, 실행·중지·상태·백업**을 관리합니다.

## 처음 한 번

```powershell
.\ops\scripts\setup_windows.ps1
notepad .env
```

## 매번 실행

```powershell
.\ops\scripts\start_sitegit.ps1
```

고정 URL Tunnel은 별도 창에서:

```powershell
.\ops\scripts\start_tunnel.ps1
```

## 상태와 백업

```powershell
.\ops\scripts\status_sitegit.ps1
.\ops\scriptsackup_database.ps1
```
