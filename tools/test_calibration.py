from __future__ import annotations

import sys
from pathlib import Path

# Allow direct execution from the project root:
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.fooocus_request import FooocusRequest
from models.generation_job import GenerationJob
from services.calibration_profile import CalibrationPoint, CalibrationProfile
from services.runtime_estimator import RuntimeEstimator
from gui.panels.queue_panel import QueuePanel


def main() -> None:
    profile = CalibrationProfile.create(
        "http://127.0.0.1:7865",
        [
            CalibrationPoint(480, 320, 10.0, 100_000),
            CalibrationPoint(1024, 768, 77.7, 7_777_777),
            CalibrationPoint(2048, 2048, 100.0, 20_000_000),
        ],
    )

    restored = CalibrationProfile.from_json(profile.to_json())
    assert restored == profile
    assert restored.point_count == 3
    print("Calibration profile serialization: OK")

    RuntimeEstimator.set_calibration(profile)
    assert RuntimeEstimator.has_calibration()

    exact = RuntimeEstimator.estimate_image(1024, 768)
    assert abs(exact.seconds - 77.7) < 0.001
    assert exact.storage_bytes == 7_777_777
    print("Calibrated runtime interpolation: OK")

    middle = RuntimeEstimator.estimate_image(1280, 768)
    assert 77.7 < middle.seconds < 100.0
    assert 7_777_777 < middle.storage_bytes < 20_000_000
    print("Calibrated interpolation between measured points: OK")

    # This is the actual QueuePanel job-estimate path used by the live queue.
    job = GenerationJob(
        job_id=1,
        request=FooocusRequest(width=1024, height=768),
    )
    queue_panel = QueuePanel.__new__(QueuePanel)
    job_estimate = queue_panel._estimate_job_seconds(job)

    assert abs(job_estimate - 77.7) < 0.001
    print("Queue job estimate uses calibrated data: OK")
    print(f"Queue job estimate for 1024x768: {job_estimate:.3f} s")
    print("=== ALL CALIBRATION TESTS PASSED ===")

    RuntimeEstimator.set_calibration(None)


if __name__ == "__main__":
    main()
