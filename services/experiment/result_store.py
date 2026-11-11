from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class ResultStoreError(RuntimeError):
    """Raised when a result-history manifest cannot be read or written."""


class ResultStore:
    """Persist run metadata in a JSON manifest paired with each experiment revision."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_id(experiment_id: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(experiment_id)).strip("._")
        return safe or "experiment"

    def path(self, experiment_id: str) -> Path:
        """Return the legacy manifest path used by older DR releases."""
        return self.root / f"{self._safe_id(experiment_id)}.results.json"

    def paired_path(self, experiment_path: str | Path) -> Path:
        """Return the result manifest paired with a timestamped experiment file."""
        source = Path(experiment_path)
        name = source.name
        if name.lower().endswith("_exp.json"):
            name = name[:-len("_exp.json")] + "_rslt.json"
        elif name.lower().endswith(".json"):
            name = name[:-len(".json")] + "_rslt.json"
        else:
            name = name + "_rslt.json"
        return source.with_name(name)

    def load_for_experiment_path(
        self, experiment_path: str | Path, experiment_id: str
    ) -> dict[str, Any]:
        """Load the paired manifest, falling back to legacy ID-based history."""
        paired = self.paired_path(experiment_path)
        if paired.exists():
            return self._load_path(paired, experiment_id)
        legacy = self.path(experiment_id)
        if legacy.exists():
            return self._load_path(legacy, experiment_id)
        return {"schema_version": 1, "experiment_id": experiment_id, "runs": []}

    def _load_path(self, target: Path, experiment_id: str) -> dict[str, Any]:
        if not target.exists():
            return {"schema_version": 1, "experiment_id": experiment_id, "runs": []}
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("runs", []), list):
                raise ValueError("Invalid result manifest structure")
            payload.setdefault("schema_version", 1)
            payload.setdefault("experiment_id", experiment_id)
            payload.setdefault("runs", [])
            return payload
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ResultStoreError(f"Could not load result history: {target}") from exc

    def load(self, experiment_id: str) -> dict[str, Any]:
        return self._load_path(self.path(experiment_id), experiment_id)

    def save(self, experiment_id: str, manifest: dict[str, Any]) -> Path:
        return self.save_to_path(experiment_id, manifest, self.path(experiment_id))

    def save_to_path(
        self, experiment_id: str, manifest: dict[str, Any], target_path: str | Path
    ) -> Path:
        target = Path(target_path)
        payload = dict(manifest)
        payload["schema_version"] = 1
        payload["experiment_id"] = experiment_id
        payload["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        payload.setdefault("runs", [])
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            temporary.replace(target)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise ResultStoreError(f"Could not save result history: {target}") from exc
        return target

    def merge_snapshot(
        self,
        experiment_id: str,
        snapshot_runs: list[dict[str, Any]],
        *,
        existing_manifest: dict[str, Any] | None = None,
        target_path: str | Path | None = None,
    ) -> Path:
        """Merge the current UI snapshot into history without dropping older runs.

        Runs absent from the current preview are intentionally retained: starting a
        new run clears the preview, not the experiment's persisted history. Legacy
        manifest entries without a run_id are retained unchanged as well.
        """
        manifest = dict(existing_manifest) if existing_manifest is not None else self.load(experiment_id)
        existing_runs = list(manifest.get("runs", []))
        runs_by_id: dict[str, dict[str, Any]] = {}
        unkeyed_runs: list[dict[str, Any]] = []

        for run in existing_runs:
            run_id = str(run.get("run_id") or "").strip()
            if not run_id:
                # Do not silently discard older/legacy history we cannot key.
                unkeyed_runs.append(run)
                continue
            runs_by_id[run_id] = dict(run)

        for snapshot in snapshot_runs:
            run_id = str(snapshot.get("run_id") or "").strip()
            if not run_id:
                # A snapshot without identity cannot safely replace a saved run.
                unkeyed_runs.append(dict(snapshot))
                continue

            previous = runs_by_id.get(run_id, {})
            merged = dict(previous)
            previous_created_at = previous.get("created_at")
            merged.update(snapshot)
            if previous_created_at:
                merged["created_at"] = previous_created_at
            else:
                merged.setdefault(
                    "created_at",
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                )

            # Merge images by stable image path so a partial snapshot cannot
            # accidentally erase earlier results from the same run. Current
            # metadata (ratings/exclusion) wins for images present in the snapshot.
            previous_images = list(previous.get("images", []))
            image_records: dict[str, dict[str, Any]] = {}
            anonymous_images: list[dict[str, Any]] = []
            for image in previous_images:
                image_path = str(image.get("path") or "").strip()
                if image_path:
                    image_records[image_path] = dict(image)
                else:
                    anonymous_images.append(image)
            for image in snapshot.get("images", []):
                image_path = str(image.get("path") or "").strip()
                if image_path:
                    image_records[image_path] = {
                        **image_records.get(image_path, {}),
                        **dict(image),
                    }
                else:
                    anonymous_images.append(dict(image))
            merged["images"] = list(image_records.values()) + anonymous_images
            runs_by_id[run_id] = merged

        manifest["runs"] = sorted(
            [*runs_by_id.values(), *unkeyed_runs],
            key=lambda run: str(run.get("created_at", "")),
        )
        if target_path is None:
            return self.save(experiment_id, manifest)
        return self.save_to_path(experiment_id, manifest, target_path)
