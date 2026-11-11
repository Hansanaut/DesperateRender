from __future__ import annotations

import json

from gradio_client import Client

from models.fooocus_request import FooocusRequest
from services.fooocus_payload_builder import FooocusPayloadBuilder
from services.fooocus_runtime_inspector import FooocusRuntimeInspector


FOOOCUS_URL = "http://127.0.0.1:7865"


def describe(value, depth=0, max_depth=4):
    """Return a compact structural description without dumping huge data."""
    if depth > max_depth:
        return f"<{type(value).__name__}>"

    if isinstance(value, dict):
        return {
            key: describe(val, depth + 1, max_depth)
            for key, val in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            describe(item, depth + 1, max_depth)
            for item in value[:5]
        ] + (["..."] if len(value) > 5 else [])

    if isinstance(value, str):
        if len(value) > 200:
            return value[:200] + "...<truncated>"
        return value

    return value


def main() -> None:
    print("Connecting to Fooocus...")
    client = Client(FOOOCUS_URL)

    print("Inspecting runtime...")
    runtime_spec = FooocusRuntimeInspector(FOOOCUS_URL).inspect()

    print(f"Task creation fn_index: {runtime_spec.task_creation_fn_index}")
    print(f"Generation fn_index: {runtime_spec.generation_fn_index}")
    print(f"Input count: {runtime_spec.input_count}")

    request = FooocusRequest(
        prompt="PROMPTLAB RAW RESULT TEST",
        negative_prompt="test negative prompt",
        seed="20260811",
        image_count=1,
    )

    print("Building payload...")
    payload = FooocusPayloadBuilder(runtime_spec).build(request)

    client_data = payload.data[1:]

    print(f"Client arguments: {len(client_data)}")
    print("Calling task-creation dependency...")

    task_result = client.predict(
        *client_data,
        fn_index=runtime_spec.task_creation_fn_index,
    )

    print(f"Task creation result: {task_result!r}")

    print()
    print("Calling generation dependency...")
    print(f"Generation fn_index: {runtime_spec.generation_fn_index}")

    endpoint = client.endpoints[runtime_spec.generation_fn_index]

    # Keep Gradio's normal submit()/WebSocket/session handling,
    # but bypass only the incompatible result deserialization.
    original_process_predictions = endpoint.process_predictions
    endpoint.process_predictions = lambda *predictions: predictions

    try:
        print("Generation job submitted...")
        job = client.submit(
            fn_index=runtime_spec.generation_fn_index,
        )

        print("Waiting for result...")
        raw_predictions = job.result()
    finally:
        endpoint.process_predictions = original_process_predictions

    print()
    print("=== RAW PREDICTIONS ===")
    print(f"Type: {type(raw_predictions)}")
    print(f"Count: {len(raw_predictions)}")

    for index, value in enumerate(raw_predictions):
        print()
        print(f"--- OUTPUT {index} ---")
        print(f"Python type: {type(value)}")
        print("Structure:")

        print(
            json.dumps(
                describe(value),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )


if __name__ == "__main__":
    main()