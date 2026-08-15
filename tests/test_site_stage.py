"""Pure geometry and adapter-setting checks for the semantic soil-pile demo."""

from __future__ import annotations

import pytest

from isaac_adapter.isaac_runner import _float_tuple
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
