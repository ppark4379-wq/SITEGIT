# Isaac Sim 연결

Isaac Sim은 Frontend와 SQLite에 직접 연결하지 않습니다.

```text
FastAPI ↔ isaac_adapter/sitegit_client.py
        ↔ work_package_mapper.py
        ↔ isaac_bridge.py
        ↔ Isaac Sim
                ↓
          evidence_exporter.py → SSD + FastAPI
```

초기에는 `mock_adapter.py`로 API와 로그인 경계를 검증합니다. 실제 시뮬레이션이 확정되면 `isaac_bridge.py`에 Isaac Python API 또는 ROS 2 연결을 구현합니다.
