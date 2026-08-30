"""Tests for the standalone three-work-front Isaac Sim demo configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from isaac_adapter.isaac_bridge import (
    MAX_EXCAVATED_SPOIL_LENGTH_M,
    MAX_EXCAVATED_SPOIL_HEIGHT_M,
    MAX_EXCAVATED_SPOIL_VISUAL_HEIGHT_M,
    MAX_EXCAVATED_SPOIL_VISUAL_VOLUME_M3,
    MAX_EXCAVATED_SPOIL_WIDTH_M,
    excavated_spoil_visual_profile,
    moved_soil_dump_position,
    per_scoop_cut_ratio,
    projected_mesh_volume,
    reshape_mound_points_for_volume,
    sculpt_soil_mesh_points,
)
from isaac_adapter.three_excavator_demo import (
    DEFAULT_SCOOP_COUNT,
    load_demo_workfronts,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_demo_uses_three_unique_excavators_and_targets() -> None:
    workfronts = load_demo_workfronts(
        REPO_ROOT / "contracts" / "site_plans" / "demolition_pipeline_v1.json"
    )

    assert [item.equipment_id for item in workfronts] == ["EXC-001", "EXC-002", "EXC-003"]
    assert len({item.equipment_prim_path for item in workfronts}) == 3
    assert len({item.target_prim_path for item in workfronts}) == 3
    all_targets = [path for item in workfronts for path in item.target_prim_paths]
    assert len(all_targets) == 8
    assert len(set(all_targets)) == 8
    assert [item.start_position[0] for item in workfronts] == pytest.approx(
        [-19.5, -0.5, -29.0]
    )
    assert [item.target_center_xy for item in workfronts] == pytest.approx(
        [(-8.25, -30.0), (-13.25, -2.0), (-11.75, 20.25)]
    )


def test_centre_excavator_is_the_only_intentional_under_excavation() -> None:
    workfronts = load_demo_workfronts()

    assert [item.intentional_under_excavation for item in workfronts] == [False, True, False]
    assert workfronts[1].excavation_cut_ratio < workfronts[0].excavation_cut_ratio
    assert workfronts[1].excavation_cut_ratio < workfronts[2].excavation_cut_ratio
    assert [item.dump_side for item in workfronts] == [1.0, 1.0, 1.0]
    assert [item.dump_bank_inset_m for item in workfronts] == [3.0, 0.0, 0.0]


def test_lower_cut_ratio_removes_less_soil_volume() -> None:
    points = [
        (-1.0, -1.0, 0.0),
        (0.0, -1.0, 1.0),
        (1.0, -1.0, 0.0),
        (-1.0, 0.0, 1.0),
        (0.0, 0.0, 2.0),
        (1.0, 0.0, 1.0),
        (-1.0, 1.0, 0.0),
        (0.0, 1.0, 1.0),
        (1.0, 1.0, 0.0),
    ]
    counts = [3] * 8
    indices = [
        0, 1, 4, 0, 4, 3,
        1, 2, 5, 1, 5, 4,
        3, 4, 7, 3, 7, 6,
        4, 5, 8, 4, 8, 7,
    ]
    before = projected_mesh_volume(points, counts, indices)
    shallow = sculpt_soil_mesh_points(points, cut_ratio=0.32, base_z_override=0.0)
    normal = sculpt_soil_mesh_points(points, cut_ratio=0.92, base_z_override=0.0)

    shallow_removed = before - projected_mesh_volume(shallow, counts, indices)
    normal_removed = before - projected_mesh_volume(normal, counts, indices)
    assert shallow_removed > 0.0
    assert normal_removed > shallow_removed


def test_large_spoil_volume_expands_footprint_instead_of_becoming_a_spike() -> None:
    points = [
        (0.0, 0.0, 3.0),
        (-2.0, -2.0, 0.0),
        (2.0, -2.0, 0.0),
        (2.0, 2.0, 0.0),
        (-2.0, 2.0, 0.0),
    ]
    counts = [3, 3, 3, 3]
    indices = [0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1]
    initial_volume = projected_mesh_volume(points, counts, indices)
    desired_volume = initial_volume * 20.0

    reshaped = reshape_mound_points_for_volume(
        points,
        counts,
        indices,
        desired_volume,
    )

    assert max(point[2] for point in reshaped) == pytest.approx(
        MAX_EXCAVATED_SPOIL_HEIGHT_M
    )
    assert max(point[0] for point in reshaped) > max(point[0] for point in points)
    assert projected_mesh_volume(reshaped, counts, indices) == pytest.approx(
        desired_volume
    )


def test_excavation_renders_one_bounded_five_pass_stockpile() -> None:
    visual_size, visual_volume = excavated_spoil_visual_profile(
        {"x": 45.0, "y": 30.0, "z": 7.0},
        removed_volume_m3=981.0,
    )

    assert visual_size == pytest.approx((10.0, 8.0, 3.15))
    assert visual_size[0] <= MAX_EXCAVATED_SPOIL_LENGTH_M
    assert visual_size[1] <= MAX_EXCAVATED_SPOIL_WIDTH_M
    assert visual_size[2] <= MAX_EXCAVATED_SPOIL_VISUAL_HEIGHT_M
    assert visual_volume == pytest.approx(MAX_EXCAVATED_SPOIL_VISUAL_VOLUME_M3)


def test_incremental_scoops_converge_on_requested_total_cut() -> None:
    for total in (0.32, 0.92):
        per_scoop = per_scoop_cut_ratio(total, DEFAULT_SCOOP_COUNT)
        cumulative = 1.0 - (1.0 - per_scoop) ** DEFAULT_SCOOP_COUNT
        assert cumulative == pytest.approx(total)

    assert per_scoop_cut_ratio(0.32, DEFAULT_SCOOP_COUNT) < per_scoop_cut_ratio(
        0.92,
        DEFAULT_SCOOP_COUNT,
    )


def test_scoop_count_must_be_positive() -> None:
    with pytest.raises(ValueError, match="scoop_count"):
        per_scoop_cut_ratio(0.9, 0)


def test_later_dump_piles_extend_the_side_bank_without_moving_backwards() -> None:
    equipment = {"x": 0.0, "y": 0.0, "z": 0.0}
    first = moved_soil_dump_position(
        equipment,
        [0.0, 1.0],
        (10.0, 8.0, 4.0),
        track_radius_m=3.0,
        dump_side=1.0,
        dump_sequence_index=0,
    )
    fifth = moved_soil_dump_position(
        equipment,
        [0.0, 1.0],
        (10.0, 8.0, 4.0),
        track_radius_m=3.0,
        dump_side=1.0,
        dump_sequence_index=4,
    )

    assert first["dump_side"] == "left"
    assert first["position_xy"][0] < -8.0
    assert first["position_xy"][1] == pytest.approx(0.0)
    assert fifth["position_xy"][0] < first["position_xy"][0]
    assert fifth["position_xy"][1] == pytest.approx(first["position_xy"][1])
    assert fifth["lateral_offset_m"] > first["lateral_offset_m"]
    assert first["bank_inset_m"] == pytest.approx(0.0)
    assert fifth["bank_inset_m"] == pytest.approx(0.0)


def test_first_workfront_bank_inset_moves_spoil_away_from_the_trench() -> None:
    equipment = {"x": -17.7, "y": -27.35, "z": 0.0}
    direction = [0.985, 0.182]
    size = (11.7, 9.1, 6.0)
    normal = moved_soil_dump_position(
        equipment,
        direction,
        size,
        track_radius_m=2.0,
        dump_side=1.0,
        dump_sequence_index=0,
    )
    inset = moved_soil_dump_position(
        equipment,
        direction,
        size,
        track_radius_m=2.0,
        dump_side=1.0,
        dump_sequence_index=0,
        bank_inset_m=3.0,
    )

    assert inset["position_xy"][0] < normal["position_xy"][0] - 2.9
    assert inset["bank_inset_m"] == pytest.approx(3.0)


def test_final_cleanup_pass_lowers_the_whole_soil_footprint() -> None:
    points = [
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
        (0.0, 0.0, 2.0),
    ]
    cleaned = sculpt_soil_mesh_points(
        points,
        cut_ratio=0.95,
        base_z_override=0.0,
        minimum_cut_influence=1.0,
    )

    assert max(point[2] for point in cleaned) <= 0.101


def test_demo_launcher_is_explicitly_sim_only() -> None:
    powershell = (
        REPO_ROOT / "ops" / "scripts" / "start_sitegit_excavator_demo.ps1"
    ).read_text(encoding="utf-8")
    batch = (REPO_ROOT / "start_sitegit_excavator_demo.bat").read_text(encoding="utf-8")

    assert "three_excavator_demo.py" in powershell
    assert "[int]$Scoops = 1" in powershell
    assert '"--intentional-defect"' in powershell
    assert "Test-SiteGitApi" not in powershell
    assert "Backend and web services are not used" in batch
