from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class EvidenceExporter:
    def __init__(self, evidence_root: Path):
        self.evidence_root = evidence_root

    def save_summary(self, storage_key: str, summary: dict[str, Any]) -> Path:
        target = (self.evidence_root / storage_key).resolve()
        root = self.evidence_root.resolve()
        if root not in target.parents:
            raise ValueError("storage_key must remain under evidence_root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def target_path(self, storage_key: str) -> Path:
        target = (self.evidence_root / storage_key).resolve()
        root = self.evidence_root.resolve()
        if root not in target.parents:
            raise ValueError("storage_key must remain under evidence_root")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def capture_lidar_points(
        self,
        stage: Any,
        storage_key: str,
        prim_path: str,
        *,
        max_points: int = 100_000,
    ) -> dict[str, Any]:
        """Save the current real UsdGeom.Points payload as an ASCII PLY file."""
        from pxr import UsdGeom

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid() or not prim.IsA(UsdGeom.Points):
            return {
                "available": False,
                "prim_path": prim_path,
                "reason": "LiDAR Points Prim not found",
            }
        values = UsdGeom.Points(prim).GetPointsAttr().Get() or []
        points = values[:max_points]
        exported = self.save_point_cloud(storage_key, points)
        return {
            **exported,
            "prim_path": prim_path,
            "source_point_count": len(values),
            "truncated": len(values) > len(points),
        }

    def save_point_cloud(
        self,
        storage_key: str,
        points: Any,
    ) -> dict[str, Any]:
        """Save world-space XYZ points as the adapter's portable ASCII PLY."""

        values = list(points)
        target = self.target_path(storage_key)
        lines = [
            "ply",
            "format ascii 1.0",
            f"element vertex {len(values)}",
            "property float x",
            "property float y",
            "property float z",
            "end_header",
        ]
        lines.extend(f"{float(p[0])} {float(p[1])} {float(p[2])}" for p in values)
        target.write_text("\n".join(lines) + "\n", encoding="ascii")
        return {
            "available": True,
            "storage_key": storage_key,
            "point_count": len(values),
            "coordinate_frame": "world-z-up-metres",
        }

    def compare_lidar_height_grids(
        self,
        before_storage_key: str | None,
        after_storage_key: str | None,
        *,
        cell_size_m: float = 0.5,
        minimum_height_change_m: float = 0.05,
    ) -> dict[str, Any]:
        """Estimate terrain volume change from two ASCII PLY point clouds.

        Each XY cell uses the highest observed Z value.  This is deliberately
        labelled as an estimate: it is useful for the demo and remains
        independent of a particular excavation scenario, but it is not a
        survey-grade mesh-volume calculation.
        """

        if not before_storage_key or not after_storage_key:
            return {
                "available": False,
                "method": "lidar_height_grid_max_z",
                "reason": "before and after LiDAR artifacts are required",
            }
        if cell_size_m <= 0:
            raise ValueError("cell_size_m must be greater than zero")

        before_path = self.target_path(before_storage_key)
        after_path = self.target_path(after_storage_key)
        if not before_path.is_file() or not after_path.is_file():
            return {
                "available": False,
                "method": "lidar_height_grid_max_z",
                "reason": "before or after LiDAR PLY file does not exist",
            }

        try:
            before_grid, before_count = _read_height_grid(before_path, cell_size_m)
            after_grid, after_count = _read_height_grid(after_path, cell_size_m)
        except (OSError, ValueError) as error:
            return {
                "available": False,
                "method": "lidar_height_grid_max_z",
                "reason": f"LiDAR PLY comparison failed: {error}",
            }

        common_cells = before_grid.keys() & after_grid.keys()
        if not common_cells:
            return {
                "available": False,
                "method": "lidar_height_grid_max_z",
                "reason": "before and after LiDAR scans have no overlapping XY cells",
                "before_point_count": before_count,
                "after_point_count": after_count,
            }

        cell_area = cell_size_m * cell_size_m
        removed_volume = 0.0
        added_volume = 0.0
        absolute_height_change = 0.0
        changed_cells = 0
        for cell in common_cells:
            # Positive delta means the observed surface became lower.
            delta = before_grid[cell] - after_grid[cell]
            if abs(delta) < minimum_height_change_m:
                continue
            changed_cells += 1
            absolute_height_change += abs(delta)
            if delta > 0:
                removed_volume += delta * cell_area
            else:
                added_volume += -delta * cell_area

        compared_cells = len(common_cells)
        return {
            "available": True,
            "method": "lidar_height_grid_max_z",
            "estimated": True,
            "cell_size_m": cell_size_m,
            "minimum_height_change_m": minimum_height_change_m,
            "compared_cell_count": compared_cells,
            "changed_cell_count": changed_cells,
            "before_point_count": before_count,
            "after_point_count": after_count,
            "overlap_ratio": round(
                compared_cells / max(len(before_grid), len(after_grid), 1), 6
            ),
            "removed_volume_m3": round(removed_volume, 6),
            "added_volume_m3": round(added_volume, 6),
            "net_volume_change_m3": round(added_volume - removed_volume, 6),
            "mean_absolute_height_change_m": round(
                absolute_height_change / changed_cells if changed_cells else 0.0,
                6,
            ),
        }


def _read_height_grid(path: Path, cell_size_m: float) -> tuple[dict[tuple[int, int], float], int]:
    """Read the limited ASCII PLY format emitted by ``capture_lidar_points``."""

    grid: dict[tuple[int, int], float] = {}
    vertex_count: int | None = None
    with path.open("r", encoding="ascii") as stream:
        if stream.readline().strip() != "ply":
            raise ValueError(f"not a PLY file: {path.name}")
        if stream.readline().strip() != "format ascii 1.0":
            raise ValueError(f"only ASCII PLY is supported: {path.name}")
        for line in stream:
            stripped = line.strip()
            if stripped.startswith("element vertex "):
                vertex_count = int(stripped.rsplit(" ", 1)[1])
            if stripped == "end_header":
                break
        if vertex_count is None:
            raise ValueError(f"PLY vertex count is missing: {path.name}")

        read_count = 0
        for line in stream:
            if read_count >= vertex_count:
                break
            values = line.split()
            if len(values) < 3:
                continue
            x, y, z = (float(values[0]), float(values[1]), float(values[2]))
            if not all(math.isfinite(value) for value in (x, y, z)):
                continue
            cell = (math.floor(x / cell_size_m), math.floor(y / cell_size_m))
            previous = grid.get(cell)
            if previous is None or z > previous:
                grid[cell] = z
            read_count += 1
    return grid, read_count
