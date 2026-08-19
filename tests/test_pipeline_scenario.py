"""Geometry policy checks for the demolition-site pipeline baseline."""

from isaac_adapter.pipeline_scenario import (
    DEFAULT_TRENCH_STATIONS,
    DEMOLITION_SOIL_TILE_UV_BOUNDS,
    _section_mesh_data,
    _station_profiles,
    trench_section_spans,
)


def test_pipeline_fill_is_split_into_work_package_sized_sections():
    spans = trench_section_spans()

    assert len(spans) == len(DEFAULT_TRENCH_STATIONS) - 1
    assert max(spans) <= 25.0
    assert all(span > 0 for span in spans)


def test_pipeline_route_crosses_zone_a_into_zone_c():
    assert DEFAULT_TRENCH_STATIONS[0].y < 0
    assert DEFAULT_TRENCH_STATIONS[-1].y > 0


def test_pipeline_terminal_profiles_close_on_intact_ground_without_pinching():
    first, second = DEFAULT_TRENCH_STATIONS[:2]
    penultimate, last = DEFAULT_TRENCH_STATIONS[-2:]

    assert first.y <= -46.0
    assert last.y >= 30.0
    assert first.width >= second.width
    assert last.width >= penultimate.width
    assert first.surface_blend == 0.0
    assert last.surface_blend == 0.0


def test_pipeline_sections_share_dense_edges_and_pinched_banks():
    def flat_surface(_x: float, _y: float, _fallback: float) -> float:
        return 0.0

    columns = 13
    profiles = _station_profiles(
        DEFAULT_TRENCH_STATIONS[:3],
        flat_surface,
        columns=columns,
        texture_scale_m=4.0,
    )
    first = _section_mesh_data(
        profiles[0], profiles[1], flat_surface, columns=columns
    )
    second = _section_mesh_data(
        profiles[1], profiles[2], flat_surface, columns=columns
    )

    first_end = first["points"][(11 - 1) * columns : 11 * columns]
    second_start = second["points"][:columns]
    assert first_end == second_start
    assert first["top_vertex_count"] == 11 * columns
    assert len(first["points"]) == 2 * 11 * columns
    assert first["top_face_count"] == 2 * (11 - 1) * (columns - 1)
    assert first["top_z"] - first["base_z"] < 0.25


def test_pipeline_outer_bank_vertices_feather_to_sampled_ground():
    def sloped_surface(x: float, y: float, _fallback: float) -> float:
        return 0.2 * x + 0.1 * y

    profiles = _station_profiles(
        DEFAULT_TRENCH_STATIONS[:2],
        sloped_surface,
        columns=13,
        texture_scale_m=4.0,
    )
    for profile in profiles:
        for point in (profile["points"][0], profile["points"][-1]):
            ground = sloped_surface(point[0], point[1], 0.0)
            assert abs(point[2] - (ground - 0.015)) < 1e-6


def test_pipeline_backfill_is_a_closed_volume_down_to_the_trench_floor():
    columns = 5
    start = {
        "points": [(float(column), 0.0, 2.0) for column in range(columns)],
        "floors": [-3.0] * columns,
        "uvs": [(0.0, 0.0)] * columns,
    }
    end = {
        "points": [(float(column), 4.0, 2.0) for column in range(columns)],
        "floors": [-3.0] * columns,
        "uvs": [(0.0, 0.0)] * columns,
    }

    data = _section_mesh_data(
        start,
        end,
        lambda _x, _y, _fallback: -3.0,
        rows=4,
        columns=columns,
    )

    assert data["top_vertex_count"] == 20
    assert len(data["points"]) == 40
    assert data["base_z"] <= -3.03
    assert data["top_z"] - data["base_z"] >= 5.0
    assert len(data["face_vertex_counts"]) > data["top_face_count"]


def test_pipeline_uvs_stay_inside_original_map_soil_atlas_region():
    def flat_surface(_x: float, _y: float, _fallback: float) -> float:
        return 0.0

    columns = 13
    profiles = _station_profiles(
        DEFAULT_TRENCH_STATIONS[:2],
        flat_surface,
        columns=columns,
        texture_scale_m=4.0,
    )
    data = _section_mesh_data(
        profiles[0],
        profiles[1],
        flat_surface,
        columns=columns,
        uv_along_start=0.25,
        uv_along_end=0.5,
    )
    u_min, v_min, u_max, v_max = DEMOLITION_SOIL_TILE_UV_BOUNDS
    assert all(u_min <= u <= u_max and v_min <= v <= v_max for u, v in data["uvs"])


def test_pipeline_atlas_region_is_the_verified_continuous_soil_island():
    assert DEMOLITION_SOIL_TILE_UV_BOUNDS == (0.0, 0.0, 1.0, 1.0)
