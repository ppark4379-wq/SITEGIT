"""Build a browser-ready SiteGit map bundle from a textured OBJ asset.

Each material becomes one interleaved little-endian float32 buffer containing
``x, y, z, u, v`` for every triangle vertex.  Diffuse textures are reduced for
the browser while the original OBJ and textures remain untouched.
"""

from __future__ import annotations

import argparse
from array import array
import json
import math
from pathlib import Path
import sys


SUPPORTED_FORMAT = "sitegit-web-mesh-v1"


def _parse_index(value: str, item_count: int) -> int:
    """Convert an OBJ one-based or negative index into a zero-based index."""

    index = int(value)
    return index - 1 if index > 0 else item_count + index


def build_web_bundle(
    source_obj: str | Path,
    output_root: str | Path,
    *,
    face_stride: int = 1,
    texture_max_size: int = 2048,
    flip_v: bool = False,
) -> Path:
    """Convert one RealityCapture-style OBJ into a SiteGit WebGL bundle."""

    if face_stride < 1:
        raise ValueError("face_stride must be at least 1")
    if texture_max_size < 256:
        raise ValueError("texture_max_size must be at least 256")

    source = Path(source_obj).expanduser().resolve()
    target = Path(output_root).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".obj":
        raise FileNotFoundError(f"OBJ asset not found: {source}")

    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Pillow is required: pip install -r isaac_adapter/requirements.txt"
        ) from error

    target.mkdir(parents=True, exist_ok=True)
    positions = array("f")
    texcoords = array("f")
    groups: dict[str, array] = {}
    current_material = "default"
    face_number = 0
    selected_triangles = 0
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]

    with source.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if line.startswith("v "):
                values = line.split()
                positions.extend(float(value) for value in values[1:4])
            elif line.startswith("vt "):
                values = line.split()
                texcoords.extend(float(value) for value in values[1:3])
            elif line.startswith("usemtl "):
                current_material = line.split(maxsplit=1)[1].strip()
            elif line.startswith("f "):
                face_number += 1
                if face_number % face_stride:
                    continue
                corners = line.split()[1:]
                if len(corners) < 3:
                    continue
                output = groups.setdefault(current_material, array("f"))
                for triangle_index in range(1, len(corners) - 1):
                    for corner in (
                        corners[0],
                        corners[triangle_index],
                        corners[triangle_index + 1],
                    ):
                        parts = corner.split("/")
                        vertex_index = _parse_index(parts[0], len(positions) // 3)
                        uv_index = (
                            _parse_index(parts[1], len(texcoords) // 2)
                            if len(parts) > 1 and parts[1]
                            else -1
                        )
                        x, y, z = positions[vertex_index * 3 : vertex_index * 3 + 3]
                        u, v = (
                            texcoords[uv_index * 2 : uv_index * 2 + 2]
                            if uv_index >= 0
                            else (0.0, 0.0)
                        )
                        output.extend((x, y, z, u, 1.0 - v if flip_v else v))
                        minimum[0] = min(minimum[0], x)
                        minimum[1] = min(minimum[1], y)
                        minimum[2] = min(minimum[2], z)
                        maximum[0] = max(maximum[0], x)
                        maximum[1] = max(maximum[1], y)
                        maximum[2] = max(maximum[2], z)
                    selected_triangles += 1

    manifest_groups: list[dict[str, object]] = []
    for material, values in groups.items():
        geometry_name = f"{material}.bin"
        with (target / geometry_name).open("wb") as output:
            if sys.byteorder != "little":
                values.byteswap()
            values.tofile(output)

        texture_name = f"{material}_diffuse.jpg"
        source_texture = source.parent / texture_name
        target_texture = target / texture_name
        if source_texture.is_file():
            with Image.open(source_texture) as image:
                image.thumbnail(
                    (texture_max_size, texture_max_size),
                    Image.Resampling.LANCZOS,
                )
                image.convert("RGB").save(
                    target_texture,
                    "JPEG",
                    quality=84,
                    optimize=True,
                )

        manifest_groups.append(
            {
                "material": material,
                "geometry": geometry_name,
                "texture": texture_name if target_texture.is_file() else None,
                "vertex_count": len(values) // 5,
            }
        )

    if not manifest_groups or selected_triangles <= 0:
        raise ValueError(f"OBJ contains no renderable faces: {source}")
    manifest = {
        "format": SUPPORTED_FORMAT,
        "source": str(source),
        "face_stride": face_stride,
        "flip_v": flip_v,
        "triangle_count": selected_triangles,
        "bounds": {"min": minimum, "max": maximum},
        "groups": manifest_groups,
    }
    temporary = target / "manifest.json.tmp"
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target / "manifest.json")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-obj", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--face-stride", type=int, default=1)
    parser.add_argument("--texture-max-size", type=int, default=2048)
    parser.add_argument(
        "--flip-v",
        action="store_true",
        help="Invert OBJ texture V coordinates for assets exported with top-left UVs",
    )
    args = parser.parse_args()
    output = build_web_bundle(
        args.source_obj,
        args.output,
        face_stride=args.face_stride,
        texture_max_size=args.texture_max_size,
        flip_v=args.flip_v,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    print(f"SiteGit web map generated: {output}")
    print(f"Triangles: {manifest['triangle_count']:,}")
    print(f"Materials: {len(manifest['groups'])}")


if __name__ == "__main__":
    main()
