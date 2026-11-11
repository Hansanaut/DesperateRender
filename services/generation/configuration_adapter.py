from __future__ import annotations

from models.fooocus_request import FooocusImagePrompt, FooocusRequest
from models.generation_configuration import GenerationConfiguration


class GenerationConfigurationAdapter:
    """Convert PromptLAB generation configurations to Fooocus requests."""

    @staticmethod
    def to_fooocus_request(
        configuration: GenerationConfiguration,
    ) -> FooocusRequest:
        """Convert one concrete configuration to a FooocusRequest."""

        return FooocusRequest(
            prompt=configuration.positive_prompt,
            negative_prompt=configuration.negative_prompt,
            styles=configuration.styles,
            image_prompts=(
                [
                    FooocusImagePrompt(
                        image=reference.path,
                        type="ImagePrompt",
                    )
                    for reference in configuration.style_references
                ] + [
                    FooocusImagePrompt(
                        image=reference.path,
                        type="PyraCanny",
                    )
                    for reference in configuration.composition_references
                ]
                or None
            ),
            performance=configuration.performance,
            width=configuration.width,
            height=configuration.height,
            aspect_ratio=None,
            image_count=1,
            output_format=configuration.output_format,
            seed=(
                str(configuration.seed)
                if configuration.seed is not None
                else None
            ),
            guidance_scale=configuration.guidance_scale,
            sharpness=configuration.sharpness,
            base_model=configuration.base_model,
            refiner_model=configuration.refiner_model,
            refiner_switch=configuration.refiner_switch,
            loras=configuration.loras,
        )