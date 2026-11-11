from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.image_generation_result import ImageGenerationResult


class GenerationBackend(ABC):
    """Backend contract used by DESPERATE RENDER's generation layer.

    The orchestration layer depends on this interface rather than on a
    concrete image-generation engine. Backend-specific request conversion,
    runtime inspection and transport details stay inside the implementation.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the configured generation backend."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the generation backend."""
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the backend is currently connected."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, request: Any) -> ImageGenerationResult:
        """Generate images for one backend request."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> bool:
        """Request cancellation of the active generation, if supported."""
        raise NotImplementedError
