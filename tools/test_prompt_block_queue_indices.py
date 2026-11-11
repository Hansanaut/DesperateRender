from __future__ import annotations

from models.experiment import Experiment, MatrixSelection, PromptSlot
from models.prompt_block import PromptBlock
from services.experiment.matrix_builder import MatrixBuilder


def main() -> None:
    experiment = Experiment("queue-test")
    experiment.prompt_blocks = [
        PromptBlock(
            "A",
            prompts=[
                PromptSlot(1, "airplane"),
                PromptSlot(2, "in flight"),
            ],
            matrix_selection=MatrixSelection(),
        )
    ]

    configurations = MatrixBuilder.build_experiment(experiment)
    assert configurations, "Expected at least one configuration"
    assert configurations[0].prompt_block_variant_id == "A1"
    assert configurations[0].positive_prompt == "airplane"

    print("Prompt block queue indices: OK")
    print("=== PROMPT BLOCK QUEUE INDICES TEST PASSED ===")


if __name__ == "__main__":
    main()
