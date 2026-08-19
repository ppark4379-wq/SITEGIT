"""Initial diggable backfill for the demolition-site pipeline scenario.

The purchased photogrammetry map already contains a long excavated corridor.
SiteGit keeps that source mesh immutable and places several small, independent
soil volumes over the corridor.  Each section stays below the Work Package
size limit and can therefore be excavated, reviewed and merged separately.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Callable


PIPELINE_ROOT_PATH = "/World/Diggable/Pipeline"
PIPELINE_MATERIAL_PATH = "/World/Looks/DemolitionSoil"
PIPELINE_VOLUME_MATERIAL_PATH = "/World/Looks/DemolitionSoilVolume"
PIPELINE_BACKFILL_TEXTURE_VERSION = 12

# The runtime texture is a deterministic dirt-only crop from the purchased
# map's ``tex_u2_v2`` diffuse/normal pair.  It no longer contains unrelated
# atlas islands, so generated soil can safely consume the whole image.
DEMOLITION_SOIL_TILE_UV_BOUNDS = (0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class TrenchStation:
    """One centerline station in normalized SiteGit site coordinates."""

    x: float
    y: float
    width: float
    surface_blend: float = 1.0


# Derived from the actual construction-site-demolition OBJ height field.  The
# original trench runs diagonally from Zone A into Zone C and widens at its
# southern end.  Values are metres after site_stage.load_site normalization.
DEFAULT_TRENCH_STATIONS = (
    # Both terminal profiles sit on intact ground beyond the photographed
    # excavation. Keeping the real trench width here (instead of pinching it
    # to a point) closes the two end voids; ``surface_blend=0`` makes the cap
    # follow the surrounding terrain rather than exposing a soil wall.
    TrenchStation(-7.0, -46.0, 10.0, 0.0),
    TrenchStation(-6.0, -30.0, 8.0),
    TrenchStation(-8.5, -22.0, 8.5),
    TrenchStation(-10.5, -14.0, 9.0),
    TrenchStation(-12.5, -6.0, 10.0),
    TrenchStation(-14.5, 2.0, 11.0),
    TrenchStation(-16.0, 10.0, 12.0),
    TrenchStation(-14.0, 18.0, 18.0),
    TrenchStation(-7.5, 30.0, 18.0, 0.0),
)


def trench_section_spans(
    stations: tuple[TrenchStation, ...] = DEFAULT_TRENCH_STATIONS,
) -> list[float]:
    """Return the maximum plan span of every default work section."""

    return [
        max(math.hypot(b.x - a.x, b.y - a.y), a.width, b.width)
        for a, b in zip(stations, stations[1:])
    ]


def _soil_material(
    stage: Any,
    *,
    base_color_texture: Path | None,
    normal_texture: Path | None,
) -> Any | None:
    """Create soil using the same shading model as the purchased site mesh.

    The converted USDZ has a converter-specific emissive material, while a
    newly-authored copy of that graph can resolve to black in RTX.  Use the
    portable diffuse path instead, but attenuate the linear texture output for
    Isaac's Stage Lights and leave the absent source normal map disconnected.
    """

    if base_color_texture is None or not base_color_texture.is_file():
        return None

    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(stage, Sdf.Path(PIPELINE_MATERIAL_PATH))
    surface = UsdShade.Shader.Define(
        stage, Sdf.Path(f"{PIPELINE_MATERIAL_PATH}/PreviewSurface")
    )
    surface.CreateIdAttr("UsdPreviewSurface")
    diffuse = surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)
    surface.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

    primvar = UsdShade.Shader.Define(
        stage, Sdf.Path(f"{PIPELINE_MATERIAL_PATH}/UVReader")
    )
    primvar.CreateIdAttr("UsdPrimvarReader_float2")
    primvar.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
    primvar.CreateOutput("result", Sdf.ValueTypeNames.Float2)

    color = UsdShade.Shader.Define(
        stage, Sdf.Path(f"{PIPELINE_MATERIAL_PATH}/BaseColorTexture")
    )
    color.CreateIdAttr("UsdUVTexture")
    color.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath(base_color_texture.resolve().as_posix())
    )
    color.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
    color.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
    color.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
    color.CreateInput("scale", Sdf.ValueTypeNames.Float4).Set(
        Gf.Vec4f(0.44, 0.41, 0.36, 1.0)
    )
    color.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
        primvar.ConnectableAPI(), "result"
    )
    color.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    diffuse.ConnectToSource(
        color.ConnectableAPI(), "rgb"
    )
    emissive = surface.GetInput("emissiveColor")
    if emissive and emissive.GetAttr().IsValid():
        emissive.DisconnectSource()
        emissive.Set(Gf.Vec3f(0.0, 0.0, 0.0))

    # Keep the extracted normal file for future PBR terrain, but deliberately
    # do not connect it here: the purchased USDZ uses base color only.
    _ = normal_texture
    normal_input = surface.GetInput("normal")
    if normal_input and normal_input.GetAttr().IsValid():
        normal_input.DisconnectSource()
        normal_input.Set(Gf.Vec3f(0.0, 0.0, 1.0))
    stale_normal_path = Sdf.Path(f"{PIPELINE_MATERIAL_PATH}/NormalTexture")
    if stage.GetPrimAtPath(stale_normal_path).IsValid():
        stage.RemovePrim(stale_normal_path)

    material.CreateSurfaceOutput().ConnectToSource(
        surface.ConnectableAPI(), "surface"
    )
    return material


def _soil_volume_material(stage: Any) -> Any:
    """Create the untextured material used below the visible soil surface.

    The photogrammetry atlas belongs only on the horizontal surface. Applying
    it to the walls and floor makes a filled trench look like a wrapped board,
    especially after an excavation exposes the interior.
    """

    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(
        stage, Sdf.Path(PIPELINE_VOLUME_MATERIAL_PATH)
    )
    surface = UsdShade.Shader.Define(
        stage, Sdf.Path(f"{PIPELINE_VOLUME_MATERIAL_PATH}/PreviewSurface")
    )
    surface.CreateIdAttr("UsdPreviewSurface")
    surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.30, 0.23, 0.16)
    )
    surface.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.96)
    surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    material.CreateSurfaceOutput().ConnectToSource(
        surface.ConnectableAPI(), "surface"
    )
    return material


def _sample_height(
    sampler: Callable[[float, float, float], float],
    x: float,
    y: float,
    fallback: float,
) -> float:
    value = float(sampler(float(x), float(y), float(fallback)))
    return value if math.isfinite(value) else float(fallback)


def _station_profiles(
    stations: tuple[TrenchStation, ...],
    surface_height: Callable[[float, float, float], float],
    *,
    columns: int,
    texture_scale_m: float,
) -> list[dict[str, Any]]:
    """Sample shared, bank-to-bank cross sections for all work sections."""

    profiles: list[dict[str, Any]] = []
    for index, station in enumerate(stations):
        previous = stations[max(0, index - 1)]
        following = stations[min(len(stations) - 1, index + 1)]
        tangent_x = following.x - previous.x
        tangent_y = following.y - previous.y
        tangent_length = math.hypot(tangent_x, tangent_y)
        if tangent_length <= 1e-6:
            raise ValueError("pipeline fill stations must not overlap")
        right_x = tangent_y / tangent_length
        right_y = -tangent_x / tangent_length
        # Sample intact grade beyond the fill's feathered overlap instead of
        # accidentally deriving the target height from the trench wall.
        bank_overlap = 1.20
        outside = station.width * 0.5 + bank_overlap + 0.50
        left_grade = _sample_height(
            surface_height,
            station.x - right_x * outside,
            station.y - right_y * outside,
            4.5,
        )
        right_grade = _sample_height(
            surface_height,
            station.x + right_x * outside,
            station.y + right_y * outside,
            left_grade,
        )
        points: list[tuple[float, float, float]] = []
        floors: list[float] = []
        uvs: list[tuple[float, float]] = []
        for column in range(columns):
            fraction = column / (columns - 1)
            across = fraction - 0.5
            # Extend onto both photographed banks. The outer vertex bands are
            # feathered back to the sampled ground so the closed volume's side
            # walls stay below the original terrain mesh.
            effective_width = station.width + bank_overlap * 2.0
            x = station.x + right_x * effective_width * across
            y = station.y + right_y * effective_width * across
            floor = _sample_height(
                surface_height,
                x,
                y,
                (left_grade + right_grade) * 0.5 - 2.0,
            )
            bank_height = left_grade * (1.0 - fraction) + right_grade * fraction
            surface_blend = max(0.0, min(1.0, float(station.surface_blend)))
            edge_fade = math.sin(math.pi * fraction)
            crown = 0.16 * edge_fade * surface_blend
            roughness = edge_fade * surface_blend * (
                0.055 * math.sin(x * 0.71 + y * 0.37)
                + 0.035 * math.cos(x * 0.29 - y * 0.83)
            )
            target_top = floor + (bank_height - floor) * surface_blend
            clearance = 0.03 + 0.09 * surface_blend
            filled_top = max(
                target_top - 0.04 * surface_blend + crown + roughness,
                floor + clearance,
            )
            edge_distance = min(fraction, 1.0 - fraction)
            feather = max(0.0, min(1.0, edge_distance / 0.18))
            feather = feather * feather * (3.0 - 2.0 * feather)
            embedded_grade = floor - 0.015
            top = embedded_grade + (filled_top - embedded_grade) * feather
            points.append((x, y, top))
            floors.append(floor)
            uvs.append((x / texture_scale_m, y / texture_scale_m))
        profiles.append({"points": points, "floors": floors, "uvs": uvs})
    return profiles


def _section_mesh_data(
    start_profile: dict[str, Any],
    end_profile: dict[str, Any],
    surface_height: Callable[[float, float, float], float],
    *,
    rows: int = 11,
    columns: int = 13,
    texture_scale_m: float = 8.0,
    atlas_uv_bounds: tuple[float, float, float, float] = DEMOLITION_SOIL_TILE_UV_BOUNDS,
    uv_along_start: float = 0.0,
    uv_along_end: float = 1.0,
) -> dict[str, Any]:
    """Build a dense soil volume whose neighboring sections share edges."""

    if rows < 2 or columns < 2:
        raise ValueError("pipeline fill mesh requires at least a 2x2 top grid")
    if len(start_profile["points"]) != columns or len(end_profile["points"]) != columns:
        raise ValueError("pipeline station profile resolution does not match")

    del texture_scale_m  # Retained in the private API for older callers.
    u_min, v_min, u_max, v_max = atlas_uv_bounds
    if not (0.0 <= u_min < u_max <= 1.0 and 0.0 <= v_min < v_max <= 1.0):
        raise ValueError("pipeline atlas UV bounds must be inside the 0..1 range")

    top_points: list[tuple[float, float, float]] = []
    top_uvs: list[tuple[float, float]] = []
    floor_samples: list[float] = []
    for row in range(rows):
        along = row / (rows - 1)
        for column in range(columns):
            across = column / (columns - 1)
            start_point = start_profile["points"][column]
            end_point = end_profile["points"][column]
            x = start_point[0] * (1.0 - along) + end_point[0] * along
            y = start_point[1] * (1.0 - along) + end_point[1] * along
            interpolated_top = start_point[2] * (1.0 - along) + end_point[2] * along
            floor = _sample_height(
                surface_height,
                x,
                y,
                interpolated_top - 2.0,
            )
            interior_fade = math.sin(math.pi * along) * math.sin(math.pi * across)
            top = max(
                interpolated_top
                + interior_fade
                * (
                    0.035 * math.sin(x * 0.91 + y * 0.43)
                    + 0.02 * math.cos(x * 0.37 - y * 0.67)
                ),
                # Nearly coplanar boundary profiles avoid the 12 cm dark rim
                # while leaving a small, valid closed-mesh thickness.
                floor + 0.025,
            )
            top_points.append((x, y, top))
            atlas_along = uv_along_start * (1.0 - along) + uv_along_end * along
            top_uvs.append(
                (
                    u_min + (u_max - u_min) * across,
                    v_min + (v_max - v_min) * atlas_along,
                )
            )
            floor_samples.append(floor)

    points = list(top_points)
    uvs = list(top_uvs)
    counts: list[int] = []
    indices: list[int] = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            b = a + 1
            c = a + columns
            d = c + 1
            indices.extend((a, c, d, a, d, b))
            counts.extend((3, 3))

    top_vertex_count = len(top_points)
    top_face_count = len(counts)

    # Build a complete lower grid that follows the photographed trench floor.
    # The earlier implementation lowered only the perimeter by 2.5 cm, which
    # produced a thin lid instead of excavatable soil filling the void.
    bottom_offset = len(points)
    for top_index, (x, y, top_z) in enumerate(top_points):
        floor_z = float(floor_samples[top_index]) - 0.035
        bottom_z = min(top_z - 0.055, floor_z)
        points.append((x, y, bottom_z))
        # These UVs are not visible because the lower faces use a solid soil
        # material, but keeping the vertex arrays aligned simplifies exports.
        uvs.append(top_uvs[top_index])

    # Close the underside. Reversed winding keeps the outward normal facing
    # down while the surface grid above faces up.
    for row in range(rows - 1):
        for column in range(columns - 1):
            a = bottom_offset + row * columns + column
            b = a + 1
            c = a + columns
            d = c + 1
            indices.extend((a, d, c, a, b, d))
            counts.extend((3, 3))

    boundary = list(range(columns))
    boundary.extend(row * columns + columns - 1 for row in range(1, rows))
    boundary.extend(
        (rows - 1) * columns + column
        for column in range(columns - 2, -1, -1)
    )
    boundary.extend(row * columns for row in range(rows - 2, 0, -1))
    for index, top_index in enumerate(boundary):
        following = (index + 1) % len(boundary)
        bottom_index = bottom_offset + top_index
        bottom_following = bottom_offset + boundary[following]
        indices.extend(
            (
                top_index,
                bottom_index,
                bottom_following,
                top_index,
                bottom_following,
                boundary[following],
            )
        )
        counts.extend((3, 3))

    return {
        "points": points,
        "uvs": uvs,
        "face_vertex_counts": counts,
        "face_vertex_indices": indices,
        "top_vertex_count": top_vertex_count,
        "top_face_count": top_face_count,
        "base_z": min(point[2] for point in points[top_vertex_count:]),
        "top_z": max(point[2] for point in top_points),
    }


def create_pipeline_backfill(
    stage: Any,
    *,
    surface_height: Callable[[float, float, float], float],
    base_color_texture: str | Path | None = None,
    normal_texture: str | Path | None = None,
    stations: tuple[TrenchStation, ...] = DEFAULT_TRENCH_STATIONS,
    update_callback: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Create the initial filled-soil sections over the photographed trench."""

    if len(stations) < 2:
        raise ValueError("pipeline scenario requires at least two trench stations")
    if any(span > 25.0 for span in trench_section_spans(stations)):
        raise ValueError("each pipeline fill section must stay within 25 metres")

    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

    UsdGeom.Xform.Define(stage, Sdf.Path("/World/Diggable"))
    UsdGeom.Xform.Define(stage, Sdf.Path(PIPELINE_ROOT_PATH))
    UsdGeom.Scope.Define(stage, Sdf.Path("/World/Looks"))
    surface_material = _soil_material(
        stage,
        base_color_texture=Path(base_color_texture).expanduser()
        if base_color_texture
        else None,
        normal_texture=Path(normal_texture).expanduser() if normal_texture else None,
    )
    volume_material = _soil_volume_material(stage)

    columns = 13
    profiles = _station_profiles(
        stations,
        surface_height,
        columns=columns,
        texture_scale_m=8.0,
    )
    sections: list[dict[str, Any]] = []
    for section_index, (start, end) in enumerate(zip(stations, stations[1:]), 1):
        prim_path = f"{PIPELINE_ROOT_PATH}/TrenchFill_{section_index:02d}"
        # Map the complete dirt-only tile to every work section. Alternating
        # the along direction reduces obvious repetition between neighbours.
        reverse_texture = section_index % 2 == 0
        data = _section_mesh_data(
            profiles[section_index - 1],
            profiles[section_index],
            surface_height,
            rows=11,
            columns=columns,
            texture_scale_m=8.0,
            atlas_uv_bounds=DEMOLITION_SOIL_TILE_UV_BOUNDS,
            uv_along_start=1.0 if reverse_texture else 0.0,
            uv_along_end=0.0 if reverse_texture else 1.0,
        )
        existing = stage.GetPrimAtPath(prim_path)
        if existing.IsValid():
            texture_upgraded = False
            current_version = existing.GetCustomDataByKey(
                "sitegitBackfillTextureVersion"
            )
            terrain_revision = int(
                existing.GetCustomDataByKey("sitegitTerrainRevision") or 0
            )
            if (
                current_version != PIPELINE_BACKFILL_TEXTURE_VERSION
                and terrain_revision == 0
            ):
                # Replace untouched baseline geometry when the route/feather
                # policy changes. A sculpted commit has a positive revision
                # and must retain its approved point positions.
                stage.RemovePrim(Sdf.Path(prim_path))
                existing = stage.GetPrimAtPath(prim_path)
            if existing.IsValid():
                current_points = UsdGeom.Mesh(existing).GetPointsAttr().Get() or []
                if (
                    current_version != PIPELINE_BACKFILL_TEXTURE_VERSION
                    and len(current_points) == len(data["uvs"])
                ):
                    # Approved stages may contain already-sculpted versions of
                    # these meshes. Preserve their points and topology, and only
                    # replace the stale atlas UVs/material binding in-place.
                    mesh = UsdGeom.Mesh(existing)
                    primvars = UsdGeom.PrimvarsAPI(mesh)
                    st = primvars.GetPrimvar("st")
                    if not st.IsDefined():
                        st = primvars.CreatePrimvar(
                            "st",
                            Sdf.ValueTypeNames.TexCoord2fArray,
                            UsdGeom.Tokens.vertex,
                        )
                    st.SetInterpolation(UsdGeom.Tokens.vertex)
                    st.Set(
                        [Gf.Vec2f(float(u), float(v)) for u, v in data["uvs"]]
                    )
                    indices_attr = st.GetIndicesAttr()
                    if indices_attr.IsValid():
                        indices_attr.Clear()
                    UsdShade.MaterialBindingAPI.Apply(existing).Bind(volume_material)
                    if surface_material is not None:
                        top_subset = UsdGeom.Subset.Define(
                            stage, Sdf.Path(f"{prim_path}/TopSurface")
                        )
                        top_subset.CreateElementTypeAttr().Set(UsdGeom.Tokens.face)
                        top_subset.CreateFamilyNameAttr().Set("materialBind")
                        top_subset.CreateIndicesAttr().Set(
                            list(range(data["top_face_count"]))
                        )
                        UsdShade.MaterialBindingAPI.Apply(top_subset.GetPrim()).Bind(
                            surface_material
                        )
                    existing.SetCustomDataByKey(
                        "sitegitBackfillTextureVersion",
                        PIPELINE_BACKFILL_TEXTURE_VERSION,
                    )
                    existing.SetCustomDataByKey(
                        "sitegitMaterialSource",
                        "construction-site-demolition/source/model/tex_u2_v2_diffuse.jpg"
                        "#dirt-only-crop-uv-0.38-0.67",
                    )
                    texture_upgraded = True
                sections.append(
                    {
                        "prim_path": prim_path,
                        "existing": True,
                        "texture_uv_upgraded": texture_upgraded,
                        "texture_uv_version": current_version
                        if not texture_upgraded
                        else PIPELINE_BACKFILL_TEXTURE_VERSION,
                    }
                )
                continue
        mesh = UsdGeom.Mesh.Define(stage, Sdf.Path(prim_path))
        mesh.CreatePointsAttr(
            [Gf.Vec3f(*[float(value) for value in point]) for point in data["points"]]
        )
        mesh.CreateFaceVertexCountsAttr(data["face_vertex_counts"])
        mesh.CreateFaceVertexIndicesAttr(data["face_vertex_indices"])
        mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
        mesh.CreateDoubleSidedAttr().Set(True)
        mesh.CreateDisplayColorAttr([Gf.Vec3f(0.48, 0.42, 0.33)])
        minimum = [min(point[axis] for point in data["points"]) for axis in range(3)]
        maximum = [max(point[axis] for point in data["points"]) for axis in range(3)]
        mesh.CreateExtentAttr(
            [
                Gf.Vec3f(*[float(value) for value in minimum]),
                Gf.Vec3f(*[float(value) for value in maximum]),
            ]
        )
        primvars = UsdGeom.PrimvarsAPI(mesh)
        st = primvars.CreatePrimvar(
            "st",
            Sdf.ValueTypeNames.TexCoord2fArray,
            UsdGeom.Tokens.vertex,
        )
        st.Set([Gf.Vec2f(float(u), float(v)) for u, v in data["uvs"]])
        # The mesh-level binding colors the buried volume. A face subset
        # overrides only the visible top grid with the original map texture.
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(volume_material)
        if surface_material is not None:
            top_subset = UsdGeom.Subset.Define(
                stage, Sdf.Path(f"{prim_path}/TopSurface")
            )
            top_subset.CreateElementTypeAttr().Set(UsdGeom.Tokens.face)
            top_subset.CreateFamilyNameAttr().Set("materialBind")
            top_subset.CreateIndicesAttr().Set(list(range(data["top_face_count"])))
            UsdShade.MaterialBindingAPI.Apply(top_subset.GetPrim()).Bind(
                surface_material
            )
        collision = UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        collision.CreateCollisionEnabledAttr().Set(True)
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr().Set("none")

        midpoint_y = (start.y + end.y) * 0.5
        zone_id = "A" if midpoint_y < 0 else "C"
        prim = mesh.GetPrim()
        prim.SetCustomDataByKey("sitegitDiggable", True)
        prim.SetCustomDataByKey(
            "sitegitDiggableId", f"Pipeline-TrenchFill-{section_index:02d}"
        )
        prim.SetCustomDataByKey("sitegitZoneId", zone_id)
        prim.SetCustomDataByKey("sitegitDisplayColor", "#7A6B54")
        prim.SetCustomDataByKey(
            "sitegitMaterialSource",
            "construction-site-demolition/source/model/tex_u2_v2_diffuse.jpg"
            "#dirt-only-crop-uv-0.38-0.67",
        )
        prim.SetCustomDataByKey("sitegitScenarioRole", "pipeline_initial_backfill")
        prim.SetCustomDataByKey("sitegitPipelineOrder", section_index)
        prim.SetCustomDataByKey("sitegitTopVertexCount", data["top_vertex_count"])
        prim.SetCustomDataByKey("sitegitTopFaceCount", data["top_face_count"])
        prim.SetCustomDataByKey(
            "sitegitBackfillTextureVersion", PIPELINE_BACKFILL_TEXTURE_VERSION
        )
        sections.append(
            {
                "prim_path": prim_path,
                "zone_id": zone_id,
                "base_z": float(data["base_z"]),
                "top_z": float(data["top_z"]),
                "size": [maximum[i] - minimum[i] for i in range(3)],
                "existing": False,
            }
        )

    if update_callback is not None:
        for _ in range(10):
            update_callback()
    return {
        "root_prim_path": PIPELINE_ROOT_PATH,
        "section_count": len(sections),
        "sections": sections,
        "material_path": PIPELINE_MATERIAL_PATH if surface_material is not None else None,
        "volume_material_path": PIPELINE_VOLUME_MATERIAL_PATH,
    }
