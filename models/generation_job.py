from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.fooocus_request import FooocusRequest


class GenerationJobStatus(str, Enum):
    """Status of one generation job."""

    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class GenerationJob:
    """One queued generation job."""

    job_id: int
    request: FooocusRequest
    status: GenerationJobStatus = GenerationJobStatus.WAITING
    error_message: str | None = None

    prompt_block_variant_id: str = ""