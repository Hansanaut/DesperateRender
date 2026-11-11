from pathlib import Path
from tempfile import TemporaryDirectory

from models.experiment import Experiment, SeedMode
from services.experiment.experiment_store import ExperimentStore
from services.experiment.matrix_builder import MatrixBuilder


def main() -> None:
    with TemporaryDirectory() as tmp:
        store = ExperimentStore(Path(tmp))
        experiment = Experiment(experiment_id="random-seed-persistence")
        experiment.generation.seed_mode = SeedMode.RANDOM
        experiment.generation.random_seed_fixed = True
        experiment.generation.random_seed_count = 2

        MatrixBuilder.build_experiment(experiment)
        expected = list(experiment.generation.random_seeds)
        path = store.save(experiment)
        loaded = store.load(path)

        assert loaded.generation.random_seed_fixed is True
        assert loaded.generation.random_seed_count == 2
        assert loaded.generation.random_seeds == expected

        print("=== RANDOM SEED PERSISTENCE TEST PASSED ===")


if __name__ == "__main__":
    main()
