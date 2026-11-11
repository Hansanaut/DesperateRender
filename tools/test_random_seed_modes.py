from models.experiment import Experiment, MatrixOperator, PromptSlot, SeedMode
from services.experiment.matrix_builder import MatrixBuilder


def _experiment() -> Experiment:
    experiment = Experiment(experiment_id="random-seed-mode-test")
    experiment.generation.seed_mode = SeedMode.RANDOM
    experiment.matrix.positive_prompts.operator = MatrixOperator.INDIVIDUAL
    experiment.positive_prompts = [
        PromptSlot(slot_id=1, text="alpha"),
        PromptSlot(slot_id=2, text="beta"),
    ]
    return experiment


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def main() -> None:
    # Fixed random: count is a true experiment dimension and the same
    # generated seeds are reused across all matrix variants and rebuilds.
    fixed = _experiment()
    fixed.generation.random_seed_fixed = True
    fixed.generation.random_seed_count = 2

    first = MatrixBuilder.build_experiment(fixed)
    first_seeds = [config.seed for config in first]

    check("Fixed random doubles the 2-prompt matrix", len(first) == 4)
    check("Fixed random creates two persisted seeds", len(fixed.generation.random_seeds) == 2)
    check("Fixed random seeds are reused across prompts", first_seeds == [first_seeds[0], first_seeds[0], first_seeds[2], first_seeds[2]])

    persisted_seeds = list(fixed.generation.random_seeds)
    second = MatrixBuilder.build_experiment(fixed)
    check("Fixed random is stable across rebuilds", [c.seed for c in second] == first_seeds)
    check("Persisted random seeds stay unchanged", fixed.generation.random_seeds == persisted_seeds)

    # Non-fixed random: count still multiplies the job count, but every job
    # gets its own freshly generated seed.
    non_fixed = _experiment()
    non_fixed.generation.random_seed_fixed = False
    non_fixed.generation.random_seed_count = 2

    generated = MatrixBuilder.build_experiment(non_fixed)
    seeds = [config.seed for config in generated]

    check("Non-fixed random doubles the 2-prompt matrix", len(generated) == 4)
    check("Non-fixed random does not persist generated seeds", non_fixed.generation.random_seeds == [])
    check("Non-fixed random gives every job its own seed", len(set(seeds)) == len(seeds))

    print("=== RANDOM SEED MODE TESTS PASSED ===")


if __name__ == "__main__":
    main()
