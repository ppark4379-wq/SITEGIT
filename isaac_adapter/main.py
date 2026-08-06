"""SiteGit ↔ Isaac Sim Adapter 실행 진입점.

실제 연결 전에는 mock_adapter.py로 API 경계를 검증합니다.
실제 연결 시 흐름:
SiteGitClient → WorkPackageMapper → IsaacBridge → EvidenceExporter → SiteGit API
"""


def main() -> None:
    print("SiteGit Isaac Adapter scaffold. Use mock_adapter.py until IsaacBridge is implemented.")


if __name__ == "__main__":
    main()
