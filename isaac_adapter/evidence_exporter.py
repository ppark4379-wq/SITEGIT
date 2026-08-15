from __future__ import annotations

import json
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
        target = self.target_path(storage_key)
        lines = [
            "ply",
            "format ascii 1.0",
            f"element vertex {len(points)}",
            "property float x",
            "property float y",
            "property float z",
            "end_header",
        ]
        lines.extend(f"{float(p[0])} {float(p[1])} {float(p[2])}" for p in points)
        target.write_text("\n".join(lines) + "\n", encoding="ascii")
        return {
            "available": True,
            "storage_key": storage_key,
            "prim_path": prim_path,
            "point_count": len(points),
            "source_point_count": len(values),
            "truncated": len(values) > len(points),
        }
