from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.image_generation_result import ImageGenerationResult
from services.generation_backend import GenerationBackend
from services.generation_service import GenerationService


class DummyBackend(GenerationBackend):
    """Minimal backend used to prove the orchestration layer is engine-agnostic."""

    def __init__(self) -> None:
        self.connected = False
        self.requests: list[object] = []
        self.cancelled = False

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def generate(self, request: object) -> ImageGenerationResult:
        self.requests.append(request)
        return ImageGenerationResult(images=("dummy.png",))

    def cancel(self) -> bool:
        self.cancelled = True
        return True


def main() -> None:
    backend = DummyBackend()
    service = GenerationService(backend)

    request = object()
    result = service.generate(request)

    assert backend.is_connected() is True
    assert backend.requests == [request]
    assert result.images == ("dummy.png",)
    assert service.cancel() is True
    assert backend.cancelled is True

    print("GenerationBackend abstraction: OK")


if __name__ == "__main__":
    main()
