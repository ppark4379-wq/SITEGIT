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

외장 SSD를 다른 PC에 연결한 뒤 환경을 검사하고 누락된 Python·Ollama와
Backend 패키지를 설치하려면:

```powershell
.\start_sitegit_portable.bat
```

이 명령은 프로그램을 실행하지 않습니다. 설치 없이 진단만 수행할 때는
`-CheckOnly`를 사용합니다. 준비 후 각각 별도 창에서 실행합니다.

```powershell
.\start_sitegit_backend.bat
.\start_sitegit_isaac.bat
```

## 반복 시연 초기화

심사위원별로 DB와 승인 Stage를 분리하고 원본 지형부터 다시 시연하려면 기존
Backend와 Isaac Sim을 닫은 뒤 다음 통합 런처를 사용합니다.

```powershell
.\start_sitegit_judge_demo.bat
```

직전 회차는 `SiteGitData/backups/demo-runs/<시각>` 아래에 복구 가능한 형태로
보관됩니다. 초기화만 수행할 때는 `reset_sitegit_demo.bat`을 사용합니다.

웹 연결 없이 Isaac Sim에서 굴착기 3대의 동시 굴착·선회·배토, 버킷 사이클별
단계적 지형 감소를 확인하는 독립 데모는 다음처럼
실행합니다.

```powershell
.\start_sitegit_excavator_demo.bat
```

Zone B 관로 취급 단계를 독립적으로 확인하려면 다음을 실행합니다. 저장된 굴착 완료
Stage가 있으면 자동으로 이어받고, 굴착기 3대가 각 배토 흙더미 옆의 짧은 취급용 관을
하나씩 집습니다. 장비는 상부 지반에 남은 채 관만 위에서 내려놓고, 마지막에는 취급용
관 대신 도면 전체 구간에 맞는 완성 관로가 한 번에 나타납니다.

```powershell
.\start_sitegit_pipeline_demo.bat
```

중앙 작업전선의 의도적 미굴착까지 확인하려면 `-IntentionalDefect`를 추가합니다.

고정 URL Tunnel은 별도 창에서:

```powershell
.\ops\scripts\start_tunnel.ps1
```

## 상태와 백업

```powershell
.\ops\scripts\status_sitegit.ps1
.\ops\scriptsackup_database.ps1
```
