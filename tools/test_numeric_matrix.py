from __future__ import annotations

import tempfile
from pathlib import Path

from models.experiment import (
    Experiment,
    NumericMatrixSelection,
    PromptSlot,
)
from services.experiment.matrix_builder import MatrixBuilder
from services.experiment.experiment_store import ExperimentStore


def main() -> None:
    guidance = NumericMatrixSelection(
        enabled=True,
        minimum=2.0,
        maximum=8.0,
        steps=4,
    )
    sharpness = NumericMatrixSelection(
        enabled=True,
        minimum=0.0,
        maximum=3.0,
        steps=4,
    )

    assert MatrixBuilder.build_numeric(guidance) == [2.0, 4.0, 6.0, 8.0]
    assert MatrixBuilder.build_numeric(sharpness) == [0.0, 1.0, 2.0, 3.0]

    experiment = Experiment(experiment_id="numeric-matrix")
    experiment.matrix.guidance_scale = guidance
    experiment.matrix.sharpness = sharpness

    # Numeric dimensions multiply with the normal experiment dimensions.
    experiment.positive_prompts = [PromptSlot(1, "test")]
    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 16
    assert (configurations[0].guidance_scale, configurations[0].sharpness) == (
        2.0,
        0.0,
    )
    assert (configurations[-1].guidance_scale, configurations[-1].sharpness) == (
        8.0,
        3.0,
    )

    # Existing experiments without numeric dimensions remain unchanged.
    experiment.matrix.guidance_scale = NumericMatrixSelection()
    experiment.matrix.sharpness = NumericMatrixSelection()
    configurations = MatrixBuilder.build_experiment(experiment)
    assert len(configurations) == 1

    with tempfile.TemporaryDirectory() as temp:
        store = ExperimentStore(Path(temp) / "experiments")
        experiment.matrix.guidance_scale = NumericMatrixSelection(
            enabled=True,
            minimum=2.0,
            maximum=8.0,
            steps=4,
        )
        experiment.matrix.sharpness = NumericMatrixSelection(
            enabled=True,
            minimum=0.0,
            maximum=3.0,
            steps=4,
        )
        target = store.save(experiment)
        loaded = store.load(target)

        assert loaded.matrix.guidance_scale.enabled is True
        assert loaded.matrix.guidance_scale.minimum == 2.0
        assert loaded.matrix.guidance_scale.maximum == 8.0
        assert loaded.matrix.guidance_scale.steps == 4
        assert loaded.matrix.sharpness.enabled is True
        assert loaded.matrix.sharpness.minimum == 0.0
        assert loaded.matrix.sharpness.maximum == 3.0
        assert loaded.matrix.sharpness.steps == 4

    print("Numeric matrix persistence: OK")
    print("=== NUMERIC MATRIX TEST PASSED ===")


if __name__ == "__main__":
    main()
