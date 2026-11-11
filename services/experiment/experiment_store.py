from __future__ import annotations

import copy
import json
import re
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from models.experiment import (
    Experiment,
    ExperimentStatus,
    GenerationSettings,
    MatrixDefinition,
    MatrixOperator,
    MatrixSelection,
    NumericMatrixSelection,
    ResolutionMatrixSelection,
    PromptSlot,
    ReferenceImage,
    ReferenceType,
    SeedMode,
)
from models.prompt_block import PromptBlock


class ExperimentStoreError(RuntimeError):
    """Raised when an experiment cannot be persisted or loaded."""


class ExperimentStore:
    """Persist each experiment revision in a dated experiment folder."""

    _INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
    _RESERVED_FILENAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }

    def __init__(
        self,
        root: str | Path = "experiments",
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def next_experiment_id(
        self,
        now: datetime | None = None,
    ) -> str:
        """Return the next date-based experiment id."""

        now = now or datetime.now()
        prefix = now.strftime("%Y%m%d")

        number = 1

        while self._find_json_for_experiment(
            f"{prefix}-{number:03d}"
        ) is not None:
            number += 1

        return f"{prefix}-{number:03d}"

    def create(
        self,
        experiment: Experiment | None = None,
    ) -> Experiment:
        """Create an in-memory experiment; persist only when explicitly saved."""

        if experiment is None:
            experiment = Experiment(
                experiment_id=self.next_experiment_id(),
            )

        return experiment

    def save(
        self,
        experiment: Experiment,
    ) -> Path:
        """Persist an experiment as a timestamped JSON file in the root."""

        if not experiment.experiment_id:
            raise ExperimentStoreError(
                "Experiment ID is required."
            )

        # Every explicit save creates a new revision timestamp.  Keep the
        # original creation timestamp intact, but never reuse the timestamp
        # of the file that was loaded.
        experiment.touch()
        persisted = copy.deepcopy(experiment)

        target = self._target_path(experiment)
        previous = self._find_json_for_experiment(
            experiment.experiment_id
        )

        self._persist_references(
            persisted,
            target,
            previous,
        )
        payload = _to_jsonable(persisted)

        try:
            target.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            # Every save is a new revision. Keep all previous JSON files and
            # their reference directories so the experiment history remains
            # available for later inspection or rollback.

            experiment.style_references = copy.deepcopy(
                persisted.style_references
            )
            experiment.composition_references = copy.deepcopy(
                persisted.composition_references
            )
            self._resolve_reference_paths(experiment, target)

        except OSError as exc:
            raise ExperimentStoreError(
                f"Could not save experiment: {target}"
            ) from exc

        return target

    def load(
        self,
        source: str | Path,
    ) -> Experiment:
        """Load an experiment from a JSON file.

        ``source`` normally is the JSON path selected by the Open dialog.
        Legacy experiment ids are still accepted so older internal callers
        can migrate without requiring a separate compatibility step.
        """

        target = self._resolve_load_path(source)

        if not target.exists() or not target.is_file():
            raise ExperimentStoreError(
                f"Experiment not found: {source}"
            )

        try:
            data = json.loads(
                target.read_text(encoding="utf-8")
            )
            experiment = _experiment_from_dict(data)
            self._resolve_reference_paths(experiment, target)
            return experiment

        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ExperimentStoreError(
                "Could not load experiment: "
                f"{source}"
            ) from exc

    def path(
        self,
        experiment_id: str,
    ) -> Path:
        """Return the JSON path for an experiment id when it can be found."""

        target = self._find_json_for_experiment(experiment_id)
        if target is not None:
            return target
        return self.root / f"{experiment_id}.json"

    def _persist_references(
        self,
        experiment: Experiment,
        target: Path,
        previous: Path | None,
    ) -> None:
        groups = (
            (experiment.style_references, "style"),
            (experiment.composition_references, "composition"),
        )
        all_references = [reference for references, _ in groups for reference in references]
        reference_root = target.parent / target.stem

        if not all_references:
            self._remove_directory_if_empty_or_stale(reference_root)
            return

        reference_root.mkdir(parents=True, exist_ok=True)
        expected_files: set[Path] = set()

        for references, subdir_name in groups:
            subdir = reference_root / subdir_name
            subdir.mkdir(parents=True, exist_ok=True)

            for reference in references:
                source = Path(reference.path)
                if not source.is_absolute():
                    candidates = [
                        self.root / source,
                        (self.root / previous.stem / source) if previous is not None else source,
                    ]
                    source = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])

                if not source.is_file():
                    raise ExperimentStoreError(
                        "Reference image does not exist: "
                        f"{reference.path}"
                    )

                source_name = re.sub(r"^\d{3}_", "", source.name)
                safe_name = self._sanitize_filename_component(
                    source_name,
                    fallback="reference.png",
                )
                target_name = f"{reference.reference_id:03d}_{safe_name}"
                destination = subdir / target_name
                expected_files.add(destination.resolve())

                if source.resolve() != destination.resolve():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)

                reference.path = destination.relative_to(target.parent).as_posix()

        # Remove files left behind by deleted/replaced references, but only
        # after all current references have been copied successfully.
        for path in sorted(reference_root.rglob("*"), reverse=True):
            if path.is_file() and path.resolve() not in expected_files:
                path.unlink(missing_ok=True)

        for path in sorted(reference_root.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _remove_directory_if_empty_or_stale(path: Path) -> None:
        if not path.exists():
            return
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass
        try:
            path.rmdir()
        except OSError:
            pass

    @staticmethod
    def _resolve_reference_paths(
        experiment: Experiment,
        json_path: Path,
    ) -> None:
        for references in (
            experiment.style_references,
            experiment.composition_references,
        ):
            for reference in references:
                path = Path(reference.path)
                if not path.is_absolute():
                    reference.path = str((json_path.parent / path).resolve())

    def _target_path(
        self,
        experiment: Experiment,
    ) -> Path:
        timestamp = experiment.updated_at.strftime(
            "%Y%m%d-%H%M%S"
        )
        name = self._sanitize_filename_component(
            experiment.name,
            fallback="Experiment",
        )
        base = f"{timestamp}-{name}"
        folder_name = f"{name}_{experiment.updated_at:%Y%m%d}"
        experiment_folder = self.root / folder_name
        experiment_folder.mkdir(parents=True, exist_ok=True)
        return experiment_folder / f"{base}_exp.json"

    def _find_json_for_experiment(
        self,
        experiment_id: str,
    ) -> Path | None:
        if not self.root.is_dir():
            return None

        # Newest revision first. This is useful for callers that need the
        # current persisted revision while keeping all older revisions intact.
        for path in sorted(self.root.rglob("*.json"), reverse=True):
            # Result manifests share the experiment_id but are not experiment
            # revisions. Never let them shadow the matching definition JSON.
            if path.name.lower().endswith((".results.json", "_rslt.json")):
                continue
            if self._read_experiment_id(path) == experiment_id:
                return path

        return None

    @staticmethod
    def _read_experiment_id(
        path: Path,
    ) -> str | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        experiment_id = data.get("experiment_id")
        return experiment_id if isinstance(experiment_id, str) else None

    def _resolve_load_path(
        self,
        source: str | Path,
    ) -> Path:
        candidate = Path(source)

        if candidate.is_absolute():
            return candidate

        if candidate.exists():
            return candidate

        if candidate.suffix.lower() == ".json":
            return self.root / candidate

        # Legacy compatibility: accept an old experiment id, including
        # timestamped JSON revisions stored in dated subfolders.
        matching = self._find_json_for_experiment(str(source))
        if matching is not None:
            return matching
        return self.root / candidate / "experiment.json"

    @classmethod
    def _sanitize_filename_component(
        cls,
        value: str,
        fallback: str,
    ) -> str:
        cleaned = cls._INVALID_FILENAME_CHARS.sub("_", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.rstrip(" .")

        if not cleaned:
            cleaned = fallback

        if cleaned.upper() in cls._RESERVED_FILENAMES:
            cleaned = f"_{cleaned}"

        return cleaned


def _to_jsonable(
    value: Any,
) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if is_dataclass(value):
        return {
            key: _to_jsonable(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            key: _to_jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _to_jsonable(item)
            for item in value
        ]

    return value


def _experiment_from_dict(
    data: dict[str, Any],
) -> Experiment:
    generation_data = data.get("generation", {})
    matrix_data = data.get("matrix", {})

    return Experiment(
        experiment_id=data["experiment_id"],
        name=data.get("name", ""),
        version=data.get("version", 1),
        status=ExperimentStatus(
            data.get(
                "status",
                ExperimentStatus.DRAFT.value,
            )
        ),
        created_at=datetime.fromisoformat(
            data["created_at"]
        ),
        updated_at=datetime.fromisoformat(
            data["updated_at"]
        ),
        positive_prompts=[
            PromptSlot(**item)
            for item in data.get(
                "positive_prompts",
                [],
            )
        ],
        negative_prompts=[
            PromptSlot(**item)
            for item in data.get(
                "negative_prompts",
                [],
            )
        ],
        prompt_blocks=[
            _prompt_block_from_dict(item)
            for item in data.get(
                "prompt_blocks",
                [],
            )
        ],
        styles=list(
            data.get("styles", [])
        ),
        available_styles=list(
            data.get("available_styles", [])
        ),
        random_style=bool(
            data.get("random_style", False)
        ),
        random_style_count=int(
            data.get("random_style_count", 1)
        ),
        style_references=[
            ReferenceImage(
                reference_id=item["reference_id"],
                path=item["path"],
                reference_type=ReferenceType(
                    item["reference_type"]
                ),
            )
            for item in data.get(
                "style_references",
                [],
            )
        ],
        composition_references=[
            ReferenceImage(
                reference_id=item["reference_id"],
                path=item["path"],
                reference_type=ReferenceType(
                    item["reference_type"]
                ),
            )
            for item in data.get(
                "composition_references",
                [],
            )
        ],
        generation=_generation_from_dict(
            generation_data
        ),
        matrix=_matrix_from_dict(
            matrix_data
        ),
        configuration_count=data.get(
            "configuration_count",
            0,
        ),
        total_image_count=data.get(
            "total_image_count",
            0,
        ),
        estimated_runtime_seconds=data.get(
            "estimated_runtime_seconds"
        ),
        estimated_storage_bytes=data.get(
            "estimated_storage_bytes"
        ),
        test_run_completed=data.get(
            "test_run_completed",
            False,
        ),
    )


def _prompt_block_from_dict(
    data: dict[str, Any],
) -> PromptBlock:
    selection_data = data.get(
        "matrix_selection",
        {},
    )

    return PromptBlock(
        block_id=data["block_id"],
        name=data.get("name", ""),
        prompts=[
            PromptSlot(**item)
            for item in data.get("prompts", [])
        ],
        matrix_selection=MatrixSelection(
            operator=MatrixOperator(
                selection_data.get(
                    "operator",
                    MatrixOperator.INDIVIDUAL.value,
                )
            ),
            minimum=selection_data.get("minimum"),
            maximum=selection_data.get("maximum"),
        ),
    )


def _generation_from_dict(
    data: dict[str, Any],
) -> GenerationSettings:
    old_seed = data.get("seed")

    seeds = [
        int(seed)
        for seed in data.get("seeds", [])
    ]

    # Migrate old experiments that only contain
    # the former single "seed".
    if not seeds and old_seed is not None:
        seeds = [int(old_seed)]

    return GenerationSettings(
        width=data.get("width", 1024),
        height=data.get("height", 768),
        aspect_ratio=data.get(
            "aspect_ratio",
            "4:3",
        ),
        seed_mode=SeedMode(
            data.get(
                "seed_mode",
                SeedMode.RANDOM.value,
            )
        ),
        seed=(
            int(old_seed)
            if old_seed is not None
            else (
                seeds[0]
                if seeds
                else None
            )
        ),
        seeds=seeds,
        random_seed_count=data.get(
            "random_seed_count",
            1,
        ),
        random_seed_fixed=data.get(
            "random_seed_fixed",
            True,
        ),
        random_seeds=[
            int(seed)
            for seed in data.get("random_seeds", [])
        ],
        performance=data.get("performance"),
        guidance_scale=data.get("guidance_scale"),
        sharpness=data.get("sharpness"),
        base_model=data.get("base_model"),
        base_models=list(
            data.get("base_models", [])
        ),
        refiner_model=data.get("refiner_model"),
        refiner_switch=data.get("refiner_switch"),
        output_format=data.get(
            "output_format",
            "png",
        ),
    )


def _matrix_from_dict(
    data: dict[str, Any],
) -> MatrixDefinition:
    def selection(
        name: str,
    ) -> MatrixSelection:
        value = data.get(name, {})

        return MatrixSelection(
            operator=MatrixOperator(
                value.get(
                    "operator",
                    MatrixOperator.INDIVIDUAL.value,
                )
            ),
            minimum=value.get("minimum"),
            maximum=value.get("maximum"),
        )

    def numeric_selection(name: str) -> NumericMatrixSelection:
        value = data.get(name, {})
        return NumericMatrixSelection(
            enabled=bool(value.get("enabled", False)),
            minimum=value.get("minimum"),
            maximum=value.get("maximum"),
            steps=int(value.get("steps", 1)),
        )

    return MatrixDefinition(
        positive_prompts=selection("positive_prompts"),
        negative_prompts=selection("negative_prompts"),
        styles=selection("styles"),
        seeds=selection("seeds"),
        style_references=selection("style_references"),
        composition_references=selection(
            "composition_references"
        ),
        base_models=selection("base_models"),
        refiner_models=selection("refiner_models"),
        lora_configurations=selection(
            "lora_configurations"
        ),
        guidance_scale=numeric_selection("guidance_scale"),
        sharpness=numeric_selection("sharpness"),
        resolution=ResolutionMatrixSelection(
            enabled=bool(data.get("resolution", {}).get("enabled", False)),
            dimension=data.get("resolution", {}).get("dimension", "width"),
            minimum=data.get("resolution", {}).get("minimum"),
            maximum=data.get("resolution", {}).get("maximum"),
            steps=int(data.get("resolution", {}).get("steps", 3)),
        ),
    )


def _selection_from_dict(
    data: dict[str, Any],
) -> MatrixSelection:
    return MatrixSelection(
        operator=MatrixOperator(
            data.get(
                "operator",
                MatrixOperator.INDIVIDUAL.value,
            )
        ),
        minimum=data.get("minimum"),
        maximum=data.get("maximum"),
    )
