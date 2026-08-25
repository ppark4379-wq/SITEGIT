"""Regression checks for the long-running Isaac review loop."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rejected_commit_keeps_stage_alive_for_remediation() -> None:
    runner = (ROOT / "isaac_adapter" / "isaac_runner.py").read_text(
        encoding="utf-8"
    )
    review_loop = runner[
        runner.index("if waiting_commit_id:") : runner.index(
            "# A restarted Adapter must only wait"
        )
    ]

    assert 'elif review_status == "rejected":' in review_loop
    assert "반려된 현장 Stage를 유지하고 보완 Work Package를 기다립니다" in review_loop
    assert "waiting_commit_id = None" in review_loop
    assert "Isaac Runner를 종료합니다" not in review_loop
    assert "break" not in review_loop
