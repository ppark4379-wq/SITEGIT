"""Print the root and notable Prim paths of a USD asset.

Run this helper with Isaac Sim's Python so the bundled USD version is used::

    E:\\isaacsim\\python.bat isaac_adapter\\inspect_usd_asset.py ASSET.usd
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, help="검사 결과를 JSON으로 저장")
    parser.add_argument(
        "--verify-equipment",
        action="store_true",
        help="첫 에셋을 SiteGit 장비 경로에 합성하고 ArmDig 재생까지 검증",
    )
    args = parser.parse_args()

    from isaacsim.simulation_app import SimulationApp

    simulation_app = SimulationApp({"headless": True})
    try:
        from pxr import Usd

        reports: list[dict[str, object]] = []
        for asset in args.assets:
            stage = Usd.Stage.Open(str(asset.resolve()), load=Usd.Stage.LoadAll)
            if stage is None:
                print(f"\n[열기 실패] {asset}")
                continue
            default_prim = stage.GetDefaultPrim()
            roots = [
                {"path": str(prim.GetPath()), "type": prim.GetTypeName() or "Prim"}
                for prim in stage.GetPseudoRoot().GetChildren()
            ]
            notable = []
            for prim in stage.TraverseAll():
                path = str(prim.GetPath())
                lowered = path.lower()
                if any(
                    keyword in lowered
                    for keyword in ("lidar", "sensor", "armature", "skeleton", "animation")
                ):
                    variants = {}
                    variant_sets = prim.GetVariantSets()
                    for set_name in variant_sets.GetNames():
                        variant_set = variant_sets.GetVariantSet(set_name)
                        variants[set_name] = {
                            "selection": variant_set.GetVariantSelection(),
                            "options": variant_set.GetVariantNames(),
                        }
                    relationships = {
                        relationship.GetName(): [str(target) for target in relationship.GetTargets()]
                        for relationship in prim.GetRelationships()
                        if "skel" in relationship.GetName().lower()
                        or "anim" in relationship.GetName().lower()
                    }
                    time_samples = sorted(
                        {
                            sample
                            for attribute in prim.GetAttributes()
                            for sample in attribute.GetTimeSamples()
                        }
                    )
                    notable.append(
                        {
                            "path": path,
                            "type": prim.GetTypeName() or "Prim",
                            "variants": variants,
                            "relationships": relationships,
                            "time_samples": {
                                "count": len(time_samples),
                                "start": time_samples[0] if time_samples else None,
                                "end": time_samples[-1] if time_samples else None,
                            },
                        }
                    )
            reports.append(
                {
                    "asset": str(asset.resolve()),
                    "default_prim": str(default_prim.GetPath()) if default_prim else None,
                    "time_codes_per_second": stage.GetTimeCodesPerSecond(),
                    "start_time_code": stage.GetStartTimeCode(),
                    "end_time_code": stage.GetEndTimeCode(),
                    "root_prims": roots,
                    "world_children": [
                        {
                            "path": str(prim.GetPath()),
                            "type": prim.GetTypeName() or "Prim",
                        }
                        for prim in stage.GetPrimAtPath("/World").GetChildren()
                    ],
                    "notable_prims": notable,
                }
            )
            print(f"\nASSET: {asset.resolve()}", flush=True)
            print(
                f"defaultPrim: {default_prim.GetPath() if default_prim else '(없음)'}",
                flush=True,
            )
            print("rootPrims:")
            for item in roots:
                print(f"  {item['path']} [{item['type']}]", flush=True)
            print("notablePrims:")
            for item in notable:
                print(f"  {item['path']} [{item['type']}]", flush=True)
            if not notable:
                print("  (없음)", flush=True)
        if args.verify_equipment:
            from isaac_bridge import IsaacBridge
            from site_stage import DEFAULT_EQUIPMENT_PRIM_PATH, load_equipment

            composed_stage = Usd.Stage.CreateInMemory()
            equipment_info = load_equipment(
                composed_stage,
                args.assets[0],
                prim_path=DEFAULT_EQUIPMENT_PRIM_PATH,
                simulation_app=simulation_app,
            )
            equipment = composed_stage.GetPrimAtPath(DEFAULT_EQUIPMENT_PRIM_PATH)
            played = IsaacBridge(
                stage=composed_stage,
                update_callback=simulation_app.update,
            )._play_skeletal_animation(
                equipment,
                "ArmDig",
                duration_seconds=0.25,
            )
            reports[0]["composed_verification"] = {
                **equipment_info,
                "played_animation": played,
            }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
