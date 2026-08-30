"""Regression checks for the long-running Isaac review loop."""

from pathlib import Path

from isaac_adapter.isaac_runner import _can_adopt_retained_stage_head


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


def test_supplemental_approval_adopts_the_retained_live_stage() -> None:
    """Approving the same retained Stage must not close the Isaac session."""

    assert _can_adopt_retained_stage_head(
        remote_head_id="commit-reopened",
        retained_rejected_commit_id="commit-reopened",
        review_status="approved",
    )
    assert not _can_adopt_retained_stage_head(
        remote_head_id="different-head",
        retained_rejected_commit_id="commit-reopened",
        review_status="approved",
    )
    assert not _can_adopt_retained_stage_head(
        remote_head_id="commit-reopened",
        retained_rejected_commit_id="commit-reopened",
        review_status="pending",
    )


def test_runner_keeps_restart_protection_for_an_unrelated_head() -> None:
    runner = (ROOT / "isaac_adapter" / "isaac_runner.py").read_text(
        encoding="utf-8"
    )

    assert "[head adopted]" in runner
    assert "추가 Evidence로 재승인된 Commit" in runner
    assert "[head changed]" in runner
    assert "최신 Stage를 복원하기 위해 Isaac Runner를 종료합니다" in runner
