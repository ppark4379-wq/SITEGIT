"""Regression checks for staged spoil consumption and trench restoration."""

from __future__ import annotations

from pathlib import Path

import pytest

from isaac_adapter.isaac_bridge import skeletal_joint_matches
from isaac_adapter.pipeline_backfill import (
    blend_backfill_points,
    shrink_spoil_points,
    smooth_progress,
    spoil_matches_targets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backfill_starts_at_bottom_and_ends_at_exact_surface() -> None:
    final = [
        (-1.0, 0.0, 4.0),
        (1.0, 0.0, 5.0),
        (-1.0, 0.0, 1.0),
        (1.0, 0.0, 1.5),
    ]

    empty = blend_backfill_points(final, 2, 0.0, empty_clearance_m=0.03)
    complete = blend_backfill_points(final, 2, 1.0)

    assert [point[2] for point in empty[:2]] == pytest.approx([1.03, 1.53])
    assert complete == pytest.approx(final)
    assert empty[2:] == pytest.approx(final[2:])


def test_backfill_progress_is_clamped_and_monotonic() -> None:
    final = [(0.0, 0.0, 5.0), (0.0, 0.0, 1.0)]
    values = [
        blend_backfill_points(final, 1, progress)[0][2]
        for progress in (-1.0, 0.25, 0.5, 0.75, 2.0)
    ]

    assert values == sorted(values)
    assert values[0] == pytest.approx(1.03)
    assert values[-1] == pytest.approx(5.0)
    assert smooth_progress(0.5) == pytest.approx(0.5)


def test_spoil_bank_is_consumed_without_moving_its_footprint() -> None:
    original = [(-2.0, -1.0, 0.0), (2.0, -1.0, 3.0), (0.0, 2.0, 6.0)]
    half = shrink_spoil_points(original, 0.5)
    complete = shrink_spoil_points(original, 1.0)

    assert [(point[0], point[1]) for point in half] == [
        (point[0], point[1]) for point in original
    ]
    assert [point[2] for point in half] == pytest.approx([0.0, 1.5, 3.0])
    assert [point[2] for point in complete] == pytest.approx([0.0, 0.0, 0.0])


def test_spoil_names_map_to_their_original_workfront_targets() -> None:
    assert spoil_matches_targets(
        "TrenchFill_02_MovedSoil_05", ["TrenchFill_01", "TrenchFill_02"]
    )
    assert not spoil_matches_targets(
        "TrenchFill_07_MovedSoil_05", ["TrenchFill_01", "TrenchFill_02"]
    )


def test_backfill_demo_has_a_separate_portable_launcher() -> None:
    powershell = (
        REPO_ROOT / "ops" / "scripts" / "start_sitegit_backfill_demo.ps1"
    ).read_text(encoding="utf-8")
    batch = (REPO_ROOT / "start_sitegit_backfill_demo.bat").read_text(encoding="utf-8")

    assert "pipeline_backfill_demo.py" in powershell
    assert "pipeline-installed-stage.usda" in powershell
    assert "[int]$Scoops = 5" in powershell
    assert "Backend and web services are not used" in batch


def test_backfill_animation_only_selects_rotator_or_arm_branch() -> None:
    rotator = "Armature/Root/Rotator"
    boom = "Armature/Root/Rotator/HydraulicsAngle_Rear/Arm_Main"
    track = "Armature/Root/Track_001"

    assert skeletal_joint_matches(rotator, suffixes=("/Rotator",))
    assert not skeletal_joint_matches(boom, suffixes=("/Rotator",))
    assert skeletal_joint_matches(
        boom,
        prefixes=("Armature/Root/Rotator/HydraulicsAngle_Rear",),
    )
    assert not skeletal_joint_matches(
        track,
        prefixes=("Armature/Root/Rotator/HydraulicsAngle_Rear",),
    )


def test_backfill_demo_pins_carriers_and_reverses_excavation_cycle() -> None:
    source = (REPO_ROOT / "isaac_adapter" / "pipeline_backfill_demo.py").read_text(
        encoding="utf-8"
    )

    assert '"stationary-kinematic"' in source
    assert '"ArmDump",\n                    duration_seconds=dump_seconds,\n                    reverse=True' in source
    assert '("ArmInDig", lift_seconds)' in source
    assert '("ArmDig", dig_seconds)' in source
    assert '("ArmOut", reach_seconds)' in source
    assert "animated_joint_prefixes=" not in source
    assert "base_pose_animation_name=" not in source


def test_web_backfill_group_reports_progress_and_commits_stage_results() -> None:
    task = (
        REPO_ROOT / "isaac_adapter" / "parallel_pipeline_backfill_task.py"
    ).read_text(encoding="utf-8")
    runner = (REPO_ROOT / "isaac_adapter" / "cube_task_runner.py").read_text(
        encoding="utf-8"
    )
    adapter = (REPO_ROOT / "isaac_adapter" / "isaac_runner.py").read_text(
        encoding="utf-8"
    )

    assert "def execute_parallel_pipeline_backfill(" in task
    assert '"operation": "pipeline_backfill"' in task
    assert '"action": "upsert"' in task
    assert '"action": "remove"' in task
    assert "backfilled_volume_m3" in task
    assert "def run_parallel_pipeline_backfill_group(" in runner
    assert "client.report_instruction_progress(" in runner
    assert "client.commit_execution(" in runner
    assert "is_parallel_pipeline_backfill" in adapter
    assert '== "parallel_pipeline_backfill"' in adapter
