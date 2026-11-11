"""Regression test for experiment style persistence."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from models.experiment import Experiment
from tools.experiment_store import ExperimentStore


def main() -> None:
    with TemporaryDirectory() as directory:
        store = ExperimentStore(directory)
        experiment = Experiment(
            experiment_id="20261007-001",
            name="Style Persistence Test",
        )
        experiment.styles = [
            "Fooocus V2",
            "Fooocus Sharp",
            "Cinematic",
        ]
        experiment.available_styles = [
            "Fooocus V2",
            "Fooocus Sharp",
            "Cinematic",
            "Unselected Style",
        ]
        experiment.random_style = True
        experiment.random_style_count = 2

        path = store.save(experiment)
        loaded = store.load(path)

        assert loaded.styles == experiment.styles
        assert loaded.available_styles == experiment.available_styles
        assert loaded.random_style is True
        assert loaded.random_style_count == 2

        print("STYLE PERSISTENCE: PASSED")


if __name__ == "__main__":
    main()
