from __future__ import annotations

from collections import deque

from models.generation_job import (
    GenerationJob,
    GenerationJobStatus,
)


class GenerationQueue:
    """FIFO queue for generation jobs."""

    def __init__(self) -> None:
        self._jobs: deque[GenerationJob] = deque()
        self._closed = False

    # ------------------------------------------------------------------
    # Queue state
    # ------------------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        """Return whether no further jobs may be added."""
        return self._closed

    @property
    def has_jobs(self) -> bool:
        """Return whether jobs are currently waiting in the queue."""
        return bool(self._jobs)

    @property
    def jobs(self) -> list[GenerationJob]:
        """Return a snapshot of all currently queued jobs."""
        return list(self._jobs)

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def add(
        self,
        job: GenerationJob,
    ) -> None:
        """
        Add a job to the FIFO queue.

        Raises:
            RuntimeError: If the queue has already been closed.
        """

        if self._closed:
            raise RuntimeError(
                "Cannot add a job to a closed generation queue."
            )

        self._jobs.append(
            job
        )

    def next(
        self,
    ) -> GenerationJob | None:
        """Remove and return the next FIFO job."""

        if not self._jobs:
            return None

        return self._jobs.popleft()

    def close(self) -> None:
        """
        Close the queue for further job additions.

        Existing pending jobs remain available for processing.
        """

        self._closed = True

    def clear(self) -> None:
        """Clear all pending jobs and reopen the queue."""

        self._jobs.clear()
        self._closed = False

    def cancel_pending(self) -> list[GenerationJob]:
        """
        Cancel all jobs that are still waiting in the queue.

        The currently running job is not part of this method because
        it has already been removed from the FIFO queue and is handled
        by GenerationWorker / GenerationService.
        """

        cancelled_jobs = list(
            self._jobs
        )

        self._jobs.clear()

        for job in cancelled_jobs:
            job.status = (
                GenerationJobStatus.CANCELLED
            )

        return cancelled_jobs

    # ------------------------------------------------------------------
    # Collection protocol
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(
            self._jobs
        )