from gradio_client import Client

from models.fooocus_request import FooocusRequest
from services.fooocus_runtime_inspector import FooocusRuntimeInspector
from services.fooocus_payload_builder import FooocusPayloadBuilder


FOOOCUS_URL = "http://127.0.0.1:7865"


def main() -> None:
    print("Connecting to Fooocus...")
    client = Client(FOOOCUS_URL)

    print("Inspecting runtime...")
    inspector = FooocusRuntimeInspector(FOOOCUS_URL)
    runtime_spec = inspector.inspect()

    print(f"Task creation fn_index: {runtime_spec.task_creation_fn_index}")
    print(f"Generation fn_index: {runtime_spec.generation_fn_index}")
    print(f"Input count: {runtime_spec.input_count}")

    print("Building payload...")

    request = FooocusRequest(
        prompt="PROMPTLAB GENERATION CHAIN TEST",
        negative_prompt="test negative prompt",
        seed="20260811",
        image_count=1,
    )

    builder = FooocusPayloadBuilder(runtime_spec)
    task_payload = builder.build(request)

    print(f"Payload length: {len(task_payload.data)}")

    # Dependency 67 has a Gradio State input at position 0.
    # gradio_client inserts that State automatically.
    if runtime_spec.inputs[0].component_type != "state":
        raise RuntimeError(
            "Expected currentTask State at RuntimeSpec payload index 0"
        )

    client_data = task_payload.data[1:]

    if len(client_data) != runtime_spec.input_count - 1:
        raise RuntimeError(
            f"Expected {runtime_spec.input_count - 1} client arguments, "
            f"got {len(client_data)}"
        )

    print("Calling task-creation dependency...")
    print(f"Client arguments: {len(client_data)}")
    print("State argument: inserted automatically by gradio_client")

    task_result = client.predict(
        *client_data,
        fn_index=runtime_spec.task_creation_fn_index,
    )

    print()
    print("=== TASK CREATION RESULT ===")
    print(f"Type: {type(task_result)}")
    print(f"Result: {task_result!r}")

    print()
    print("Calling generation dependency...")
    print(f"Generation fn_index: {runtime_spec.generation_fn_index}")
    print("Using same gradio_client session...")

    job = client.submit(
        fn_index=runtime_spec.generation_fn_index,
    )

    print("Generation job submitted.")
    print("Waiting for result...")

    generation_result = job.result()

    print()
    print("=== GENERATION RESULT ===")
    print(f"Type: {type(generation_result)}")
    print(f"Result: {generation_result!r}")


if __name__ == "__main__":
    main()