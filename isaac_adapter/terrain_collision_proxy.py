"""Build and attach a lightweight collision surface for the site-map stage.

The rendered USD keeps its full photogrammetry mesh.  Physics and ray sensors
use a regular, cached terrain proxy so Isaac does not cook roughly one million
source triangles every time the runner starts.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


PROXY_PRIM_PATH = "/World/SiteGitTerrainCollision"
PROXY_CACHE_NAME = "terrain_collision_proxy_2m.npz"


def _bundle_signature(bundle_root: Path, manifest: dict[str, Any]) -> str:
    """Return a stable cache key for one published browser mesh bundle."""

    digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    for group in manifest.get("groups", []):
        path = (bundle_root / str(group.get("geometry") or "")).resolve()
        stat = path.stat()
        digest.update(path.name.encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def build_collision_proxy_data(
    bundle_root: str | Path,
    *,
    resolution_m: float = 2.0,
) -> dict[str, Any]:
    """Convert the published OBJ-coordinate mesh buffers into a Z-up grid."""

    import numpy as np

    root = Path(bundle_root).resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "sitegit-web-mesh-v1":
        raise ValueError("terrain collision proxy requires sitegit-web-mesh-v1")
    if resolution_m <= 0:
        raise ValueError("terrain collision proxy resolution must be positive")

    bounds_min = np.asarray(manifest["bounds"]["min"], dtype=np.float64)
    bounds_max = np.asarray(manifest["bounds"]["max"], dtype=np.float64)
    center_x = float((bounds_min[0] + bounds_max[0]) * 0.5)
    center_z = float((bounds_min[2] + bounds_max[2]) * 0.5)
    site_min_x = float(bounds_min[0] - center_x)
    site_max_x = float(bounds_max[0] - center_x)
    site_min_y = float(center_z - bounds_max[2])
    site_max_y = float(center_z - bounds_min[2])
    nx = max(2, int(math.ceil((site_max_x - site_min_x) / resolution_m)))
    ny = max(2, int(math.ceil((site_max_y - site_min_y) / resolution_m)))
    heights = np.full(nx * ny, -np.inf, dtype=np.float32)
    source_vertex_count = 0

    for group in manifest.get("groups", []):
        geometry = str(group.get("geometry") or "")
        path = (root / geometry).resolve()
        if root not in path.parents or not path.is_file():
            raise FileNotFoundError(f"invalid terrain geometry path: {geometry}")
        values = np.fromfile(path, dtype="<f4")
        if values.size % 5:
            raise ValueError(f"invalid terrain geometry buffer: {geometry}")
        vertices = values.reshape((-1, 5))
        source_vertex_count += int(vertices.shape[0])
        site_x = vertices[:, 0].astype(np.float64) - center_x
        site_y = center_z - vertices[:, 2].astype(np.float64)
        site_z = vertices[:, 1].astype(np.float64) - float(bounds_min[1])
        ix = np.floor((site_x - site_min_x) / resolution_m).astype(np.int64)
        iy = np.floor((site_y - site_min_y) / resolution_m).astype(np.int64)
        valid = (
            (ix >= 0)
            & (ix < nx)
            & (iy >= 0)
            & (iy < ny)
            & np.isfinite(site_z)
        )
        np.maximum.at(heights, iy[valid] * nx + ix[valid], site_z[valid])

    valid_cells = np.isfinite(heights).reshape((ny, nx))
    height_grid = heights.reshape((ny, nx))
    x_values = site_min_x + (np.arange(nx, dtype=np.float32) + 0.5) * resolution_m
    y_values = site_min_y + (np.arange(ny, dtype=np.float32) + 0.5) * resolution_m
    grid_x, grid_y = np.meshgrid(x_values, y_values)
    bounded_heights = np.where(valid_cells, height_grid, 0.0)
    points = np.column_stack(
        (grid_x.ravel(), grid_y.ravel(), bounded_heights.ravel())
    ).astype(np.float32)

    quads = (
        valid_cells[:-1, :-1]
        & valid_cells[:-1, 1:]
        & valid_cells[1:, :-1]
        & valid_cells[1:, 1:]
    )
    rows, columns = np.nonzero(quads)
    lower_left = rows * nx + columns
    lower_right = lower_left + 1
    upper_left = lower_left + nx
    upper_right = upper_left + 1
    first = np.column_stack((lower_left, lower_right, upper_right))
    second = np.column_stack((lower_left, upper_right, upper_left))
    face_indices = np.concatenate((first, second), axis=0).astype(np.int32).ravel()

    return {
        "points": points,
        "face_indices": face_indices,
        "valid_cells": valid_cells,
        "nx": nx,
        "ny": ny,
        "site_min_x": site_min_x,
        "site_min_y": site_min_y,
        "resolution_m": float(resolution_m),
        "source_vertex_count": source_vertex_count,
        "valid_cell_count": int(valid_cells.sum()),
        "triangle_count": int(face_indices.size // 3),
        "signature": _bundle_signature(root, manifest),
    }


def load_or_build_collision_proxy_data(
    bundle_root: str | Path,
    cache_path: str | Path,
    *,
    resolution_m: float = 2.0,
) -> tuple[dict[str, Any], bool]:
    """Load a matching proxy cache, or build and atomically replace it."""

    import numpy as np

    root = Path(bundle_root).resolve()
    target = Path(cache_path).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    signature = _bundle_signature(root, manifest)
    if target.is_file():
        try:
            with np.load(target, allow_pickle=False) as cached:
                cached_signature = str(cached["signature"].item())
                cached_resolution = float(cached["resolution_m"].item())
                if cached_signature == signature and math.isclose(
                    cached_resolution, resolution_m
                ):
                    return (
                        {
                            "points": cached["points"].copy(),
                            "face_indices": cached["face_indices"].copy(),
                            "valid_cells": cached["valid_cells"].copy(),
                            "nx": int(cached["nx"].item()),
                            "ny": int(cached["ny"].item()),
                            "site_min_x": float(cached["site_min_x"].item()),
                            "site_min_y": float(cached["site_min_y"].item()),
                            "resolution_m": cached_resolution,
                            "source_vertex_count": int(cached["source_vertex_count"].item()),
                            "valid_cell_count": int(cached["valid_cell_count"].item()),
                            "triangle_count": int(cached["triangle_count"].item()),
                            "signature": cached_signature,
                        },
                        True,
                    )
        except (OSError, ValueError, KeyError):
            pass

    data = build_collision_proxy_data(root, resolution_m=resolution_m)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp.npz")
    np.savez(
        temporary,
        points=data["points"],
        face_indices=data["face_indices"],
        valid_cells=data["valid_cells"],
        nx=np.asarray(data["nx"], dtype=np.int64),
        ny=np.asarray(data["ny"], dtype=np.int64),
        site_min_x=np.asarray(data["site_min_x"], dtype=np.float64),
        site_min_y=np.asarray(data["site_min_y"], dtype=np.float64),
        resolution_m=np.asarray(data["resolution_m"], dtype=np.float64),
        source_vertex_count=np.asarray(data["source_vertex_count"], dtype=np.int64),
        valid_cell_count=np.asarray(data["valid_cell_count"], dtype=np.int64),
        triangle_count=np.asarray(data["triangle_count"], dtype=np.int64),
        signature=np.asarray(data["signature"]),
    )
    temporary.replace(target)
    return data, False


def collision_proxy_height_sampler(cache_path: str | Path):
    """Load one cached grid and return a fast ``(x, y, fallback) -> z`` sampler."""

    import numpy as np

    target = Path(cache_path).resolve()
    with np.load(target, allow_pickle=False) as cached:
        points = cached["points"].copy()
        valid = cached["valid_cells"].copy().astype(bool)
        nx = int(cached["nx"].item())
        ny = int(cached["ny"].item())
        resolution = float(cached["resolution_m"].item())
        site_min_x = float(cached["site_min_x"].item())
        site_min_y = float(cached["site_min_y"].item())
    heights = points[:, 2].reshape((ny, nx))
    origin_x = site_min_x + 0.5 * resolution
    origin_y = site_min_y + 0.5 * resolution

    def sample(x: float, y: float, fallback: float = 0.0) -> float:
        fractional_x = (float(x) - origin_x) / resolution
        fractional_y = (float(y) - origin_y) / resolution
        ix = int(math.floor(fractional_x))
        iy = int(math.floor(fractional_y))
        tx = fractional_x - ix
        ty = fractional_y - iy
        if 0 <= ix < nx - 1 and 0 <= iy < ny - 1:
            corners_valid = (
                valid[iy, ix]
                and valid[iy, ix + 1]
                and valid[iy + 1, ix]
                and valid[iy + 1, ix + 1]
            )
            if corners_valid:
                lower = heights[iy, ix] * (1.0 - tx) + heights[iy, ix + 1] * tx
                upper = (
                    heights[iy + 1, ix] * (1.0 - tx)
                    + heights[iy + 1, ix + 1] * tx
                )
                return float(lower * (1.0 - ty) + upper * ty)

        nearest_x = min(max(int(round(fractional_x)), 0), nx - 1)
        nearest_y = min(max(int(round(fractional_y)), 0), ny - 1)
        for radius in range(5):
            x0, x1 = max(0, nearest_x - radius), min(nx, nearest_x + radius + 1)
            y0, y1 = max(0, nearest_y - radius), min(ny, nearest_y + radius + 1)
            candidates = valid[y0:y1, x0:x1]
            if candidates.any():
                return float(np.median(heights[y0:y1, x0:x1][candidates]))
        return float(fallback)

    return sample


def create_terrain_collision_proxy(
    stage: Any,
    data_root: str | Path,
    *,
    resolution_m: float = 2.0,
    prim_path: str = PROXY_PRIM_PATH,
) -> dict[str, Any]:
    """Create one invisible static PhysX mesh from the cached proxy grid."""

    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    root = Path(data_root).resolve()
    bundle_root = root / "isaac" / "site-work-map"
    cache_path = root / "isaac" / PROXY_CACHE_NAME
    data, cache_hit = load_or_build_collision_proxy_data(
        bundle_root,
        cache_path,
        resolution_m=resolution_m,
    )

    site = stage.GetPrimAtPath("/World/Site")
    disabled_source_meshes = 0
    if site.IsValid():
        for source_prim in Usd.PrimRange(site):
            if source_prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI(source_prim).CreateCollisionEnabledAttr().Set(False)
                disabled_source_meshes += 1

    mesh = UsdGeom.Mesh.Define(stage, Sdf.Path(prim_path))
    mesh.CreatePointsAttr().Set([Gf.Vec3f(*map(float, point)) for point in data["points"]])
    indices = [int(value) for value in data["face_indices"]]
    mesh.CreateFaceVertexCountsAttr().Set([3] * (len(indices) // 3))
    mesh.CreateFaceVertexIndicesAttr().Set(indices)
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr().Set(True)
    mesh.MakeInvisible()
    collision = UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    collision.CreateCollisionEnabledAttr().Set(True)
    UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr().Set("none")
    mesh.GetPrim().SetCustomDataByKey("sitegitCollisionProxy", True)
    mesh.GetPrim().SetCustomDataByKey("sitegitResolutionM", float(resolution_m))

    return {
        "prim_path": prim_path,
        "cache_path": str(cache_path),
        "cache_hit": cache_hit,
        "resolution_m": data["resolution_m"],
        "source_vertex_count": data["source_vertex_count"],
        "valid_cell_count": data["valid_cell_count"],
        "triangle_count": data["triangle_count"],
        "disabled_source_meshes": disabled_source_meshes,
    }
