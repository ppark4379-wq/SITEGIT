"""Equipment-mounted camera and PhysX raycast LiDAR for SiteGit evidence.

The sensor rig is attached below the assigned excavator Prim.  Its local
transform compensates for the source asset's import scale/up-axis conversion,
so configuration values stay in the site's Z-up metre coordinate system while
the rig still follows the equipment when it moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
from typing import Any, Callable, Iterable


def parse_number_tuple(raw: str, count: int, setting_name: str) -> tuple[float, ...]:
    """Parse a comma-separated numeric setting with a useful error message."""

    try:
        values = tuple(float(value.strip()) for value in raw.split(","))
    except ValueError as error:
        raise ValueError(f"{setting_name} must contain {count} comma-separated numbers") from error
    if len(values) != count:
        raise ValueError(f"{setting_name} must contain {count} comma-separated numbers")
    return values


def generate_lidar_directions(
    horizontal_fov_degrees: float,
    vertical_min_degrees: float,
    vertical_max_degrees: float,
    horizontal_rays: int,
    vertical_rays: int,
) -> tuple[tuple[float, float, float], ...]:
    """Create unit rays in the rig frame (+Y forward, +X right, +Z up)."""

    if horizontal_rays < 1 or vertical_rays < 1:
        raise ValueError("LiDAR ray counts must be positive")
    if horizontal_fov_degrees <= 0 or horizontal_fov_degrees > 360:
        raise ValueError("LiDAR horizontal FOV must be in (0, 360]")
    if vertical_min_degrees > vertical_max_degrees:
        raise ValueError("LiDAR vertical minimum must not exceed its maximum")

    def values(start: float, stop: float, count: int) -> Iterable[float]:
        if count == 1:
            yield (start + stop) * 0.5
            return
        step = (stop - start) / (count - 1)
        for index in range(count):
            yield start + step * index

    directions: list[tuple[float, float, float]] = []
    horizontal_angles = tuple(
        values(-horizontal_fov_degrees * 0.5, horizontal_fov_degrees * 0.5, horizontal_rays)
    )
    vertical_angles = tuple(values(vertical_min_degrees, vertical_max_degrees, vertical_rays))
    for vertical_degrees in vertical_angles:
        vertical = math.radians(vertical_degrees)
        vertical_cosine = math.cos(vertical)
        for horizontal_degrees in horizontal_angles:
            horizontal = math.radians(horizontal_degrees)
            directions.append(
                (
                    math.sin(horizontal) * vertical_cosine,
                    math.cos(horizontal) * vertical_cosine,
                    math.sin(vertical),
                )
            )
    return tuple(directions)


def _bool_setting(raw: str) -> bool:
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _json_safe(value: Any) -> Any:
    """Convert Isaac/numpy sensor values into JSON-compatible Python values."""

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class SensorRigConfig:
    """User-configurable geometry and sampling settings for one sensor rig."""

    # Offsets are relative to the track-contact anchor.  These values restore
    # the mount position selected in the Isaac viewport (0, 1.640, 1.927 m in
    # the original stage) after the excavator was normalized for SiteGit.
    mount_offset_m: tuple[float, float, float] = (0.705, -0.986, 1.90)
    # Optional authored placement source.  The old excavator_lidar.usd is a
    # complete stage, so only this Prim's transform is read from it; the stage
    # itself is never referenced into the production scene.
    sensor_reference_usd: str = ""
    sensor_reference_prim_path: str = "/World/LidarMount"
    # Legacy absolute camera placement, retained as a fallback for existing
    # deployments without an authored LiDAR mount.
    camera_mount_offset_m: tuple[float, float, float] = (2.45, -0.986, 2.15)
    # Camera placement in the SiteGit LiDAR frame (+X right, +Y forward,
    # +Z up). It is rigidly attached next to the LiDAR.
    camera_offset_from_lidar_m: tuple[float, float, float] = (0.35, 0.0, 0.15)
    camera_resolution: tuple[int, int] = (960, 540)
    camera_pitch_degrees: float = 18.0
    camera_focal_length_mm: float = 18.0
    camera_warmup_frames: int = 60
    camera_level_horizon: bool = True
    lidar_horizontal_fov_degrees: float = 120.0
    lidar_vertical_min_degrees: float = -75.0
    lidar_vertical_max_degrees: float = 15.0
    lidar_horizontal_rays: int = 81
    lidar_vertical_rays: int = 25
    lidar_min_range_m: float = 0.2
    lidar_max_range_m: float = 20.0
    lidar_draw_points: bool = True
    lidar_point_width_m: float = 0.035
    # A physical IMU is created directly below the excavator RigidBody. Its XY
    # location is the track centre and this height is above the track top.
    imu_height_above_tracks_m: float = 0.45
    imu_frequency_hz: int = 60

    @classmethod
    def from_environment(cls) -> "SensorRigConfig":
        """Load sensor settings without importing Isaac modules."""

        mount = parse_number_tuple(
            os.getenv("SITEGIT_SENSOR_MOUNT_OFFSET", "0.705,-0.986,1.90"),
            3,
            "SITEGIT_SENSOR_MOUNT_OFFSET",
        )
        camera_mount = parse_number_tuple(
            os.getenv("SITEGIT_CAMERA_MOUNT_OFFSET", "2.45,-0.986,2.15"),
            3,
            "SITEGIT_CAMERA_MOUNT_OFFSET",
        )
        camera_from_lidar = parse_number_tuple(
            os.getenv("SITEGIT_CAMERA_OFFSET_FROM_LIDAR", "0.35,0,0.15"),
            3,
            "SITEGIT_CAMERA_OFFSET_FROM_LIDAR",
        )
        resolution_values = parse_number_tuple(
            os.getenv("SITEGIT_CAMERA_RESOLUTION", "960,540"),
            2,
            "SITEGIT_CAMERA_RESOLUTION",
        )
        resolution = (int(resolution_values[0]), int(resolution_values[1]))
        if min(resolution) < 1:
            raise ValueError("SITEGIT_CAMERA_RESOLUTION values must be positive")
        config = cls(
            mount_offset_m=(mount[0], mount[1], mount[2]),
            sensor_reference_usd=os.getenv("SITEGIT_SENSOR_REFERENCE_USD", "").strip(),
            sensor_reference_prim_path=os.getenv(
                "SITEGIT_SENSOR_REFERENCE_PRIM", "/World/LidarMount"
            ).strip()
            or "/World/LidarMount",
            camera_mount_offset_m=(
                camera_mount[0],
                camera_mount[1],
                camera_mount[2],
            ),
            camera_offset_from_lidar_m=(
                camera_from_lidar[0],
                camera_from_lidar[1],
                camera_from_lidar[2],
            ),
            camera_resolution=resolution,
            camera_pitch_degrees=float(os.getenv("SITEGIT_CAMERA_PITCH_DEG", "18")),
            camera_focal_length_mm=float(os.getenv("SITEGIT_CAMERA_FOCAL_LENGTH_MM", "18")),
            camera_warmup_frames=int(os.getenv("SITEGIT_CAMERA_WARMUP_FRAMES", "60")),
            camera_level_horizon=_bool_setting(
                os.getenv("SITEGIT_CAMERA_LEVEL_HORIZON", "true")
            ),
            lidar_horizontal_fov_degrees=float(
                os.getenv("SITEGIT_LIDAR_HORIZONTAL_FOV_DEG", "120")
            ),
            lidar_vertical_min_degrees=float(
                os.getenv("SITEGIT_LIDAR_VERTICAL_MIN_DEG", "-75")
            ),
            lidar_vertical_max_degrees=float(
                os.getenv("SITEGIT_LIDAR_VERTICAL_MAX_DEG", "15")
            ),
            lidar_horizontal_rays=int(os.getenv("SITEGIT_LIDAR_HORIZONTAL_RAYS", "81")),
            lidar_vertical_rays=int(os.getenv("SITEGIT_LIDAR_VERTICAL_RAYS", "25")),
            lidar_min_range_m=float(os.getenv("SITEGIT_LIDAR_MIN_RANGE_M", "0.2")),
            lidar_max_range_m=float(os.getenv("SITEGIT_LIDAR_MAX_RANGE_M", "20")),
            lidar_draw_points=_bool_setting(os.getenv("SITEGIT_LIDAR_DRAW_POINTS", "true")),
            lidar_point_width_m=float(os.getenv("SITEGIT_LIDAR_POINT_WIDTH_M", "0.035")),
            imu_height_above_tracks_m=float(
                os.getenv("SITEGIT_IMU_HEIGHT_ABOVE_TRACKS_M", "0.45")
            ),
            imu_frequency_hz=int(os.getenv("SITEGIT_IMU_FREQUENCY_HZ", "60")),
        )
        # Run the same validation used by the scanner during startup.
        generate_lidar_directions(
            config.lidar_horizontal_fov_degrees,
            config.lidar_vertical_min_degrees,
            config.lidar_vertical_max_degrees,
            config.lidar_horizontal_rays,
            config.lidar_vertical_rays,
        )
        if config.lidar_min_range_m < 0 or config.lidar_max_range_m <= config.lidar_min_range_m:
            raise ValueError("LiDAR range must satisfy 0 <= min < max")
        if config.imu_height_above_tracks_m < 0:
            raise ValueError("SITEGIT_IMU_HEIGHT_ABOVE_TRACKS_M must be non-negative")
        if config.imu_frequency_hz < 1:
            raise ValueError("SITEGIT_IMU_FREQUENCY_HZ must be positive")
        return config


def prepare_raycast_collisions(
    stage: Any,
    root_paths: Iterable[str],
    *,
    update_callback: Callable[[], Any] | None = None,
    cooking_frames: int = 90,
) -> dict[str, int]:
    """Apply static triangle-mesh collision below site/diggable roots."""

    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    if not stage.GetPrimAtPath("/World/PhysicsScene").IsValid():
        scene = UsdPhysics.Scene.Define(stage, Sdf.Path("/World/PhysicsScene"))
        scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
        scene.CreateGravityMagnitudeAttr(9.81)

    scanned = 0
    applied = 0
    for root_path in root_paths:
        root = stage.GetPrimAtPath(root_path)
        if not root.IsValid():
            continue
        for prim in Usd.PrimRange(root):
            if not prim.IsActive() or not prim.IsA(UsdGeom.Mesh):
                continue
            scanned += 1
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(prim)
                applied += 1
            mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
            mesh_collision.CreateApproximationAttr().Set("none")

    if update_callback is not None:
        for _ in range(max(0, cooking_frames)):
            update_callback()
    return {"mesh_count": scanned, "new_collision_count": applied}


class EquipmentSensorRig:
    """Camera, 3D ray scanner, and physical IMU attached to equipment."""

    def __init__(
        self,
        stage: Any,
        equipment_prim_path: str,
        *,
        update_callback: Callable[[], Any] | None = None,
        config: SensorRigConfig | None = None,
        physics_world: Any = None,
    ) -> None:
        self.stage = stage
        self.equipment_prim_path = equipment_prim_path.rstrip("/")
        self.update_callback = update_callback
        self.config = config or SensorRigConfig.from_environment()
        self.physics_world = physics_world
        self.mount_path = f"{self.equipment_prim_path}/SiteGitSensors"
        self.lidar_path = f"{self.mount_path}/RaycastLidar"
        self.camera_path = f"{self.mount_path}/Camera"
        # IMU sensors must be immediate children of a PhysX RigidBody.
        self.imu_path = f"{self.equipment_prim_path}/SiteGitImu"
        equipment_name = self.equipment_prim_path.rsplit("/", 1)[-1]
        self.lidar_points_path = f"/World/SiteGitSensors/{equipment_name}_LidarPoints"
        self._camera: Any = None
        self._imu: Any = None
        self._camera_transform_op: Any = None
        self._scan_sequence = 0
        self._directions = generate_lidar_directions(
            self.config.lidar_horizontal_fov_degrees,
            self.config.lidar_vertical_min_degrees,
            self.config.lidar_vertical_max_degrees,
            self.config.lidar_horizontal_rays,
            self.config.lidar_vertical_rays,
        )

    def initialize(self) -> dict[str, Any]:
        """Create the attached mount/camera and initialize its RGB annotator."""

        from isaacsim.core.utils.rotations import lookat_to_quatf
        from isaacsim.sensors.camera import Camera
        from isaacsim.sensors.physics import IMUSensor
        import numpy as np
        from pxr import Gf, Sdf, Usd, UsdGeom

        equipment = self.stage.GetPrimAtPath(self.equipment_prim_path)
        if not equipment.IsValid():
            raise ValueError(f"equipment Prim not found: {self.equipment_prim_path}")

        anchor_value = equipment.GetCustomDataByKey("sitegitEquipmentAnchor")
        if isinstance(anchor_value, dict) and all(
            axis in anchor_value for axis in ("x", "y", "z")
        ):
            anchor = (
                float(anchor_value["x"]),
                float(anchor_value["y"]),
                float(anchor_value["z"]),
            )
        elif isinstance(anchor_value, (list, tuple)) and len(anchor_value) == 3:
            anchor = tuple(float(value) for value in anchor_value)
        else:
            world = UsdGeom.Xformable(equipment).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            anchor = tuple(float(value) for value in world.ExtractTranslation())
        equipment_world = UsdGeom.Xformable(equipment).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        desired_position, placement = self._resolve_mount_position(
            equipment,
            equipment_world,
            anchor,
        )
        desired_world = Gf.Matrix4d(1.0)
        # The imported excavator's boom points toward site -Y. Rotate the
        # sensor frame so its conventional +Y-forward rays face the boom.
        desired_world.SetRotateOnly(
            Gf.Rotation(Gf.Vec3d(0.0, 0.0, 1.0), 180.0).GetQuat()
        )
        desired_world.SetTranslateOnly(desired_position)
        mount_local = desired_world * equipment_world.GetInverse()

        mount = UsdGeom.Xform.Define(self.stage, Sdf.Path(self.mount_path))
        mount_xform = UsdGeom.Xformable(mount)
        mount_xform.ClearXformOpOrder()
        mount_xform.AddTransformOp(UsdGeom.XformOp.PrecisionDouble).Set(mount_local)
        mount.GetPrim().SetCustomDataByKey("sitegitAttachedTo", self.equipment_prim_path)

        lidar = UsdGeom.Xform.Define(self.stage, Sdf.Path(self.lidar_path))
        lidar.GetPrim().SetCustomDataByKey("sitegitSensorType", "physx-raycast-lidar")
        lidar.GetPrim().SetCustomDataByKey(
            "sitegitReferencePrim", placement.get("reference_prim_path", "")
        )

        camera = UsdGeom.Camera.Define(self.stage, Sdf.Path(self.camera_path))
        camera.CreateFocalLengthAttr().Set(self.config.camera_focal_length_mm)
        camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.1, 1000.0))
        pitch = math.radians(self.config.camera_pitch_degrees)
        if placement["source"] == "legacy-anchor-offset":
            camera_position = Gf.Vec3d(
                float(anchor[0]) + self.config.camera_mount_offset_m[0],
                float(anchor[1]) + self.config.camera_mount_offset_m[1],
                float(anchor[2]) + self.config.camera_mount_offset_m[2],
            )
        else:
            camera_position = desired_world.Transform(
                Gf.Vec3d(*self.config.camera_offset_from_lidar_m)
            )
        eye = Gf.Vec3f(*[float(value) for value in camera_position])
        forward = desired_world.TransformDir(
            Gf.Vec3d(0.0, math.cos(pitch), -math.sin(pitch))
        )
        up = desired_world.TransformDir(Gf.Vec3d(0.0, 0.0, 1.0))
        target = eye + Gf.Vec3f(*[float(value) * 10.0 for value in forward])
        orientation = lookat_to_quatf(
            target,
            eye,
            Gf.Vec3f(*[float(value) for value in up]),
        )
        camera_world = Gf.Matrix4d(1.0)
        camera_world.SetRotateOnly(Gf.Quatd(orientation))
        camera_world.SetTranslateOnly(camera_position)
        camera_local = camera_world * desired_world.GetInverse()
        camera_xform = UsdGeom.Xformable(camera)
        camera_xform.ClearXformOpOrder()
        self._camera_transform_op = camera_xform.AddTransformOp(
            UsdGeom.XformOp.PrecisionDouble
        )
        self._camera_transform_op.Set(camera_local)

        self._camera = Camera(
            prim_path=self.camera_path,
            name="sitegit_equipment_camera",
            resolution=self.config.camera_resolution,
        )
        self._camera.initialize(attach_rgb_annotator=True)

        # The equipment root was made the dynamic rigid body before this rig
        # starts. Put the IMU near the upper-frame centre derived from the exact
        # left/right track faces and express that point in equipment-local axes.
        from equipment_physics import track_visual_bounds

        track_bounds = track_visual_bounds(self.stage, self.equipment_prim_path)
        imu_world_position = Gf.Vec3d(
            (float(track_bounds["min"][0]) + float(track_bounds["max"][0])) * 0.5,
            (float(track_bounds["min"][1]) + float(track_bounds["max"][1])) * 0.5,
            float(track_bounds["max"][2]) + self.config.imu_height_above_tracks_m,
        )
        imu_local_position = equipment_world.GetInverse().Transform(imu_world_position)
        self._imu = IMUSensor(
            prim_path=self.imu_path,
            name="sitegit_equipment_imu",
            frequency=self.config.imu_frequency_hz,
            translation=np.asarray(
                [float(imu_local_position[index]) for index in range(3)],
                dtype=np.float64,
            ),
            orientation=np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
        )
        if self.physics_world is not None:
            # Isaac registers newly created physics sensors during World.reset.
            # Adding it to the Scene also ensures later resets reinitialize it.
            self.physics_world.scene.add(self._imu)
            self.physics_world.reset()
        else:
            self._imu.initialize()
        self._pump_updates(self.config.camera_warmup_frames)
        # A saved working Stage may contain the previous run's green points.
        # Start every runner session with an explicitly empty visualization.
        self._draw_points([])
        return {
            "equipment_prim_path": self.equipment_prim_path,
            "mount_prim_path": self.mount_path,
            "lidar_prim_path": self.lidar_path,
            "camera_prim_path": self.camera_path,
            "imu_prim_path": self.imu_path,
            "lidar_points_prim_path": self.lidar_points_path,
            "mount_position_m": [float(value) for value in desired_position],
            "camera_position_m": [float(value) for value in camera_position],
            "imu_position_m": [float(value) for value in imu_world_position],
            "placement_source": placement["source"],
            "sensor_reference_usd": placement.get("reference_usd"),
            "sensor_reference_prim_path": placement.get("reference_prim_path"),
            "camera_offset_from_lidar_m": list(self.config.camera_offset_from_lidar_m),
            "camera_level_horizon": self.config.camera_level_horizon,
            "camera_resolution": list(self.config.camera_resolution),
            "lidar_ray_count": len(self._directions),
            "imu_frequency_hz": self.config.imu_frequency_hz,
        }

    def _resolve_mount_position(
        self,
        equipment: Any,
        equipment_world: Any,
        anchor: tuple[float, float, float],
    ) -> tuple[Any, dict[str, Any]]:
        """Resolve the authored LiDAR marker without importing its old full stage."""

        from pxr import Gf, Usd, UsdGeom

        reference_path = self.config.sensor_reference_prim_path
        relative_reference_path = reference_path
        if reference_path.startswith("/World/"):
            relative_reference_path = reference_path[len("/World") :]
        elif not reference_path.startswith("/"):
            relative_reference_path = f"/{reference_path}"
        composed_path = f"{self.equipment_prim_path}{relative_reference_path}"
        composed_reference = self.stage.GetPrimAtPath(composed_path)
        if composed_reference.IsValid() and composed_path != self.mount_path:
            world = UsdGeom.Xformable(composed_reference).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            return world.ExtractTranslation(), {
                "source": "composed-authored-prim",
                "reference_prim_path": composed_path,
            }

        reference_usd = self.config.sensor_reference_usd
        if reference_usd:
            asset = Path(os.path.expandvars(reference_usd)).expanduser().resolve()
            if not asset.is_file():
                raise FileNotFoundError(f"sensor reference USD not found: {asset}")
            reference_stage = Usd.Stage.Open(asset.as_posix(), load=Usd.Stage.LoadNone)
            if reference_stage is None:
                raise RuntimeError(f"could not open sensor reference USD: {asset}")
            reference_prim = reference_stage.GetPrimAtPath(reference_path)
            if not reference_prim.IsValid() or not reference_prim.IsA(UsdGeom.Xformable):
                raise ValueError(
                    f"sensor reference Prim not found or not transformable: {reference_path}"
                )
            default_prim = reference_stage.GetDefaultPrim()
            if not default_prim.IsValid() or not default_prim.IsA(UsdGeom.Xformable):
                raise ValueError(f"sensor reference USD has no transformable default Prim: {asset}")
            marker_world = UsdGeom.Xformable(reference_prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            root_world = UsdGeom.Xformable(default_prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            marker_relative = marker_world * root_world.GetInverse()
            authored_world = marker_relative * equipment_world
            return authored_world.ExtractTranslation(), {
                "source": "usd-reference",
                "reference_usd": str(asset),
                "reference_prim_path": reference_path,
                "authored_translation": [
                    float(value) for value in marker_relative.ExtractTranslation()
                ],
                "reference_meters_per_unit": float(
                    UsdGeom.GetStageMetersPerUnit(reference_stage)
                ),
            }

        return Gf.Vec3d(
            float(anchor[0]) + self.config.mount_offset_m[0],
            float(anchor[1]) + self.config.mount_offset_m[1],
            float(anchor[2]) + self.config.mount_offset_m[2],
        ), {"source": "legacy-anchor-offset"}

    def capture_camera(self, exporter: Any, storage_key: str) -> dict[str, Any]:
        """Capture an RGB PNG from the excavator-mounted camera."""

        if self._camera is None:
            return {"available": False, "reason": "equipment camera is not initialized"}
        point_imageable = None
        previous_point_visibility = None
        try:
            import numpy as np
            from PIL import Image
            from pxr import Gf, Usd, UsdGeom

            # Keep the live green LiDAR overlay in the viewport, but do not
            # burn debug points into the photographic RGB evidence.
            point_prim = self.stage.GetPrimAtPath(self.lidar_points_path)
            if point_prim.IsValid():
                point_imageable = UsdGeom.Imageable(point_prim)
                previous_point_visibility = point_imageable.GetVisibilityAttr().Get(
                    Usd.TimeCode.Default()
                )
                point_imageable.MakeInvisible()
                self._pump_updates(2)

            if self.config.camera_level_horizon:
                self._level_camera_horizon()
            self._camera.resume()
            self._pump_updates(self.config.camera_warmup_frames)
            self._wait_for_camera_render()
            rgba = self._camera.get_rgba(device="cpu")
            if hasattr(rgba, "numpy"):
                rgba = rgba.numpy()
            pixels = np.asarray(rgba)
            if pixels.size == 0 or pixels.ndim != 3 or pixels.shape[2] < 3:
                return {"available": False, "reason": "equipment camera returned no RGB frame"}
            rgb = pixels[:, :, :3]
            if rgb.dtype != np.uint8:
                if np.issubdtype(rgb.dtype, np.floating) and float(np.max(rgb, initial=0.0)) <= 1.0:
                    rgb = rgb * 255.0
                rgb = np.clip(rgb, 0, 255).astype(np.uint8)
            target = exporter.target_path(storage_key)
            Image.fromarray(rgb, mode="RGB").save(target, format="PNG")
            pose = self._world_pose(self.camera_path)
            camera_world = UsdGeom.Xformable(
                self.stage.GetPrimAtPath(self.camera_path)
            ).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            right = camera_world.TransformDir(Gf.Vec3d(1.0, 0.0, 0.0))
            return {
                "available": True,
                "storage_key": storage_key,
                "prim_path": self.camera_path,
                "mount_prim_path": self.mount_path,
                "source": "equipment-mounted-camera",
                "resolution": [int(rgb.shape[1]), int(rgb.shape[0])],
                "position_m": pose["position_m"],
                "orientation_wxyz": pose["orientation_wxyz"],
                "horizon_levelled": self.config.camera_level_horizon,
                "horizon_roll_degrees": math.degrees(
                    math.asin(max(-1.0, min(1.0, float(right.GetNormalized()[2]))))
                ),
                "lidar_overlay_hidden": point_imageable is not None,
            }
        except Exception as error:
            return {"available": False, "reason": f"equipment camera capture failed: {error}"}
        finally:
            if point_imageable is not None:
                from pxr import UsdGeom

                point_imageable.GetVisibilityAttr().Set(
                    previous_point_visibility or UsdGeom.Tokens.inherited
                )
                self._pump_updates(2)

    def capture_lidar(self, exporter: Any, storage_key: str) -> dict[str, Any]:
        """Cast one full 3D scan from the current moving mount pose."""

        try:
            import omni.physx
            from pxr import Gf, Usd, UsdGeom

            self._pump_updates(2)
            mount = self.stage.GetPrimAtPath(self.lidar_path)
            if not mount.IsValid():
                return {"available": False, "reason": f"LiDAR origin not found: {self.lidar_path}"}
            world = UsdGeom.Xformable(mount).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            origin_value = world.ExtractTranslation()
            origin = Gf.Vec3f(*[float(value) for value in origin_value])
            query = omni.physx.get_physx_scene_query_interface()
            points: list[tuple[float, float, float]] = []
            hit_paths: dict[str, int] = {}

            for local_direction in self._directions:
                world_direction_value = world.TransformDir(Gf.Vec3d(*local_direction)).GetNormalized()
                direction = Gf.Vec3f(*[float(value) for value in world_direction_value])
                ray_hits: list[Any] = []

                def collect_hit(hit: Any) -> bool:
                    ray_hits.append(hit)
                    return True

                query.raycast_all(origin, direction, self.config.lidar_max_range_m, collect_hit, True)
                valid_hits = [
                    hit
                    for hit in ray_hits
                    if float(hit.distance) >= self.config.lidar_min_range_m
                    and not str(hit.collision).startswith(self.equipment_prim_path)
                    and not str(hit.rigid_body).startswith(self.equipment_prim_path)
                ]
                if not valid_hits:
                    continue
                hit = min(valid_hits, key=lambda value: float(value.distance))
                position = hit.position
                points.append((float(position.x), float(position.y), float(position.z)))
                collision_path = str(hit.collision or hit.rigid_body or "unknown")
                hit_paths[collision_path] = hit_paths.get(collision_path, 0) + 1

            exported = exporter.save_point_cloud(storage_key, points)
            if self.config.lidar_draw_points:
                self._draw_points(points)
            return {
                **exported,
                "prim_path": self.lidar_points_path,
                "mount_prim_path": self.mount_path,
                "sensor_prim_path": self.lidar_path,
                "source": "equipment-mounted-physx-raycast-lidar",
                "ray_count": len(self._directions),
                "hit_ratio": round(len(points) / max(len(self._directions), 1), 6),
                "origin_m": [float(origin[index]) for index in range(3)],
                "horizontal_fov_degrees": self.config.lidar_horizontal_fov_degrees,
                "vertical_fov_degrees": [
                    self.config.lidar_vertical_min_degrees,
                    self.config.lidar_vertical_max_degrees,
                ],
                "range_m": [self.config.lidar_min_range_m, self.config.lidar_max_range_m],
                "hit_prim_counts": dict(
                    sorted(hit_paths.items(), key=lambda item: item[1], reverse=True)[:20]
                ),
            }
        except Exception as error:
            return {"available": False, "reason": f"equipment LiDAR scan failed: {error}"}

    def capture_imu(self, exporter: Any, storage_key: str) -> dict[str, Any]:
        """Capture one real PhysX IMU sample for before/after evidence."""

        if self._imu is None:
            return {"available": False, "reason": "equipment IMU is not initialized"}
        try:
            self._imu.resume()
            # Advance beyond one sensor period so the first capture is valid.
            self._pump_updates(3)
            frame = _json_safe(self._imu.get_current_frame(read_gravity=True))
            if not isinstance(frame, dict) or not frame:
                return {
                    "available": False,
                    "prim_path": self.imu_path,
                    "reason": "equipment IMU returned an empty frame",
                }
            payload = {
                "prim_path": self.imu_path,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "frame": frame,
                "source": "equipment-mounted-isaac-imu",
                **self._world_pose(self.imu_path),
            }
            exporter.save_summary(storage_key, payload)
            return {
                "available": True,
                "storage_key": storage_key,
                "sample_count": 1,
                **payload,
            }
        except Exception as error:
            return {
                "available": False,
                "prim_path": self.imu_path,
                "reason": f"equipment IMU capture failed: {error}",
            }

    def _draw_points(self, points: list[tuple[float, float, float]]) -> None:
        from pxr import Gf, Sdf, UsdGeom

        UsdGeom.Scope.Define(self.stage, Sdf.Path("/World/SiteGitSensors"))
        point_prim = UsdGeom.Points.Define(self.stage, Sdf.Path(self.lidar_points_path))
        imageable = UsdGeom.Imageable(point_prim.GetPrim())
        imageable.MakeInvisible()
        point_values = [Gf.Vec3f(*point) for point in points]
        point_prim.CreatePointsAttr().Set([])
        point_prim.CreateWidthsAttr().Set([])
        point_prim.CreatePointsAttr().Set(point_values)
        point_prim.CreateWidthsAttr().Set(
            [self.config.lidar_point_width_m] * len(point_values)
        )
        point_prim.CreateDisplayColorAttr().Set([Gf.Vec3f(0.1, 1.0, 0.2)])
        if point_values:
            minimum = Gf.Vec3f(
                *[min(float(point[axis]) for point in point_values) for axis in range(3)]
            )
            maximum = Gf.Vec3f(
                *[max(float(point[axis]) for point in point_values) for axis in range(3)]
            )
            point_prim.CreateExtentAttr().Set([minimum, maximum])
        else:
            point_prim.CreateExtentAttr().Set(
                [Gf.Vec3f(0.0, 0.0, 0.0), Gf.Vec3f(0.0, 0.0, 0.0)]
            )
        self._scan_sequence += 1
        point_prim.GetPrim().SetCustomDataByKey("sitegitScanSequence", self._scan_sequence)
        imageable.MakeVisible()
        self._pump_updates(2)

    def _level_camera_horizon(self) -> None:
        """Keep the mounted camera's horizon level while following equipment yaw."""

        if self._camera is None:
            return
        from isaacsim.core.utils.rotations import lookat_to_quatf
        from pxr import Gf, Usd, UsdGeom

        mount = self.stage.GetPrimAtPath(self.mount_path)
        lidar = self.stage.GetPrimAtPath(self.lidar_path)
        camera = self.stage.GetPrimAtPath(self.camera_path)
        if not mount.IsValid() or not lidar.IsValid() or not camera.IsValid():
            return
        mount_world = UsdGeom.Xformable(mount).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        lidar_world = UsdGeom.Xformable(lidar).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        camera_xform = UsdGeom.Xformable(camera)
        camera_world_current = camera_xform.ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
        position = camera_world_current.ExtractTranslation()
        forward_value = lidar_world.TransformDir(Gf.Vec3d(0.0, 1.0, 0.0))
        horizontal = Gf.Vec3d(float(forward_value[0]), float(forward_value[1]), 0.0)
        if horizontal.GetLength() < 1e-6:
            horizontal = Gf.Vec3d(0.0, -1.0, 0.0)
        horizontal = horizontal.GetNormalized()
        pitch = math.radians(self.config.camera_pitch_degrees)
        view_direction = (
            horizontal * math.cos(pitch) + Gf.Vec3d(0.0, 0.0, -math.sin(pitch))
        ).GetNormalized()
        eye = Gf.Vec3f(*[float(value) for value in position])
        target = eye + Gf.Vec3f(*[float(value) * 10.0 for value in view_direction])
        orientation = lookat_to_quatf(target, eye, Gf.Vec3f(0.0, 0.0, 1.0))
        level_world = Gf.Matrix4d(1.0)
        level_world.SetRotateOnly(Gf.Quatd(orientation))
        level_world.SetTranslateOnly(position)
        ordered_ops = camera_xform.GetOrderedXformOps()
        transform_op = next(
            (
                op
                for op in ordered_ops
                if op.GetOpType() == UsdGeom.XformOp.TypeTransform
            ),
            None,
        )
        if transform_op is None:
            camera_xform.ClearXformOpOrder()
            transform_op = camera_xform.AddTransformOp(UsdGeom.XformOp.PrecisionDouble)
        transform_op.Set(level_world * mount_world.GetInverse())
        self._pump_updates(2)

    def _world_pose(self, prim_path: str) -> dict[str, list[float]]:
        from pxr import Usd, UsdGeom

        prim = self.stage.GetPrimAtPath(prim_path)
        world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        translation = world.ExtractTranslation()
        quaternion = world.ExtractRotationQuat()
        imaginary = quaternion.GetImaginary()
        return {
            "position_m": [float(value) for value in translation],
            "orientation_wxyz": [
                float(quaternion.GetReal()),
                float(imaginary[0]),
                float(imaginary[1]),
                float(imaginary[2]),
            ],
        }

    def _pump_updates(self, count: int) -> None:
        if self.update_callback is None:
            return
        for _ in range(max(0, count)):
            self.update_callback()

    def _wait_for_camera_render(self) -> None:
        """Wait for this camera's render product using Kit's async engine."""

        import omni.replicator.core as rep

        # A regular Kit update is not guaranteed to render an off-screen
        # product.  Replicator's synchronous step explicitly renders every
        # attached product and is the supported standalone/headless path.
        for _ in range(3):
            rep.orchestrator.step(
                delta_time=0.0,
                rt_subframes=4,
                pause_timeline=False,
            )
            pixels = self._camera.get_rgba(device="cpu")
            if pixels is not None and int(getattr(pixels, "size", 0)) > 0:
                return

        import omni.kit.async_engine
        import omni.syntheticdata

        coroutine = omni.syntheticdata.sensors.next_render_simulation_async(
            self._camera.get_render_product_path(),
            2,
        )
        simulation_app = getattr(self.update_callback, "__self__", None)
        run_coroutine = getattr(simulation_app, "run_coroutine", None)
        if callable(run_coroutine):
            run_coroutine(coroutine)
            return
        future = omni.kit.async_engine.run_coroutine(coroutine)
        while not future.done():
            if self.update_callback is None:
                raise RuntimeError("camera render wait requires a Kit update callback")
            self.update_callback()
        future.result()
