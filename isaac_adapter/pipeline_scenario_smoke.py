"""Build the demolition-site pipeline baseline without starting the backend.

This smoke test loads the purchased site, rebuilds the lightweight terrain
collision cache, creates the independent trench-fill sections, and exports a
small USDA inspection stage plus a JSON report under ``SITEGIT_DATA_ROOT``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

from dotenv import load_dotenv


ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv(ADAPTER_DIR / ".env", override=True)
if str(ADAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTER_DIR))


def main() -> None:
    """Create and validate the initial pipeline construction Stage."""

    from isaacsim.simulation_app import SimulationApp

    app = SimulationApp({"headless": True})
    output_root: Path | None = None
    try:
        import omni.usd
        from pxr import Usd, UsdGeom, UsdShade

        from pipeline_scenario import (
            PIPELINE_BACKFILL_TEXTURE_VERSION,
            create_pipeline_backfill,
        )
        from site_stage import default_site_asset, load_site, resolved_data_root
        from terrain_collision_proxy import (
            collision_proxy_height_sampler,
            create_terrain_collision_proxy,
            load_or_build_collision_proxy_data,
        )

        data_root = resolved_data_root()
        output_root = data_root / "isaac" / "pipeline-baseline-smoke"
        output_root.mkdir(parents=True, exist_ok=True)
        context = omni.usd.get_context()
        context.new_stage()
        stage = context.get_stage()
        site_asset = default_site_asset(data_root)
        if site_asset is None:
            raise FileNotFoundError("configured demolition-site asset is unavailable")

        site = load_site(stage, site_asset, simulation_app=app)
        source_material_shaders: list[dict[str, object]] = []
        for prim in stage.TraverseAll():
            if not prim.IsA(UsdShade.Shader):
                continue
            shader = UsdShade.Shader(prim)
            connections: dict[str, list[str]] = {}
            for shader_input in shader.GetInputs():
                try:
                    sources, _ = shader_input.GetConnectedSources()
                except (AttributeError, TypeError):
                    sources = []
                if sources:
                    connections[shader_input.GetBaseName()] = [
                        f"{source.source.GetPrim().GetPath()}.{source.sourceName}"
                        for source in sources
                    ]
            inputs = {
                value.GetBaseName(): str(value.Get())
                for value in shader.GetInputs()
                if value.Get() is not None
            }
            if "/Materials/tex_u2_v2/" not in str(prim.GetPath()):
                continue
            source_material_shaders.append(
                {
                    "path": str(prim.GetPath()),
                    "id": str(shader.GetIdAttr().Get()),
                    "inputs": inputs,
                    "connections": connections,
                }
            )
        collision = create_terrain_collision_proxy(
            stage,
            data_root,
            resolution_m=float(
                os.getenv("SITEGIT_TERRAIN_COLLISION_RESOLUTION_M", "2")
            ),
        )
        visual_height_cache = (
            data_root / "isaac" / "terrain_backfill_height_0_5m.npz"
        )
        visual_height_data, visual_height_cache_hit = load_or_build_collision_proxy_data(
            data_root / "isaac" / "site-work-map",
            visual_height_cache,
            resolution_m=float(
                os.getenv("SITEGIT_PIPELINE_HEIGHT_RESOLUTION_M", "0.5")
            ),
        )
        sampler = collision_proxy_height_sampler(visual_height_cache)
        backfill = create_pipeline_backfill(
            stage,
            surface_height=sampler,
            base_color_texture=os.getenv("SITEGIT_PIPELINE_SOIL_BASECOLOR") or None,
            normal_texture=os.getenv("SITEGIT_PIPELINE_SOIL_NORMAL") or None,
            update_callback=app.update,
        )

        # A restored approved Stage can contain the old atlas UVs. Exercise
        # the in-place migration path while preserving the existing geometry.
        first_section = stage.GetPrimAtPath(backfill["sections"][0]["prim_path"])
        first_section.SetCustomDataByKey("sitegitTerrainRevision", 1)
        first_section.SetCustomDataByKey(
            "sitegitBackfillTextureVersion",
            PIPELINE_BACKFILL_TEXTURE_VERSION - 1,
        )
        upgrade_probe = create_pipeline_backfill(
            stage,
            surface_height=sampler,
            base_color_texture=os.getenv("SITEGIT_PIPELINE_SOIL_BASECOLOR") or None,
            normal_texture=os.getenv("SITEGIT_PIPELINE_SOIL_NORMAL") or None,
        )
        if not upgrade_probe["sections"][0].get("texture_uv_upgraded"):
            raise RuntimeError("restored pipeline section UV migration did not run")

        bbox_cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
            useExtentsHint=True,
        )
        verified_sections: list[dict[str, object]] = []
        for section in backfill["sections"]:
            prim_path = str(section["prim_path"])
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
                raise RuntimeError(f"pipeline section is not a mesh: {prim_path}")
            aligned = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
            material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
            top_subset = stage.GetPrimAtPath(f"{prim_path}/TopSurface")
            if not top_subset.IsValid():
                raise RuntimeError(f"pipeline top material subset is missing: {prim_path}")
            top_material, _ = UsdShade.MaterialBindingAPI(
                top_subset
            ).ComputeBoundMaterial()
            if not top_material:
                raise RuntimeError(f"pipeline top material is missing: {prim_path}")
            verified_sections.append(
                {
                    "prim_path": prim_path,
                    "zone_id": prim.GetCustomDataByKey("sitegitZoneId"),
                    "bounds_min": [float(value) for value in aligned.GetMin()],
                    "bounds_max": [float(value) for value in aligned.GetMax()],
                    "material": str(material.GetPath()) if material else None,
                    "top_material": str(top_material.GetPath()),
                }
            )

        inspection_stage = output_root / "pipeline_baseline.usda"
        stage.GetRootLayer().Export(inspection_stage.as_posix())
        report = {
            "site": site,
            "source_material_shaders": source_material_shaders,
            "collision": collision,
            "pipeline_visual_height": {
                "cache_path": str(visual_height_cache),
                "cache_hit": visual_height_cache_hit,
                "resolution_m": visual_height_data["resolution_m"],
                "valid_cell_count": visual_height_data["valid_cell_count"],
            },
            "pipeline": backfill,
            "restored_stage_uv_upgrade": upgrade_probe["sections"][0],
            "verified_sections": verified_sections,
            "inspection_stage": str(inspection_stage),
        }
        (output_root / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_root / "failure.txt").unlink(missing_ok=True)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception:
        if output_root is None:
            output_root = REPO_ROOT / "runtime" / "pipeline-baseline-smoke"
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "failure.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        raise
    finally:
        # A one-shot smoke test does not need the full Replicator/cache drain;
        # immediate shutdown avoids minutes of USDZ texture-cache cleanup.
        app.close(wait_for_replicator=False, skip_cleanup=True)


if __name__ == "__main__":
    main()
