from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.experiment import Experiment, PromptSlot, ResolutionMatrixSelection
from services.experiment.experiment_store import ExperimentStore
from services.experiment.matrix_builder import MatrixBuilder


def make_experiment() -> Experiment:
    experiment = Experiment(experiment_id="resolution-matrix-test")
    experiment.positive_prompts = [PromptSlot(1, "resolution test")]
    experiment.generation.width = 1024
    experiment.generation.height = 768
    experiment.matrix.resolution = ResolutionMatrixSelection(
        enabled=True,
        dimension="width",
        minimum=600,
        maximum=1200,
        steps=3,
    )
    return experiment


def main() -> None:
    experiment = make_experiment()
    configurations = MatrixBuilder.build_experiment(experiment)
    sizes = [(item.width, item.height) for item in configurations]
    assert sizes == [(600, 450), (900, 675), (1200, 900)], sizes
    assert experiment.configuration_count == 3

    experiment.matrix.resolution.dimension = "height"
    experiment.matrix.resolution.minimum = 480
    experiment.matrix.resolution.maximum = 960
    experiment.matrix.resolution.steps = 3
    configurations = MatrixBuilder.build_experiment(experiment)
    sizes = [(item.width, item.height) for item in configurations]
    assert sizes == [(640, 480), (960, 720), (1280, 960)], sizes

    with tempfile.TemporaryDirectory() as temp:
        store = ExperimentStore(Path(temp) / "experiments")
        experiment = make_experiment()
        path = store.save(experiment)
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["matrix"]["resolution"] == {
            "enabled": True,
            "dimension": "width",
            "minimum": 600,
            "maximum": 1200,
            "steps": 3,
        }
        loaded = store.load(path)
        assert loaded.matrix.resolution == experiment.matrix.resolution

    # Existing experiments without a resolution matrix retain their baseline size.
    experiment = make_experiment()
    experiment.matrix.resolution.enabled = False
    configurations = MatrixBuilder.build_experiment(experiment)
    assert [(item.width, item.height) for item in configurations] == [(1024, 768)]

    print("=== RESOLUTION MATRIX TESTS PASSED ===")


if __name__ == "__main__":
    main()
