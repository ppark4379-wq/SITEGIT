# SiteGit 초기 데이터

- `pipeline_demo_state.json`: 현재 관로 시공 통합 데모의 공식 초기 상태
- `equipment_models.json`: 현재 Isaac Sim 데모에서 실제 사용하는 `EXC-001`~`EXC-003` Registry 기준
- `sasang_state.json`: 이전 사상구 콘셉트 UI 호환을 위한 보관 자료(현재 초기화에는 사용하지 않음)
- `sasang_project.json`: 이전 사상구 프로젝트 참고 자료(현재 초기화에는 사용하지 않음)

Backend는 `pipeline_demo_state.json`을 새 데이터베이스의 Seed로 사용합니다. 웹에서 변경한 데이터는 외장 SSD의 데이터베이스에 저장되며 Seed 파일은 자동으로 바뀌지 않습니다.
