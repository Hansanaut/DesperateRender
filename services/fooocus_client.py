from __future__ import annotations

import json
import os
import time
from typing import Any

from gradio_client import Client

from models.fooocus_request import FooocusRequest
from models.image_generation_result import ImageGenerationResult
from services.fooocus_payload_builder import FooocusPayloadBuilder
from services.fooocus_result_adapter import FooocusResultAdapter
from services.fooocus_runtime_inspector import FooocusRuntimeInspector
from services.generation_backend import GenerationBackend


class FooocusClient(GenerationBackend):
    """Communicate with a running Fooocus instance through Gradio."""

    def __init__(self, url: str = "http://127.0.0.1:7865"):
        self.url = url.rstrip("/")

        self.client: Client | None = None
        self.api = None
        self.runtime_spec = None
        self.connect_benchmark = None
        self.generation_benchmark = None

        # The currently running Gradio job.
        #
        # This reference is required so that PromptLAB can request
        # cancellation of the actual Fooocus generation.
        self._active_job = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Connect to Fooocus and inspect its current runtime."""

        try:
            connect_start = time.perf_counter()

            print("Connecting to Fooocus...")

            client_start = time.perf_counter()
            self.client = Client(self.url)
            client_ms = (time.perf_counter() - client_start) * 1000.0

            print("Inspecting Fooocus runtime...")

            inspection_start = time.perf_counter()
            inspector = FooocusRuntimeInspector(self.url)
            self.runtime_spec = inspector.inspect()
            inspection_ms = (time.perf_counter() - inspection_start) * 1000.0

            total_ms = (time.perf_counter() - connect_start) * 1000.0

            self.connect_benchmark = {
                "client_ms": client_ms,
                "inspection_ms": inspection_ms,
                "total_ms": total_ms,
            }

            print(
                "Runtime inspected:"
                f" task_creation={self.runtime_spec.task_creation_fn_index},"
                f" generation={self.runtime_spec.generation_fn_index},"
                f" inputs={len(self.runtime_spec.inputs)}"
            )

            print("Fooocus connect benchmark:")
            print(f"  client={client_ms:.1f} ms")
            print(f"  inspection={inspection_ms:.1f} ms")
            print(f"  total={total_ms:.1f} ms")

            return True

        except Exception:
            import traceback

            traceback.print_exc()

            self.client = None
            self.api = None
            self.runtime_spec = None
            self._active_job = None
            self.connect_benchmark = None
            self.generation_benchmark = None

            return False

    def disconnect(self) -> None:
        """Disconnect from Fooocus."""

        self._active_job = None
        self.client = None
        self.api = None
        self.runtime_spec = None
        self.connect_benchmark = None
        self.generation_benchmark = None

    def is_connected(self) -> bool:
        """Return whether a Fooocus client is connected."""

        return self.client is not None

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self) -> bool:
        """
        Request cancellation of the currently active Gradio job.

        Returns True when a cancellation request was submitted
        successfully to the active Gradio job.
        """

        job = self._active_job

        if job is None:
            print(
                "Cancel requested, but no active Fooocus job exists."
            )

            return False

        cancel_method = getattr(
            job,
            "cancel",
            None,
        )

        if not callable(cancel_method):
            print(
                "Cancel requested, but the active Gradio job "
                "does not provide cancel()."
            )

            return False

        try:
            print(
                "Requesting cancellation of active Fooocus job..."
            )

            result = cancel_method()

            print(
                f"Fooocus job.cancel() returned: {result!r}"
            )

            # gradio_client may return None even though the request
            # has been sent successfully. Therefore the existence of
            # a callable cancel method and the absence of an exception
            # are considered a successful cancellation request.
            return True

        except Exception as exc:
            print(
                "Fooocus job cancellation failed:"
            )
            print(
                exc
            )

            return False

    # ------------------------------------------------------------------
    # Runtime / Gradio inspection
    # ------------------------------------------------------------------

    def view_api(self):
        """Return the Gradio API description."""

        if self.client is None:
            raise RuntimeError("Not connected.")

        return self.client.view_api(return_format="dict")

    def config(self):
        """Return the current Gradio configuration."""

        if self.client is None:
            raise RuntimeError("Not connected.")

        return self.client.config

    def get_api(self):
        """Return the cached API information."""

        return self.api

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        request: FooocusRequest,
    ) -> ImageGenerationResult:
        """Generate images through the dynamically inspected Fooocus chain."""

        if self.client is None:
            raise RuntimeError("Not connected.")

        if self.runtime_spec is None:
            raise RuntimeError(
                "Fooocus runtime has not been inspected."
            )

        # --------------------------------------------------------------
        # Build task payload from current runtime defaults.
        # --------------------------------------------------------------

        builder = FooocusPayloadBuilder(
            self.runtime_spec
        )

        payload = builder.build(
            request
        )

        if len(payload.data) != len(
            self.runtime_spec.inputs
        ):
            raise RuntimeError(
                "Payload length does not match the inspected "
                "Fooocus runtime: "
                f"{len(payload.data)} != "
                f"{len(self.runtime_spec.inputs)}"
            )

        # Gradio Client automatically inserts the State input.
        #
        # The runtime payload contains currentTask at index 0.
        # Client.predict()/submit() therefore receive the remaining
        # 152 arguments.
        client_data = payload.data[1:]

        expected_client_arguments = (
            len(self.runtime_spec.inputs) - 1
        )

        if len(client_data) != expected_client_arguments:
            raise RuntimeError(
                "Unexpected Gradio client argument count: "
                f"{len(client_data)} != "
                f"{expected_client_arguments}"
            )

        # --------------------------------------------------------------
        # Dependency 67: create currentTask.
        # --------------------------------------------------------------

        generation_start = time.perf_counter()

        print(
            "Calling task-creation dependency "
            f"{self.runtime_spec.task_creation_fn_index}..."
        )

        task_start = time.perf_counter()
        task_result = self.client.predict(
            *client_data,
            fn_index=self.runtime_spec.task_creation_fn_index,
        )

        task_ms = (time.perf_counter() - task_start) * 1000.0

        print(
            f"Task creation result: {task_result!r}"
        )

        # --------------------------------------------------------------
        # Dependency 68: execute generation.
        #
        # IMPORTANT:
        # The same gradio_client.Client instance must be used here so
        # that the currentTask state belongs to the same Gradio session.
        # --------------------------------------------------------------

        generation_fn_index = (
            self.runtime_spec.generation_fn_index
        )

        print(
            "Calling generation dependency "
            f"{generation_fn_index}..."
        )

        endpoint = self.client.endpoints[
            generation_fn_index
        ]

        # gradio_client 0.5.0 expects the gallery output in an older
        # serialized format. Fooocus currently returns FileData-like
        # dictionaries instead:
        #
        # {
        #     "name": "...png",
        #     "data": None,
        #     "is_file": True,
        # }
        #
        # Therefore the raw generator output is intentionally passed
        # through unchanged. FooocusResultAdapter handles it afterwards.
        original_process_predictions = (
            endpoint.process_predictions
        )

        endpoint.process_predictions = (
            lambda *predictions: predictions
        )

        try:
            job = self.client.submit(
                fn_index=generation_fn_index,
            )

            # Store the actual Gradio job so that cancel() can access it.
            self._active_job = job

            print(
                "Generation job submitted."
            )

            print(
                "Waiting for result..."
            )

            generation_wait_start = time.perf_counter()
            raw_result = job.result()
            generation_wait_ms = (
                time.perf_counter() - generation_wait_start
            ) * 1000.0

        finally:
            # The job is no longer active after result() returns or raises.
            self._active_job = None

            endpoint.process_predictions = (
                original_process_predictions
            )

        # --------------------------------------------------------------
        # Convert Fooocus-specific result into PromptLAB's neutral
        # ImageGenerationResult.
        # --------------------------------------------------------------

        result_adapter = FooocusResultAdapter()

        result = result_adapter.adapt(
            raw_result
        )

        file_sizes = []
        for image_path in result.images:
            try:
                file_sizes.append(
                    os.path.getsize(image_path)
                )
            except OSError:
                file_sizes.append(None)

        total_ms = (time.perf_counter() - generation_start) * 1000.0
        self.generation_benchmark = {
            "task_creation_ms": task_ms,
            "generation_wait_ms": generation_wait_ms,
            "total_ms": total_ms,
            "image_count": len(result.images),
            "file_sizes_bytes": file_sizes,
        }

        if not result.images:
            raise RuntimeError(
                "Fooocus generation completed but returned no images."
            )

        print("Fooocus generation benchmark:")
        print(f"  task_creation={task_ms:.1f} ms")
        print(f"  generation_wait={generation_wait_ms:.1f} ms")
        print(f"  total={total_ms:.1f} ms")
        print(f"  images={len(result.images)}")

        print(
            f"Generated images: {len(result.images)}"
        )

        for image_path in result.images:
            print(
                f"  {image_path}"
            )

        return result

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    @staticmethod
    def pretty(
        obj: Any,
    ) -> str:
        """Return an object as readable JSON."""

        return json.dumps(
            obj,
            indent=4,
            ensure_ascii=False,
            default=str,
        )