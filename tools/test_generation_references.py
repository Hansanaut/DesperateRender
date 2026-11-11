from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.experiment import ReferenceImage, ReferenceType
from models.generation_configuration import GenerationConfiguration
from services.fooocus_client import FooocusClient
from services.generation.configuration_adapter import GenerationConfigurationAdapter
from services.generation_service import GenerationService


STYLE_NAME = "robot.png.jpg"
COMPOSITION_NAME = "janitor_closet_933x320.jpg"


def find_reference(filename: str) -> Path:
    candidates = [
        PROJECT_ROOT / "references" / filename,
        PROJECT_ROOT / filename,
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(
        f"Reference image not found: {filename}\n"
        + "Checked:\n"
        + "\n".join(f"  {p}" for p in candidates)
    )


def main() -> None:
    style_path = find_reference(STYLE_NAME)
    composition_path = find_reference(COMPOSITION_NAME)

    print("Style reference:", style_path)
    print("Composition reference:", composition_path)
    print()

    configuration = GenerationConfiguration(
        configuration_id=9001,
        positive_prompt="a small friendly cleaning robot in a spaceship janitor closet",
        negative_prompt="blurry, distorted, low quality",
        style_references=[
            ReferenceImage(1, str(style_path), ReferenceType.STYLE),
        ],
        composition_references=[
            ReferenceImage(2, str(composition_path), ReferenceType.COMPOSITION),
        ],
        performance="Quality",
        aspect_ratio=None,
        seed=4242,
        output_format="png",
    )

    request = GenerationConfigurationAdapter.to_fooocus_request(configuration)

    print("=== ADAPTED REQUEST ===")
    print(request)
    print()

    if request.image_prompts is None or len(request.image_prompts) != 2:
        raise RuntimeError("Expected exactly two image prompts.")

    if request.image_prompts[0].type != "ImagePrompt":
        raise RuntimeError("First reference is not mapped to ImagePrompt.")

    if request.image_prompts[1].type != "PyraCanny":
        raise RuntimeError("Second reference is not mapped to PyraCanny.")

    print("Reference mapping: OK")
    print()

    client = FooocusClient()
    service = GenerationService(client)

    print("=== LIVE FOOOCUS REFERENCE TEST ===")
    result = service.generate(request)

    print()
    print("=== LIVE TEST PASSED ===")
    print(f"Generated images: {len(result.images)}")
    for image in result.images:
        print(f"  {image}")


if __name__ == "__main__":
    main()
