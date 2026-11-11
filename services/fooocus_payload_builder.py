"""Build validated Fooocus task payloads from a runtime specification."""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import re
from typing import Any, Callable

from models.fooocus_request import FooocusImagePrompt, FooocusRequest
from models.lora import LoRA
from services.fooocus_runtime_inspector import FooocusInputSpec, FooocusRuntimeSpec


class PayloadBuilderError(ValueError):
    """Raised when a Fooocus task payload cannot be built safely."""


@dataclass(frozen=True)
class FooocusTaskPayload:
    """A complete, validated input list for Fooocus task creation."""

    data: list[Any]
    task_creation_fn_index: int
    gradio_version: str | None
    input_count: int
    overridden_indices: tuple[int, ...]
    lora_slot_count: int
    set_lora_count: int


@dataclass(frozen=True)
class _LoRASlot:
    enabled: FooocusInputSpec
    filename: FooocusInputSpec
    weight: FooocusInputSpec


class FooocusPayloadBuilder:
    """Create task-creation payloads from Fooocus runtime defaults and overrides.

    This class only builds and validates data in memory. It does not make HTTP
    requests and does not invoke the discovered Fooocus dependency.
    """

    _CONTROL_SELECTORS: dict[str, Callable[[FooocusInputSpec], bool]] = {
        "prompt": lambda spec: spec.elem_id == "positive_prompt",
        "negative_prompt": lambda spec: spec.label == "Negative Prompt",
        "styles": lambda spec: spec.label == "Selected Styles",
        "performance": lambda spec: spec.label == "Performance",
        "width": lambda spec: spec.label == "Forced Overwrite of Generating Width",
        "height": lambda spec: spec.label == "Forced Overwrite of Generating Height",        
        "aspect_ratio": lambda spec: spec.label == "Aspect Ratios",
        "image_count": lambda spec: spec.label == "Image Number",
        "output_format": lambda spec: spec.label == "Output Format",
        "seed": lambda spec: spec.label == "Seed",
        "read_wildcards_in_order": lambda spec: spec.label == "Read wildcards in order",
        "sharpness": lambda spec: spec.label == "Image Sharpness",
        "guidance_scale": lambda spec: spec.label == "Guidance Scale",
        "base_model": lambda spec: spec.label == "Base Model (SDXL only)",
        "refiner_model": lambda spec: spec.label == "Refiner (SDXL or SD 1.5)",
        "refiner_switch": lambda spec: spec.label == "Refiner Switch At",
    }

    def __init__(self, runtime_spec: FooocusRuntimeSpec) -> None:
        self.runtime_spec = runtime_spec
        self._validate_runtime_spec()
        self._controls = {
            name: self._find_unique_input(name, selector)
            for name, selector in self._CONTROL_SELECTORS.items()
        }
        self._lora_slots = self._find_lora_slots()
        self._image_prompt_slots = self._find_image_prompt_slots()

    def build(self, request: FooocusRequest) -> FooocusTaskPayload:
        """Build a complete payload without invoking Fooocus."""

        self._validate_request(request)
        data = [input_spec.default_value for input_spec in self.runtime_spec.inputs]
        overridden_indices: set[int] = set()

        for field_name, input_spec in self._controls.items():
            value = getattr(request, field_name)
            if value is None:
                continue
            if field_name == "seed":
                value = str(value)
            self._set_value(data, input_spec, value)
            overridden_indices.add(input_spec.payload_index)

        set_lora_count = self._apply_loras(data, request.loras, overridden_indices)
        self._apply_image_prompts(data, request.image_prompts, overridden_indices)
        self._validate_payload(data, overridden_indices)

        return FooocusTaskPayload(
            data=data,
            task_creation_fn_index=self.runtime_spec.task_creation_fn_index,
            gradio_version=self.runtime_spec.gradio_version,
            input_count=self.runtime_spec.input_count,
            overridden_indices=tuple(sorted(overridden_indices)),
            lora_slot_count=len(self._lora_slots),
            set_lora_count=set_lora_count,
        )

    def _validate_runtime_spec(self) -> None:
        expected_indices = list(range(self.runtime_spec.input_count))
        actual_indices = [input_spec.payload_index for input_spec in self.runtime_spec.inputs]
        if actual_indices != expected_indices:
            raise PayloadBuilderError("RuntimeSpec payload indices are not complete and consecutive.")
        if not self.runtime_spec.inputs:
            raise PayloadBuilderError("RuntimeSpec does not contain task inputs.")

        current_task = self.runtime_spec.inputs[0]
        if current_task.component_id != self.runtime_spec.current_task_component_id:
            raise PayloadBuilderError("RuntimeSpec input index 0 is not the currentTask component.")
        if current_task.component_type != "state":
            raise PayloadBuilderError("RuntimeSpec currentTask component is not a Gradio state.")

    def _validate_request(self, request: FooocusRequest) -> None:
        known_fields = {field.name for field in fields(FooocusRequest)}
        extra_fields = set(vars(request)) - known_fields
        if extra_fields:
            raise PayloadBuilderError(
                "FooocusRequest contains unknown fields: "
                + ", ".join(sorted(extra_fields))
            )
        if request.random_seed is not None:
            raise PayloadBuilderError(
                "random_seed belongs to Fooocus' seed-refresh dependency and "
                "cannot be used by the task payload builder."
            )

    def _find_unique_input(
        self,
        control_name: str,
        selector: Callable[[FooocusInputSpec], bool],
    ) -> FooocusInputSpec:
        matches = [input_spec for input_spec in self.runtime_spec.inputs if selector(input_spec)]
        if len(matches) != 1:
            raise PayloadBuilderError(
                f"Could not identify exactly one runtime control for '{control_name}'."
            )
        return matches[0]

    def _find_lora_slots(self) -> tuple[_LoRASlot, ...]:
        slots: list[_LoRASlot] = []
        inputs = self.runtime_spec.inputs

        for filename in inputs:
            if not filename.label or not re.fullmatch(r"LoRA \d+", filename.label):
                continue
            index = filename.payload_index
            if index == 0 or index + 1 >= len(inputs):
                raise PayloadBuilderError(f"Incomplete runtime LoRA slot at index {index}.")

            enabled = inputs[index - 1]
            weight = inputs[index + 1]
            if (
                enabled.label != "Enable"
                or enabled.component_type != "checkbox"
                or weight.label != "Weight"
                or weight.component_type != "slider"
            ):
                raise PayloadBuilderError(
                    f"Runtime LoRA slot around '{filename.label}' has an unexpected structure."
                )
            slots.append(_LoRASlot(enabled=enabled, filename=filename, weight=weight))

        return tuple(sorted(slots, key=lambda slot: slot.filename.payload_index))

    def _apply_loras(
        self,
        data: list[Any],
        loras: list[LoRA] | None,
        overridden_indices: set[int],
    ) -> int:
        if loras is None:
            return 0
        if len(loras) > len(self._lora_slots):
            raise PayloadBuilderError(
                f"Request contains {len(loras)} LoRAs, but Fooocus exposes only "
                f"{len(self._lora_slots)} runtime LoRA slots."
            )

        for index, slot in enumerate(self._lora_slots):
            if index < len(loras):
                self._set_lora(data, slot, loras[index])
                overridden_indices.update(
                    (slot.enabled.payload_index, slot.filename.payload_index, slot.weight.payload_index)
                )
            else:
                self._set_value(data, slot.enabled, False)
                overridden_indices.add(slot.enabled.payload_index)

        return len(loras)

    @dataclass(frozen=True)
    class _ImagePromptSlot:
        image: FooocusInputSpec
        stop_at: FooocusInputSpec
        weight: FooocusInputSpec
        type: FooocusInputSpec

    def _find_image_prompt_slots(self) -> tuple[_ImagePromptSlot, ...]:
        """Discover Fooocus Image Prompt groups from the runtime structure."""
        inputs = self.runtime_spec.inputs
        slots: list[FooocusPayloadBuilder._ImagePromptSlot] = []
        for index in range(len(inputs) - 3):
            image, stop_at, weight, type_input = inputs[index:index + 4]
            if (
                image.component_type == "image"
                and image.label == "Image"
                and stop_at.label == "Stop At"
                and stop_at.component_type == "slider"
                and weight.label == "Weight"
                and weight.component_type == "slider"
                and type_input.label == "Type"
                and type_input.component_type == "radio"
            ):
                slots.append(self._ImagePromptSlot(image, stop_at, weight, type_input))
        return tuple(slots)

    def _apply_image_prompts(
        self,
        data: list[Any],
        image_prompts: list[FooocusImagePrompt] | None,
        overridden_indices: set[int],
    ) -> None:
        if image_prompts is None:
            return
        if len(image_prompts) > len(self._image_prompt_slots):
            raise PayloadBuilderError(
                f"Request contains {len(image_prompts)} image prompts, but Fooocus exposes only "
                f"{len(self._image_prompt_slots)} Image Prompt slots."
            )

        # Explicit image-prompt requests own all discovered slots.
        for index, slot in enumerate(self._image_prompt_slots):
            if index < len(image_prompts):
                prompt = image_prompts[index]
                if not isinstance(prompt, FooocusImagePrompt):
                    raise PayloadBuilderError("Each image_prompts entry must be a FooocusImagePrompt instance.")
                self._set_value(data, slot.image, prompt.image)
                self._set_value(data, slot.stop_at, prompt.stop_at if prompt.stop_at is not None else slot.stop_at.default_value)
                self._set_value(data, slot.weight, prompt.weight if prompt.weight is not None else slot.weight.default_value)
                self._set_value(data, slot.type, prompt.type)
                overridden_indices.update({
                    slot.image.payload_index, slot.stop_at.payload_index,
                    slot.weight.payload_index, slot.type.payload_index,
                })
            else:
                self._set_value(data, slot.image, None)
                overridden_indices.add(slot.image.payload_index)

    def _set_lora(self, data: list[Any], slot: _LoRASlot, lora: LoRA) -> None:
        if not isinstance(lora, LoRA):
            raise PayloadBuilderError("Each loras entry must be a LoRA instance.")
        self._set_value(data, slot.enabled, lora.enabled)
        self._set_value(data, slot.filename, lora.filename)
        self._set_value(data, slot.weight, lora.weight)

    def _set_value(self, data: list[Any], input_spec: FooocusInputSpec, value: Any) -> None:
        self._validate_value(input_spec, value)
        data[input_spec.payload_index] = value

    def _validate_value(self, input_spec: FooocusInputSpec, value: Any) -> None:
        component_type = input_spec.component_type
        if component_type == "checkbox" and type(value) is not bool:
            raise PayloadBuilderError(f"'{self._display_name(input_spec)}' requires a boolean value.")
        if component_type == "slider" and (
            type(value) is bool or not isinstance(value, (int, float))
        ):
            raise PayloadBuilderError(f"'{self._display_name(input_spec)}' requires a numeric value.")
        if component_type in {"textbox", "radio", "dropdown"} and not isinstance(value, str):
            raise PayloadBuilderError(f"'{self._display_name(input_spec)}' requires a string value.")
        if component_type == "image" and value is not None and not isinstance(value, str):
            raise PayloadBuilderError(f"'{self._display_name(input_spec)}' requires a file path or None.")
        if component_type == "checkboxgroup" and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            raise PayloadBuilderError(
                f"'{self._display_name(input_spec)}' requires a list of strings."
            )

        choice_values = self._choice_values(input_spec)
        if choice_values is None:
            return
        values = value if component_type == "checkboxgroup" else [value]
        invalid_values = [item for item in values if item not in choice_values]
        if invalid_values:
            raise PayloadBuilderError(
                f"'{self._display_name(input_spec)}' contains values not offered by Fooocus: "
                f"{invalid_values!r}."
            )

    @staticmethod
    def _choice_values(input_spec: FooocusInputSpec) -> set[Any] | None:
        if input_spec.choices is None:
            return None

        values: set[Any] = set()
        for choice in input_spec.choices:
            if isinstance(choice, (list, tuple)) and len(choice) >= 2:
                values.add(choice[1])
            else:
                values.add(choice)
        return values

    def _validate_payload(self, data: list[Any], overridden_indices: set[int]) -> None:
        if len(data) != self.runtime_spec.input_count:
            raise PayloadBuilderError("Built payload length does not match RuntimeSpec input_count.")
        if data[0] != self.runtime_spec.inputs[0].default_value:
            raise PayloadBuilderError("currentTask at payload index 0 must remain unchanged.")

        for payload_index in overridden_indices:
            self._validate_value(self.runtime_spec.inputs[payload_index], data[payload_index])

        try:
            json.dumps(data)
        except (TypeError, ValueError) as error:
            raise PayloadBuilderError("Built payload is not JSON-serializable.") from error

    @staticmethod
    def _display_name(input_spec: FooocusInputSpec) -> str:
        return input_spec.label or input_spec.elem_id or f"component {input_spec.component_id}"
