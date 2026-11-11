from __future__ import annotations

from models.fooocus_request import FooocusRequest
from services.generation_backend import GenerationBackend


class GenerationService:
    """High-level image generation service."""

    def __init__(self, backend: GenerationBackend):
        self.backend = backend

    def generate(self, request: FooocusRequest):

        if not self.backend.is_connected():

            print("Connecting to generation backend...")

            connected = self.backend.connect()

            print("connect() returned:", connected)
            print("Connected:", self.backend.is_connected())

            if not connected:
                raise RuntimeError("Could not connect to Fooocus.")

        print("=" * 80)
        print("Generate Request")
        print("=" * 80)
        print(request)
        print()
        print("Connected:", self.backend.is_connected())

        response = self.backend.generate(request)

        print()
        print(response)

        return response

    def cancel(self) -> bool:
        """Request cancellation of the currently running generation."""

        return self.backend.cancel()