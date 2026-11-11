from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageGenerationResult:
    """Result of an image generation operation."""

    images: tuple[str, ...]
    # Stable identity of the single generation job that produced this result.
    job_id: int | None = None