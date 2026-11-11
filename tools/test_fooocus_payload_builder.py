"""Read-only smoke test for FooocusPayloadBuilder."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.fooocus_request import FooocusRequest
from models.lora import LoRA
from services.fooocus_payload_builder import FooocusPayloadBuilder, PayloadBuilderError
from services.fooocus_runtime_inspector import FooocusInputSpec, FooocusRuntimeInspector


def find_input(specification, *, label: str | None = None, elem_id: str | None = None):
    matches = [
        input_spec
        for input_spec in specification.inputs
        if (label is None or input_spec.label == label)
        and (elem_id is None or input_spec.elem_id == elem_id)
    ]
    assert len(matches) == 1
    return matches[0]


def choice_values(input_spec: FooocusInputSpec) -> list[str]:
    assert input_spec.choices is not None
    values = []
    for choice in input_spec.choices:
        values.append(choice[1] if isinstance(choice, (list, tuple)) else choice)
    return values


def main() -> None:
    specification = FooocusRuntimeInspector().inspect()
    builder = FooocusPayloadBuilder(specification)

    prompt = find_input(specification, elem_id="positive_prompt")
    negative_prompt = find_input(specification, label="Negative Prompt")
    styles = find_input(specification, label="Selected Styles")
    performance = find_input(specification, label="Performance")
    aspect_ratio = find_input(specification, label="Aspect Ratios")
    image_count = find_input(specification, label="Image Number")
    base_model = find_input(specification, label="Base Model (SDXL only)")
    seed = find_input(specification, label="Seed")

    lora_filename_inputs = [
        input_spec
        for input_spec in specification.inputs
        if input_spec.label and input_spec.label.startswith("LoRA ")
    ]
    assert lora_filename_inputs
    first_lora = lora_filename_inputs[0]
    lora_weight = specification.inputs[first_lora.payload_index + 1]

    request = FooocusRequest(
        prompt="PromptLAB payload builder read-only test",
        negative_prompt="test negative prompt",
        styles=list(styles.default_value),
        performance=performance.default_value,
        aspect_ratio=aspect_ratio.default_value,
        image_count=1,
        output_format="png",
        seed=4242,
        base_model=base_model.default_value,
        loras=[
            LoRA(
                enabled=True,
                filename=first_lora.default_value,
                weight=lora_weight.default_value,
            )
        ],
    )
    payload = builder.build(request)
    default_payload = builder.build(FooocusRequest())
    cleared_loras_payload = builder.build(FooocusRequest(loras=[]))

    assert len(payload.data) == specification.input_count
    assert payload.task_creation_fn_index == specification.task_creation_fn_index
    assert payload.data[0] == specification.inputs[0].default_value
    assert payload.data[prompt.payload_index] == request.prompt
    assert payload.data[negative_prompt.payload_index] == request.negative_prompt
    assert payload.data[styles.payload_index] == request.styles
    assert payload.data[performance.payload_index] == request.performance
    assert payload.data[aspect_ratio.payload_index] == request.aspect_ratio
    assert payload.data[image_count.payload_index] == request.image_count
    assert payload.data[base_model.payload_index] == request.base_model
    assert payload.data[seed.payload_index] == str(request.seed)
    assert payload.lora_slot_count == len(lora_filename_inputs)
    assert payload.set_lora_count == 1

    assert default_payload.overridden_indices == ()
    assert default_payload.data == [input_spec.default_value for input_spec in specification.inputs]
    assert cleared_loras_payload.set_lora_count == 0
    for filename_input in lora_filename_inputs:
        enabled_input = specification.inputs[filename_input.payload_index - 1]
        assert cleared_loras_payload.data[enabled_input.payload_index] is False

    try:
        builder.build(FooocusRequest(loras=[LoRA()] * (payload.lora_slot_count + 1)))
    except PayloadBuilderError:
        pass
    else:
        raise AssertionError("Too many LoRAs must be rejected.")

    for input_spec in specification.inputs:
        if input_spec.payload_index not in payload.overridden_indices:
            assert payload.data[input_spec.payload_index] == input_spec.default_value

    print(f"Payload length: {len(payload.data)}")
    print(f"task_creation_fn_index: {payload.task_creation_fn_index}")
    print(f"Prompt: {payload.data[prompt.payload_index]!r}")
    print(f"Negative Prompt: {payload.data[negative_prompt.payload_index]!r}")
    print(f"Styles: {payload.data[styles.payload_index]!r}")
    print(f"Performance: {payload.data[performance.payload_index]!r}")
    print(f"Aspect Ratio: {payload.data[aspect_ratio.payload_index]!r}")
    print(f"Image Count: {payload.data[image_count.payload_index]!r}")
    print(f"Base Model: {payload.data[base_model.payload_index]!r}")
    print(f"Seed: {payload.data[seed.payload_index]!r}")
    print(f"Detected LoRA slots: {payload.lora_slot_count}")
    print(f"Set LoRAs: {payload.set_lora_count}")
    print("LoRA None / [] / overflow validation: OK")
    print("Runtime defaults for non-overridden values: OK")


if __name__ == "__main__":
    main()
