from models.generation_configuration import GenerationConfiguration
from models.lora import LoRA


def main() -> None:

    configuration = GenerationConfiguration(
        configuration_id=17,
        positive_prompt="a small friendly robot",
        negative_prompt="blurry, distorted",
        styles=["Fooocus V2", "Pixel Art"],
        loras=[
            LoRA(
                enabled=True,
                filename="example_lora.safetensors",
                weight=0.8,
            ),
        ],
        base_model="DreamShaper XL",
        width=640,
        height=360,
        aspect_ratio="16:9",
        seed=4242,
    )

    assert configuration.configuration_id == 17

    assert configuration.positive_prompt == (
        "a small friendly robot"
    )

    assert configuration.styles == [
        "Fooocus V2",
        "Pixel Art",
    ]

    assert len(configuration.loras) == 1

    assert configuration.loras[0].enabled is True
    assert configuration.loras[0].filename == (
        "example_lora.safetensors"
    )
    assert configuration.loras[0].weight == 0.8

    print("GenerationConfiguration: OK")
    print("LoRA: OK")
    print()
    print(configuration)


if __name__ == "__main__":
    main()