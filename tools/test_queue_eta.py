from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Allow this test to be run directly via:
#   python tools\\test_queue_eta.py
# from the project root.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication

from models.fooocus_request import FooocusRequest
from models.generation_job import GenerationJob, GenerationJobStatus
from services.generation_queue import GenerationQueue
from gui.panels.queue_panel import QueuePanel
from services.runtime_estimator import RuntimeEstimator


def main() -> None:
    print("=== Queue ETA Tests ===")

    app = QApplication.instance() or QApplication([])

    queue = GenerationQueue()
    queue.add(
        GenerationJob(
            job_id=1,
            request=FooocusRequest(
                styles=[],
                width=1024,
                height=768,
            ),
        )
    )
    queue.add(
        GenerationJob(
            job_id=2,
            request=FooocusRequest(
                styles=[],
                width=1024,
                height=768,
            ),
        )
    )

    panel = QueuePanel()
    panel.set_queue(queue)

    expected = 2 * RuntimeEstimator.estimate_image(
        1024,
        768,
    ).seconds

    assert abs(
        panel._job_estimates[1] - expected / 2
    ) < 0.001
    assert abs(
        panel._job_estimates[2] - expected / 2
    ) < 0.001
    assert f"{panel._format_duration(expected)}" in panel.remaining_label.text()
    assert panel.estimate_label.text().startswith("Estimated: ~")
    original_estimate = panel.estimate_label.text()
    print("Initial fixed estimate: OK")

    # Simulate a running experiment.  The displayed Estimate must stay
    # unchanged while Remaining/Ahead/Behind is refreshed every second.
    panel._experiment_started_at = time.monotonic() - 5.0
    panel._current_job_id = 1
    panel._current_job_started_at = panel._experiment_started_at

    remaining = panel._remaining_seconds()
    assert (
        expected - 6.0
        < remaining
        < expected - 4.0
    )
    panel._refresh_remaining_time()

    assert panel.estimate_label.text() == original_estimate
    assert (
        "Ahead by" in panel.remaining_label.text()
        or "Behind by" in panel.remaining_label.text()
    )
    print("Live ahead/behind display: OK")

    # A completed job still adapts the remaining projection, but never the
    # frozen original estimate.
    jobs = [queue.jobs[0], queue.jobs[1]]
    jobs[0].status = GenerationJobStatus.RUNNING
    panel.update_job_status(jobs[0])
    panel._current_job_started_at = time.monotonic() - 5.0
    jobs[0].status = GenerationJobStatus.COMPLETED
    panel.update_job_status(jobs[0])

    assert panel.estimate_label.text() == original_estimate
    assert panel._job_estimates[2] < RuntimeEstimator.estimate_image(
        1024,
        768,
    ).seconds
    print("Adaptive Remaining without changing Estimate: OK")

    jobs[1].status = GenerationJobStatus.RUNNING
    panel.update_job_status(jobs[1])
    panel._current_job_started_at = time.monotonic()
    jobs[1].status = GenerationJobStatus.COMPLETED
    panel.update_job_status(jobs[1])

    assert panel.estimate_label.text() == original_estimate
    assert "Actual Time:" in panel.remaining_label.text()
    assert "Finished —" in panel.remaining_label.text()
    print("Finished actual-vs-estimate display: OK")

    panel.close()
    app.quit()

    print("\n=== ALL QUEUE ETA TESTS PASSED ===")


if __name__ == "__main__":
    main()
