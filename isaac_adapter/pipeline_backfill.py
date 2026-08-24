"""Pure geometry helpers for the staged pipeline backfill demo.

The Isaac entry point keeps these calculations separate so they can be tested
without importing Omniverse.  Backfill sections are restored from their buried
bottom grid to the approved surface, while the previously excavated spoil-bank
meshes collapse by the same progress ratio.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


Point3 = tuple[float, float, float]


def smooth_progress(progress: float) -> float:
    """Clamp progress to 0..1 and apply a smoothstep easing curve."""

    value = max(0.0, min(1.0, float(progress)))
    return value * value * (3.0 - 2.0 * value)


def blend_backfill_points(
    final_points: Sequence[Sequence[float]],
    top_vertex_count: int,
    progress: float,
    *,
    empty_clearance_m: float = 0.03,
) -> list[Point3]:
    """Restore one trench-fill mesh from its bottom grid to its final surface.

    ``create_pipeline_backfill`` authors the top grid first and an equal-sized
    bottom grid immediately after it.  At zero progress the top vertices sit a
    few centimetres above that bottom grid, leaving the installed pipe visible.
    At full progress the original approved surface is recovered exactly.
    """

    count = int(top_vertex_count)
    if count <= 0:
        raise ValueError("top_vertex_count must be positive")
    if len(final_points) < count * 2:
        raise ValueError("backfill mesh does not contain matching top and bottom grids")
    clearance = max(0.0, float(empty_clearance_m))
    eased = smooth_progress(progress)
    result: list[Point3] = []
    for index, raw in enumerate(final_points):
        x, y, z = (float(raw[0]), float(raw[1]), float(raw[2]))
        if index < count:
            bottom = final_points[index + count]
            empty_z = float(bottom[2]) + clearance
            z = empty_z + (z - empty_z) * eased
        result.append((x, y, z))
    return result


def shrink_spoil_points(
    original_points: Sequence[Sequence[float]],
    consumed_progress: float,
    *,
    minimum_height_m: float = 0.02,
) -> list[Point3]:
    """Lower an excavated spoil pile as its material is returned to the trench."""

    if not original_points:
        return []
    base_z = min(float(point[2]) for point in original_points)
    remaining = 1.0 - smooth_progress(consumed_progress)
    minimum = max(0.0, float(minimum_height_m))
    result: list[Point3] = []
    for raw in original_points:
        x, y, z = (float(raw[0]), float(raw[1]), float(raw[2]))
        height = max(0.0, z - base_z)
        adjusted_height = (
            0.0
            if remaining <= 1e-9 or height <= 1e-9
            else max(minimum, height * remaining)
        )
        result.append((x, y, base_z + adjusted_height))
    return result


def spoil_matches_targets(spoil_name: str, target_names: Iterable[str]) -> bool:
    """Return whether a moved-soil Prim was produced from one assigned target."""

    name = str(spoil_name)
    return "_MovedSoil_" in name and any(
        name.startswith(f"{str(target)}_MovedSoil_") for target in target_names
    )
