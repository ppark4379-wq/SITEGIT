"""Pure adapter-side checks for pending Stage snapshot export."""

from __future__ import annotations

from pathlib import Path

from isaac_adapter.stage_snapshots import save_pending_stage_snapshot


class _FakeRootLayer:
    def Export(self, path: str) -> bool:  # noqa: N802 - USD API compatibility
        target = Path(path)
        assert target.suffix == ".usda"
        target.write_text("#usda 1.0\n", encoding="utf-8")
        return True


class _FakeStage:
    def GetRootLayer(self):  # noqa: N802 - USD API compatibility
        return _FakeRootLayer()


def test_pending_stage_snapshot_is_written_below_data_root(tmp_path):
    snapshot = save_pending_stage_snapshot(
        _FakeStage(),
        data_root=tmp_path,
        project_id="SASANG-001",
        branch="main",
        instruction_id="instruction-1",
        execution_id="execution-1",
        base_commit_id="parent-commit",
        scenario_id="pipeline-demolition-v1",
    )
    target = tmp_path / snapshot["storage_key"]
    assert target.is_file()
    assert target.suffix == ".usda"
    assert snapshot["status"] == "pending"
    assert snapshot["base_commit_id"] == "parent-commit"
    assert snapshot["scenario_id"] == "pipeline-demolition-v1"
    assert snapshot["size_bytes"] == target.stat().st_size
    assert len(snapshot["sha256"]) == 64
