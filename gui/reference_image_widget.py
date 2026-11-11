from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


class ReferenceDropList(QListWidget):
    """Image list that accepts local image files by drag and drop."""

    paths_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setIconSize(QSize(72, 72))
        self.setGridSize(QSize(112, 108))
        self.setMinimumHeight(118)
        self.setMaximumHeight(190)
        self.setToolTip("Drop image files here, or use Add…")

    def dragEnterEvent(self, event) -> None:
        if self._has_image_urls(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._has_image_urls(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = [
            Path(url.toLocalFile()).resolve()
            for url in event.mimeData().urls()
            if url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES
        ]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    @staticmethod
    def _has_image_urls(urls) -> bool:
        return any(
            url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES
            for url in urls
        )

    def add_paths(self, paths: list[Path]) -> None:
        existing = {
            Path(self.item(index).data(Qt.UserRole)).resolve()
            for index in range(self.count())
        }

        changed = False
        for path in paths:
            path = path.resolve()
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if path in existing:
                continue

            item = QListWidgetItem()
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            item.setText(path.name)
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(
                    72,
                    72,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )))
            self.addItem(item)
            existing.add(path)
            changed = True

        if changed:
            self.paths_changed.emit()

    def set_paths(self, paths: list[str]) -> None:
        self.clear()
        self.add_paths([Path(path) for path in paths if path])
        self.clearSelection()

    def paths(self) -> list[str]:
        return [
            str(Path(self.item(index).data(Qt.UserRole)).resolve())
            for index in range(self.count())
        ]

    def remove_selected(self) -> None:
        selected = self.selectedItems()
        if not selected:
            return
        for item in selected:
            self.takeItem(self.row(item))
        self.paths_changed.emit()


class ReferenceImagePanel(QWidget):
    """Compact reference-image picker with file selection and drag/drop."""

    paths_changed = Signal()

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: 600;")

        self.hint_label = QLabel("Drop images here")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("color: #8A97AA;")

        self.list_widget = ReferenceDropList()
        self.list_widget.paths_changed.connect(self._changed)

        self.add_button = QPushButton("Add…")
        self.add_button.clicked.connect(self._browse)

        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self._remove_selected)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(5)
        layout.addWidget(self.title_label)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.hint_label)
        layout.addLayout(actions)

        self._update_hint()

    def dragEnterEvent(self, event) -> None:
        if ReferenceDropList._has_image_urls(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if ReferenceDropList._has_image_urls(event.mimeData().urls()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        paths = [
            Path(url.toLocalFile()).resolve()
            for url in event.mimeData().urls()
            if url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES
        ]
        if paths:
            self.list_widget.add_paths(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    def _browse(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            f"Select {self.title_label.text()} reference images",
            "",
            IMAGE_FILTER,
        )
        if files:
            self.list_widget.add_paths([Path(path) for path in files])

    def _remove_selected(self) -> None:
        self.list_widget.remove_selected()

    def _changed(self) -> None:
        self._update_hint()
        self.paths_changed.emit()

    def _update_hint(self) -> None:
        self.hint_label.setVisible(self.list_widget.count() == 0)

    def set_paths(self, paths: list[str]) -> None:
        self.list_widget.set_paths(paths)
        self._update_hint()

    def paths(self) -> list[str]:
        return self.list_widget.paths()
