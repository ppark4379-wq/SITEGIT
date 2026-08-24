"""Regression checks for drawing-driven pipe segment generation."""

from __future__ import annotations

import math

import pytest

from isaac_adapter.pipeline_installation import (
    build_pipe_segment_plans,
    build_workfront_pipe_plans,
    clip_centerline_station_range,
    hollow_pipe_mesh_data,
    nearest_centerline_station,
    select_workfront_pipe_plans,
    total_pipe_length,
    total_station_length,
    terminal_grade_clamped_floor_sampler,
    trim_centerline_terminals,
)
from isaac_adapter.pipeline_scenario import DEFAULT_TRENCH_STATIONS
from isaac_adapter.parallel_pipeline_installation_task import _map_change


def _flat_floor(_x: float, _y: float, fallback: float) -> float:
    return fallback


def test_pipe_plan_covers_the_complete_design_centerline() -> None:
    centerline = [
        {
            "station_m": float(index),
            "x": station.x,
            "y": station.y,
            "z": 0.0,
        }
        for index, station in enumerate(DEFAULT_TRENCH_STATIONS)
    ]
    # Station values do not affect geometric coverage; use actual XY length.
    expected = sum(
        math.hypot(b.x - a.x, b.y - a.y)
        for a, b in zip(DEFAULT_TRENCH_STATIONS, DEFAULT_TRENCH_STATIONS[1:])
    )
    plans = build_pipe_segment_plans(
        centerline,
        floor_height=_flat_floor,
        maximum_segment_length_m=4.0,
    )

    assert total_pipe_length(plans) == pytest.approx(expected)
    assert max(plan.length_m for plan in plans) <= 4.0 + 1e-9
    assert plans[0].start_xyz[:2] == pytest.approx(
        (DEFAULT_TRENCH_STATIONS[0].x, DEFAULT_TRENCH_STATIONS[0].y)
    )
    assert plans[-1].end_xyz[:2] == pytest.approx(
        (DEFAULT_TRENCH_STATIONS[-1].x, DEFAULT_TRENCH_STATIONS[-1].y)
    )


def test_pipe_progress_uses_design_station_length_instead_of_sloped_3d_length() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
        {"station_m": 4.0, "x": 4.0, "y": 0.0, "z": 0.0},
    ]
    plans = build_pipe_segment_plans(
        centerline,
        floor_height=lambda x, _y, _fallback: x,
        maximum_segment_length_m=4.0,
    )

    assert total_station_length(plans) == pytest.approx(4.0)
    assert total_pipe_length(plans) == pytest.approx(math.sqrt(32.0))


def test_pipe_pieces_share_joint_coordinates_without_route_gaps() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0, "z": 0.0},
    ]
    plans = build_pipe_segment_plans(
        centerline,
        floor_height=_flat_floor,
        maximum_segment_length_m=4.0,
    )

    assert len(plans) == 3
    for first, second in zip(plans, plans[1:]):
        assert first.end_xyz == pytest.approx(second.start_xyz)


def test_pipe_center_sits_one_radius_and_bedding_above_floor() -> None:
    plans = build_pipe_segment_plans(
        [
            {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"station_m": 3.0, "x": 3.0, "y": 0.0, "z": 0.0},
        ],
        floor_height=lambda _x, _y, _fallback: 1.5,
        outside_diameter_m=1.2,
        bedding_clearance_m=0.08,
    )

    assert plans[0].center_xyz[2] == pytest.approx(2.18)


def test_handling_demo_selects_one_segment_per_workfront() -> None:
    plans = build_pipe_segment_plans(
        [
            {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"station_m": 30.0, "x": 30.0, "y": 0.0, "z": 0.0},
        ],
        floor_height=_flat_floor,
        maximum_segment_length_m=2.0,
    )
    selected = select_workfront_pipe_plans(
        plans,
        [
            {"station_start_m": 0.0, "station_end_m": 10.0},
            {"station_start_m": 10.0, "station_end_m": 20.0},
            {"station_start_m": 20.0, "station_end_m": 30.0},
        ],
    )

    assert len(selected) == 3
    assert len({plan.prim_path for plan in selected}) == 3
    assert [
        (plan.station_start_m + plan.station_end_m) * 0.5 for plan in selected
    ] == pytest.approx([5.0, 15.0, 25.0], abs=1.0)


def test_workfront_pipes_form_one_continuous_three_piece_route() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0, "z": 0.0},
        {"station_m": 20.0, "x": 20.0, "y": 5.0, "z": 0.0},
        {"station_m": 30.0, "x": 30.0, "y": 5.0, "z": 0.0},
    ]
    workfronts = [
        {"station_start_m": 0.0, "station_end_m": 10.0},
        {"station_start_m": 10.0, "station_end_m": 20.0},
        {"station_start_m": 20.0, "station_end_m": 30.0},
    ]

    plans = build_workfront_pipe_plans(
        centerline,
        workfronts,
        floor_height=_flat_floor,
    )

    assert [plan.segment_id for plan in plans] == [
        "PIPE-WF-01",
        "PIPE-WF-02",
        "PIPE-WF-03",
    ]
    assert total_station_length(plans) == pytest.approx(30.0)
    for first, second in zip(plans, plans[1:]):
        assert first.end_xyz == pytest.approx(second.start_xyz)


