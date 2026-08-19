"""PhysX preparation and locomotion helpers for imported excavator assets.

The PBR excavator is a skinned animation asset, not a ready-made articulated
vehicle.  This module therefore gives it a conservative physical carrier:

* the equipment root is a dynamic rigid body;
* two invisible capsule colliders are fitted to the authored ``TrackL`` and
  ``TrackR`` geometry subsets;
* the visual mesh and equipment-mounted sensors remain children of that body.

The terrain stays a static triangle mesh.  Gravity and the two track colliders
then determine the excavator's height and tilt instead of an overall visual
bounding box (whose lowest point can be the bucket).
"""

from __future__ import annotations

from collections.abc import Callable
import os
from typing import Any


TRACK_COLLIDER_SCOPE = "SiteGitTrackColliders"
TRACK_NAMES = ("TrackL", "TrackR")


def _prim(stage: Any, path: str) -> Any:
    """Return a Prim using an explicit SdfPath for USD 24/25 compatibility."""

    from pxr import Sdf

    return stage.GetPrimAtPath(Sdf.Path(path))


def _subset_world_bounds(subset_prim: Any) -> tuple[list[float], list[float]]:
    """Compute bounds from only the faces referenced by one GeomSubset."""

    from pxr import Gf, Usd, UsdGeom

    mesh_prim = subset_prim.GetParent()
    if not mesh_prim.IsValid() or not mesh_prim.IsA(UsdGeom.Mesh):
        raise RuntimeError(f"Track subset parent is not a Mesh: {subset_prim.GetPath()}")
    mesh = UsdGeom.Mesh(mesh_prim)
    points = mesh.GetPointsAttr().Get(Usd.TimeCode.Default()) or []
    face_counts = mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.Default()) or []
    face_vertices = mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.Default()) or []
    face_indices = subset_prim.GetAttribute("indices").Get(Usd.TimeCode.Default()) or []
    if not points or not face_counts or not face_indices:
        raise RuntimeError(f"Track subset has no usable faces: {subset_prim.GetPath()}")

    offsets: list[int] = [0]
    for count in face_counts:
        offsets.append(offsets[-1] + int(count))
    vertex_indices: set[int] = set()
    for face_index_value in face_indices:
        face_index = int(face_index_value)
        if face_index < 0 or face_index + 1 >= len(offsets):
            continue
        vertex_indices.update(
            int(value) for value in face_vertices[offsets[face_index] : offsets[face_index + 1]]
        )
    if not vertex_indices:
        raise RuntimeError(f"Track subset resolved to zero vertices: {subset_prim.GetPath()}")

    matrix = UsdGeom.Xformable(mesh_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    world_points = [matrix.Transform(Gf.Vec3d(points[index])) for index in vertex_indices]
    return (
        [min(float(point[axis]) for point in world_points) for axis in range(3)],
        [max(float(point[axis]) for point in world_points) for axis in range(3)],
    )


def track_visual_bounds(stage: Any, equipment_prim_path: str) -> dict[str, Any]:
    """Return exact world-space bounds for the imported left/right track faces."""

    from pxr import Usd

    equipment = _prim(stage, equipment_prim_path)
    if not equipment.IsValid() or not equipment.IsActive():
        raise RuntimeError(f"Equipment Prim is unavailable: {equipment_prim_path}")

    tracks: dict[str, dict[str, list[float]]] = {}
    for descendant in Usd.PrimRange(equipment):
        name = descendant.GetName()
        if descendant.GetTypeName() != "GeomSubset" or name not in TRACK_NAMES:
            continue
        minimum, maximum = _subset_world_bounds(descendant)
        tracks[name] = {"min": minimum, "max": maximum}
    missing = [name for name in TRACK_NAMES if name not in tracks]
    if missing:
        raise RuntimeError(
            "Excavator track GeomSubset is missing: " + ", ".join(missing)
        )
    combined_min = [min(item["min"][axis] for item in tracks.values()) for axis in range(3)]
    combined_max = [max(item["max"][axis] for item in tracks.values()) for axis in range(3)]
    return {"tracks": tracks, "min": combined_min, "max": combined_max}


def _move_root_z(stage: Any, equipment_prim_path: str, delta_z: float) -> None:
    from pxr import Gf, UsdGeom

    equipment = _prim(stage, equipment_prim_path)
    xformable = UsdGeom.Xformable(equipment)
    translate = next(
        (
            op
            for op in xformable.GetOrderedXformOps()
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate
        ),
        None,
    )
    if translate is None:
        translate = xformable.AddTranslateOp(opSuffix="sitegitPhysics")
    current = translate.Get() or Gf.Vec3d(0.0, 0.0, 0.0)
    translate.Set(Gf.Vec3d(float(current[0]), float(current[1]), float(current[2]) + delta_z))


def _sample_initial_surface(
    track_bounds: dict[str, Any],
    surface_height: Callable[[float, float, float], float],
) -> float:
    """Sample both track footprints and return a non-penetrating start height."""

    samples: list[float] = []
    for item in track_bounds["tracks"].values():
        minimum, maximum = item["min"], item["max"]
        center_x = (minimum[0] + maximum[0]) * 0.5
        center_y = (minimum[1] + maximum[1]) * 0.5
        inset_x = (maximum[0] - minimum[0]) * 0.35
        inset_y = (maximum[1] - minimum[1]) * 0.35
        for x in (center_x - inset_x, center_x, center_x + inset_x):
            for y in (center_y - inset_y, center_y, center_y + inset_y):
                samples.append(surface_height(float(x), float(y), float(minimum[2])))
    return max(samples) if samples else float(track_bounds["min"][2])


def _define_world_capsule(
    stage: Any,
    path: str,
    parent_world: Any,
    center: list[float],
    radius: float,
    total_length: float,
) -> Any:
    """Create a smooth track capsule aligned to the site's world Y axis."""

    from pxr import Gf, Sdf, UsdGeom, UsdPhysics

    capsule = UsdGeom.Capsule.Define(stage, Sdf.Path(path))
    capsule.CreateAxisAttr(UsdGeom.Tokens.y)
    capsule.CreateRadiusAttr(float(radius))
    capsule.CreateHeightAttr(max(0.05, float(total_length) - 2.0 * float(radius)))
    desired_world = Gf.Matrix4d(1.0)
    desired_world.SetTranslateOnly(Gf.Vec3d(*center))
    local = desired_world * parent_world.GetInverse()
    xformable = UsdGeom.Xformable(capsule)
    xformable.ClearXformOpOrder()
    xformable.AddTransformOp(UsdGeom.XformOp.PrecisionDouble).Set(local)
    imageable = UsdGeom.Imageable(capsule)
    imageable.CreatePurposeAttr(UsdGeom.Tokens.guide)
    imageable.MakeInvisible()
    collision = UsdPhysics.CollisionAPI.Apply(capsule.GetPrim())
    collision.CreateCollisionEnabledAttr(True)
    try:
        from pxr import PhysxSchema

        physx_collision = PhysxSchema.PhysxCollisionAPI.Apply(capsule.GetPrim())
        physx_collision.CreateContactOffsetAttr().Set(0.03)
        physx_collision.CreateRestOffsetAttr().Set(0.0)
    except (ImportError, AttributeError):
        pass
    return capsule.GetPrim()


def prepare_equipment_physics(
    stage: Any,
    equipment_prim_path: str,
    *,
    surface_height: Callable[[float, float, float], float] | None = None,
) -> dict[str, Any]:
    """Fit track colliders, align the tracks, and enable a dynamic rigid body."""

    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    equipment = _prim(stage, equipment_prim_path)
    if not equipment.IsValid() or not equipment.IsActive():
        raise RuntimeError(f"Equipment Prim is unavailable: {equipment_prim_path}")

    visual = track_visual_bounds(stage, equipment_prim_path)
    clearance = max(0.0, float(os.getenv("SITEGIT_EQUIPMENT_GROUND_CLEARANCE_M", "0.03")))
    if surface_height is not None:
        surface_z = _sample_initial_surface(visual, surface_height)
        _move_root_z(
            stage,
            equipment_prim_path,
            float(surface_z) + clearance - float(visual["min"][2]),
        )
        visual = track_visual_bounds(stage, equipment_prim_path)
    else:
        surface_z = float(visual["min"][2]) - clearance

    collider_scope_path = f"{equipment_prim_path}/{TRACK_COLLIDER_SCOPE}"
    if _prim(stage, collider_scope_path).IsValid():
        stage.RemovePrim(Sdf.Path(collider_scope_path))
    UsdGeom.Scope.Define(stage, Sdf.Path(collider_scope_path))
    parent_world = UsdGeom.Xformable(equipment).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    collider_paths: list[str] = []
    collider_bounds: dict[str, dict[str, list[float]]] = {}
    for name in TRACK_NAMES:
        item = visual["tracks"][name]
        minimum, maximum = item["min"], item["max"]
        visual_size = [max(0.01, maximum[i] - minimum[i]) for i in range(3)]
        # A low capsule follows the lower tread but has no box corners to snag
        # on the dense scanned mud mesh. Two capsules also give the rigid body
        # a stable left/right support footprint on slopes.
        radius = max(0.16, min(0.34, visual_size[0] * 0.38))
        total_length = max(1.0, visual_size[1] * 0.88)
        center = [
            (minimum[0] + maximum[0]) * 0.5,
            (minimum[1] + maximum[1]) * 0.5,
            minimum[2] + radius + 0.015,
        ]
        path = f"{collider_scope_path}/{name}Collider"
        _define_world_capsule(stage, path, parent_world, center, radius, total_length)
        collider_paths.append(path)
        collider_bounds[name] = {
            "center": [float(value) for value in center],
            "radius": float(radius),
            "total_length": float(total_length),
        }

    rigid = UsdPhysics.RigidBodyAPI.Apply(equipment)
    rigid.CreateRigidBodyEnabledAttr(True)
    rigid.CreateKinematicEnabledAttr(False)
    rigid.CreateVelocityAttr(Gf.Vec3f(0.0, 0.0, 0.0))
    rigid.CreateAngularVelocityAttr(Gf.Vec3f(0.0, 0.0, 0.0))
    mass = UsdPhysics.MassAPI.Apply(equipment)
    mass.CreateMassAttr().Set(float(os.getenv("SITEGIT_EQUIPMENT_MASS_KG", "18000")))
    try:
        from pxr import PhysxSchema

        physx_body = PhysxSchema.PhysxRigidBodyAPI.Apply(equipment)
        physx_body.CreateDisableGravityAttr().Set(False)
        physx_body.CreateLinearDampingAttr().Set(
            float(os.getenv("SITEGIT_EQUIPMENT_LINEAR_DAMPING", "1.5"))
        )
        physx_body.CreateAngularDampingAttr().Set(
            float(os.getenv("SITEGIT_EQUIPMENT_ANGULAR_DAMPING", "6.0"))
        )
    except (ImportError, AttributeError):
        pass

    equipment.SetCustomDataByKey("sitegitPhysicsMode", "dynamic-track-capsules")
    # USD customData does not accept a plain Python ``list[str]`` consistently
    # across the USD 24/25 bindings shipped by Isaac Sim.  Keep the diagnostic
    # value portable; the structured paths are still returned to Python.
    equipment.SetCustomDataByKey("sitegitTrackColliderPaths", ",".join(collider_paths))
    equipment.SetCustomDataByKey(
        "sitegitEquipmentAnchor",
        {
            "x": float((visual["min"][0] + visual["max"][0]) * 0.5),
            "y": float((visual["min"][1] + visual["max"][1]) * 0.5),
            "z": float(visual["min"][2]),
        },
    )
    return {
        "equipment_prim_path": equipment_prim_path,
        "physics_mode": "dynamic-track-capsules",
        "collider_paths": collider_paths,
        "colliders": collider_bounds,
        "track_visual_bounds": visual,
        "surface_z": float(surface_z),
        "clearance_m": clearance,
    }


def track_contact_pose(stage: Any, equipment_prim_path: str) -> dict[str, float]:
    """Read the physical track carrier's current world center and bottom Z."""

    equipment = _prim(stage, equipment_prim_path)
    anchor = equipment.GetCustomDataByKey("sitegitEquipmentAnchor")
    if isinstance(anchor, dict) and all(axis in anchor for axis in ("x", "y", "z")):
        return {axis: float(anchor[axis]) for axis in ("x", "y", "z")}

    # Invisible guide-purpose collider bounds are not reliable once PhysX has
    # taken ownership of a body (some USD builds return an empty FLT_MAX
    # range).  Fall back to the authored track faces before simulation starts.
    visual = track_visual_bounds(stage, equipment_prim_path)
    return {
        "x": float((visual["min"][0] + visual["max"][0]) * 0.5),
        "y": float((visual["min"][1] + visual["max"][1]) * 0.5),
        "z": float(visual["min"][2]),
    }


def is_physical_equipment(stage: Any, equipment_prim_path: str) -> bool:
    """Return whether the equipment has the SiteGit rigid-body track setup."""

    from pxr import UsdPhysics

    equipment = _prim(stage, equipment_prim_path)
    return bool(
        equipment.IsValid()
        and equipment.HasAPI(UsdPhysics.RigidBodyAPI)
        and _prim(stage, f"{equipment_prim_path}/{TRACK_COLLIDER_SCOPE}").IsValid()
    )
