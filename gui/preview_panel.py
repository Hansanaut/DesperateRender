from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from models.image_generation_result import ImageGenerationResult


class PreviewPanel(QGroupBox):
    """Displays generated images."""

    def __init__(self) -> None:
        super().__init__("Preview")
        self.setObjectName("mainPanel")

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(320, 240)
        self._original_pixmap = None
        self._current_image_path: Path | None = None
        self._logo_pixmap = self._load_logo()

        frame = QFrame()
        frame_layout = QVBoxLayout(frame)
        frame_layout.addWidget(self.image)

        layout = QVBoxLayout(self)
        layout.addWidget(frame)

        # Until the first generated image is available, show the PromptLAB
        # logo as the neutral preview placeholder.
        self._show_logo()

    @staticmethod
    def _load_logo() -> QPixmap:
        """Load PromptLAB's root-level preview.png, if available."""
        logo_path = Path(__file__).resolve().parents[2] / "preview.png"
        pixmap = QPixmap(str(logo_path))
        return pixmap if not pixmap.isNull() else QPixmap()

    def _show_logo(self) -> None:
        """Show the PromptLAB logo as the empty-preview placeholder."""
        self._original_pixmap = None
        self._current_image_path = None
        if self._logo_pixmap.isNull():
            self.image.setPixmap(QPixmap())
            self.image.setText("No image selected")
            return
        self._update_logo()

    def _update_logo(self) -> None:
        if self._logo_pixmap.isNull():
            return
        scaled = self._logo_pixmap.scaled(
            self.image.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image.setPixmap(scaled)
        self.image.setText("")

    def set_images(self, result: ImageGenerationResult) -> None:
        """Display the first generated image."""

        if not result.images:
            self.clear()
            return

        image_path = Path(result.images[0])

        if not image_path.exists():
            self.image.setText(
                f"Image file not found:\n{image_path}"
            )
            self.image.setPixmap(QPixmap())
            return

        pixmap = QPixmap(str(image_path))

        if pixmap.isNull():
            self.image.setText(
                f"Could not load image:\n{image_path}"
            )
            self.image.setPixmap(QPixmap())
            return

        self._original_pixmap = pixmap
        self._current_image_path = image_path
        self._update_preview()

    @property
    def current_image_path(self) -> Path | None:
        """Return the last successfully displayed generated image."""
        return self._current_image_path

    def clear(self) -> None:
        """Clear the preview and restore the PromptLAB logo."""

        self._show_logo()

    def resizeEvent(self, event) -> None:
        """Keep the preview image fitted to the available space."""

        super().resizeEvent(event)
        self._update_preview()

    def _update_preview(self) -> None:
        """Scale the current image to fit the preview area."""

        pixmap = getattr(self, "_original_pixmap", None)

        if pixmap is None or pixmap.isNull():
            self._update_logo()
            return

        available_size = self.image.size()

        scaled = pixmap.scaled(
            available_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.image.setPixmap(scaled)
        self.image.setText("")