from models.experiment import Experiment, MatrixOperator, PromptSlot, SeedMode
from services.experiment.matrix_builder import MatrixBuilder


def main():
    experiment = Experiment(experiment_id="seed-order-test")
    experiment.positive_prompts = [
        PromptSlot(1, "PP1"),
        PromptSlot(2, "PP2"),
        PromptSlot(3, "PP3"),
    ]
    experiment.negative_prompts = []
    experiment.styles = []
    experiment.generation.seed_mode = SeedMode.RANDOM
    experiment.generation.random_seed_count = 3
    experiment.matrix.positive_prompts.operator = MatrixOperator.INDIVIDUAL

    configs = MatrixBuilder.build_experiment(experiment)

    assert len(configs) == 9

    actual = [
        (config.positive_prompt, config.seed)
        for config in configs
    ]

    # Same seed must be used across all prompts before moving to S2.
    seeds = [seed for _, seed in actual]
    assert seeds[0] == seeds[1] == seeds[2]
    assert seeds[3] == seeds[4] == seeds[5]
    assert seeds[6] == seeds[7] == seeds[8]

    assert seeds[0] != seeds[3]
    assert seeds[3] != seeds[6]

    prompts = [prompt for prompt, _ in actual]
    assert prompts == [
        "PP1", "PP2", "PP3",
        "PP1", "PP2", "PP3",
        "PP1", "PP2", "PP3",
    ]

    print("=== SEED ORDERING TEST PASSED ===")
    for index, (prompt, seed) in enumerate(actual, start=1):
        print(f"#{index}: {prompt} -> S{seeds.index(seed) + 1}")


if __name__ == "__main__":
    main()
