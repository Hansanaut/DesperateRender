from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QDialog

from gui.windows_chrome import apply_desperate_render_titlebar


class _DesperateRenderDialogChrome(QObject):
    """Apply the DR title-bar treatment to dialogs as they are shown."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            title = watched.windowTitle().strip().lower()
            if title in {"desperate render settings", "prompt blocks"}:
                apply_desperate_render_titlebar(watched)
        return False


_filter: _DesperateRenderDialogChrome | None = None


def install_dialog_chrome() -> None:
    """Install the dialog title-bar filter once for the current Qt app."""
    global _filter
    app = QApplication.instance()
    if app is None or _filter is not None:
        return
    _filter = _DesperateRenderDialogChrome(app)
    app.installEventFilter(_filter)
