from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.generation_configuration import GenerationConfiguration
from services.generation.configuration_adapter import GenerationConfigurationAdapter


def main() -> None:
    configuration = GenerationConfiguration(
        configuration_id=1,
        positive_prompt="test",
        performance="Quality",
        width=1024,
        height=576,
        guidance_scale=6.5,
        sharpness=3.5,
        refiner_model="refiner.safetensors",
        refiner_switch=0.75,
        output_format="webp",
    )

    request = GenerationConfigurationAdapter.to_fooocus_request(configuration)

    assert request.performance == "Quality"
    assert request.aspect_ratio is None
    assert request.width == 1024
    assert request.height == 576
    assert request.guidance_scale == 6.5
    assert request.sharpness == 3.5
    assert request.refiner_model == "refiner.safetensors"
    assert request.refiner_switch == 0.75
    assert request.output_format == "webp"

    print("Fooocus experiment settings: OK")
    print("=== FOOOCUS EXPERIMENT SETTINGS TEST PASSED ===")


if __name__ == "__main__":
    main()
