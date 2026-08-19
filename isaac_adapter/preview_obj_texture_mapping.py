"""Render quick top-view previews for both OBJ texture-V conventions.

This diagnostic avoids a full renderer: it projects triangle centroids into a
height-buffer and samples each material atlas.  The two images make an upside-
down UV import immediately visible when preparing a browser mesh bundle.
"""

from __future__ import annotations

import argparse
from array import array
from pathlib import Path

import numpy as np
from PIL import Image


def _index(value: str, count: int) -> int:
    index = int(value)
    return index - 1 if index > 0 else count + index


def render(source_obj: Path, output_root: Path, size: int) -> None:
    """Write ``v-direct.png`` and ``v-flipped.png`` top views."""

    positions = array("f")
    texcoords = array("f")
    material = "default"
    atlases: dict[str, np.ndarray] = {}
    height = np.full((size, size), -np.inf, dtype=np.float32)
    direct = np.zeros((size, size, 3), dtype=np.uint8)
    flipped = np.zeros_like(direct)
    bounds = [np.inf, -np.inf, np.inf, -np.inf]

    with source_obj.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if line.startswith("v "):
                x, y, z = map(float, line.split()[1:4])
                positions.extend((x, y, z))
                bounds[0] = min(bounds[0], x)
                bounds[1] = max(bounds[1], x)
                bounds[2] = min(bounds[2], z)
                bounds[3] = max(bounds[3], z)
            elif line.startswith("vt "):
                texcoords.extend(map(float, line.split()[1:3]))

    span_x = max(bounds[1] - bounds[0], 1e-6)
    span_z = max(bounds[3] - bounds[2], 1e-6)
    with source_obj.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if line.startswith("usemtl "):
                material = line.split(maxsplit=1)[1].strip()
                if material not in atlases:
                    texture = source_obj.parent / f"{material}_diffuse.jpg"
                    atlases[material] = np.asarray(Image.open(texture).convert("RGB"))
            elif not line.startswith("f "):
                continue
            corners = line.split()[1:]
            for triangle_index in range(1, len(corners) - 1):
                triangle = (corners[0], corners[triangle_index], corners[triangle_index + 1])
                xyz = []
                uv = []
                for corner in triangle:
                    parts = corner.split("/")
                    vi = _index(parts[0], len(positions) // 3)
                    ti = _index(parts[1], len(texcoords) // 2)
                    xyz.append(positions[vi * 3 : vi * 3 + 3])
                    uv.append(texcoords[ti * 2 : ti * 2 + 2])
                center = np.mean(np.asarray(xyz), axis=0)
                center_uv = np.mod(np.mean(np.asarray(uv), axis=0), 1.0)
                px = min(size - 1, max(0, int((center[0] - bounds[0]) / span_x * (size - 1))))
                py = min(size - 1, max(0, int((bounds[3] - center[2]) / span_z * (size - 1))))
                if center[1] < height[py, px]:
                    continue
                atlas = atlases[material]
                tx = min(atlas.shape[1] - 1, int(center_uv[0] * atlas.shape[1]))
                ty = min(atlas.shape[0] - 1, int(center_uv[1] * atlas.shape[0]))
                height[py, px] = center[1]
                direct[py, px] = atlas[ty, tx]
                flipped[py, px] = atlas[atlas.shape[0] - 1 - ty, tx]

    output_root.mkdir(parents=True, exist_ok=True)
    Image.fromarray(direct).save(output_root / "v-direct.png")
    Image.fromarray(flipped).save(output_root / "v-flipped.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-obj", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=900)
    args = parser.parse_args()
    render(args.source_obj.resolve(), args.output.resolve(), args.size)


if __name__ == "__main__":
    main()
