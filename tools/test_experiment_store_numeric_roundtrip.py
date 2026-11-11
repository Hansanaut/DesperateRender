from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.experiment import Experiment
from services.experiment.experiment_store import ExperimentStore


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "experiments"
        store = ExperimentStore(root)

        experiment = Experiment(
            experiment_id="20261007-001",
            name="Numeric Matrix Roundtrip",
        )
        experiment.generation.performance = "Speed"
        experiment.generation.guidance_scale = 6.5
        experiment.generation.sharpness = 3.5
        experiment.matrix.guidance_scale.enabled = True
        experiment.matrix.guidance_scale.minimum = 2.0
        experiment.matrix.guidance_scale.maximum = 8.0
        experiment.matrix.guidance_scale.steps = 4
        experiment.matrix.sharpness.enabled = True
        experiment.matrix.sharpness.minimum = 0.0
        experiment.matrix.sharpness.maximum = 6.0
        experiment.matrix.sharpness.steps = 3

        target = store.save(experiment)
        assert target.exists()
        assert target.suffix == ".json"
        assert target.name != "experiment.json"

        raw = json.loads(target.read_text(encoding="utf-8"))
        assert raw["matrix"]["guidance_scale"] == {
            "enabled": True,
            "minimum": 2.0,
            "maximum": 8.0,
            "steps": 4,
        }
        assert raw["matrix"]["sharpness"] == {
            "enabled": True,
            "minimum": 0.0,
            "maximum": 6.0,
            "steps": 3,
        }

        loaded = store.load(target)
        assert loaded.generation.performance == "Speed"
        assert loaded.generation.guidance_scale == 6.5
        assert loaded.generation.sharpness == 3.5
        assert loaded.matrix.guidance_scale.enabled is True
        assert loaded.matrix.guidance_scale.minimum == 2.0
        assert loaded.matrix.guidance_scale.maximum == 8.0
        assert loaded.matrix.guidance_scale.steps == 4
        assert loaded.matrix.sharpness.enabled is True
        assert loaded.matrix.sharpness.minimum == 0.0
        assert loaded.matrix.sharpness.maximum == 6.0
        assert loaded.matrix.sharpness.steps == 3

    print("=== EXPERIMENT NUMERIC ROUNDTRIP TEST PASSED ===")


if __name__ == "__main__":
    main()
