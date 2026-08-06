# Isaac Adapter

SiteGit과 Isaac Sim 사이의 유일한 연결 영역입니다.

```text
FastAPI ↔ sitegit_client.py ↔ work_package_mapper.py ↔ isaac_bridge.py ↔ Isaac Sim
                                                       ↓
                                             evidence_exporter.py
```

- Backend나 SQLite를 Isaac Sim에서 직접 열지 않습니다.
- 실제 Isaac API·ROS 2·Prim 경로 변경은 이 폴더만 수정합니다.
- Work Package/Evidence 필드 자체가 바뀌면 `contracts`도 함께 수정합니다.
- `mock_adapter.py`는 Isaac 없이 로그인·공동 상태 API를 검증합니다.
