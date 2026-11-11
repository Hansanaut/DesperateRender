from models.experiment import Experiment, MatrixOperator, SeedMode, PromptSlot
from services.experiment.matrix_builder import MatrixBuilder


MODEL_A = "dreamshaperXL_alpha2Xl10.safetensors"
MODEL_B = "juggernautXL_v8Rundiffusion.safetensors"


def make_experiment(experiment_id: str) -> Experiment:
    experiment = Experiment(experiment_id=experiment_id)
    experiment.generation.seed_mode = SeedMode.FIXED
    experiment.generation.seed = 123

    # A valid positive prompt is required for a generation configuration.
    experiment.positive_prompts = [
        PromptSlot(
            slot_id=1,
            text="TEST PROMPT",
            fixed=True,
        )
    ]

    return experiment


def test_two_base_models_make_two_configurations() -> None:
    experiment = make_experiment("test-base-model")
    experiment.generation.base_model = MODEL_A
    experiment.generation.base_models = [MODEL_A, MODEL_B]
    experiment.matrix.base_models.operator = MatrixOperator.INDIVIDUAL

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 2
    assert [c.base_model for c in configurations] == [MODEL_A, MODEL_B]
    assert experiment.configuration_count == 2


def test_legacy_single_base_model_still_works() -> None:
    experiment = make_experiment("test-legacy-model")
    experiment.generation.base_model = MODEL_A
    experiment.matrix.base_models.operator = MatrixOperator.INDIVIDUAL

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 1
    assert configurations[0].base_model == MODEL_A


if __name__ == "__main__":
    test_two_base_models_make_two_configurations()
    print("Two base models -> two configurations: OK")

    test_legacy_single_base_model_still_works()
    print("Legacy single base model: OK")

    print("=== ALL BASE MODEL MATRIX TESTS PASSED ===")