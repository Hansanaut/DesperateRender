from __future__ import annotations

from dataclasses import dataclass, field

from models.experiment import ReferenceImage
from models.lora import LoRA


@dataclass
class GenerationConfiguration:
    """One concrete, reproducible generation configuration."""

    configuration_id: int

    positive_prompt: str = ""
    negative_prompt: str = ""

    # PromptLAB UI metadata: original prompt slot positions used for this configuration.
    positive_prompt_slots: list[int] = field(default_factory=list)
    negative_prompt_slots: list[int] = field(default_factory=list)

    # Prompt Block provenance. Example: ``A2+A3+B1``.
    # The value contains only variable prompt selections; fixed prompts
    # remain implicit in the block definition.
    prompt_block_variant_id: str = ""

    styles: list[str] = field(default_factory=list)

    style_references: list[ReferenceImage] = field(
        default_factory=list
    )

    composition_references: list[ReferenceImage] = field(
        default_factory=list
    )

    loras: list[LoRA] = field(
        default_factory=list
    )

    base_model: str | None = None
    refiner_model: str | None = None
    refiner_switch: float | None = None

    performance: str | None = None

    width: int = 640
    height: int = 360
    aspect_ratio: str = "16:9"

    seed: int | None = None

    guidance_scale: float | None = None
    sharpness: float | None = None

    output_format: str = "png"
