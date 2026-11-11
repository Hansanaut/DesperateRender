from __future__ import annotations

import time
from threading import Event, Lock

from models.image_generation_result import ImageGenerationResult

from PySide6.QtCore import QObject, Signal

from models.generation_job import (
    GenerationJob,
    GenerationJobStatus,
)
from services.generation_queue import GenerationQueue


class GenerationWorker(QObject):
    """Processes queued generation jobs sequentially."""

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int)
    job_status = Signal(object)
    completed = Signal()
    cancelled = Signal()
    paused = Signal()
    resumed = Signal()

    def __init__(
        self,
        generation_service,
        queue: GenerationQueue,
    ) -> None:
        super().__init__()

        self.generation_service = generation_service
        self.queue = queue

        self._cancel_requested = Event()
        self._pause_requested = Event()

        self._current_job: GenerationJob | None = None
        self._state_lock = Lock()

    # ------------------------------------------------------------------
    # Pause / Resume
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """
        Pause the generation queue.

        The currently running Fooocus job is allowed to finish.
        No following job will start until resume() is called.
        """

        if self.is_cancel_requested():
            return

        if self._pause_requested.is_set():
            return

        print(
            "GenerationWorker: pause requested."
        )

        self._pause_requested.set()

        self.paused.emit()

    def resume(self) -> None:
        """Resume a paused generation queue."""

        if self.is_cancel_requested():
            return

        if not self._pause_requested.is_set():
            return

        print(
            "GenerationWorker: resume requested."
        )

        self._pause_requested.clear()

        self.resumed.emit()

    def is_paused(self) -> bool:
        """Return whether the queue is currently paused."""

        return self._pause_requested.is_set()

    def _wait_if_paused(self) -> bool:
        """Wait until the queue is resumed or cancelled."""

        if not self.is_paused():
            return True

        print(
            "GenerationWorker: waiting while paused."
        )

        while self.is_paused():

            if self.is_cancel_requested():
                return False

            time.sleep(0.1)

        return not self.is_cancel_requested()

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """
        Request cancellation of the complete generation run.

        Pending jobs are cancelled immediately.

        The currently running job is cancelled through the generation
        service / Fooocus backend.
        """

        print(
            "GenerationWorker: cancellation requested."
        )

        self._cancel_requested.set()

        # Release a paused worker so that it can notice cancellation.
        self._pause_requested.clear()

        # Cancel all jobs which have not started yet.
        pending_jobs = self.queue.cancel_pending()

        for job in pending_jobs:

            print(
                f"GenerationWorker: cancelling pending job "
                f"#{job.job_id}"
            )

            self.job_status.emit(
                job
            )

        # Cancel the currently running backend job.
        with self._state_lock:
            current_job = self._current_job

        if current_job is not None:

            print(
                f"GenerationWorker: cancelling running job "
                f"#{current_job.job_id}"
            )

            try:

                cancelled = (
                    self.generation_service.cancel()
                )

                print(
                    "GenerationWorker: backend cancel returned "
                    f"{cancelled!r}"
                )

            except Exception as exc:

                print(
                    "GenerationWorker: backend cancellation "
                    f"failed: {exc}"
                )

    def is_cancel_requested(self) -> bool:
        """Return whether cancellation has been requested."""

        return self._cancel_requested.is_set()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Process all queued jobs."""

        total = len(
            self.queue
        )

        current = 0

        while True:

            # ----------------------------------------------------------
            # Check cancellation before starting another job.
            # ----------------------------------------------------------

            if self.is_cancel_requested():

                self.cancelled.emit()

                return

            # ----------------------------------------------------------
            # Pause between jobs.
            # ----------------------------------------------------------

            if not self._wait_if_paused():

                self.cancelled.emit()

                return

            # ----------------------------------------------------------
            # Get next job.
            # ----------------------------------------------------------

            job = self.queue.next()

            if job is None:

                if self.queue.is_closed:
                    break

                time.sleep(0.1)
                continue

            current += 1

            with self._state_lock:

                self._current_job = job

            # ----------------------------------------------------------
            # Check cancellation after removing the job from queue.
            # ----------------------------------------------------------

            if self.is_cancel_requested():

                job.status = (
                    GenerationJobStatus.CANCELLED
                )

                self.job_status.emit(
                    job
                )

                with self._state_lock:

                    self._current_job = None

                self.cancelled.emit()

                return

            # ----------------------------------------------------------
            # Mark job as running.
            # ----------------------------------------------------------

            job.status = (
                GenerationJobStatus.RUNNING
            )

            self.job_status.emit(
                job
            )

            self.progress.emit(
                current,
                total,
            )

            print(
                f"GenerationWorker: starting job "
                f"#{job.job_id}"
            )

            # ----------------------------------------------------------
            # Execute generation.
            # ----------------------------------------------------------

            try:

                result = (
                    self.generation_service.generate(
                        job.request
                    )
                )

                # ------------------------------------------------------
                # Cancellation may have happened while Fooocus was
                # generating.
                # ------------------------------------------------------

                if self.is_cancel_requested():

                    job.status = (
                        GenerationJobStatus.CANCELLED
                    )

                    self.job_status.emit(
                        job
                    )

                    with self._state_lock:

                        self._current_job = None

                    self.cancelled.emit()

                    return

                # ------------------------------------------------------
                # Successful generation.
                # ------------------------------------------------------

                job.status = (
                    GenerationJobStatus.COMPLETED
                )

                self.job_status.emit(
                    job
                )

                # Preserve the queue's durable Job# all the way to the Preview.
                # Each DR job produces exactly one image.
                if isinstance(result, ImageGenerationResult):
                    result = ImageGenerationResult(
                        images=result.images,
                        job_id=job.job_id,
                    )
                self.finished.emit(result)

                print(
                    f"GenerationWorker: job "
                    f"#{job.job_id} completed."
                )

            except Exception as exc:

                # ------------------------------------------------------
                # Cancellation usually causes job.result() to raise.
                # That must NOT become FAILED.
                # ------------------------------------------------------

                if self.is_cancel_requested():

                    job.status = (
                        GenerationJobStatus.CANCELLED
                    )

                    job.error_message = str(
                        exc
                    )

                    self.job_status.emit(
                        job
                    )

                    print(
                        f"GenerationWorker: job "
                        f"#{job.job_id} cancelled."
                    )

                    with self._state_lock:

                        self._current_job = None

                    self.cancelled.emit()

                    return

                # ------------------------------------------------------
                # Genuine generation failure.
                # ------------------------------------------------------

                job.status = (
                    GenerationJobStatus.FAILED
                )

                job.error_message = str(
                    exc
                )

                self.job_status.emit(
                    job
                )

                self.error.emit(
                    str(exc)
                )

                with self._state_lock:

                    self._current_job = None

                return

            finally:

                with self._state_lock:

                    if self._current_job is job:

                        self._current_job = None

            # ----------------------------------------------------------
            # Pause after the completed job.
            # ----------------------------------------------------------

            if self.is_paused():

                print(
                    "GenerationWorker: generation paused "
                    "after completed job."
                )

                if not self._wait_if_paused():

                    self.cancelled.emit()

                    return

        # ----------------------------------------------------------------
        # All jobs completed normally.
        # ----------------------------------------------------------------

        self.completed.emit()