def test_terminal_trim_interpolates_inside_the_excavated_corridor() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 1.0, "width_m": 8.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0, "z": 2.0, "width_m": 10.0},
        {"station_m": 20.0, "x": 20.0, "y": 5.0, "z": 3.0, "width_m": 12.0},
    ]

    trimmed = trim_centerline_terminals(centerline, 4.0)

    assert [point["station_m"] for point in trimmed] == pytest.approx(
        [4.0, 10.0, 16.0]
    )
    assert (trimmed[0]["x"], trimmed[0]["z"], trimmed[0]["width_m"]) == pytest.approx(
        (4.0, 1.4, 8.8)
    )
    assert (trimmed[-1]["x"], trimmed[-1]["y"], trimmed[-1]["z"]) == pytest.approx(
        (16.0, 3.0, 2.6)
    )


def test_terminal_trim_rejects_an_inset_that_removes_the_route() -> None:
    with pytest.raises(ValueError):
        trim_centerline_terminals(
            [
                {"station_m": 0.0, "x": 0.0, "y": 0.0},
                {"station_m": 6.0, "x": 6.0, "y": 0.0},
            ],
            3.0,
        )


def test_station_range_clip_excludes_asymmetric_terrain_caps() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 1.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0, "z": 2.0},
        {"station_m": 30.0, "x": 30.0, "y": 10.0, "z": 3.0},
    ]

    clipped = clip_centerline_station_range(centerline, 8.0, 24.0)

    assert [point["station_m"] for point in clipped] == pytest.approx(
        [8.0, 10.0, 24.0]
    )
    assert (clipped[0]["x"], clipped[0]["z"]) == pytest.approx((8.0, 1.8))
    assert (clipped[-1]["x"], clipped[-1]["y"]) == pytest.approx((24.0, 7.0))


def test_station_range_clip_rejects_values_outside_centerline() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0},
    ]

    with pytest.raises(ValueError):
        clip_centerline_station_range(centerline, -1.0, 8.0)
    with pytest.raises(ValueError):
        clip_centerline_station_range(centerline, 8.0, 8.0)


def test_nearest_station_projects_onto_bent_centerline() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0},
        {"station_m": 20.0, "x": 10.0, "y": 10.0},
    ]

    assert nearest_centerline_station(centerline, 4.0, 2.0) == pytest.approx(4.0)
    assert nearest_centerline_station(centerline, 12.0, 7.0) == pytest.approx(17.0)


def test_terminal_floor_is_buried_but_interior_floor_is_unchanged() -> None:
    centerline = [
        {"station_m": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
        {"station_m": 10.0, "x": 10.0, "y": 0.0, "z": 0.0},
        {"station_m": 20.0, "x": 20.0, "y": 0.0, "z": 0.0},
        {"station_m": 30.0, "x": 30.0, "y": 0.0, "z": 0.0},
    ]

    def terrain(x: float, _y: float, _fallback: float) -> float:
        return 5.0 if x < 10.0 or x > 20.0 else 2.0 + x * 0.01

    sample = terminal_grade_clamped_floor_sampler(
        centerline,
        terrain,
        grade_start_station_m=10.0,
        grade_end_station_m=20.0,
    )

    assert sample(2.0, 0.0, 0.0) == pytest.approx(2.1)
    assert sample(15.0, 0.0, 0.0) == pytest.approx(2.15)
    assert sample(28.0, 0.0, 0.0) == pytest.approx(2.2)


def test_hollow_pipe_mesh_has_an_open_bore_and_closed_wall() -> None:
    radial_segments = 16
    mesh = hollow_pipe_mesh_data(
        4.0,
        0.6,
        0.48,
        radial_segments=radial_segments,
    )

    assert len(mesh["points"]) == radial_segments * 4
    assert len(mesh["face_vertex_counts"]) == radial_segments * 4
    assert set(mesh["face_vertex_counts"]) == {4}
    assert len(mesh["face_vertex_indices"]) == radial_segments * 16


def test_installed_pipe_map_delta_keeps_world_geometry_and_bounds() -> None:
    plan = build_pipe_segment_plans(
        [
            {"station_m": 0.0, "x": 1.0, "y": 2.0, "z": 0.0},
            {"station_m": 4.0, "x": 5.0, "y": 2.0, "z": 0.0},
        ],
        floor_height=_flat_floor,
        maximum_segment_length_m=4.0,
    )[0]

    change = _map_change(plan, "EXC-FRONT-01")

    assert change["action"] == "upsert"
    assert change["type"] == "installed_pipe"
    assert change["geometry"]["format"] == "sitegit-triangle-mesh-v1"
    assert change["geometry"]["top_face_count"] == 0
    assert len(change["geometry"]["points"]) == 64
    assert change["size"]["x"] == pytest.approx(4.0)
    assert change["size"]["y"] == pytest.approx(1.2)
    assert change["size"]["z"] == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("inside", "outside"),
    [(0.0, 0.6), (0.6, 0.6), (0.7, 0.6)],
)
def test_hollow_pipe_rejects_invalid_radii(inside: float, outside: float) -> None:
    with pytest.raises(ValueError):
        hollow_pipe_mesh_data(4.0, outside, inside)
