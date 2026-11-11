from gradio_client import Client

from models.fooocus_request import FooocusRequest
from services.fooocus_runtime_inspector import FooocusRuntimeInspector
from services.fooocus_payload_builder import FooocusPayloadBuilder


FOOOCUS_URL = "http://127.0.0.1:7865"

TEST_RESOLUTIONS = [
    (200, 296),
    (200, 300),
    (200, 304),
]


def main() -> None:
    print("Connecting to Fooocus...")
    client = Client(FOOOCUS_URL)

    print("Inspecting runtime...")
    inspector = FooocusRuntimeInspector(FOOOCUS_URL)
    runtime_spec = inspector.inspect()

    width_spec = next(
        spec for spec in runtime_spec.inputs
        if spec.label == "Forced Overwrite of Generating Width"
    )

    height_spec = next(
        spec for spec in runtime_spec.inputs
        if spec.label == "Forced Overwrite of Generating Height"
    )

    print(
        f"Width component:  index {width_spec.payload_index}, "
        f"component {width_spec.component_id}"
    )
    print(
        f"Height component: index {height_spec.payload_index}, "
        f"component {height_spec.component_id}"
    )

    builder = FooocusPayloadBuilder(runtime_spec)

    print()
    print("=" * 60)
    print("CUSTOM RESOLUTION TEST")
    print("=" * 60)

    for width, height in TEST_RESOLUTIONS:
        print()
        print(f"Testing {width} x {height} ...")

        request = FooocusRequest(
            prompt=f"PromptLAB resolution test {width}x{height}",
            negative_prompt="",
            seed=8247122344241169659,
            image_count=1,
            width=width,
            height=height,
        )

        task_payload = builder.build(request)

        client_data = task_payload.data[1:]

        try:
            print("  Creating Fooocus task...")

            task_result = client.predict(
                *client_data,
                fn_index=runtime_spec.task_creation_fn_index,
            )

            print(f"  Task result: {task_result!r}")
            print(f"  Task result type: {type(task_result)}")
            print("  Starting generation...")

            client.predict(
                fn_index=runtime_spec.generation_fn_index,
            )

            print(f"  Generation result: {result!r}")
            print(f"  >>> ACCEPTED: {width} x {height}")

        except Exception as exc:
            print(f"  >>> REJECTED: {width} x {height}")
            print(f"  Error: {type(exc).__name__}: {exc}")

    print()
    print("=" * 60)
    print("TEST FINISHED")
    print("=" * 60)


if __name__ == "__main__":
    main()