from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication

from gui.panels.queue_panel import QueuePanel
from models.fooocus_request import FooocusRequest
from models.generation_job import GenerationJob, GenerationJobStatus


def make_job(job_id: int) -> GenerationJob:
    request = FooocusRequest(
        prompt=f"test {job_id}",
        styles=[],
        width=1024,
        height=768,
    )
    return GenerationJob(job_id=job_id, request=request)


def main() -> None:
    print("=== Queue Progress Tests ===")
    app = QApplication.instance() or QApplication([])
    panel = QueuePanel()

    jobs = [make_job(1), make_job(2), make_job(3)]
    for job in jobs:
        panel.jobs.addItem(panel._format_job(job))

    panel.progress.setRange(0, 3)
    panel._total_jobs = 3

    panel.update_progress(1, 3)
    assert panel.progress.value() == 0
    assert panel.progress_label.text() == "0 / 3"
    print("Running job does not count as completed: OK")

    jobs[0].status = GenerationJobStatus.RUNNING
    panel.update_job_status(jobs[0])
    assert panel.current_job_label.text() == "Current: #1 — RUNNING"
    assert panel.progress.value() == 0
    assert panel.progress.maximum() == 3000
    print("Current job display and time-based scale: OK")

    jobs[0].status = GenerationJobStatus.COMPLETED
    panel.update_job_status(jobs[0])
    assert panel.progress.value() == 1
    assert panel.progress.maximum() == 3
    assert panel.progress_label.text() == "1 / 3"
    assert panel.current_job_label.text() == "Current: #1 — COMPLETED"
    print("Completed job advances progress: OK")

    jobs[1].status = GenerationJobStatus.RUNNING
    panel.update_job_status(jobs[1])
    assert 1000 < panel.progress.value() < 2000
    assert panel.progress.maximum() == 3000
    assert panel.progress_label.text() == "1 / 3"
    assert panel.current_job_label.text() == "Current: #2 — RUNNING"
    print("Second running job keeps completed count: OK")

    # Deterministic check that the overall bar really moves continuously
    # inside the current job's 1/3 slice.
    panel._job_estimates[jobs[1].job_id] = 10.0
    panel._current_job_started_at = time.monotonic() - 5.0
    panel._update_time_based_progress()
    assert 1000 < panel.progress.value() < 2000
    print("Time-based interpolation: OK")

    print("\n=== ALL QUEUE PROGRESS TESTS PASSED ===")


if __name__ == "__main__":
    main()