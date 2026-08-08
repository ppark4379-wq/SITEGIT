"""Publish an Isaac Sim site-map bundle for the SiteGit web viewer.

The browser-ready bundle stays under SITEGIT_DATA_ROOT/isaac instead of Git.
A bundle consists of a sitegit-web-mesh-v1 manifest, float32 mesh buffers,
and optional texture images. The manifest is written last so the web viewer
never observes a partially published revision.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_DIRECTORY_NAME = "site-work-map"
MANIFEST_NAME = "manifest.json"
SUPPORTED_FORMAT = "sitegit-web-mesh-v1"


def _resolved_data_root(value: str | Path | None = None) -> Path:
    """Resolve the SiteGit runtime root using the same root .env as Backend."""
    load_dotenv(REPO_ROOT / ".env")
    raw = Path(value or os.getenv("SITEGIT_DATA_ROOT", REPO_ROOT / "runtime"))
    if not raw.is_absolute():
        raw = REPO_ROOT / raw
    return raw.resolve()


def _safe_bundle_file(source_root: Path, relative_name: str) -> Path:
    """Return one validated file inside the source bundle."""
    if not relative_name or Path(relative_name).is_absolute():
        raise ValueError(f"Invalid bundle file name: {relative_name!r}")
    candidate = (source_root / relative_name).resolve()
    if source_root != candidate and source_root not in candidate.parents:
        raise ValueError(f"Bundle file escapes source directory: {relative_name}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Bundle file not found: {candidate}")
    return candidate


def _load_manifest(source_root: Path) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    """Validate a browser mesh manifest and list every referenced file."""
    manifest_path = _safe_bundle_file(source_root, MANIFEST_NAME)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != SUPPORTED_FORMAT:
        raise ValueError(
            f"Unsupported map format: {manifest.get('format')!r}; expected {SUPPORTED_FORMAT!r}"
        )
    groups = manifest.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("Map manifest must contain at least one mesh group")

    files: list[tuple[str, Path]] = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Each map group must be an object")
        geometry = str(group.get("geometry") or "")
        files.append((geometry, _safe_bundle_file(source_root, geometry)))
        texture = group.get("texture")
        if texture:
            texture_name = str(texture)
            files.append((texture_name, _safe_bundle_file(source_root, texture_name)))
    return manifest, files


def publish_map_bundle(
    source: str | Path,
    *,
    data_root: str | Path | None = None,
) -> Path:
    """Copy one exported Isaac map bundle into SiteGit's active Isaac data area."""
    source_root = Path(source).expanduser().resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Isaac map bundle directory not found: {source_root}")
    manifest, files = _load_manifest(source_root)

    target_root = _resolved_data_root(data_root) / "isaac" / MAP_DIRECTORY_NAME
    target_root.mkdir(parents=True, exist_ok=True)
    resolved_target_root = target_root.resolve()
    for relative_name, source_file in files:
        target_file = (resolved_target_root / relative_name).resolve()
        if resolved_target_root not in target_file.parents:
            raise ValueError(f"Bundle target escapes map directory: {relative_name}")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target_file)

    publication = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "publisher": "isaac_adapter.map_publisher",
        "source_bundle": str(source_root),
        "triangle_count": int(manifest.get("triangle_count", 0)),
        "group_count": len(manifest["groups"]),
    }
    (resolved_target_root / "publication.json").write_text(
        json.dumps(publication, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest_temp = resolved_target_root / f"{MANIFEST_NAME}.tmp"
    manifest_temp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest_temp.replace(resolved_target_root / MANIFEST_NAME)
    return resolved_target_root


def main() -> None:
    """Publish an exported Isaac map bundle from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Directory containing manifest.json")
    parser.add_argument(
        "--data-root",
        default=None,
        help="Override SITEGIT_DATA_ROOT for this publication",
    )
    args = parser.parse_args()
    target = publish_map_bundle(args.source, data_root=args.data_root)
    manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    print("=" * 60)
    print("SiteGit Isaac Site Work Map 게시 완료")
    print(f"Source: {Path(args.source).resolve()}")
    print(f"Target: {target}")
    print(f"Triangles: {int(manifest.get('triangle_count', 0)):,}")
    print("Web: /isaac-data/site-work-map/manifest.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
