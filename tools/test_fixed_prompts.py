import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from models.experiment import (
    Experiment,
    MatrixOperator,
    MatrixSelection,
    PromptSlot,
    SeedMode,
)
from services.experiment.matrix_builder import MatrixBuilder


def main() -> None:
    experiment = Experiment(
        experiment_id="fixed-prompt-test",
    )

    experiment.positive_prompts = [
        PromptSlot(1, "BASE SETTING", fixed=True),
        PromptSlot(2, "RED DECK"),
        PromptSlot(3, "BLUE DECK"),
    ]

    experiment.matrix.positive_prompts = MatrixSelection(
        operator=MatrixOperator.INDIVIDUAL,
    )

    experiment.generation.seed_mode = SeedMode.FIXED
    experiment.generation.seeds = [123]

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 2, len(configurations)
    assert (
        configurations[0].positive_prompt == "BASE SETTING RED DECK"
    ), configurations[0].positive_prompt
    assert (
        configurations[1].positive_prompt == "BASE SETTING BLUE DECK"
    ), configurations[1].positive_prompt

    # Fixed prompt remains in its original position when prompt 2 is varied.
    experiment.positive_prompts = [
        PromptSlot(1, "BASE", fixed=True),
        PromptSlot(2, "VARIANT A"),
        PromptSlot(3, "FIXED MIDDLE", fixed=True),
        PromptSlot(4, "VARIANT B"),
    ]

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 2, len(configurations)
    assert (
        configurations[0].positive_prompt
        == "BASE VARIANT A FIXED MIDDLE"
    ), configurations[0].positive_prompt
    assert (
        configurations[1].positive_prompt
        == "BASE FIXED MIDDLE VARIANT B"
    ), configurations[1].positive_prompt

    # If all prompts are fixed, there is exactly one configuration.
    experiment.positive_prompts = [
        PromptSlot(1, "ONE", fixed=True),
        PromptSlot(2, "TWO", fixed=True),
    ]

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 1, len(configurations)
    assert configurations[0].positive_prompt == "ONE TWO"

    # Negative prompts use the same fixed semantics.
    # A valid positive prompt is required for a generation configuration.
    experiment.positive_prompts = [
        PromptSlot(1, "BASE PROMPT", fixed=True),
    ]
    experiment.negative_prompts = [
        PromptSlot(1, "NO BASE", fixed=True),
        PromptSlot(2, "NO RED"),
        PromptSlot(3, "NO BLUE"),
    ]

    configurations = MatrixBuilder.build_experiment(experiment)

    assert len(configurations) == 2, len(configurations)
    assert configurations[0].negative_prompt == "NO BASE NO RED"
    assert configurations[1].negative_prompt == "NO BASE NO BLUE"

    # GUI representation: numbered rows and Fixed checkbox.
    app = QApplication.instance() or QApplication(sys.argv)
    from gui.panels.properties_panel import PropertiesPanel

    gui_experiment = Experiment(experiment_id="fixed-prompt-gui-test")
    panel = PropertiesPanel(gui_experiment)

    assert len(panel.positive_prompt_edits) == 1
    assert panel.positive_prompt_numbers[0].text() == "1"

    panel.positive_prompt_edits[0].setPlainText("BASE")
    panel.add_positive_prompt()
    panel.positive_prompt_edits[1].setPlainText("VARIANT")
    panel.positive_prompt_fixed[0].setChecked(True)
    app.processEvents()

    assert panel.positive_prompt_numbers[0].text() == "1"
    assert panel.positive_prompt_numbers[1].text() == "2"
    assert gui_experiment.positive_prompts[0].fixed is True
    assert gui_experiment.positive_prompts[1].fixed is False

    panel.deleteLater()
    app.processEvents()

    print("Fixed prompt GUI controls: OK")
    print("Fixed prompt matrix behavior: OK")
    print("Fixed prompt position preservation: OK")
    print("All-fixed prompt behavior: OK")
    print("Fixed negative prompt behavior: OK")
    print("=== ALL FIXED PROMPT TESTS PASSED ===")


if __name__ == "__main__":
    main()