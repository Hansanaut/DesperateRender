from models.experiment import Experiment, MatrixOperator, PromptSlot, SeedMode
from services.experiment.matrix_builder import MatrixBuilder


def check(name, actual, expected):
    assert actual == expected, f"{name} failed: expected {expected!r}, got {actual!r}"
    print(f"{name}: OK")


def main():
    experiment = Experiment(experiment_id="style-seed-test")
    experiment.positive_prompts = [PromptSlot(1, "car")]
    experiment.negative_prompts = [PromptSlot(1, "blur")]
    experiment.styles = ["Style A", "Style B", "Style C"]
    experiment.available_styles = list(experiment.styles)
    experiment.generation.seed_mode = SeedMode.FIXED
    experiment.generation.seeds = [101, 202]

    # Manual styles: Individual -> one selected style per configuration.
    # Seeds are the outer matrix dimension, so all styles for seed 101
    # are generated before styles for seed 202.
    experiment.matrix.styles.operator = MatrixOperator.INDIVIDUAL
    configs = MatrixBuilder.build_experiment(experiment)

    check("Manual styles / Individual count", len(configs), 6)
    check("Manual styles / Individual first", configs[0].styles, ["Style A"])
    check("Manual styles / Individual second", configs[1].styles, ["Style B"])
    check("Manual styles / Individual third", configs[2].styles, ["Style C"])
    check("Manual styles / Individual fourth", configs[3].styles, ["Style A"])
    check("Manual styles / Individual fifth", configs[4].styles, ["Style B"])
    check("Manual styles / Individual sixth", configs[5].styles, ["Style C"])
    check(
        "Manual seeds / Individual",
        [c.seed for c in configs],
        [101, 101, 101, 202, 202, 202],
    )

    # Manual styles: All -> one configuration containing all selected styles.
    experiment.matrix.styles.operator = MatrixOperator.ALL
    configs = MatrixBuilder.build_experiment(experiment)

    check("Manual styles / All count", len(configs), 2)
    check("Manual styles / All first", configs[0].styles, experiment.styles)
    check("Manual styles / All second", configs[1].styles, experiment.styles)
    check("Manual styles / All seeds", [c.seed for c in configs], [101, 202])

    # Manual styles: Combination(2) -> C(3,2) style groups × 2 seeds.
    experiment.matrix.styles = type(experiment.matrix.styles)(
        operator=MatrixOperator.COMBINATION,
        minimum=2,
        maximum=2,
    )
    configs = MatrixBuilder.build_experiment(experiment)

    check("Manual styles / Combination count", len(configs), 6)
    check(
        "Manual styles / Combination first",
        configs[0].styles,
        ["Style A", "Style B"],
    )

    # Random styles: requested count means number of independent random
    # style variants per prompt/seed combination, each carrying one style.
    experiment.random_style = True
    experiment.random_style_count = 3
    experiment.matrix.styles.operator = MatrixOperator.INDIVIDUAL
    configs = MatrixBuilder.build_experiment(experiment)

    check("Random styles count", len(configs), 6)
    check(
        "Random styles each single",
        all(len(c.styles) == 1 for c in configs),
        True,
    )
    check(
        "Random styles from pool",
        all(c.styles[0] in experiment.available_styles for c in configs),
        True,
    )

    # Seeds are always individual generation configurations.
    experiment.random_style = False
    experiment.matrix.styles.operator = MatrixOperator.INDIVIDUAL
    experiment.matrix.seeds.operator = MatrixOperator.INDIVIDUAL
    experiment.generation.seed_mode = SeedMode.RANDOM
    experiment.generation.random_seed_count = 3
    configs = MatrixBuilder.build_experiment(experiment)

    check("Random seeds count", len(configs), 9)
    check(
        "Random seeds are integers",
        all(isinstance(c.seed, int) for c in configs),
        True,
    )
    check(
        "Random seeds positive",
        all(c.seed > 0 for c in configs),
        True,
    )

    # Seed matrix operator is currently not used to group seeds.
    # Each selected seed always produces its own generation configuration,
    # because a GenerationConfiguration contains exactly one seed.
    experiment.generation.seed_mode = SeedMode.FIXED
    experiment.generation.seeds = [101, 202]
    experiment.matrix.seeds.operator = MatrixOperator.ALL

    configs = MatrixBuilder.build_experiment(experiment)

    check("Seed ALL count", len(configs), 6)
    check(
        "Seed ALL ordering",
        [c.seed for c in configs],
        [101, 101, 101, 202, 202, 202],
    )
    check(
        "Seed ALL styles",
        [c.styles for c in configs],
        [
            ["Style A"],
            ["Style B"],
            ["Style C"],
            ["Style A"],
            ["Style B"],
            ["Style C"],
        ],
    )

    print("=== ALL STYLE / SEED MATRIX TESTS PASSED ===")


if __name__ == "__main__":
    main()