from __future__ import annotations

import json

import numpy as np

from isaac_adapter.terrain_collision_proxy import (
    build_collision_proxy_data,
    collision_proxy_height_sampler,
    load_or_build_collision_proxy_data,
)


def _write_bundle(root) -> None:
    root.mkdir()
    # Browser buffers store original OBJ X,Y,Z followed by U,V.  This square
    # becomes a 2x2 SiteGit X,Y grid after the Y-up to Z-up conversion.
    values = np.asarray(
        [
            [1.0, 1.0, 3.0, 0.0, 0.0],
            [3.0, 2.0, 3.0, 1.0, 0.0],
            [1.0, 3.0, 1.0, 0.0, 1.0],
            [3.0, 4.0, 1.0, 1.0, 1.0],
        ],
        dtype="<f4",
    )
    values.tofile(root / "ground.bin")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "format": "sitegit-web-mesh-v1",
                "bounds": {"min": [0.0, 0.0, 0.0], "max": [4.0, 4.0, 4.0]},
                "groups": [{"geometry": "ground.bin"}],
            }
        ),
        encoding="utf-8",
    )


def test_proxy_reduces_browser_mesh_to_regular_collision_grid(tmp_path) -> None:
    bundle = tmp_path / "bundle"
    _write_bundle(bundle)

    data = build_collision_proxy_data(bundle, resolution_m=2.0)

    assert data["source_vertex_count"] == 4
    assert data["valid_cell_count"] == 4
    assert data["triangle_count"] == 2
    assert data["points"].shape == (4, 3)
    assert sorted(data["points"][:, 2].tolist()) == [1.0, 2.0, 3.0, 4.0]


def test_proxy_cache_is_reused_when_bundle_is_unchanged(tmp_path) -> None:
    bundle = tmp_path / "bundle"
    cache = tmp_path / "proxy.npz"
    _write_bundle(bundle)

    first, first_hit = load_or_build_collision_proxy_data(
        bundle, cache, resolution_m=2.0
    )
    second, second_hit = load_or_build_collision_proxy_data(
        bundle, cache, resolution_m=2.0
    )

    assert first_hit is False
    assert second_hit is True
    assert second["signature"] == first["signature"]
    assert np.array_equal(second["face_indices"], first["face_indices"])

    sample_height = collision_proxy_height_sampler(cache)
    assert sample_height(-1.0, -1.0, 0.0) == 1.0
    assert sample_height(0.0, 0.0, 0.0) == 2.5
