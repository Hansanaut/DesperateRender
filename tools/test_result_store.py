from __future__ import annotations

import tempfile
from pathlib import Path

from services.experiment.result_store import ResultStore


def test_result_store_preserves_multiple_runs_and_merges_snapshot() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        store = ResultStore(temporary)
        first = {
            "run_id": "run-1",
            "created_at": "2026-10-14T09:00:00+02:00",
            "images": [{"path": "first.png", "job_id": 1, "rating": 2, "excluded": False}],
        }
        second = {
            "run_id": "run-2",
            "created_at": "2026-10-14T09:10:00+02:00",
            "images": [{"path": "second.png", "job_id": 1, "rating": 0, "excluded": True}],
        }
        store.merge_snapshot("20261014-001", [first])
        store.merge_snapshot("20261014-001", [second])
        updated_first = {
            **first,
            "images": [{"path": "first.png", "job_id": 1, "rating": 3, "excluded": False}],
        }
        store.merge_snapshot("20261014-001", [updated_first])
        manifest = store.load("20261014-001")
        runs = {run["run_id"]: run for run in manifest["runs"]}
        assert set(runs) == {"run-1", "run-2"}
        assert runs["run-1"]["images"][0]["rating"] == 3
        assert runs["run-2"]["images"][0]["excluded"] is True
        assert store.path("20261014-001").is_file()

        # A partial snapshot for an existing run must not remove an image that
        # was already persisted, and older runs must remain present.
        partial_first = {
            **updated_first,
            "images": [{"path": "first.png", "job_id": 1, "rating": 1, "excluded": False}],
        }
        store.merge_snapshot("20261014-001", [partial_first])
        manifest = store.load("20261014-001")
        runs = {run["run_id"]: run for run in manifest["runs"]}
        assert set(runs) == {"run-1", "run-2"}
        assert runs["run-2"]["images"][0]["path"] == "second.png"


def test_result_store_missing_manifest_is_empty() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        manifest = ResultStore(temporary).load("new-experiment")
        assert manifest["runs"] == []
        assert manifest["schema_version"] == 1


if __name__ == "__main__":
    test_result_store_preserves_multiple_runs_and_merges_snapshot()
    test_result_store_missing_manifest_is_empty()
    print("result store tests passed")


def test_paired_result_filename_and_history_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        store = ResultStore(temporary)
        experiment_path = Path(temporary) / "20261014-131945-SpeedBurger_exp.json"
        paired_path = store.paired_path(experiment_path)
        assert paired_path.name == "20261014-131945-SpeedBurger_rslt.json"

        run1 = {"run_id": "run-1", "created_at": "2026-10-14T13:00:00+02:00", "images": [{"path": "one.png", "job_id": 1}]}
        store.merge_snapshot("20261014-001", [run1], existing_manifest={"runs": []}, target_path=paired_path)
        manifest = store.load_for_experiment_path(experiment_path, "20261014-001")
        assert [run["run_id"] for run in manifest["runs"]] == ["run-1"]

        run2 = {"run_id": "run-2", "created_at": "2026-10-14T13:10:00+02:00", "images": [{"path": "two.png", "job_id": 1}]}
        store.merge_snapshot("20261014-001", [run2], existing_manifest=manifest, target_path=paired_path)
        manifest = store.load_for_experiment_path(experiment_path, "20261014-001")
        assert {run["run_id"] for run in manifest["runs"]} == {"run-1", "run-2"}


if __name__ == "__main__":
    test_result_store_preserves_multiple_runs_and_merges_snapshot()
    test_result_store_missing_manifest_is_empty()
    test_paired_result_filename_and_history_roundtrip()
    print("result store tests passed")
