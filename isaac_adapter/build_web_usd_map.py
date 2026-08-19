"""Export the exact USDZ mesh, UVs and material tiles for SiteGit WebGL.

Unlike the legacy OBJ converter, this exporter reads the same USD geometry and
``st0`` primvar that Isaac Sim renders.  It therefore preserves mesh splits,
per-vertex UVs and material bindings instead of trying to reconstruct them from
an adjacent OBJ delivery.

Run this module with Isaac Sim's ``python.bat``.
"""

from __future__ import annotations

import argparse
from array import array
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any
import zipfile

from isaacsim.simulation_app import SimulationApp


SUPPORTED_FORMAT = "sitegit-web-mesh-v1"


def _extract_usdz(source: Path, temporary_root: Path) -> tuple[Path, Path]:
    """Extract a USDZ and return its root layer plus extraction directory."""

    with zipfile.ZipFile(source) as archive:
        archive.extractall(temporary_root)
    layers = sorted(
        list(temporary_root.rglob("*.usdc"))
        + list(temporary_root.rglob("*.usd"))
        + list(temporary_root.rglob("*.usda")),
        key=lambda item: (len(item.parts), item.name.lower()),
    )
    if not layers:
        raise ValueError(f"USDZ contains no USD root layer: {source}")
    return layers[0], temporary_root


def _material_texture_paths(stage: Any, source_root: Path) -> dict[str, Path]:
    """Resolve each bound USD material to its authored base-color image."""

    from pxr import Usd, UsdShade

    result: dict[str, Path] = {}
    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Material):
            continue
        material_path = str(prim.GetPath())
        for child in Usd.PrimRange(prim):
            if child == prim or not child.IsA(UsdShade.Shader):
                continue
            shader = UsdShade.Shader(child)
            if str(shader.GetIdAttr().Get() or "") != "UsdUVTexture":
                continue
            file_input = shader.GetInput("file")
            asset = file_input.Get() if file_input else None
            relative = str(getattr(asset, "path", asset) or "")
            if not relative:
                continue
            candidate = (source_root / relative.replace("/", "\\")).resolve()
            if candidate.is_file():
                result[material_path] = candidate
                break
    return result


def _uv_at(
    values: Any,
    indices: Any,
    interpolation: str,
    *,
    point_index: int,
    face_index: int,
    face_vertex_index: int,
) -> tuple[float, float]:
    """Read a USD primvar value for one triangle corner."""

    if interpolation in {"vertex", "varying"}:
        logical_index = point_index
    elif interpolation == "uniform":
        logical_index = face_index
    elif interpolation == "constant":
        logical_index = 0
    else:
        logical_index = face_vertex_index
    value_index = int(indices[logical_index]) if indices else logical_index
    if value_index < 0 or value_index >= len(values):
        return (0.0, 0.0)
    value = values[value_index]
    return (float(value[0]), float(value[1]))


