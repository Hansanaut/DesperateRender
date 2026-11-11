from __future__ import annotations

import os
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication

from controllers.generation_worker import GenerationWorker
from gui.main_window import MainWindow
from models.fooocus_request import FooocusRequest
from models.generation_job import GenerationJob, GenerationJobStatus
from services.generation_queue import GenerationQueue


class BlockingGenerationService:
    """Deterministic fake backend for live queue tests."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[int] = []
        self._lock = threading.Lock()

    def generate(self, request):
        job_number = len(self.calls) + 1
        with self._lock:
            self.calls.append(job_number)
        self.started.set()

        # Job 1 is held until the test has requested pause.
        if job_number == 1:
            if not self.release.wait(timeout=5.0):
                raise TimeoutError("Timed out waiting to release job 1.")

        return object()

    def cancel(self):
        return True


class FakeStatus:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str) -> None:
        self.messages.append(message)


class FakeQueuePanel:
    def __init__(self) -> None:
        self.cancelling_calls = 0

    def set_cancelling_state(self) -> None:
        self.cancelling_calls += 1


class FakeWorker:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1


def make_job(job_id: int) -> GenerationJob:
    return GenerationJob(
        job_id=job_id,
        request=FooocusRequest(
            prompt=f"test {job_id}",
            styles=[],
            width=1024,
            height=768,
        ),
    )


def wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Timed out waiting for expected state.")
        time.sleep(0.01)


def test_pause_blocks_next_job() -> None:
    queue = GenerationQueue()
    jobs = [make_job(1), make_job(2), make_job(3)]
    for job in jobs:
        queue.add(job)
    queue.close()

    service = BlockingGenerationService()
    worker = GenerationWorker(service, queue)

    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()

    assert service.started.wait(timeout=5.0)
    worker.pause()

    # Let the current image finish. The critical assertion is that the
    # next job must NOT start while pause is active.
    service.release.set()

    wait_until(
        lambda: jobs[0].status is GenerationJobStatus.COMPLETED
    )
    time.sleep(0.2)

    assert service.calls == [1], (
        "A paused queue started a following job unexpectedly: "
        f"{service.calls}"
    )
    assert jobs[1].status is GenerationJobStatus.WAITING
    assert jobs[2].status is GenerationJobStatus.WAITING

    worker.resume()

    wait_until(
        lambda: jobs[1].status is GenerationJobStatus.COMPLETED
    )
    wait_until(
        lambda: jobs[2].status is GenerationJobStatus.COMPLETED
    )

    thread.join(timeout=5.0)
    assert not thread.is_alive()
    assert service.calls == [1, 2, 3]


def test_cancel_confirmation() -> None:
    """No leaves the run untouched; Yes, cancel runs existing cancel logic."""

    status = FakeStatus()
    queue_panel = FakeQueuePanel()
    worker = FakeWorker()

    # The method only needs these attributes; calling it unbound avoids
    # constructing the real QWidget/MainWindow in this unit test.
    class FakeWindow:
        pass

    window = FakeWindow()
    window.generation_worker = worker
    window.status = status
    window.queue_panel = queue_panel

    original_message_box = MainWindow.__dict__.get("_d3_test_message_box")

    class FakeDialog:
        last = None

        class Icon:
            Question = object()

        class ButtonRole:
            RejectRole = object()
            AcceptRole = object()

        def __init__(self, icon, title, text, parent=None):
            self.icon = icon
            self.title = title
            self.text = text
            self.parent = parent
            self.buttons = []
            self.clicked = None
            FakeDialog.last = self

        def addButton(self, text, role):
            button = (text, role)
            self.buttons.append(button)
            return button

        def setDefaultButton(self, button):
            self.default = button

        def exec(self):
            self.clicked = self.buttons[0]

        def clickedButton(self):
            return self.clicked

    original_qmessagebox = __import__(
        "gui.main_window",
        fromlist=["QMessageBox"],
    ).QMessageBox
    module = __import__("gui.main_window", fromlist=["QMessageBox"])
    module.QMessageBox = FakeDialog

    try:
        MainWindow.cancel_generation(window)

        dialog = FakeDialog.last
        assert dialog.title == "Cancel Generation"
        assert dialog.text == "Are you sure you want to cancel the generation?"
        assert [button[0] for button in dialog.buttons] == ["No", "Yes, cancel"]
        assert worker.cancel_calls == 0
        assert queue_panel.cancelling_calls == 0

        class YesDialog(FakeDialog):
            def exec(self):
                self.clicked = self.buttons[1]

        module.QMessageBox = YesDialog
        MainWindow.cancel_generation(window)

        dialog = YesDialog.last
        assert worker.cancel_calls == 1
        assert queue_panel.cancelling_calls == 1
        assert status.messages[-1] == "🟠 Cancelling generation..."

    finally:
        module.QMessageBox = original_qmessagebox


def main() -> None:
    print("=== D3 Live Queue Tests ===")
    app = QApplication.instance() or QApplication([])

    test_pause_blocks_next_job()
    print("Pause blocks unintended next-job start: OK")

    test_cancel_confirmation()
    print("Cancel confirmation dialog: OK")

    app.quit()
    print("=== ALL D3 LIVE QUEUE TESTS PASSED ===")


if __name__ == "__main__":
    main()
