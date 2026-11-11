from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gui.panels.properties_panel import PropertiesPanel
from models.experiment import Experiment


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    panel = PropertiesPanel(
        Experiment(experiment_id="style-ui-test")
    )
    panel.resize(460, 700)
    panel.show()
    app.processEvents()

    styles = [f"Style {index:02d}" for index in range(20)]
    panel.set_style_choices(styles)
    app.processEvents()

    list_widget = panel.style_list

    # The runtime style pool must be loaded completely.
    assert list_widget.count() == 20
    assert panel.experiment.available_styles == styles

    original_order = [
        list_widget.item(index).text()
        for index in range(list_widget.count())
    ]

    # Exercise the real itemChanged -> styles_changed() path directly.
    # This is deterministic on Qt's offscreen platform and tests the same
    # state transition used by the checkable style rows.
    for index in range(10):
        list_widget.item(index).setCheckState(Qt.Checked)

    app.processEvents()

    assert [
        list_widget.item(index).text()
        for index in range(list_widget.count())
    ] == original_order

    assert len(panel.experiment.styles) == 10
    assert panel.style_selection_label.text() == "10 styles selected"

    assert list_widget.item(0).text().startswith("STY#1  ")
    assert list_widget.item(1).text().startswith("STY#2  ")

    assert all(
        list_widget.item(index).checkState() == Qt.Checked
        for index in range(10)
    )

    assert all(
        list_widget.item(index).checkState() == Qt.Unchecked
        for index in range(10, 20)
    )

    # Random Selected must be limited to the currently selected styles.
    panel.random_style_checkbox.setChecked(True)
    app.processEvents()

    assert panel.random_style_count.maximum() == 10

    panel.random_style_count.setValue(10)

    # Reduce the selection pool to three styles.
    for index in range(3, 20):
        list_widget.item(index).setCheckState(Qt.Unchecked)

    app.processEvents()

    assert len(panel.experiment.styles) == 3
    assert panel.random_style_count.maximum() == 3
    assert panel.random_style_count.value() == 3

    # A partial selection must produce the tri-state Select All indicator.
    assert panel.style_select_all.checkState() == Qt.PartiallyChecked

    # Select All selects the complete pool without rebuilding the list.
    QTest.mouseClick(
        panel.style_select_all,
        Qt.LeftButton,
    )
    app.processEvents()

    assert len(panel.experiment.styles) == 20
    assert panel.style_select_all.checkState() == Qt.Checked

    assert all(
        list_widget.item(index).checkState() == Qt.Checked
        for index in range(list_widget.count())
    )

    # Clicking Select All again clears the complete pool.
    QTest.mouseClick(
        panel.style_select_all,
        Qt.LeftButton,
    )
    app.processEvents()

    assert panel.experiment.styles == []
    assert panel.style_select_all.checkState() == Qt.Unchecked

    assert all(
        list_widget.item(index).checkState() == Qt.Unchecked
        for index in range(list_widget.count())
    )

    # Partial selection + "Selected styles on top".
    for index in (1, 4, 7):
        list_widget.item(index).setCheckState(Qt.Checked)

    app.processEvents()

    assert len(panel.experiment.styles) == 3

    panel.style_sort_selected_top.setChecked(True)
    app.processEvents()

    assert [
        list_widget.item(index).checkState() == Qt.Checked
        for index in range(3)
    ] == [True, True, True]

    # Disable sorting again. The original runtime/Fooocus order must return.
    panel.style_sort_selected_top.setChecked(False)
    app.processEvents()

    assert [
        list_widget.item(index).text()
        for index in range(list_widget.count())
    ] == original_order

    # From a partial selection, Select All selects everything.
    QTest.mouseClick(
        panel.style_select_all,
        Qt.LeftButton,
    )
    app.processEvents()

    assert len(panel.experiment.styles) == 20

    # A second click clears everything again.
    QTest.mouseClick(
        panel.style_select_all,
        Qt.LeftButton,
    )
    app.processEvents()

    assert panel.experiment.styles == []
    assert panel.style_select_all.checkState() == Qt.Unchecked

    panel.deleteLater()
    app.processEvents()

    print("Style pool loading: OK")
    print("Style selection / itemChanged path: OK")
    print("Random Selected selection pool: OK")
    print("Select All / tri-state selection: OK")
    print("Selected styles on top / restore order: OK")
    print("=== ALL STYLE SELECTION UI TESTS PASSED ===")


def test_random_selected_uses_selection_pool() -> None:
    """Regression: Random Selected must never sample unselected styles."""
    from models.experiment import Experiment
    from services.experiment.matrix_builder import MatrixBuilder

    experiment = Experiment()
    experiment.available_styles = ["A", "B", "C", "D"]
    experiment.styles = ["B", "D"]
    experiment.random_style = True
    experiment.random_style_count = 2

    configs = MatrixBuilder.build_experiment(experiment)

    assert configs
    assert all(
        set(config.styles) <= {"B", "D"}
        for config in configs
    )


if __name__ == "__main__":
    main()