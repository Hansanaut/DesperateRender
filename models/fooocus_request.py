from __future__ import annotations

from dataclasses import dataclass

from models.lora import LoRA


@dataclass(frozen=True)
class FooocusImagePrompt:
    """One Fooocus Image Prompt slot override."""

    image: str
    stop_at: float | None = None
    weight: float | None = None
    type: str = "ImagePrompt"


@dataclass
class FooocusRequest:
    """Explicit PromptLAB overrides for a Fooocus generation request.

    Every task-payload field uses ``None`` to preserve the corresponding
    runtime default discovered from Fooocus. A concrete value is an explicit
    override. ``random_seed`` belongs to Fooocus' separate seed-refresh step,
    not to the later task-payload builder.

    LoRA semantics:
    - ``loras is None`` preserves all Fooocus runtime LoRA defaults.
    - ``loras == []`` explicitly disables every discovered runtime LoRA slot.
    - a non-empty list applies its entries to the leading runtime slots and
      explicitly disables all remaining runtime slots.
    """

    prompt: str | None = None
    negative_prompt: str | None = None

    styles: list[str] | None = None

    image_prompts: list[FooocusImagePrompt] | None = None

    performance: str | None = None
    aspect_ratio: str | None = None

    width: int | None = None
    height: int | None = None

    image_count: int | None = None
    output_format: str | None = None

    random_seed: bool | None = None
    seed: int | None = None

    read_wildcards_in_order: bool | None = None

    sharpness: float | None = None
    guidance_scale: float | None = None

    base_model: str | None = None
    refiner_model: str | None = None
    refiner_switch: float | None = None

    loras: list[LoRA] | None = None

    def to_dict(self) -> dict:
        """Return the request as a dictionary."""

        return self.__dict__.copy()
