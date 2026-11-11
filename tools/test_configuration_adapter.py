from models.experiment import ReferenceImage, ReferenceType
from models.generation_configuration import GenerationConfiguration
from models.lora import LoRA
from services.generation.configuration_adapter import (
    GenerationConfigurationAdapter,
)


def check(name: str, actual, expected) -> None:
    assert actual == expected, (
        f"{name} failed:\n"
        f"Expected: {expected}\n"
        f"Actual:   {actual}"
    )

    print(f"{name}: OK")


def main() -> None:

    configuration = GenerationConfiguration(
        configuration_id=42,
        positive_prompt="a small friendly robot in a laboratory",
        negative_prompt="blurry, distorted, low quality",
        styles=[
            "Fooocus V2",
            "Pixel Art",
        ],
        style_references=[
            ReferenceImage(1, "references/style.png", ReferenceType.STYLE),
        ],
        composition_references=[
            ReferenceImage(2, "references/composition.png", ReferenceType.COMPOSITION),
        ],
        loras=[
            LoRA(
                enabled=True,
                filename="example_lora.safetensors",
                weight=0.8,
            ),
        ],
        performance="Quality",
        width=800,
        height=600,
        aspect_ratio="16:9",
        seed=4242,
        guidance_scale=4.0,
        sharpness=2.0,
        base_model="DreamShaper XL",
        refiner_model=None,
        refiner_switch=None,
        output_format="png",
    )

    request = (
        GenerationConfigurationAdapter.to_fooocus_request(
            configuration
        )
    )

    # --------------------------------------------------
    # Basic prompt data
    # --------------------------------------------------

    check(
        "Positive prompt",
        request.prompt,
        "a small friendly robot in a laboratory",
    )

    check(
        "Negative prompt",
        request.negative_prompt,
        "blurry, distorted, low quality",
    )

    # --------------------------------------------------
    # Styles
    # --------------------------------------------------

    check(
        "Styles",
        request.styles,
        [
            "Fooocus V2",
            "Pixel Art",
        ],
    )

    check(
        "Image reference count",
        len(request.image_prompts),
        2,
    )

    check(
        "Style reference mapping",
        (request.image_prompts[0].image, request.image_prompts[0].type),
        ("references/style.png", "ImagePrompt"),
    )

    check(
        "Composition reference mapping",
        (request.image_prompts[1].image, request.image_prompts[1].type),
        ("references/composition.png", "PyraCanny"),
    )

    # --------------------------------------------------
    # Generation settings
    # --------------------------------------------------

    check(
        "Performance",
        request.performance,
        "Quality",
    )

    check(
        "Image count",
        request.image_count,
        1,
    )

    check(
        "Output format",
        request.output_format,
        "png",
    )

    check(
        "Width",
        request.width,
        800,
    )

    check(
        "Height",
        request.height,
        600,
    )
    
    # --------------------------------------------------
    # Seed
    # --------------------------------------------------

    check(
        "Seed",
        request.seed,
        "4242",
    )

    # --------------------------------------------------
    # Quality
    # --------------------------------------------------

    check(
        "Guidance scale",
        request.guidance_scale,
        4.0,
    )

    check(
        "Sharpness",
        request.sharpness,
        2.0,
    )

    # --------------------------------------------------
    # Models
    # --------------------------------------------------

    check(
        "Base model",
        request.base_model,
        "DreamShaper XL",
    )

    check(
        "Refiner model",
        request.refiner_model,
        None,
    )

    check(
        "Refiner switch",
        request.refiner_switch,
        None,
    )

    # --------------------------------------------------
    # LoRA
    # --------------------------------------------------

    check(
        "LoRA count",
        len(request.loras),
        1,
    )

    check(
        "LoRA enabled",
        request.loras[0].enabled,
        True,
    )

    check(
        "LoRA filename",
        request.loras[0].filename,
        "example_lora.safetensors",
    )

    check(
        "LoRA weight",
        request.loras[0].weight,
        0.8,
    )

    print()
    print("=== CONFIGURATION ADAPTER TEST PASSED ===")
    print()
    print(request)


if __name__ == "__main__":
    main()