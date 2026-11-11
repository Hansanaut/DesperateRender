from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.prompt_block import PromptBlock


MIN_GENERATION_WIDTH = 480
MAX_GENERATION_WIDTH = 2048

MIN_GENERATION_HEIGHT = 320
MAX_GENERATION_HEIGHT = 2048

GENERATION_SIZE_STEP = 8


class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class ReferenceType(str, Enum):
    STYLE = "STYLE"
    COMPOSITION = "COMPOSITION"


class MatrixOperator(str, Enum):
    ALL = "ALL"
    INDIVIDUAL = "INDIVIDUAL"
    PERMUTATION = "PERMUTATION"
    COMBINATION = "COMBINATION"


class SeedMode(str, Enum):
    FIXED = "FIXED"
    RANDOM = "RANDOM"


@dataclass
class PromptSlot:
    """One positive or negative prompt slot."""

    slot_id: int
    text: str = ""
    fixed: bool = False


@dataclass
class ReferenceImage:
    """Reference image belonging to an experiment."""

    reference_id: int
    path: str
    reference_type: ReferenceType


@dataclass
class MatrixSelection:
    """Matrix behavior for one experimental dimension."""

    operator: MatrixOperator = MatrixOperator.INDIVIDUAL
    minimum: int | None = None
    maximum: int | None = None


@dataclass
class NumericMatrixSelection:
    """Numeric range definition for one experimental dimension."""

    enabled: bool = False
    minimum: float | None = None
    maximum: float | None = None
    steps: int = 1


@dataclass
class ResolutionMatrixSelection:
    """Range of render resolutions while preserving the experiment aspect ratio."""

    enabled: bool = False
    dimension: str = "width"
    minimum: int | None = None
    maximum: int | None = None
    steps: int = 3


@dataclass
class GenerationSettings:
    """Fixed generation settings for one experiment."""

    width: int = 1024
    height: int = 768

    aspect_ratio: str = "4:3"

    seed_mode: SeedMode = SeedMode.RANDOM

    # Kept for backwards compatibility with existing experiments.
    seed: int | None = None

    # Manual multi-seed support.
    seeds: list[int] = field(default_factory=list)

    # Number of random seeds per matrix combination.
    random_seed_count: int = 1

    # When True, random seeds are generated once and reused for the
    # experiment. When False, every generated job receives a fresh seed.
    random_seed_fixed: bool = True

    # Persisted random seeds used by the fixed-random mode.
    random_seeds: list[int] = field(default_factory=list)

    performance: str | None = None
    guidance_scale: float | None = None
    sharpness: float | None = None

    # Kept for backwards compatibility with existing experiments.
    base_model: str | None = None

    # Manual multi-base-model support.
    base_models: list[str] = field(default_factory=list)

    refiner_model: str | None = None
    refiner_switch: float | None = None

    output_format: str = "png"


@dataclass
class MatrixDefinition:
    """Defines how experiment dimensions are combined."""

    positive_prompts: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    negative_prompts: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    styles: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    seeds: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    style_references: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    composition_references: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    base_models: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    refiner_models: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    lora_configurations: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    guidance_scale: NumericMatrixSelection = field(
        default_factory=NumericMatrixSelection
    )

    sharpness: NumericMatrixSelection = field(
        default_factory=NumericMatrixSelection
    )

    resolution: ResolutionMatrixSelection = field(
        default_factory=ResolutionMatrixSelection
    )


@dataclass
class Experiment:
    """Complete PromptLAB experiment definition."""

    experiment_id: str
    name: str = ""

    version: int = 1

    status: ExperimentStatus = ExperimentStatus.DRAFT

    created_at: datetime = field(
        default_factory=datetime.now
    )

    updated_at: datetime = field(
        default_factory=datetime.now
    )

    # Legacy single positive-prompt dimension. Kept for backwards
    # compatibility; new experiments should use prompt_blocks.
    positive_prompts: list[PromptSlot] = field(
        default_factory=list
    )

    negative_prompts: list[PromptSlot] = field(
        default_factory=list
    )

    # New independent positive-prompt dimensions.
    prompt_blocks: list["PromptBlock"] = field(
        default_factory=list
    )

    # Styles explicitly selected by the user.
    styles: list[str] = field(
        default_factory=list
    )

    # Complete Fooocus runtime style pool.
    available_styles: list[str] = field(
        default_factory=list
    )

    random_style: bool = False

    random_style_count: int = 1

    style_references: list[ReferenceImage] = field(
        default_factory=list
    )

    composition_references: list[ReferenceImage] = field(
        default_factory=list
    )

    generation: GenerationSettings = field(
        default_factory=GenerationSettings
    )

    matrix: MatrixDefinition = field(
        default_factory=MatrixDefinition
    )

    configuration_count: int = 0

    total_image_count: int = 0

    estimated_runtime_seconds: float | None = None

    estimated_storage_bytes: int | None = None

    test_run_completed: bool = False

    def update_image_count(self) -> int:
        """Update the derived total image count."""

        self.total_image_count = self.configuration_count

        return self.total_image_count

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = datetime.now()

    def set_configuration_count(
        self,
        count: int,
    ) -> None:
        """Set the matrix result and update derived values."""

        if count < 0:
            raise ValueError(
                "Configuration count cannot be negative."
            )

        self.configuration_count = count
        self.update_image_count()
        self.touch()
