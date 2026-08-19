"""Extract nearby photogrammetry soil patches for the pipeline scenario.

The browser mesh bundle contains the exact world positions, USD UVs and
material split used by the construction-site-demolition stage. This helper
finds upward-facing triangles close to the pipeline corridor, ranks their UV
neighbourhoods and writes a contact sheet made from the original 8K textures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


DEFAULT_STATIONS = (
    (-6.5, -38.0),
    (-6.0, -30.0),
    (-8.5, -22.0),
    (-10.5, -14.0),
    (-12.5, -6.0),
    (-14.5, 2.0),
    (-16.0, 10.0),
    (-14.0, 18.0),
    (-11.5, 22.0),
)


def _distance_to_corridor(points: np.ndarray, centerline: np.ndarray) -> np.ndarray:
    """Return each XZ point's planar distance to a polyline."""

    result = np.full(points.shape[0], np.inf, dtype=np.float32)
    for start, end in zip(centerline[:-1], centerline[1:]):
        segment = end - start
        denominator = float(np.dot(segment, segment))
        if denominator <= 1e-9:
            continue
        factor = np.clip(((points - start) @ segment) / denominator, 0.0, 1.0)
        closest = start + factor[:, None] * segment
        result = np.minimum(result, np.linalg.norm(points - closest, axis=1))
    return result


def _wrapped_crop(image: Image.Image, center: tuple[float, float], size: int) -> Image.Image:
    """Crop around normalized USD UV coordinates with texture wrapping."""

    source = np.asarray(image.convert("RGB"))
    height, width = source.shape[:2]
    center_x = int(round((center[0] % 1.0) * width))
    center_y = int(round((1.0 - center[1] % 1.0) * height))
    x_indices = (np.arange(size) + center_x - size // 2) % width
    y_indices = (np.arange(size) + center_y - size // 2) % height
    return Image.fromarray(source[np.ix_(y_indices, x_indices)], "RGB")


def extract_references(
    bundle: Path,
    texture_root: Path,
    output: Path,
    *,
    candidates: int = 12,
    crop_size: int = 1536,
) -> list[dict[str, object]]:
    """Build and save a ranked contact sheet of map-derived soil patches."""

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    bounds = manifest["bounds"]
    center_x = (float(bounds["min"][0]) + float(bounds["max"][0])) * 0.5
    center_z = (float(bounds["min"][2]) + float(bounds["max"][2])) * 0.5
    centerline = np.asarray(
        [(x + center_x, -y + center_z) for x, y in DEFAULT_STATIONS],
        dtype=np.float32,
    )

    ranked: list[dict[str, object]] = []
    for group in manifest["groups"]:
        material = str(group["material"])
        raw = np.fromfile(bundle / str(group["geometry"]), dtype="<f4")
        vertices = raw.reshape((-1, 5)).reshape((-1, 3, 5))
        xyz = vertices[:, :, :3]
        normals = np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])
        normal_length = np.linalg.norm(normals, axis=1)
        upward = np.abs(normals[:, 1]) / np.maximum(normal_length, 1e-8)
        centers = xyz.mean(axis=1)
        distance = _distance_to_corridor(centers[:, (0, 2)], centerline)
        selected = (upward >= 0.72) & (distance >= 4.5) & (distance <= 14.0)
        if not np.any(selected):
            continue
        uv = np.mod(vertices[selected, :, 3:5].mean(axis=1), 1.0)
        area = normal_length[selected] * 0.5
        histogram, u_edges, v_edges = np.histogram2d(
            uv[:, 0], uv[:, 1], bins=32, range=((0.0, 1.0), (0.0, 1.0)), weights=area
        )
        for flat_index in np.argsort(histogram.ravel())[::-1][:6]:
            score = float(histogram.ravel()[flat_index])
            if score <= 0.0:
                continue
            u_index, v_index = np.unravel_index(flat_index, histogram.shape)
            mask = (
                (uv[:, 0] >= u_edges[u_index])
                & (uv[:, 0] < u_edges[u_index + 1])
                & (uv[:, 1] >= v_edges[v_index])
                & (uv[:, 1] < v_edges[v_index + 1])
            )
            local_uv = uv[mask]
            ranked.append(
                {
                    "material": material,
                    "score": score,
                    "uv": [float(np.median(local_uv[:, 0])), float(np.median(local_uv[:, 1]))],
                    "samples": int(mask.sum()),
                }
            )

    ranked.sort(key=lambda item: float(item["score"]), reverse=True)
    chosen: list[dict[str, object]] = []
    for item in ranked:
        if any(
            item["material"] == previous["material"]
            and np.linalg.norm(np.asarray(item["uv"]) - np.asarray(previous["uv"])) < 0.08
            for previous in chosen
        ):
            continue
        chosen.append(item)
        if len(chosen) >= candidates:
            break

    tile_size = 512
    columns = 3
    rows = (len(chosen) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_size, rows * (tile_size + 40)), "#101820")
    draw = ImageDraw.Draw(sheet)
    crop_root = output.parent / f"{output.stem}_crops"
    crop_root.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(chosen):
        material = str(item["material"])
        source = texture_root / f"{material}_diffuse.jpg"
        with Image.open(source) as texture:
            crop = _wrapped_crop(texture, tuple(item["uv"]), crop_size)
        crop_path = crop_root / f"{index + 1:02d}_{material}.png"
        crop.save(crop_path)
        preview = crop.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_size
        y = (index // columns) * (tile_size + 40)
        sheet.paste(preview, (x, y + 40))
        draw.text(
            (x + 10, y + 12),
            f"{index + 1:02d} {material}  UV {item['uv'][0]:.3f}, {item['uv'][1]:.3f}",
            fill="white",
        )
        item["crop"] = str(crop_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    output.with_suffix(".json").write_text(
        json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return chosen


def main() -> None:
    """Run with Isaac Sim Python or an environment containing NumPy/Pillow."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--texture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates", type=int, default=12)
    parser.add_argument("--crop-size", type=int, default=1536)
    args = parser.parse_args()
    selected = extract_references(
        args.bundle,
        args.texture_root,
        args.output,
        candidates=args.candidates,
        crop_size=args.crop_size,
    )
    print(f"wrote {args.output} with {len(selected)} map-derived candidates")


if __name__ == "__main__":
    main()
