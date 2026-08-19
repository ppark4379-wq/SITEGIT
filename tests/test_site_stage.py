"""Pure geometry and adapter-setting checks for the semantic soil-pile demo."""

from __future__ import annotations

import pytest

from isaac_adapter.isaac_runner import _float_tuple
from isaac_adapter.isaac_bridge import projected_mesh_volume, sculpt_soil_mesh_points
from isaac_adapter.site_stage import _triangle_surface_z_at_xy


def test_triangle_surface_height_interpolates_inside_triangle():
    height = _triangle_surface_z_at_xy(
        0.25,
        0.25,
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 3.0),
        (0.0, 1.0, 5.0),
    )

    assert height == pytest.approx(2.5)


def test_triangle_surface_height_rejects_point_outside_triangle():
    assert (
        _triangle_surface_z_at_xy(
            0.9,
            0.9,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        is None
    )


def test_adapter_vector_setting_requires_exact_component_count():
    assert _float_tuple("-12, 12", count=2, setting_name="POSITION") == (-12.0, 12.0)
    with pytest.raises(SystemExit, match="숫자 3개"):
        _float_tuple("6,5", count=3, setting_name="SIZE")


def test_soil_mesh_sculpt_removes_volume_without_deleting_the_rim():
    points = [
        (0.0, 0.0, 3.0),
        (-2.0, -2.0, 0.0),
        (2.0, -2.0, 0.0),
        (2.0, 2.0, 0.0),
        (-2.0, 2.0, 0.0),
    ]
    counts = [3, 3, 3, 3]
    indices = [0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1]

    sculpted = sculpt_soil_mesh_points(points, cut_ratio=0.9)
    before = projected_mesh_volume(points, counts, indices)
    after = projected_mesh_volume(sculpted, counts, indices)

    assert sculpted[0][2] < points[0][2]
    assert sculpted[1:] == points[1:]
    assert 0.0 < after < before
