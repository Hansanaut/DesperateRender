"""Read-only checks for RuntimeSpec metadata and FooocusRequest semantics."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.fooocus_request import FooocusRequest
from models.lora import LoRA
from services.fooocus_runtime_inspector import FooocusRuntimeInspector


def test_runtime_spec() -> None:
    specification = FooocusRuntimeInspector().inspect()
    positive_prompt = next(
        input_spec
        for input_spec in specification.inputs
        if input_spec.elem_id == "positive_prompt"
    )
    styles = next(
        input_spec
        for input_spec in specification.inputs
        if input_spec.label == "Selected Styles"
    )

    assert positive_prompt.component_props["elem_id"] == "positive_prompt"
    assert styles.choices is not None
    assert any(
        choice == "Fooocus V2"
        or isinstance(choice, (list, tuple)) and "Fooocus V2" in choice
        for choice in styles.choices
    )

    print("RuntimeSpec metadata: OK")
    print(f"Positive prompt component: {positive_prompt.component_id}")
    print(f"Style choices: {len(styles.choices)}")


def test_request_semantics() -> None:
    defaults = FooocusRequest()
    assert defaults.prompt is None
    assert defaults.styles is None
    assert defaults.performance is None
    assert defaults.aspect_ratio is None
    assert defaults.image_count is None
    assert defaults.output_format is None
    assert defaults.seed is None
    assert defaults.read_wildcards_in_order is None
    assert defaults.sharpness is None
    assert defaults.guidance_scale is None
    assert defaults.base_model is None
    assert defaults.refiner_model is None
    assert defaults.refiner_switch is None
    assert defaults.loras is None

    overrides = FooocusRequest(
        prompt="PromptLAB test",
        styles=[],
        performance="Quality",
        image_count=3,
        loras=[LoRA(enabled=True, filename="example.safetensors", weight=0.7)],
    )
    assert overrides.prompt == "PromptLAB test"
    assert overrides.styles == []
    assert overrides.performance == "Quality"
    assert overrides.image_count == 3
    assert overrides.loras is not None
    assert overrides.loras[0].filename == "example.safetensors"

    assert FooocusRequest().loras is None
    assert FooocusRequest(loras=[]).loras == []
    assert FooocusRequest(loras=[LoRA()]).loras is not None

    print("FooocusRequest override semantics: OK")
    print("LoRA None / [] / [LoRA(...)] semantics: OK")


def main() -> None:
    test_runtime_spec()
    test_request_semantics()
    print("PayloadBuilder preparation checks: OK")


if __name__ == "__main__":
    main()
