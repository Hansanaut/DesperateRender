from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.experiment import Experiment, ReferenceImage, ReferenceType
from services.experiment.experiment_store import ExperimentStore


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        store = ExperimentStore(root / "experiments")

        created_at = datetime(2026, 10, 5, 11, 59, 54)
        source_style = root / "source_style.png"
        source_composition = root / "source_composition.jpg"
        source_style.write_bytes(b"style-reference")
        source_composition.write_bytes(b"composition-reference")

        experiment = Experiment(
            experiment_id="20261005-001",
            name='Storage Test: <direct> / JSON?',
            created_at=created_at,
            updated_at=created_at,
            available_styles=["Fooocus V2", "Fooocus Enhance"],
            random_style=True,
            random_style_count=2,
            style_references=[
                ReferenceImage(1, str(source_style), ReferenceType.STYLE),
            ],
            composition_references=[
                ReferenceImage(2, str(source_composition), ReferenceType.COMPOSITION),
            ],
        )

        target = store.save(experiment)

        assert target.exists()
        assert target.parent == store.root
        assert re.fullmatch(
            r"\d{8}-\d{6}-Storage Test_ _direct_ _ JSON_\.json",
            target.name,
        )

        reference_root = store.root / target.stem
        style_copy = reference_root / "style" / "001_source_style.png"
        composition_copy = reference_root / "composition" / "002_source_composition.jpg"
        assert style_copy.is_file()
        assert composition_copy.is_file()

        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["experiment_id"] == "20261005-001"
        assert data["name"] == experiment.name
        assert data["style_references"][0]["path"] == (
            f"{target.stem}/style/001_source_style.png"
        )
        assert data["composition_references"][0]["path"] == (
            f"{target.stem}/composition/002_source_composition.jpg"
        )

        loaded = store.load(target)
        assert loaded.experiment_id == experiment.experiment_id
        assert loaded.name == experiment.name
        assert loaded.created_at == created_at
        assert loaded.available_styles == ["Fooocus V2", "Fooocus Enhance"]
        assert loaded.random_style is True
        assert loaded.random_style_count == 2
        assert Path(loaded.style_references[0].path).resolve() == style_copy.resolve()
        assert Path(loaded.composition_references[0].path).resolve() == composition_copy.resolve()
        assert loaded.style_references[0].reference_type == ReferenceType.STYLE
        assert loaded.composition_references[0].reference_type == ReferenceType.COMPOSITION

        # Each explicit save creates a new revision. Older JSON files and
        # their reference images remain available for rollback/inspection.
        loaded.name = "Renamed Experiment"
        second_target = store.save(loaded)

        assert re.fullmatch(
            r"\d{8}-\d{6}-Renamed Experiment(?:-\d+)?\.json",
            second_target.name,
        )
        assert second_target.exists()
        assert target.exists()
        assert {
            path.resolve()
            for path in store.root.glob("*.json")
        } == {
            target.resolve(),
            second_target.resolve(),
        }
        assert reference_root.is_dir()
        assert style_copy.is_file()
        assert composition_copy.is_file()

        second_reference_root = store.root / second_target.stem
        assert (second_reference_root / "style" / "001_source_style.png").is_file()
        assert (second_reference_root / "composition" / "002_source_composition.jpg").is_file()

        # Removing references affects only the new revision. Earlier revisions
        # and their reference folders must not be deleted.
        loaded.style_references.clear()
        loaded.composition_references.clear()
        third_target = store.save(loaded)
        assert third_target.exists()
        assert not (store.root / third_target.stem).exists()
        assert target.exists()
        assert second_target.exists()
        assert reference_root.is_dir()
        assert second_reference_root.is_dir()

        reloaded = store.load(third_target)
        assert not reloaded.style_references
        assert not reloaded.composition_references

        # The Open workflow can load a JSON path directly.
        reloaded.name = "Renamed Again"
        fourth_target = store.save(reloaded)
        assert fourth_target.exists()

        # Invalid JSON must fail cleanly rather than partially replacing the
        # currently loaded in-memory experiment in the GUI workflow.
        invalid_json = store.root / "invalid-json-test.json"
        invalid_json.write_text("{ definitely not valid JSON", encoding="utf-8")
        try:
            store.load(invalid_json)
        except Exception as exc:
            assert "Could not load experiment" in str(exc)
        else:
            raise AssertionError("Malformed JSON unexpectedly loaded")

        # Legacy ids remain accepted only when an old experiment directory exists.
        legacy_dir = store.root / "legacy-id"
        legacy_dir.mkdir()
        legacy_target = legacy_dir / "experiment.json"
        legacy_target.write_text(
            fourth_target.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        legacy_loaded = store.load("legacy-id")
        assert legacy_loaded.experiment_id == "20261005-001"

        assert re.fullmatch(r"\d{8}-\d{6}-.*\.json", fourth_target.name)

    print("=== EXPERIMENT STORE TEST PASSED ===")


if __name__ == "__main__":
    main()
