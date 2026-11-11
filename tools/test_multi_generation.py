from __future__ import annotations
from services.generation_queue import GenerationQueue
from models.generation_job import GenerationJob


from models.experiment import Experiment, PromptSlot
from services.experiment.matrix_builder import MatrixBuilder
from services.generation.configuration_adapter import (
    GenerationConfigurationAdapter,
)
from services.generation_service import GenerationService
from controllers.connection_controller import ConnectionController
from controllers.generation_worker import GenerationWorker


def main() -> None:
    print("=" * 80)
    print("PromptLAB – Multi Generation Test")
    print("=" * 80)

    # --------------------------------------------------
    # 1. Build test experiment
    # --------------------------------------------------

    experiment = Experiment(
        experiment_id="multi-generation-test",
    )

    experiment.positive_prompts = [
        PromptSlot(
            1,
            "car, traffic, road yellow",
        ),
        PromptSlot(
            2,
            "aircraft carrier in a bath tube",
        ),
    ]

    experiment.negative_prompts = [
        PromptSlot(
            1,
            "forest",
        ),
    ]

    experiment.styles = [
        "Fooocus V2",
        "Fooocus Enhance",
    ]

    # Use a small, valid PromptLAB resolution.
    experiment.generation.width = 480
    experiment.generation.height = 320

    # --------------------------------------------------
    # 2. Build matrix
    # --------------------------------------------------

    configurations = MatrixBuilder.build_experiment(
        experiment
    )

    print()
    print(
        f"Experiment configurations: {len(configurations)}"
    )

    assert len(configurations) == 4, (
        "Expected 4 configurations "
        "(2 prompts × 2 styles), "
        f"got {len(configurations)}"
    )

    # --------------------------------------------------
    # 3. Convert configurations to Fooocus requests
    # --------------------------------------------------

    requests = []

    for configuration in configurations:
        request = (
            GenerationConfigurationAdapter.to_fooocus_request(
                configuration
            )
        )

        requests.append(request)

        print()
        print(
            f"Configuration "
            f"{configuration.configuration_id}:"
        )
        print(
            f"  Prompt: {request.prompt}"
        )
        print(
            f"  Style:  {request.styles}"
        )
        print(
            f"  Size:   "
            f"{request.width}x{request.height}"
        )

    assert len(requests) == 4, (
        "Expected 4 Fooocus requests, "
        f"got {len(requests)}"
    )

    # --------------------------------------------------
    # 4. Connect to Fooocus
    # --------------------------------------------------

    connection_controller = ConnectionController()

    print()
    print("Connecting to Fooocus...")

    if not connection_controller.connect():
        raise RuntimeError(
            "Could not connect to Fooocus."
        )

    print("Connected to Fooocus.")

    generation_service = GenerationService(
        connection_controller.client
    )

    # --------------------------------------------------
    # 5. Run multiple requests through the worker
    # --------------------------------------------------

    queue = GenerationQueue()

    for job_id, request in enumerate(requests, start=1):
        queue.add(
            GenerationJob(
                job_id=job_id,
                request=request,
            )
        )

    worker = GenerationWorker(
        generation_service,
        queue,
    )

    results = []
    errors = []

    def on_finished(result) -> None:
        results.append(result)

        print()
        print(
            f"Generation result "
            f"{len(results)}/4:"
        )

        for image in result.images:
            print(f"  {image}")

    def on_progress(
        current: int,
        total: int,
    ) -> None:
        print(
            f"Progress: {current}/{total}"
        )

    def on_error(message: str) -> None:
        errors.append(message)

        print()
        print("ERROR:")
        print(message)

    def on_completed() -> None:
        print()
        print("Worker completed.")

    worker.finished.connect(on_finished)
    worker.progress.connect(on_progress)
    worker.error.connect(on_error)
    worker.completed.connect(on_completed)

    print()
    print("=" * 80)
    print("Starting multi-generation worker")
    print("=" * 80)

    # The worker itself is normally executed in a QThread.
    # For this isolated test we call run() directly.
    worker.run()

    # --------------------------------------------------
    # 6. Validate results
    # --------------------------------------------------

    if errors:
        raise RuntimeError(
            "Multi-generation test failed:\n"
            + "\n".join(errors)
        )

    assert len(results) == 4, (
        "Expected 4 generation results, "
        f"got {len(results)}"
    )

    total_images = sum(
        len(result.images)
        for result in results
    )

    assert total_images == 4, (
        "Expected 4 generated images, "
        f"got {total_images}"
    )

    print()
    print("=" * 80)
    print("=== MULTI GENERATION TEST PASSED ===")
    print("=" * 80)

    connection_controller.disconnect()


if __name__ == "__main__":
    main()