from __future__ import annotations

from pathlib import Path
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gui.panels.properties_panel import PropertiesPanel
from models.experiment import Experiment, GenerationSettings


def main() -> None:
    settings = GenerationSettings()
    assert settings.width == 1024, settings.width
    assert settings.height == 768, settings.height
    assert settings.aspect_ratio == "4:3", settings.aspect_ratio

    app = QApplication.instance() or QApplication(sys.argv)
    experiment = Experiment(experiment_id="block-b-test")
    panel = PropertiesPanel(experiment)

    assert experiment.styles == []
    assert panel.style_selection_label.text() == "0 styles selected"

    panel.set_style_choices([
        "Fooocus V2",
        "Fooocus Enhance",
        "Fooocus Sharp",
    ])

    assert experiment.styles == []
    assert panel.style_selection_label.text() == "0 styles selected"

    item = panel.style_list.item(0)
    item.setCheckState(Qt.Checked)
    app.processEvents()

    assert len(experiment.styles) == 1
    assert panel.style_selection_label.text() == "1 styles selected"

    print("Default resolution 1024x768: OK")
    print("Initial styles selected: 0: OK")
    print("Runtime styles start unchecked: OK")
    print("Style selection counter: OK")

    panel.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
