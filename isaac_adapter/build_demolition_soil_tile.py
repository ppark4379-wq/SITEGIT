"""Extract a dirt-only material tile from the purchased demolition map.

RealityCapture packs soil, buildings, roads and debris into the same 8K
atlases.  Sampling those atlases directly on a generated backfill mesh can
therefore expose unrelated islands when an importer changes the texture-V
convention.  This helper deterministically crops a verified dirt-only region
from ``tex_u2_v2`` and applies the identical crop to its normal map.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


SOURCE_MATERIAL = "tex_u2_v2"
SOURCE_UV_CENTER = (0.38, 0.67)
OUTPUT_SIZE = (640, 512)


def crop_bounds(image_size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Return the verified crop in top-left-origin image coordinates."""

    width, height = image_size
    center_x = round(SOURCE_UV_CENTER[0] * width)
    center_y = round((1.0 - SOURCE_UV_CENTER[1]) * height)
    half_width = OUTPUT_SIZE[0] // 2
    half_height = OUTPUT_SIZE[1] // 2
    return (
        center_x - half_width,
        center_y - half_height,
        center_x + half_width,
        center_y + half_height,
    )


def build_soil_tile(source_root: Path, output_root: Path) -> dict[str, object]:
    """Crop the original diffuse/normal pair without synthesizing pixels."""

    resolved_source = source_root.expanduser().resolve()
    resolved_output = output_root.expanduser().resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)
    diffuse_source = resolved_source / f"{SOURCE_MATERIAL}_diffuse.jpg"
    normal_source = resolved_source / f"{SOURCE_MATERIAL}_normal.jpg"
    if not diffuse_source.is_file() or not normal_source.is_file():
        raise FileNotFoundError(
            f"source texture pair is unavailable under {resolved_source}"
        )

    outputs: dict[str, str] = {}
    bounds: tuple[int, int, int, int] | None = None
    for kind, source in (("diffuse", diffuse_source), ("normal", normal_source)):
        with Image.open(source) as image:
            current_bounds = crop_bounds(image.size)
            bounds = current_bounds if bounds is None else bounds
            tile = image.convert("RGB").crop(current_bounds)
            destination = resolved_output / f"demolition_soil_tile_{kind}.jpg"
            tile.save(destination, "JPEG", quality=95, optimize=True)
            outputs[kind] = str(destination)

    report: dict[str, object] = {
        "source_material": SOURCE_MATERIAL,
        "source_uv_center": list(SOURCE_UV_CENTER),
        "source_pixel_bounds": list(bounds or ()),
        "output_size": list(OUTPUT_SIZE),
        "pixel_policy": "original-map-crop-only",
        "outputs": outputs,
    }
    (resolved_output / "demolition_soil_tile.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    """Build the tile into a selected workspace or runtime directory."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            build_soil_tile(args.source_root, args.output_root),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
