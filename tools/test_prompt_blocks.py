import json
import tempfile
from pathlib import Path

from models.experiment import (
    Experiment,
    MatrixOperator,
    MatrixSelection,
    PromptSlot,
    SeedMode,
)
from models.prompt_block import PromptBlock
from services.experiment.experiment_store import ExperimentStore
from services.experiment.matrix_builder import MatrixBuilder


def main() -> None:
    experiment = Experiment(
        experiment_id="prompt-block-test",
    )

    experiment.prompt_blocks = [
        PromptBlock(
            block_id="A",
            name="Corridor State",
            prompts=[
                PromptSlot(1, "spaceship corridor", fixed=True),
                PromptSlot(2, "damaged"),
                PromptSlot(3, "flooded"),
            ],
            matrix_selection=MatrixSelection(
                operator=MatrixOperator.INDIVIDUAL,
            ),
        ),
        PromptBlock(
            block_id="B",
            name="Lighting",
            prompts=[
                PromptSlot(1, "cold lighting"),
                PromptSlot(2, "red emergency lighting"),
            ],
            matrix_selection=MatrixSelection(
                operator=MatrixOperator.INDIVIDUAL,
            ),
        ),
    ]

    experiment.generation.seed_mode = SeedMode.FIXED
    experiment.generation.seeds = [123]

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 4
    assert [
        configuration.positive_prompt
        for configuration in configurations
    ] == [
        "spaceship corridor damaged cold lighting",
        "spaceship corridor damaged red emergency lighting",
        "spaceship corridor flooded cold lighting",
        "spaceship corridor flooded red emergency lighting",
    ]

    assert [
        configuration.prompt_block_variant_id
        for configuration in configurations
    ] == [
        "A1+A2+B1",
        "A1+A2+B2",
        "A1+A3+B1",
        "A1+A3+B2",
    ]

    assert experiment.configuration_count == 4
    print("Multiple blocks + Cartesian product: OK")
    print("Fixed prompt position inside block: OK")
    print("Block provenance IDs: OK")

    # Combination follows the GUI order and preserves the block ID order.
    experiment.prompt_blocks[0].matrix_selection = MatrixSelection(
        operator=MatrixOperator.COMBINATION,
        minimum=2,
        maximum=2,
    )

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 2
    assert [
        configuration.prompt_block_variant_id
        for configuration in configurations
    ] == [
        "A1+A2+A3+B1",
        "A1+A2+A3+B2",
    ]
    assert configurations[0].positive_prompt == (
        "spaceship corridor damaged flooded cold lighting"
    )
    print("Combination inside Prompt Block: OK")

    # Permutation changes prompt order inside the block.
    experiment.prompt_blocks[0].matrix_selection = MatrixSelection(
        operator=MatrixOperator.PERMUTATION,
        minimum=2,
        maximum=2,
    )
    experiment.prompt_blocks[1].matrix_selection = MatrixSelection(
        operator=MatrixOperator.INDIVIDUAL,
    )

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 4
    assert [
        configuration.prompt_block_variant_id
        for configuration in configurations
    ] == [
        "A1+A2+A3+B1",
        "A1+A2+A3+B2",
        "A1+A3+A2+B1",
        "A1+A3+A2+B2",
    ]
    assert configurations[2].positive_prompt == (
        "spaceship corridor flooded damaged cold lighting"
    )
    print("Permutation order inside Prompt Block: OK")

    # Empty blocks are ignored.
    experiment.prompt_blocks.insert(
        1,
        PromptBlock(
            block_id="C",
            name="Empty",
        ),
    )
    configurations = MatrixBuilder.build_experiment(experiment)
    assert len(configurations) == 4
    assert all(
        "+C" not in configuration.prompt_block_variant_id
        for configuration in configurations
    )
    print("Empty block ignored: OK")

    # A single block is the natural reduction of the legacy matrix behavior.
    experiment.prompt_blocks = [
        PromptBlock(
            block_id="A",
            prompts=[
                PromptSlot(1, "one"),
                PromptSlot(2, "two"),
                PromptSlot(3, "three"),
            ],
            matrix_selection=MatrixSelection(
                operator=MatrixOperator.INDIVIDUAL,
            ),
        )
    ]
    configurations = MatrixBuilder.build_experiment(experiment)
    assert len(configurations) == 3
    assert [
        configuration.prompt_block_variant_id
        for configuration in configurations
    ] == ["A1", "A2", "A3"]
    print("Single block reduction: OK")

    # No positive prompt means no generation candidates.
    empty_experiment = Experiment(
        experiment_id="empty-prompt-test",
    )
    empty_experiment.generation.seed_mode = SeedMode.FIXED
    empty_experiment.generation.seeds = [1]
    assert MatrixBuilder.build_experiment(empty_experiment) == []
    assert empty_experiment.configuration_count == 0
    print("No experiment without a prompt: OK")

    # Prompt blocks must survive experiment persistence.
    with tempfile.TemporaryDirectory() as tmp:
        store = ExperimentStore(Path(tmp))
        stored_experiment = Experiment(
            experiment_id="20261005-001",
            prompt_blocks=[
                PromptBlock(
                    block_id="A",
                    name="Corridor State",
                    prompts=[
                        PromptSlot(1, "base", fixed=True),
                        PromptSlot(2, "damaged"),
                    ],
                    matrix_selection=MatrixSelection(
                        operator=MatrixOperator.INDIVIDUAL,
                    ),
                ),
                PromptBlock(
                    block_id="B",
                    name="Lighting",
                    prompts=[
                        PromptSlot(1, "cold"),
                        PromptSlot(2, "red"),
                    ],
                ),
            ],
        )

        target = store.save(stored_experiment)
        payload = json.loads(
            target.read_text(encoding="utf-8")
        )
        assert len(payload["prompt_blocks"]) == 2

        loaded = store.load(target)
        assert [
            block.block_id
            for block in loaded.prompt_blocks
        ] == ["A", "B"]
        assert loaded.prompt_blocks[0].name == "Corridor State"
        assert loaded.prompt_blocks[0].prompts[0].fixed is True
        assert loaded.prompt_blocks[0].prompts[1].text == "damaged"
        assert loaded.prompt_blocks[1].matrix_selection.operator == (
            MatrixOperator.INDIVIDUAL
        )
        print("Prompt Block persistence round-trip: OK")

    print("=== ALL PROMPT BLOCK TESTS PASSED ===")


if __name__ == "__main__":
    main()


def test_fixed_prompt_provenance() -> None:
    block = PromptBlock(
        block_id="A",
        prompts=[
            PromptSlot(slot_id=1, text="fixed", fixed=True),
            PromptSlot(slot_id=2, text="one"),
            PromptSlot(slot_id=3, text="two"),
        ],
        matrix_selection=MatrixSelection(
            operator=MatrixOperator.INDIVIDUAL
        ),
    )
    variants = MatrixBuilder.build_prompt_block_variants(block)
    assert block.variant_id(variants[0]) == "A1+A2"
    assert block.variant_id(variants[1]) == "A1+A3"
    print("Fixed prompt provenance: OK")
