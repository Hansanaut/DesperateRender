from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow direct execution via: python tools\\test_gui_layout.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea

from gui.main_window import MainWindow


EXPECTED_EXPANDED_WIDTHS = [668, 700, 360]
COLLAPSED_PANEL_WIDTH = 32
TOGGLE_BUTTON_WIDTH = 24


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    window = MainWindow()
    # The offscreen Qt platform can expose a tiny virtual screen.  Give the
    # layout test a realistic window size so the production auto-collapse
    # logic does not intentionally collapse Preview before the assertions.
    window.resize(1800, 1000)
    QApplication.processEvents()
    window._set_preview_visible(True)
    window._set_queue_visible(True)
    QApplication.processEvents()
    window.show()
    app.processEvents()

    splitter = window.splitter
    assert splitter is not None
    assert splitter.count() == 3
    assert not splitter.childrenCollapsible()

    actual_min_widths = [
        splitter.widget(index).minimumWidth()
        for index in range(splitter.count())
    ]
    assert actual_min_widths == EXPECTED_EXPANDED_WIDTHS, actual_min_widths

    assert window.preview_toggle_button.objectName() == "panelToggleButton"
    assert window.queue_toggle_button.objectName() == "panelToggleButton"

    # The Properties form must remain usable when it grows vertically.
    scroll_areas = window.properties_panel.findChildren(QScrollArea)
    assert len(scroll_areas) == 1

    scroll_area = scroll_areas[0]
    assert scroll_area.widgetResizable()
    assert scroll_area.verticalScrollBarPolicy() != Qt.ScrollBarAlwaysOff
    assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff

    # Collapse both side panels. Their visible footprint is exactly the
    # dedicated 32 px toggle area; the buttons themselves remain 24 px wide.
    window._set_preview_visible(False)
    window._set_queue_visible(False)
    app.processEvents()

    assert splitter.widget(0).minimumWidth() == COLLAPSED_PANEL_WIDTH
    assert splitter.widget(0).maximumWidth() == COLLAPSED_PANEL_WIDTH
    assert splitter.widget(2).minimumWidth() == COLLAPSED_PANEL_WIDTH
    assert splitter.widget(2).maximumWidth() == COLLAPSED_PANEL_WIDTH

    assert not window.preview_toggle_button.isChecked()
    assert not window.queue_toggle_button.isChecked()

    assert window.preview_toggle_area.layout().contentsMargins().left() == 7
    assert window.preview_toggle_area.layout().contentsMargins().right() == 1
    assert window.queue_toggle_area.layout().contentsMargins().left() == 1
    assert window.queue_toggle_area.layout().contentsMargins().right() == 7
    assert window.preview_toggle_button.width() == TOGGLE_BUTTON_WIDTH
    assert window.queue_toggle_button.width() == TOGGLE_BUTTON_WIDTH

    # Re-expand both panels. This specifically guards against the previous
    # 20/24/32 px mix-up and verifies that expanded minimums are restored.
    window._set_preview_visible(True)
    window._set_queue_visible(True)
    app.processEvents()

    assert splitter.widget(0).minimumWidth() == EXPECTED_EXPANDED_WIDTHS[0]
    assert splitter.widget(1).minimumWidth() == EXPECTED_EXPANDED_WIDTHS[1]
    assert splitter.widget(2).minimumWidth() == EXPECTED_EXPANDED_WIDTHS[2]
    assert splitter.widget(0).maximumWidth() > EXPECTED_EXPANDED_WIDTHS[0]
    assert splitter.widget(2).maximumWidth() > EXPECTED_EXPANDED_WIDTHS[2]
    assert window.preview_toggle_button.isChecked()
    assert window.queue_toggle_button.isChecked()

    # Queue-only collapse must not affect Preview and must not reference the
    # removed stale queue_toggle_action.
    window._set_queue_visible(False)
    app.processEvents()

    assert window.preview_toggle_button.isChecked()
    assert splitter.widget(0).minimumWidth() == EXPECTED_EXPANDED_WIDTHS[0]
    assert splitter.widget(2).minimumWidth() == COLLAPSED_PANEL_WIDTH
    assert splitter.widget(2).maximumWidth() == COLLAPSED_PANEL_WIDTH
    assert not window.queue_toggle_button.isChecked()

    # Restore the normal state before testing the compact/collapsed layout.
    window._set_preview_visible(False)
    app.processEvents()

    expected_compact_width = (
        COLLAPSED_PANEL_WIDTH
        + EXPECTED_EXPANDED_WIDTHS[1]
        + COLLAPSED_PANEL_WIDTH
    )
    window.resize(expected_compact_width, 700)
    app.processEvents()

    actual_sizes = splitter.sizes()
    assert actual_sizes[0] == COLLAPSED_PANEL_WIDTH, actual_sizes
    assert actual_sizes[1] >= EXPECTED_EXPANDED_WIDTHS[1], actual_sizes
    assert actual_sizes[2] == COLLAPSED_PANEL_WIDTH, actual_sizes

    window.close()

    print("GUI minimum-size checks: OK")
    print("Properties vertical scrolling: OK")
    print("Panel collapse/expand checks: OK")
    print("Compact resize check: OK")
    print("\n=== ALL GUI LAYOUT TESTS PASSED ===")


if __name__ == "__main__":
    main()


def test_prompt_reorder_ui():
    """Prompt rows expose a drag handle and keyboard reorder support."""
    from gui.panels.properties_panel import PromptDragHandle

    assert PromptDragHandle is not None
    assert PromptDragHandle.staticMetaObject.className() == "PromptDragHandle"
    panel = MainWindow().properties_panel
    assert panel.positive_prompt_rows
    assert panel.negative_prompt_rows
    assert panel.positive_prompt_rows[0].findChild(PromptDragHandle) is not None
    assert panel.negative_prompt_rows[0].findChild(PromptDragHandle) is not None
