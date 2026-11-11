from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from models.generation_configuration import GenerationConfiguration
from services.calibration_profile import CalibrationProfile


@dataclass(frozen=True)
class RuntimeEstimate:
    """Estimated runtime and storage for one generated image."""

    seconds: float
    storage_bytes: int


class RuntimeEstimator:
    """Estimate runtime/storage from the active hardware calibration."""

    # Legacy fallback only. New installations should calibrate before use.
    LEGACY_CALIBRATION = (
        (480, 320, 12.8638, 162),
        (1024, 768, 22.3236, 1154),
        (1536, 1024, 39.0188, 2348),
        (2048, 2048, 122.3866, 4834),
    )

    _profile: CalibrationProfile | None = None

    @classmethod
    def set_calibration(cls, profile: CalibrationProfile | None) -> None:
        cls._profile = profile

    @classmethod
    def has_calibration(cls) -> bool:
        return cls._profile is not None and cls._profile.point_count >= 2

    @classmethod
    def estimate_image(cls, width: int, height: int) -> RuntimeEstimate:
        pixels = max(1, int(width)) * max(1, int(height))

        if cls.has_calibration():
            points = sorted(
                (
                    point.width * point.height,
                    point.seconds,
                    point.storage_bytes,
                )
                for point in cls._profile.points
            )
        else:
            points = sorted(
                (width * height, seconds, storage_kib * 1024)
                for width, height, seconds, storage_kib in cls.LEGACY_CALIBRATION
            )

        time_points = [(p[0], p[1]) for p in points]
        if cls.has_calibration() and len(time_points) >= 3:
            # The current 3-point calibration defines a second-order
            # render-time curve.  Evaluate it only inside the measured range;
            # outside that range, clamp to the nearest measured endpoint
            # instead of making an unsafe quadratic extrapolation.
            seconds = cls._quadratic_interpolate(pixels, time_points[:3])
        else:
            seconds = cls._interpolate(pixels, time_points)

        # File size remains linearly interpolated.  PNG compression does not
        # have the same predictable curvature as render time.
        storage = cls._interpolate(
            pixels,
            [(p[0], p[2]) for p in points],
        )

        return RuntimeEstimate(
            seconds=seconds,
            storage_bytes=max(0, int(round(storage))),
        )

    @classmethod
    def estimate_configuration(cls, configuration: GenerationConfiguration) -> RuntimeEstimate:
        return cls.estimate_image(configuration.width, configuration.height)

    @classmethod
    def estimate_configurations(cls, configurations: Sequence[GenerationConfiguration]) -> RuntimeEstimate:
        total_seconds = 0.0
        total_storage = 0
        for configuration in configurations:
            estimate = cls.estimate_configuration(configuration)
            total_seconds += estimate.seconds
            total_storage += estimate.storage_bytes
        return RuntimeEstimate(total_seconds, total_storage)

    @staticmethod
    def _quadratic_interpolate(
        pixels: int,
        points: list[tuple[int, float]],
    ) -> float:
        """Evaluate the quadratic through the three calibration points."""
        if len(points) < 3:
            return RuntimeEstimator._interpolate(pixels, points)

        (x1, y1), (x2, y2), (x3, y3) = points[:3]
        if len({x1, x2, x3}) < 3:
            return RuntimeEstimator._interpolate(pixels, points)

        # Never extrapolate the fitted curve beyond the calibrated range.
        if pixels <= x1:
            return y1
        if pixels >= x3:
            return y3

        x = float(pixels)
        l1 = ((x - x2) * (x - x3)) / ((x1 - x2) * (x1 - x3))
        l2 = ((x - x1) * (x - x3)) / ((x2 - x1) * (x2 - x3))
        l3 = ((x - x1) * (x - x2)) / ((x3 - x1) * (x3 - x2))
        return y1 * l1 + y2 * l2 + y3 * l3

    @staticmethod
    def _interpolate(pixels: int, points: list[tuple[int, float]]) -> float:
        if len(points) == 1:
            return points[0][1]
        if pixels <= points[0][0]:
            return points[0][1]
        if pixels >= points[-1][0]:
            return points[-1][1]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 <= pixels <= x2:
                fraction = (pixels - x1) / (x2 - x1)
                return y1 + fraction * (y2 - y1)
        return points[-1][1]
