from __future__ import annotations

from models.generation_configuration import GenerationConfiguration
from services.calibration_profile import CalibrationPoint, CalibrationProfile
from services.runtime_estimator import RuntimeEstimator


def main() -> None:
    print("=== Runtime Estimator Tests ===")

    RuntimeEstimator.set_calibration(None)
    first = RuntimeEstimator.estimate_image(480, 320)
    assert abs(first.seconds - 12.8638) < 0.001
    assert first.storage_bytes == 162 * 1024
    print("Legacy calibration 480x320: OK")

    profile = CalibrationProfile.create(
        "http://127.0.0.1:7865",
        [
            CalibrationPoint(1024, 768, 25.483, 803 * 1024),
            CalibrationPoint(1536, 1024, 38.160, 1300 * 1024),
            CalibrationPoint(2048, 2048, 122.223, 3700 * 1024),
        ],
    )
    RuntimeEstimator.set_calibration(profile)

    for width, height, expected in (
        (1024, 768, 25.483),
        (1536, 1024, 38.160),
        (2048, 2048, 122.223),
    ):
        actual = RuntimeEstimator.estimate_image(width, height).seconds
        assert abs(actual - expected) < 0.001
    print("Quadratic calibration points: OK")

    middle = RuntimeEstimator.estimate_image(1280, 768)
    assert 25.483 < middle.seconds < 38.160
    assert abs(middle.seconds - 28.1095716) < 0.001
    print("Quadratic interpolation 1280x768: OK")

    # The quadratic is never extrapolated beyond the measured range.
    assert RuntimeEstimator.estimate_image(480, 320).seconds == 25.483
    assert RuntimeEstimator.estimate_image(4096, 4096).seconds == 122.223
    print("Quadratic endpoint clamping: OK")

    configurations = [
        GenerationConfiguration(configuration_id=1, width=1024, height=768),
        GenerationConfiguration(configuration_id=2, width=1536, height=1024),
    ]
    total = RuntimeEstimator.estimate_configurations(configurations)
    assert abs(total.seconds - (25.483 + 38.160)) < 0.001
    print("Configuration total: OK")

    print("\n=== ALL RUNTIME ESTIMATOR TESTS PASSED ===")


if __name__ == "__main__":
    main()