def export_bundle(
    source: Path,
    output: Path,
    *,
    texture_max_size: int,
) -> Path:
    """Export one USDZ/USDC asset into SiteGit's browser mesh bundle."""

    from PIL import Image
    from pxr import Gf, Usd, UsdGeom, UsdShade

    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=True)

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if source.suffix.lower() == ".usdz":
        temporary = tempfile.TemporaryDirectory(prefix="sitegit-usdz-", dir=str(output.parent))
        layer, source_root = _extract_usdz(source, Path(temporary.name))
    else:
        layer, source_root = source, source.parent

    try:
        stage = Usd.Stage.Open(str(layer), load=Usd.Stage.LoadAll)
        if stage is None:
            raise RuntimeError(f"Unable to open USD layer: {layer}")
        meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
        xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        texture_by_material = _material_texture_paths(stage, source_root)

        groups: dict[str, array] = {}
        material_paths: dict[str, str] = {}
        minimum = [math.inf, math.inf, math.inf]
        maximum = [-math.inf, -math.inf, -math.inf]
        triangle_count = 0

        for prim in stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh) or not prim.IsActive():
                continue
            mesh = UsdGeom.Mesh(prim)
            points = mesh.GetPointsAttr().Get(Usd.TimeCode.Default()) or []
            counts = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.Default()) or []
            face_indices = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.Default()) or []
            if not points or not counts or not face_indices:
                continue

            material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
            material_path = str(material.GetPath()) if material else "default"
            material_name = material_path.rsplit("/", 1)[-1] or "default"
            material_paths[material_name] = material_path
            vertices = groups.setdefault(material_name, array("f"))

            primvars = UsdGeom.PrimvarsAPI(prim)
            uv = primvars.GetPrimvar("st0")
            if not uv or not uv.HasValue():
                uv = primvars.GetPrimvar("st")
            uv_values = uv.Get(Usd.TimeCode.Default()) if uv and uv.HasValue() else []
            uv_indices = uv.GetIndices(Usd.TimeCode.Default()) if uv and uv.IsIndexed() else []
            interpolation = str(uv.GetInterpolation()) if uv and uv.HasValue() else "constant"
            matrix = xform_cache.GetLocalToWorldTransform(prim)
            world_points = []
            for point in points:
                transformed = matrix.Transform(Gf.Vec3d(point))
                world_points.append(
                    (
                        float(transformed[0]) * meters_per_unit,
                        float(transformed[1]) * meters_per_unit,
                        float(transformed[2]) * meters_per_unit,
                    )
                )

            offset = 0
            for face_number, raw_count in enumerate(counts):
                count = int(raw_count)
                face = [int(value) for value in face_indices[offset : offset + count]]
                if count >= 3:
                    for fan_index in range(1, count - 1):
                        for local_corner in (0, fan_index, fan_index + 1):
                            point_index = face[local_corner]
                            x, y, z = world_points[point_index]
                            u, v = _uv_at(
                                uv_values,
                                uv_indices,
                                interpolation,
                                point_index=point_index,
                                face_index=face_number,
                                face_vertex_index=offset + local_corner,
                            )
                            vertices.extend((x, y, z, u, v))
                            for axis, value in enumerate((x, y, z)):
                                minimum[axis] = min(minimum[axis], value)
                                maximum[axis] = max(maximum[axis], value)
                        triangle_count += 1
                offset += count

        manifest_groups: list[dict[str, object]] = []
        for material_name, values in groups.items():
            geometry_name = f"{material_name}.bin"
            with (output / geometry_name).open("wb") as stream:
                if sys.byteorder != "little":
                    values.byteswap()
                values.tofile(stream)

            texture_name: str | None = None
            texture_source = texture_by_material.get(material_paths[material_name])
            if texture_source and texture_source.is_file():
                texture_name = f"{material_name}_baseColor.jpg"
                with Image.open(texture_source) as image:
                    image.thumbnail(
                        (texture_max_size, texture_max_size),
                        Image.Resampling.LANCZOS,
                    )
                    image.convert("RGB").save(
                        output / texture_name,
                        "JPEG",
                        quality=88,
                        optimize=True,
                    )
            manifest_groups.append(
                {
                    "material": material_name,
                    "geometry": geometry_name,
                    "texture": texture_name,
                    "vertex_count": len(values) // 5,
                }
            )

        if not manifest_groups or triangle_count <= 0:
            raise ValueError(f"USD contains no renderable mesh: {source}")
        manifest = {
            "format": SUPPORTED_FORMAT,
            "exporter": "isaac_adapter.build_web_usd_map",
            "source": str(source),
            "source_up_axis": str(UsdGeom.GetStageUpAxis(stage)),
            "source_meters_per_unit": meters_per_unit,
            "texture_flip_y": True,
            "triangle_count": triangle_count,
            "bounds": {"min": minimum, "max": maximum},
            "groups": manifest_groups,
        }
        temporary_manifest = output / "manifest.json.tmp"
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_manifest.replace(output / "manifest.json")
        return output
    finally:
        if temporary is not None:
            temporary.cleanup()


def main() -> None:
    """Run the USD exporter using Isaac Sim's Python environment."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--texture-max-size", type=int, default=2048)
    args = parser.parse_args()

    app = SimulationApp({"headless": True})
    try:
        target = export_bundle(
            args.source,
            args.output,
            texture_max_size=args.texture_max_size,
        )
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        print(f"SiteGit USD web map generated: {target}")
        print(f"Triangles: {manifest['triangle_count']:,}")
        print(f"Materials: {len(manifest['groups'])}")
    finally:
        app.close(wait_for_replicator=False)


if __name__ == "__main__":
    main()
