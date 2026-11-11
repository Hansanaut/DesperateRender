from __future__ import annotations

import random
from itertools import combinations, permutations, product
from typing import Iterator, Sequence, TypeVar

from models.experiment import (
    Experiment,
    MatrixOperator,
    MatrixSelection,
    NumericMatrixSelection,
    ResolutionMatrixSelection,
    PromptSlot,
    SeedMode,
    MIN_GENERATION_WIDTH,
    MAX_GENERATION_WIDTH,
    MIN_GENERATION_HEIGHT,
    MAX_GENERATION_HEIGHT,
)
from models.generation_configuration import GenerationConfiguration
from models.prompt_block import PromptBlock


T = TypeVar("T")


class MatrixBuilder:
    """Build deterministic generation configurations."""

    @staticmethod
    def build(
        values: Sequence[T],
        selection: MatrixSelection,
    ) -> list[tuple[T, ...]]:

        values = list(values)

        if not values:
            return [()]

        operator = selection.operator

        if operator == MatrixOperator.INDIVIDUAL:
            return [(value,) for value in values]

        if operator == MatrixOperator.ALL:
            return [tuple(values)]

        if operator == MatrixOperator.PERMUTATION:
            minimum = (
                selection.minimum
                if selection.minimum is not None
                else 1
            )
            maximum = (
                selection.maximum
                if selection.maximum is not None
                else len(values)
            )

            if minimum < 1:
                raise ValueError(
                    "Permutation minimum must be >= 1."
                )

            if maximum < minimum:
                raise ValueError(
                    "Permutation maximum must be >= minimum."
                )

            if maximum > len(values):
                raise ValueError(
                    "Permutation maximum cannot exceed "
                    "the number of values."
                )

            result: list[tuple[T, ...]] = []

            for size in range(minimum, maximum + 1):
                result.extend(permutations(values, size))

            return result

        if operator == MatrixOperator.COMBINATION:
            minimum = (
                selection.minimum
                if selection.minimum is not None
                else 1
            )
            maximum = (
                selection.maximum
                if selection.maximum is not None
                else len(values)
            )

            if minimum < 1:
                raise ValueError(
                    "Combination minimum must be >= 1."
                )

            if maximum < minimum:
                raise ValueError(
                    "Combination maximum must be >= minimum."
                )

            if maximum > len(values):
                raise ValueError(
                    "Combination maximum cannot exceed "
                    "the number of values."
                )

            result: list[tuple[T, ...]] = []

            for size in range(minimum, maximum + 1):
                result.extend(combinations(values, size))

            return result

        raise ValueError(
            f"Unsupported matrix operator: {operator}"
        )

    @staticmethod
    def build_numeric(
        selection: NumericMatrixSelection,
    ) -> list[float]:
        """Build the numeric values represented by a matrix range."""
        if not selection.enabled:
            return []

        if selection.minimum is None or selection.maximum is None:
            raise ValueError(
                "Enabled numeric matrix selections require minimum and maximum."
            )

        minimum = float(selection.minimum)
        maximum = float(selection.maximum)
        steps = int(selection.steps)

        if steps < 1:
            raise ValueError("Numeric matrix steps must be >= 1.")

        if maximum < minimum:
            raise ValueError(
                "Numeric matrix maximum must be >= minimum."
            )

        if steps > 1 and maximum == minimum:
            raise ValueError(
                "Numeric matrix maximum must be greater than minimum "
                "when more than one step is requested."
            )

        if steps == 1:
            return [minimum]

        step = (maximum - minimum) / (steps - 1)
        return [
            round(minimum + index * step, 10)
            for index in range(steps)
        ]

    @classmethod
    def build_product(
        cls,
        dimensions: Sequence[
            tuple[Sequence[T], MatrixSelection]
        ],
    ) -> list[tuple[tuple[T, ...], ...]]:

        variants = [
            cls.build(values, selection)
            for values, selection in dimensions
        ]

        if not variants:
            return [()]

        return list(product(*variants))

    @staticmethod
    def _assemble_prompt_slots(
        prompts: Sequence[PromptSlot],
        selected_values: Sequence[PromptSlot],
    ) -> list[PromptSlot]:
        """Assemble prompt slots while preserving permutation order."""

        selected_ids = {
            prompt.slot_id
            for prompt in selected_values
        }

        variable_positions = [
            index
            for index, prompt in enumerate(prompts)
            if not prompt.fixed
            and prompt.slot_id in selected_ids
        ]

        result = list(prompts)

        for index, prompt in zip(
            variable_positions,
            selected_values,
        ):
            result[index] = prompt

        return [
            prompt
            for prompt in result
            if prompt.fixed
            or prompt.slot_id in selected_ids
        ]

    @classmethod
    def build_prompt_block_variants(
        cls,
        block: PromptBlock,
    ) -> list[tuple[PromptSlot, ...]]:
        """
        Build the variable selections for one Prompt Block.

        Empty blocks are ignored by the experiment builder. A block
        containing only fixed prompts produces one empty variable
        selection so its fixed prompt content remains active.
        """

        if not block.prompts:
            return []

        return cls.build(
            block.variable_prompts,
            block.matrix_selection,
        )

    @classmethod
    def build_prompt_blocks(
        cls,
        blocks: Sequence[PromptBlock],
    ) -> list[tuple[tuple[PromptBlock, tuple[PromptSlot, ...]], ...]]:
        """
        Build the Cartesian product of all non-empty Prompt Blocks.

        Block order is the canonical GUI order. Prompt order inside a
        block is the canonical GUI order.
        """

        active_blocks = [
            block
            for block in blocks
            if block.has_prompt
        ]

        if not active_blocks:
            return []

        block_variants = [
            [
                (block, selected_values)
                for selected_values in cls.build_prompt_block_variants(block)
            ]
            for block in active_blocks
        ]

        return list(product(*block_variants))

    @classmethod
    def _assemble_prompt_blocks(
        cls,
        block_variant: tuple[
            tuple[PromptBlock, tuple[PromptSlot, ...]], ...
        ],
    ) -> tuple[str, str]:
        """Return assembled positive text and compact block provenance."""

        prompt_parts: list[str] = []
        variant_ids: list[str] = []

        for block, selected_values in block_variant:
            prompt_slots = cls._assemble_prompt_slots(
                block.prompts,
                selected_values,
            )

            text = " ".join(
                prompt.text
                for prompt in prompt_slots
                if prompt.text
            )

            if text:
                prompt_parts.append(text)

            variant_id = block.variant_id(selected_values)
            if variant_id:
                variant_ids.append(variant_id)

        return (
            " ".join(prompt_parts),
            "+".join(variant_ids),
        )

    @staticmethod
    def build_resolution_values(
        selection: ResolutionMatrixSelection,
        width: int,
        height: int,
    ) -> list[tuple[int, int]]:
        """Build exact integer render sizes at a fixed aspect ratio.

        The selected axis is interpolated inclusively between minimum and
        maximum. The other axis is derived from the baseline width/height
        ratio; sizes are passed to Fooocus without post-render resizing.
        """
        if not selection.enabled:
            return []

        if selection.dimension not in {"width", "height"}:
            raise ValueError("Resolution matrix dimension must be 'width' or 'height'.")

        current = width if selection.dimension == "width" else height
        minimum = current if selection.minimum is None else int(selection.minimum)
        maximum = current if selection.maximum is None else int(selection.maximum)
        steps = int(selection.steps)

        if steps < 1:
            raise ValueError("Resolution matrix steps must be >= 1.")
        if maximum < minimum:
            raise ValueError("Resolution matrix maximum must be >= minimum.")

        axis_minimum, axis_maximum = (
            (MIN_GENERATION_WIDTH, MAX_GENERATION_WIDTH)
            if selection.dimension == "width"
            else (MIN_GENERATION_HEIGHT, MAX_GENERATION_HEIGHT)
        )
        if minimum < axis_minimum or maximum > axis_maximum:
            raise ValueError(
                f"Resolution matrix {selection.dimension} must be between "
                f"{axis_minimum} and {axis_maximum} pixels."
            )

        ratio = width / height if height else 1.0
        values = (
            [minimum]
            if steps == 1
            else [
                round(minimum + (maximum - minimum) * index / (steps - 1))
                for index in range(steps)
            ]
        )

        sizes: list[tuple[int, int]] = []
        for value in values:
            if selection.dimension == "width":
                resolved_width = value
                resolved_height = round(value / ratio)
            else:
                resolved_height = value
                resolved_width = round(value * ratio)

            if not (
                MIN_GENERATION_WIDTH <= resolved_width <= MAX_GENERATION_WIDTH
                and MIN_GENERATION_HEIGHT <= resolved_height <= MAX_GENERATION_HEIGHT
            ):
                raise ValueError(
                    "Resolution matrix produces a size outside the supported "
                    f"range: {resolved_width}x{resolved_height}."
                )
            sizes.append((resolved_width, resolved_height))

        return sizes

    @classmethod
    def iter_experiment(
        cls,
        experiment: Experiment,
    ) -> Iterator[GenerationConfiguration]:
        """Yield concrete generation configurations one by one."""

        if (
            not experiment.prompt_blocks
            and not experiment.positive_prompts
        ):
            # An experiment without a positive prompt is never a
            # generation candidate.
            experiment.set_configuration_count(0)
            return

        dimensions = []

        # Prompt Blocks replace the legacy positive-prompt dimension
        # whenever at least one non-empty block exists.
        prompt_block_mode = any(
            block.has_prompt
            for block in experiment.prompt_blocks
        )

        if not prompt_block_mode and experiment.positive_prompts:
            dimensions.append(
                (
                    [
                        prompt
                        for prompt in experiment.positive_prompts
                        if not prompt.fixed
                    ],
                    experiment.matrix.positive_prompts,
                    "positive_prompt",
                )
            )

        if experiment.negative_prompts:
            dimensions.append(
                (
                    [
                        prompt
                        for prompt in experiment.negative_prompts
                        if not prompt.fixed
                    ],
                    experiment.matrix.negative_prompts,
                    "negative_prompt",
                )
            )

        if experiment.styles and not experiment.random_style:
            dimensions.append(
                (
                    experiment.styles,
                    experiment.matrix.styles,
                    "styles",
                )
            )

        if experiment.style_references:
            dimensions.append(
                (
                    experiment.style_references,
                    experiment.matrix.style_references,
                    "style_references",
                )
            )

        if experiment.composition_references:
            dimensions.append(
                (
                    experiment.composition_references,
                    experiment.matrix.composition_references,
                    "composition_references",
                )
            )

        if experiment.generation.base_models:
            base_model_values = list(
                experiment.generation.base_models
            )
        elif experiment.generation.base_model:
            base_model_values = [
                experiment.generation.base_model
            ]
        else:
            base_model_values = []

        if base_model_values:
            dimensions.append(
                (
                    base_model_values,
                    experiment.matrix.base_models,
                    "base_model",
                )
            )

        if experiment.generation.refiner_model:
            dimensions.append(
                (
                    [experiment.generation.refiner_model],
                    experiment.matrix.refiner_models,
                    "refiner_model",
                )
            )

        if experiment.matrix.guidance_scale.enabled:
            dimensions.append(
                (
                    cls.build_numeric(
                        experiment.matrix.guidance_scale
                    ),
                    MatrixSelection(
                        operator=MatrixOperator.INDIVIDUAL
                    ),
                    "guidance_scale",
                )
            )

        if experiment.matrix.sharpness.enabled:
            dimensions.append(
                (
                    cls.build_numeric(
                        experiment.matrix.sharpness
                    ),
                    MatrixSelection(
                        operator=MatrixOperator.INDIVIDUAL
                    ),
                    "sharpness",
                )
            )

        if experiment.matrix.resolution.enabled:
            dimensions.append(
                (
                    cls.build_resolution_values(
                        experiment.matrix.resolution,
                        experiment.generation.width,
                        experiment.generation.height,
                    ),
                    MatrixSelection(
                        operator=MatrixOperator.INDIVIDUAL
                    ),
                    "resolution",
                )
            )

        raw_dimensions = [
            (values, selection)
            for values, selection, _ in dimensions
        ]

        variants = cls.build_product(raw_dimensions)

        if prompt_block_mode:
            prompt_block_variants = cls.build_prompt_blocks(
                experiment.prompt_blocks
            )
        else:
            prompt_block_variants = [()]

        configurations_count = 0
        configuration_id = 1

        requested_seed_count = max(
            1,
            experiment.generation.random_seed_count,
        )

        if experiment.generation.seed_mode == SeedMode.RANDOM:
            if experiment.generation.random_seed_fixed:
                # Fixed-random mode is a real experiment dimension: generate
                # the requested seeds once, persist them on the experiment,
                # and reuse them for every matrix combination and subsequent
                # run.
                stored_random_seeds = list(
                    experiment.generation.random_seeds
                )
                while len(stored_random_seeds) < requested_seed_count:
                    stored_random_seeds.append(
                        random.randint(
                            1,
                            (1 << 63) - 1,
                        )
                    )
                experiment.generation.random_seeds = stored_random_seeds
                selected_seeds = stored_random_seeds[:requested_seed_count]
            else:
                # Non-fixed random mode deliberately does not preselect a
                # seed dimension. Each job below receives a fresh seed.
                selected_seeds = [None]
        else:
            if experiment.generation.seeds:
                selected_seeds = list(
                    experiment.generation.seeds
                )
            else:
                selected_seeds = [
                    experiment.generation.seed
                ]

        # Fixed seeds remain the outer loop, preserving the established
        # comparison-friendly ordering. In non-fixed random mode there is
        # only one outer placeholder and the actual seed is generated per job.
        for selected_seed in selected_seeds:
            for prompt_block_variant in prompt_block_variants:
                block_prompt, block_variant_id = (
                    cls._assemble_prompt_blocks(
                        prompt_block_variant
                    )
                )

                for variant in variants:
                    if experiment.random_style:
                        available_styles = list(
                            experiment.styles
                        )

                        if not available_styles:
                            raise ValueError(
                                "Random Selected is enabled, "
                                "but no styles are selected."
                            )

                        requested_style_count = max(
                            1,
                            experiment.random_style_count,
                        )

                        if (
                            requested_style_count
                            > len(available_styles)
                        ):
                            raise ValueError(
                                "Random Style count "
                                f"({requested_style_count}) exceeds "
                                "the number of available styles "
                                f"({len(available_styles)})."
                            )

                        selected_styles = random.sample(
                            available_styles,
                            requested_style_count,
                        )
                    else:
                        selected_styles = [None]

                    for selected_style in selected_styles:
                        if (
                            experiment.generation.seed_mode == SeedMode.RANDOM
                            and not experiment.generation.random_seed_fixed
                        ):
                            # A non-fixed seed is generated per concrete job,
                            # including when Random Style creates multiple jobs.
                            job_seeds = [
                                random.randint(
                                    1,
                                    (1 << 63) - 1,
                                )
                                for _ in range(requested_seed_count)
                            ]
                        else:
                            job_seeds = [selected_seed]

                        for job_seed in job_seeds:
                            configuration = GenerationConfiguration(
                                configuration_id=configuration_id,
                                width=experiment.generation.width,
                                height=experiment.generation.height,
                                aspect_ratio=experiment.generation.aspect_ratio,
                                seed=job_seed,
                                positive_prompt=block_prompt,
                                prompt_block_variant_id=block_variant_id,
                                positive_prompt_slots=(
                                    [
                                        prompt.slot_id
                                        for block, selected_values
                                        in prompt_block_variant
                                        for prompt in cls._assemble_prompt_slots(
                                            block.prompts,
                                            selected_values,
                                        )
                                    ]
                                    if prompt_block_mode
                                    else [
                                        prompt.slot_id
                                        for prompt in experiment.positive_prompts
                                        if prompt.fixed
                                    ]
                                ),
                                negative_prompt_slots=[
                                    prompt.slot_id
                                    for prompt in experiment.negative_prompts
                                    if prompt.fixed
                                ],
                                performance=experiment.generation.performance,
                                guidance_scale=(
                                    experiment.generation.guidance_scale
                                ),
                                sharpness=experiment.generation.sharpness,
                                base_model=None,
                                refiner_model=(
                                    experiment.generation.refiner_model
                                ),
                                refiner_switch=(
                                    experiment.generation.refiner_switch
                                ),
                                output_format=(
                                    experiment.generation.output_format
                                ),
                            )

                            for (
                                (_, _, field_name),
                                selected_values,
                            ) in zip(
                                dimensions,
                                variant,
                            ):
                                if field_name == "positive_prompt":
                                    prompt_slots = (
                                        cls._assemble_prompt_slots(
                                            experiment.positive_prompts,
                                            selected_values,
                                        )
                                    )

                                    configuration.positive_prompt = (
                                        " ".join(
                                            prompt.text
                                            for prompt in prompt_slots
                                        )
                                    )

                                    configuration.positive_prompt_slots = [
                                        prompt.slot_id
                                        for prompt in prompt_slots
                                    ]

                                elif field_name == "negative_prompt":
                                    prompt_slots = (
                                        cls._assemble_prompt_slots(
                                            experiment.negative_prompts,
                                            selected_values,
                                        )
                                    )

                                    configuration.negative_prompt = (
                                        " ".join(
                                            prompt.text
                                            for prompt in prompt_slots
                                        )
                                    )

                                    configuration.negative_prompt_slots = [
                                        prompt.slot_id
                                        for prompt in prompt_slots
                                    ]

                                elif field_name == "styles":
                                    configuration.styles = list(
                                        selected_values
                                    )

                                elif field_name == "style_references":
                                    configuration.style_references = list(
                                        selected_values
                                    )

                                elif field_name == "composition_references":
                                    configuration.composition_references = list(
                                        selected_values
                                    )

                                elif field_name == "base_model":
                                    configuration.base_model = (
                                        selected_values[0]
                                    )

                                elif field_name == "refiner_model":
                                    configuration.refiner_model = (
                                        selected_values[0]
                                    )

                                elif field_name == "guidance_scale":
                                    configuration.guidance_scale = float(
                                        selected_values[0]
                                    )

                                elif field_name == "sharpness":
                                    configuration.sharpness = float(
                                        selected_values[0]
                                    )

                                elif field_name == "resolution":
                                    configuration.width, configuration.height = (
                                        selected_values[0]
                                    )

                            if selected_style is not None:
                                configuration.styles = [
                                    selected_style
                                ]

                            configurations_count += 1
                            yield configuration
                            configuration_id += 1

        experiment.set_configuration_count(
            configurations_count
        )

    @classmethod
    def build_experiment(
        cls,
        experiment: Experiment,
    ) -> list[GenerationConfiguration]:
        """Build all concrete generation configurations."""

        return list(
            cls.iter_experiment(experiment)
        )
