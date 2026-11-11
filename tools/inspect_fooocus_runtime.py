"""Manual, read-only inspection of a running Fooocus Gradio configuration."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.fooocus_runtime_inspector import FooocusRuntimeInspector


def main() -> None:
    specification = FooocusRuntimeInspector().inspect()

    print("Fooocus runtime specification")
    print(f"Gradio version: {specification.gradio_version}")
    print(f"Generate button component: {specification.generate_button_id}")
    print(f"Seed refresh dependency: {specification.seed_refresh_fn_index}")
    print(f"Task creation dependency: {specification.task_creation_fn_index}")
    print(f"Generation dependency: {specification.generation_fn_index}")
    print(f"currentTask component: {specification.current_task_component_id}")
    print(f"Inputs: {specification.input_count}")
    print()
    print("index | component | type | label | default | serializer")

    for input_spec in specification.inputs:
        print(
            f"{input_spec.payload_index:03} | "
            f"{input_spec.component_id} | "
            f"{input_spec.component_type} | "
            f"{input_spec.label!r} | "
            f"{input_spec.default_value!r} | "
            f"{input_spec.serializer}"
        )


if __name__ == "__main__":
    main()
