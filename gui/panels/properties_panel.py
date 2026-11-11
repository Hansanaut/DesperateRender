from __future__ import annotations

from pathlib import Path
from typing import Any

from models.experiment import (
    Experiment,
    MatrixOperator,
    PromptSlot,
    ReferenceImage,
    ReferenceType,
    SeedMode,
    MIN_GENERATION_WIDTH,
    MAX_GENERATION_WIDTH,
    MIN_GENERATION_HEIGHT,
    MAX_GENERATION_HEIGHT,
    GENERATION_SIZE_STEP,
)

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPainter
from gui.reference_image_widget import ReferenceImagePanel

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsOpacityEffect,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class PromptTextEdit(QTextEdit):
    """Prompt editor with TAB navigation."""

    def __init__(
        self,
        panel: "PropertiesPanel",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel = panel
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
        if event.key() == Qt.Key_Tab:
            if self.panel.focus_next_prompt(self):
                event.accept()
                return

        if event.key() == Qt.Key_Backtab:
            if self.panel.focus_previous_prompt(self):
                event.accept()
                return

        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Up:
                if self.panel.move_prompt_by(self, -1):
                    event.accept()
                    return
            if event.key() == Qt.Key_Down:
                if self.panel.move_prompt_by(self, 1):
                    event.accept()
                    return

        super().keyPressEvent(event)


class PromptDragHandle(QLabel):
    """Small drag handle used to reorder prompt rows."""

    def __init__(
        self,
        panel: "PropertiesPanel",
        row: QWidget,
        group: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel = panel
        self.row = row
        self.group = group
        self._press_pos: QPoint | None = None
        self._dragging = False

        self.setText("")
        self.setFixedSize(44, 28)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to reorder")
        self.setStyleSheet(
            "QLabel { border: 1px solid transparent; border-radius: 4px; }"
            "QLabel:hover { background: rgba(0, 0, 0, 0.06); "
            "border-color: rgba(0, 0, 0, 0.15); }"
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(self.foregroundRole()))

        # Three short horizontal grip lines: wide, calm, and visually unobtrusive.
        center_x = self.width() / 2
        center_y = self.height() / 2
        line_width = 24.0
        line_height = 2.0
        for y in (center_y - 6.0, center_y, center_y + 6.0):
            painter.drawRoundedRect(
                center_x - line_width / 2,
                y - line_height / 2,
                line_width,
                line_height,
                1.0,
                1.0,
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._press_pos is not None
            and event.buttons() & Qt.LeftButton
        ):
            pos = event.position().toPoint()
            if not self._dragging:
                delta = pos - self._press_pos
                if delta.manhattanLength() < 5:
                    event.accept()
                    return
                self._dragging = True

            global_pos = self.mapToGlobal(pos)
            self.panel._update_prompt_drag(
                self.group,
                self.row,
                global_pos.y(),
                global_pos,
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            was_dragging = self._dragging
            self._press_pos = None
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
            if was_dragging:
                self.panel._finish_prompt_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class StyleListWidget(QListWidget):
    """Style list whose complete rows toggle the check state.

    The native QListWidget checkbox interaction is deliberately handled here
    so clicking anywhere on a style row has the same effect as clicking the
    checkbox. This keeps the interaction fast and predictable for large,
    rapidly clicked style lists.
    """

    def _update_grid_layout(self) -> None:
        """Keep the style list in its stable single-column layout."""
        available_width = max(180, self.viewport().width())
        self.setGridSize(QSize(available_width, 28))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_grid_layout()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None and self.isEnabled():
                item.setCheckState(
                    Qt.Unchecked
                    if item.checkState() == Qt.Checked
                    else Qt.Checked
                )
                # If the clicked item is on the last visible row, advance by
                # exactly one row so the next styles become selectable.
                self._advance_if_last_visible_row(item)
                event.accept()
                return

        super().mousePressEvent(event)

    def _advance_if_last_visible_row(self, item: QListWidgetItem) -> None:
        rect = self.visualItemRect(item)
        viewport_height = self.viewport().height()
        if rect.bottom() < viewport_height - 2:
            return

        row_height = max(1, self.gridSize().height())
        bar = self.verticalScrollBar()
        if bar.value() >= bar.maximum():
            return
        bar.setValue(min(bar.maximum(), bar.value() + row_height))


class BaseModelListWidget(StyleListWidget):
    """Single-column model list with the same row-toggle behavior as Styles."""

    def resizeEvent(self, event) -> None:
        super(StyleListWidget, self).resizeEvent(event)
        self.setGridSize(QSize(max(180, self.viewport().width()), 28))


class CollapsibleSection(QWidget):
    """Section with a clickable header and a collapsible content widget."""

    def __init__(
        self,
        title: str,
        content: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._header = QToolButton()
        self._header.setObjectName("sectionHeader")
        self._header.setProperty("role", "sectionTitle")
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setAutoRaise(True)
        # Match QLabel[role="sectionTitle"] exactly: this is the same
        # visual treatment used by the fixed "Experiment" heading.
        self._header.setStyleSheet(
            "QToolButton#sectionHeader {"
            " background: transparent;"
            " border: none;"
            " color: #7CEEFF;"
            " font-weight: 700;"
            " padding: 1px 0px;"
            " margin: 0px;"
            " text-align: left;"
            "}"
            "QToolButton#sectionHeader:hover {"
            " background: transparent;"
            "}"
        )
        # Start with the Properties sections collapsed to maximize working space.
        self._header.setChecked(False)
        self._header.setArrowType(Qt.RightArrow)
        self._header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header.setSizePolicy(
            self._header.sizePolicy().horizontalPolicy(),
            self._header.sizePolicy().verticalPolicy(),
        )
        self._header.toggled.connect(self._set_expanded)

        self._content = content
        # Expanded sections use their natural content height instead of
        # absorbing spare vertical space in the scroll-area viewport.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(self._header)
        layout.addWidget(self._content)
        self._content.setVisible(False)

    def _set_expanded(self, expanded: bool) -> None:
        self._header.setArrowType(
            Qt.DownArrow if expanded else Qt.RightArrow
        )
        self._content.setVisible(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._header.setChecked(expanded)

class PropertiesPanel(QGroupBox):
    """Displays and edits the properties of the selected experiment."""

    prompt_inputs_changed = Signal()

    def __init__(
        self,
        experiment: Experiment,
    ) -> None:
        super().__init__()
        self.setObjectName("mainPanel")

        self.experiment = experiment

        self.positive_prompt_edits: list[QTextEdit] = []
        self.negative_prompt_edits: list[QTextEdit] = []

        self.positive_prompt_fixed: list[QCheckBox] = []
        self.negative_prompt_fixed: list[QCheckBox] = []

        self.positive_prompt_numbers: list[QLabel] = []
        self.negative_prompt_numbers: list[QLabel] = []

        self.positive_prompt_rows: list[QWidget] = []
        self.negative_prompt_rows: list[QWidget] = []

        self._active_prompt_drag = False
        self._dragged_prompt_row: QWidget | None = None
        self._drag_ghost: QLabel | None = None
        self._drag_opacity_effect: QGraphicsOpacityEffect | None = None
        self._prompt_drop_lines: dict[str, QFrame | None] = {
            "positive": None,
            "negative": None,
        }
        self._active_prompt_drag_group: str | None = None
        self._positive_add_button: QPushButton | None = None
        self._negative_add_button: QPushButton | None = None

        self.seed_edits: list[QLineEdit] = []
        self.seed_numbers: list[QLabel] = []

        self.style_names: list[str] = []
        self.base_model_names: list[str] = []

        self.style_reference_panel: ReferenceImagePanel | None = None
        self.composition_reference_panel: ReferenceImagePanel | None = None

        self.matrix_controls: dict[
            str,
            QComboBox,
        ] = {}

        self.matrix_count_controls: dict[
            str,
            QSpinBox,
        ] = {}

        self.numeric_matrix_controls: dict[
            str,
            tuple[QCheckBox, QDoubleSpinBox, QDoubleSpinBox, QSpinBox],
        ] = {}

        self.random_style_enabled = (
            experiment.random_style
        )

        # Resolution lock state. Initialize before any slider signal can fire.
        self._updating_resolution = False
        generation_width = max(1, experiment.generation.width)
        generation_height = max(1, experiment.generation.height)
        self._resolution_ratio = generation_width / generation_height

        # Keep labels and controls usable even when the panel is embedded
        # elsewhere. MainWindow applies the complete splitter policy.
        self.setMinimumWidth(660)

        self.create_ui()

    # ------------------------------------------------------------------
    # Reference images
    # ------------------------------------------------------------------

    def _next_reference_id(self) -> int:
        ids = [
            reference.reference_id
            for references in (
                self.experiment.style_references,
                self.experiment.composition_references,
            )
            for reference in references
        ]
        return max(ids, default=0) + 1

    def _sync_reference_images(self) -> None:
        if self.style_reference_panel is None or self.composition_reference_panel is None:
            return

        current_style_paths = self.style_reference_panel.paths()
        current_composition_paths = self.composition_reference_panel.paths()

        old_style = {Path(reference.path).resolve(): reference for reference in self.experiment.style_references}
        old_composition = {Path(reference.path).resolve(): reference for reference in self.experiment.composition_references}

        next_id = self._next_reference_id()

        new_style: list[ReferenceImage] = []
        for path in current_style_paths:
            resolved = Path(path).resolve()
            reference = old_style.get(resolved)
            if reference is None:
                reference = ReferenceImage(next_id, str(resolved), ReferenceType.STYLE)
                next_id += 1
            else:
                reference.path = str(resolved)
            new_style.append(reference)

        new_composition: list[ReferenceImage] = []
        for path in current_composition_paths:
            resolved = Path(path).resolve()
            reference = old_composition.get(resolved)
            if reference is None:
                reference = ReferenceImage(next_id, str(resolved), ReferenceType.COMPOSITION)
                next_id += 1
            else:
                reference.path = str(resolved)
            new_composition.append(reference)

        self.experiment.style_references = new_style
        self.experiment.composition_references = new_composition
        self._update_matrix_availability()
        self._update_matrix_count_limits()
        self.prompt_inputs_changed.emit()

    def _create_reference_controls(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.style_reference_panel = ReferenceImagePanel("Style")
        self.composition_reference_panel = ReferenceImagePanel("Composition")

        self.style_reference_panel.set_paths(
            [reference.path for reference in self.experiment.style_references]
        )
        self.composition_reference_panel.set_paths(
            [reference.path for reference in self.experiment.composition_references]
        )

        self.style_reference_panel.paths_changed.connect(self._sync_reference_images)
        self.composition_reference_panel.paths_changed.connect(self._sync_reference_images)

        layout.addWidget(self.style_reference_panel, 1)
        layout.addWidget(self.composition_reference_panel, 1)
        return container

    # ------------------------------------------------------------------
    # Generation settings
    # ------------------------------------------------------------------

    def _resolution_from_slider(self, value: int, minimum: int) -> int:
        return minimum + value * GENERATION_SIZE_STEP

    def _set_resolution_value(self, slider: QSlider, pixels: int, minimum: int, maximum: int) -> int:
        pixels = max(minimum, min(maximum, pixels))
        pixels = minimum + round((pixels - minimum) / GENERATION_SIZE_STEP) * GENERATION_SIZE_STEP
        pixels = max(minimum, min(maximum, pixels))
        slider.setValue((pixels - minimum) // GENERATION_SIZE_STEP)
        return pixels

    def keep_aspect_ratio_changed(self, checked: bool) -> None:
        if checked and self.experiment.generation.height > 0:
            self._resolution_ratio = (
                self.experiment.generation.width / self.experiment.generation.height
            )

    def _update_resolution_matrix_summary(self) -> None:
        """Refresh the compact Resolution overview in the Matrix hub."""
        if not hasattr(self, "resolution_matrix_summary"):
            return
        selection = self.experiment.matrix.resolution
        dimension = "Width" if selection.dimension == "width" else "Height"
        minimum, maximum = selection.minimum, selection.maximum
        steps = max(2, int(selection.steps or 2))
        if minimum is None or maximum is None:
            summary = f"Current: {self.experiment.generation.width} × {self.experiment.generation.height}"
        else:
            summary = f"{dimension} {minimum}–{maximum} · {steps} steps · {self.experiment.generation.aspect_ratio or 'fixed ratio'}"
        self.resolution_matrix_summary.setText(summary)
        self.resolution_matrix_hub_enabled.blockSignals(True)
        self.resolution_matrix_hub_enabled.setChecked(bool(selection.enabled))
        self.resolution_matrix_hub_enabled.blockSignals(False)

    def _resolution_matrix_hub_toggled(self, checked: bool) -> None:
        self.resolution_matrix_enabled.setChecked(checked)
        self._update_resolution_matrix_summary()

    def _configure_resolution_matrix_dialog(self) -> None:
        """Edit the shared resolution-matrix settings from the Matrix hub."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Resolution Matrix")
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        dimension = QComboBox(dialog)
        dimension.addItem("Width", "width")
        dimension.addItem("Height", "height")
        dimension.setCurrentIndex(max(0, dimension.findData(self.resolution_matrix_dimension.currentData())))
        minimum = QSpinBox(dialog)
        maximum = QSpinBox(dialog)
        minimum.setRange(self.resolution_matrix_minimum.minimum(), self.resolution_matrix_minimum.maximum())
        maximum.setRange(self.resolution_matrix_maximum.minimum(), self.resolution_matrix_maximum.maximum())
        minimum.setSingleStep(GENERATION_SIZE_STEP)
        maximum.setSingleStep(GENERATION_SIZE_STEP)
        minimum.setValue(self.resolution_matrix_minimum.value())
        maximum.setValue(self.resolution_matrix_maximum.value())
        steps = QSpinBox(dialog)
        steps.setRange(2, 20)
        steps.setValue(self.resolution_matrix_steps.value())
        form.addRow("Vary", dimension)
        form.addRow("Minimum", minimum)
        form.addRow("Maximum", maximum)
        form.addRow("Steps", steps)
        layout.addLayout(form)

        def update_limits(_index: int = -1) -> None:
            selected = dimension.currentData() or "width"
            low, high = ((MIN_GENERATION_WIDTH, MAX_GENERATION_WIDTH) if selected == "width"
                         else (MIN_GENERATION_HEIGHT, MAX_GENERATION_HEIGHT))
            for control in (minimum, maximum):
                old_value = control.value()
                control.blockSignals(True)
                control.setRange(low, high)
                control.setValue(max(low, min(high, old_value)))
                control.blockSignals(False)
        dimension.currentIndexChanged.connect(update_limits)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            self.resolution_matrix_dimension.setCurrentIndex(max(0, self.resolution_matrix_dimension.findData(dimension.currentData())))
            self.resolution_matrix_minimum.setValue(minimum.value())
            self.resolution_matrix_maximum.setValue(maximum.value())
            self.resolution_matrix_steps.setValue(steps.value())
            self._update_resolution_matrix_summary()

    def resolution_matrix_changed(self, *_args) -> None:
        """Persist the resolution matrix controls and enable their inputs."""
        selection = self.experiment.matrix.resolution
        if self.resolution_matrix_minimum.value() > self.resolution_matrix_maximum.value():
            if self.sender() is self.resolution_matrix_minimum:
                self.resolution_matrix_maximum.setValue(
                    self.resolution_matrix_minimum.value()
                )
            else:
                self.resolution_matrix_minimum.setValue(
                    self.resolution_matrix_maximum.value()
                )
        selection.enabled = self.resolution_matrix_enabled.isChecked()
        selection.dimension = self.resolution_matrix_dimension.currentData() or "width"
        selection.minimum = self.resolution_matrix_minimum.value()
        selection.maximum = self.resolution_matrix_maximum.value()
        selection.steps = self.resolution_matrix_steps.value()

        active = selection.enabled
        if active and not self.keep_aspect_ratio_checkbox.isChecked():
            self.keep_aspect_ratio_checkbox.setChecked(True)
        self.keep_aspect_ratio_checkbox.setEnabled(not active)
        for control in (
            self.resolution_matrix_dimension,
            self.resolution_matrix_minimum,
            self.resolution_matrix_maximum,
            self.resolution_matrix_steps,
        ):
            control.setEnabled(active)
        self._update_resolution_matrix_summary()

    def resolution_matrix_dimension_changed(self, *_args) -> None:
        """Switch the min/max controls to the selected axis."""
        dimension = self.resolution_matrix_dimension.currentData() or "width"
        minimum, maximum, current = (
            (MIN_GENERATION_WIDTH, MAX_GENERATION_WIDTH, self.experiment.generation.width)
            if dimension == "width"
            else (MIN_GENERATION_HEIGHT, MAX_GENERATION_HEIGHT, self.experiment.generation.height)
        )
        selection = self.experiment.matrix.resolution
        stored_minimum = selection.minimum if selection.dimension == dimension else current
        stored_maximum = selection.maximum if selection.dimension == dimension else current
        self.resolution_matrix_minimum.setRange(minimum, maximum)
        self.resolution_matrix_maximum.setRange(minimum, maximum)
        self.resolution_matrix_minimum.setValue(max(minimum, min(maximum, stored_minimum or current)))
        self.resolution_matrix_maximum.setValue(max(minimum, min(maximum, stored_maximum or current)))
        self.resolution_matrix_changed()

    def width_changed(self, value: int) -> None:
        width = self._resolution_from_slider(value, MIN_GENERATION_WIDTH)
        if self.keep_aspect_ratio_checkbox.isChecked() and not self._updating_resolution:
            self._updating_resolution = True
            height = round(width / self._resolution_ratio)
            height = self._set_resolution_value(
                self.height_slider, height, MIN_GENERATION_HEIGHT, MAX_GENERATION_HEIGHT
            )
            self.experiment.generation.height = height
            self.height_value.setText(str(height))
            self._updating_resolution = False

        self.experiment.generation.width = width
        self.width_value.setText(str(width))

    def height_changed(self, value: int) -> None:
        height = self._resolution_from_slider(value, MIN_GENERATION_HEIGHT)
        if self.keep_aspect_ratio_checkbox.isChecked() and not self._updating_resolution:
            self._updating_resolution = True
            width = round(height * self._resolution_ratio)
            width = self._set_resolution_value(
                self.width_slider, width, MIN_GENERATION_WIDTH, MAX_GENERATION_WIDTH
            )
            self.experiment.generation.width = width
            self.width_value.setText(str(width))
            self._updating_resolution = False

        self.experiment.generation.height = height
        self.height_value.setText(str(height))

    def fooocus_performance_changed(self, value: str) -> None:
        self.experiment.generation.performance = value or None
        self._update_performance_parameter_availability()

    def _update_performance_parameter_availability(self) -> None:
        """Disable Guidance/Sharpness controls for fixed-performance modes.

        Fooocus Lightning and Extreme Speed do not honor these parameters
        as normal configurable generation settings, so exposing them as
        experiment dimensions would be misleading.
        """
        fixed_performance = self.experiment.generation.performance in {"Lightning", "Extreme Speed"}

        if hasattr(self, "fooocus_guidance_spin"):
            self.fooocus_guidance_spin.setEnabled(not fixed_performance)
            self._set_performance_dimmed(self.fooocus_guidance_spin, fixed_performance)
        if hasattr(self, "fooocus_sharpness_spin"):
            self.fooocus_sharpness_spin.setEnabled(not fixed_performance)
            self._set_performance_dimmed(self.fooocus_sharpness_spin, fixed_performance)

        for key in ("guidance_scale", "sharpness"):
            controls = self.numeric_matrix_controls.get(key)
            if controls is None:
                continue
            checkbox, minimum, maximum, steps = controls
            checkbox.setEnabled(not fixed_performance)
            minimum.setEnabled(not fixed_performance and checkbox.isChecked())
            maximum.setEnabled(not fixed_performance and checkbox.isChecked())
            steps.setEnabled(not fixed_performance and checkbox.isChecked())
            for control in (checkbox, minimum, maximum, steps):
                self._set_performance_dimmed(control, fixed_performance)

    @staticmethod
    def _set_performance_dimmed(widget: QWidget, dimmed: bool) -> None:
        """Visually dim a disabled performance-incompatible control.

        The application theme does not provide a sufficiently distinct
        disabled palette for all input widgets, so use an opacity effect
        in addition to Qt's disabled state.
        """
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.42 if dimmed else 1.0)

    def fooocus_guidance_changed(self, value: float) -> None:
        self.experiment.generation.guidance_scale = float(value)

    def fooocus_sharpness_changed(self, value: float) -> None:
        self.experiment.generation.sharpness = float(value)

    def fooocus_refiner_changed(self, value: str) -> None:
        self.experiment.generation.refiner_model = value or None

    def fooocus_refiner_switch_changed(self, value: float) -> None:
        self.experiment.generation.refiner_switch = float(value)

    def fooocus_output_format_changed(self, value: str) -> None:
        self.experiment.generation.output_format = value or "png"

    def set_refiner_choices(self, choices: list[str]) -> None:
        if not hasattr(self, "fooocus_refiner_combo"):
            return
        current = self.experiment.generation.refiner_model or ""
        self.fooocus_refiner_combo.blockSignals(True)
        self.fooocus_refiner_combo.clear()
        self.fooocus_refiner_combo.addItem("None", "")
        for choice in choices:
            self.fooocus_refiner_combo.addItem(choice, choice)
        index = self.fooocus_refiner_combo.findData(current)
        self.fooocus_refiner_combo.setCurrentIndex(max(0, index))
        self.fooocus_refiner_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Prompt handling
    # ------------------------------------------------------------------

    def _prompt_texts(
        self,
        edits: list[QTextEdit],
    ) -> list[str]:
        return [
            edit.toPlainText().strip()
            for edit in edits
            if edit.toPlainText().strip()
        ]

    def _sync_prompt_slots(
        self,
        edits: list[QTextEdit],
        fixed_controls: list[QCheckBox],
    ) -> list[PromptSlot]:
        slots: list[PromptSlot] = []

        for slot_id, (edit, fixed_control) in enumerate(
            zip(edits, fixed_controls),
            start=1,
        ):
            text = edit.toPlainText().strip()
            if not text:
                continue
            slots.append(
                PromptSlot(
                    slot_id=slot_id,
                    text=text,
                    fixed=fixed_control.isChecked(),
                )
            )
        return slots

    def positive_prompts_changed(self) -> None:
        self.experiment.positive_prompts = self._sync_prompt_slots(
            self.positive_prompt_edits, self.positive_prompt_fixed
        )
        self._renumber_prompt_rows(self.positive_prompt_numbers)
        self._update_matrix_count_limits()
        self.prompt_inputs_changed.emit()

    def negative_prompts_changed(self) -> None:
        self.experiment.negative_prompts = self._sync_prompt_slots(
            self.negative_prompt_edits, self.negative_prompt_fixed
        )
        self._renumber_prompt_rows(self.negative_prompt_numbers)
        self._update_matrix_count_limits()
        self.prompt_inputs_changed.emit()

    @staticmethod
    def _renumber_prompt_rows(labels: list[QLabel]) -> None:
        for index, label in enumerate(labels, start=1):
            label.setText(str(index))

    def _renumber_prompt_group(self, group: str) -> None:
        """Keep prompt numbers tied to visual row positions, not prompt content."""
        rows = (
            self.positive_prompt_rows
            if group == "positive"
            else self.negative_prompt_rows
        )
        for index, row in enumerate(rows, start=1):
            labels = row.findChildren(QLabel)
            if labels:
                labels[0].setText(str(index))

    def _update_prompt_edit_heights(self) -> None:
        """Apply the prompt height policy to all existing prompt rows and editors."""
        total = len(self.positive_prompt_edits) + len(self.negative_prompt_edits)
        compact = total > 5

        # Positive and negative prompt rows must follow the same geometry
        # policy so adding a negative prompt cannot trigger a different layout.
        prompt_height = 40 if compact else 70
        positive_height = prompt_height
        negative_height = prompt_height

        for row, edit in zip(self.positive_prompt_rows, self.positive_prompt_edits):
            row.setMinimumHeight(positive_height)
            row.setMaximumHeight(positive_height)
            row.setFixedHeight(positive_height)
            edit.setMinimumHeight(positive_height)
            edit.setMaximumHeight(positive_height)
            edit.setFixedHeight(positive_height)

        for row, edit in zip(self.negative_prompt_rows, self.negative_prompt_edits):
            row.setMinimumHeight(negative_height)
            row.setMaximumHeight(negative_height)
            row.setFixedHeight(negative_height)
            edit.setMinimumHeight(negative_height)
            edit.setMaximumHeight(negative_height)
            edit.setFixedHeight(negative_height)

    def _create_prompt_row(
        self,
        edits: list[QTextEdit],
        fixed_controls: list[QCheckBox],
        number_labels: list[QLabel],
        rows: list[QWidget],
        callback,
        minimum_height: int,
        group: str,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        drag_handle = PromptDragHandle(
            self,
            row,
            group,
            row,
        )

        number_label = QLabel()
        number_label.setMinimumWidth(20)
        number_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fixed_checkbox = QCheckBox("Fixed")
        fixed_checkbox.setToolTip(
            "Keep this prompt at this exact position. "
            "It is included in every matrix configuration but is not varied by the prompt matrix."
        )

        edit = PromptTextEdit(self)
        row.setMinimumHeight(minimum_height)
        row.setMaximumHeight(minimum_height)
        row.setFixedHeight(minimum_height)

        edit.setMinimumHeight(minimum_height)
        edit.setMaximumHeight(minimum_height)
        edit.setFixedHeight(minimum_height)

        # Keep the first prompt slot, but do not show a remove cross for it.
        # The fixed-width blank button preserves identical row geometry.
        is_first_prompt = len(edits) == 0
        remove_button = QPushButton("" if is_first_prompt else "✕")
        remove_button.setFixedWidth(32)
        remove_button.setFocusPolicy(Qt.NoFocus)
        remove_button.setEnabled(not is_first_prompt)
        remove_button.setToolTip(
            "At least one prompt must remain" if is_first_prompt else "Remove prompt"
        )
        remove_button.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                margin: 0px;
                font-family: "Segoe UI Symbol";
                font-size: 16px;
                font-weight: bold;
                color: #F044FF;
                border: 1px solid transparent;
            }
            QPushButton:hover {
                color: #FF8CFF;
                border: 1px solid #35E4FF;
            }
            QPushButton:pressed {
                color: #D62BFF;
                border: 1px solid #D62BFF;
            }
            """
        )

        edits.append(edit)
        fixed_controls.append(fixed_checkbox)
        number_labels.append(number_label)
        rows.append(row)
        self._renumber_prompt_rows(number_labels)

        edit.textChanged.connect(callback)
        edit.textChanged.connect(
            lambda editor=edit: editor.setToolTip(editor.toPlainText())
        )
        edit.setToolTip(edit.toPlainText())
        fixed_checkbox.toggled.connect(callback)

        def remove_row() -> None:
            if len(edits) <= 1:
                edit.clear()
                fixed_checkbox.setChecked(False)
                return
            index = edits.index(edit)
            edits.pop(index)
            fixed_controls.pop(index)
            number_labels.pop(index)
            rows.pop(index)
            edit.deleteLater()
            fixed_checkbox.deleteLater()
            number_label.deleteLater()
            drag_handle.deleteLater()
            remove_button.deleteLater()
            row.deleteLater()
            self._renumber_prompt_group(group)
            self._update_prompt_edit_heights()
            callback()

        remove_button.clicked.connect(remove_row)
        layout.addWidget(drag_handle)
        layout.addWidget(number_label)
        layout.addWidget(fixed_checkbox)
        layout.addWidget(edit, 1)
        layout.addWidget(remove_button)
        return row

    def _prompt_group_data(
        self,
        group: str,
    ) -> tuple[
        list[QWidget],
        list[QTextEdit],
        list[QCheckBox],
        list[QLabel],
        QVBoxLayout,
        Any,
    ]:
        if group == "positive":
            return (
                self.positive_prompt_rows,
                self.positive_prompt_edits,
                self.positive_prompt_fixed,
                self.positive_prompt_numbers,
                self.positive_prompt_layout,
                self.positive_prompts_changed,
            )
        return (
            self.negative_prompt_rows,
            self.negative_prompt_edits,
            self.negative_prompt_fixed,
            self.negative_prompt_numbers,
            self.negative_prompt_layout,
            self.negative_prompts_changed,
        )

    def _start_prompt_drag(
        self,
        group: str,
        row: QWidget,
        global_pos: QPoint,
    ) -> None:
        if self._dragged_prompt_row is not None:
            return

        self._dragged_prompt_row = row

        # Keep the real row in the layout, but dim it while a floating
        # snapshot follows the mouse. This makes the object being moved
        # immediately obvious without disturbing the layout geometry.
        effect = QGraphicsOpacityEffect(row)
        effect.setOpacity(0.38)
        row.setGraphicsEffect(effect)
        self._drag_opacity_effect = effect

        pixmap = row.grab()
        ghost = QLabel(None)
        ghost.setPixmap(pixmap)
        ghost.setFixedSize(pixmap.size())
        ghost.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        ghost.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        ghost.setWindowOpacity(0.82)
        ghost.show()
        ghost.raise_()
        self._drag_ghost = ghost
        self._move_drag_ghost(global_pos)
        self._active_prompt_drag_group = group

        # Keep a separate drop indicator for each prompt list. Reusing one
        # QFrame across positive/negative lists makes the indicator remain
        # attached to the first list after switching groups.
        if self._prompt_drop_lines.get(group) is None:
            parent = row.parentWidget()
            if parent is not None:
                line = QFrame(parent)
                line.setFrameShape(QFrame.HLine)
                line.setFixedHeight(3)
                line.setStyleSheet(
                    "QFrame { background: #4a90e2; border: none; }"
                )
                line.hide()
                self._prompt_drop_lines[group] = line

    def _move_drag_ghost(self, global_pos: QPoint) -> None:
        if self._drag_ghost is None:
            return
        offset_x = self._drag_ghost.width() // 2
        offset_y = 18
        self._drag_ghost.move(
            global_pos.x() - offset_x,
            global_pos.y() - offset_y,
        )

    def _update_prompt_drop_line(
        self,
        group: str,
        rows: list[QWidget],
        target_index: int,
    ) -> None:
        line = self._prompt_drop_lines.get(group)
        if line is None or not rows:
            return

        target = rows[target_index]
        parent = line.parentWidget()
        if parent is None:
            return

        if target_index == len(rows) - 1:
            y = target.geometry().bottom() + 1
        else:
            y = target.geometry().top() - 2

        line.setGeometry(0, y, parent.width(), 3)
        line.raise_()
        line.show()

    def _update_prompt_drag(
        self,
        group: str,
        row: QWidget,
        global_y: int,
        global_pos: QPoint | None = None,
    ) -> None:
        rows, edits, fixed_controls, number_labels, layout, callback = (
            self._prompt_group_data(group)
        )
        if row not in rows:
            return

        if self._dragged_prompt_row is None:
            self._start_prompt_drag(
                group,
                row,
                global_pos or row.mapToGlobal(QPoint(0, 0)),
            )

        if global_pos is not None:
            self._move_drag_ghost(global_pos)

        current_index = rows.index(row)
        target_index = current_index

        for index, candidate in enumerate(rows):
            if candidate is row:
                continue
            center_y = candidate.mapToGlobal(
                QPoint(0, candidate.height() // 2)
            ).y()
            if global_y < center_y:
                target_index = index
                break
        else:
            target_index = len(rows) - 1

        if target_index == current_index:
            line = self._prompt_drop_lines.get(group)
            if line is not None:
                line.hide()
            return

        rows.insert(target_index, rows.pop(current_index))
        edits.insert(target_index, edits.pop(current_index))
        fixed_controls.insert(
            target_index,
            fixed_controls.pop(current_index),
        )
        number_labels.insert(
            target_index,
            number_labels.pop(current_index),
        )

        layout.removeWidget(row)
        layout.insertWidget(target_index, row)
        self._renumber_prompt_group(group)
        callback()
        self._active_prompt_drag = True
        self._update_prompt_drop_line(group, rows, target_index)

    def _finish_prompt_drag(self) -> None:
        if self._drag_opacity_effect is not None and self._dragged_prompt_row is not None:
            self._dragged_prompt_row.setGraphicsEffect(None)

        if self._drag_ghost is not None:
            self._drag_ghost.close()
            self._drag_ghost.deleteLater()

        if self._active_prompt_drag_group is not None:
            line = self._prompt_drop_lines.get(self._active_prompt_drag_group)
            if line is not None:
                line.hide()

        self._drag_ghost = None
        self._drag_opacity_effect = None
        self._dragged_prompt_row = None
        self._active_prompt_drag = False
        self._active_prompt_drag_group = None

    def _keep_prompt_add_button_last(self, group: str) -> None:
        """Keep the add button anchored after all prompt rows.

        Keyboard reordering changes layout indices directly. Explicitly
        re-append the add button so it can never become part of the reordered
        prompt sequence (mouse drag already targets only prompt rows).
        """
        if group == "positive":
            layout = self.positive_prompt_layout
            button = self._positive_add_button
        else:
            layout = self.negative_prompt_layout
            button = self._negative_add_button

        if button is not None:
            layout.removeWidget(button)
            layout.addWidget(button)

    def move_prompt_by(
        self,
        edit: QTextEdit,
        delta: int,
    ) -> bool:
        """Move prompt content between fixed numbered rows.

        Keyboard reordering intentionally does not move row widgets or their
        numbers. The prompt text and Fixed state are swapped between the
        adjacent numbered rows.
        """
        for group, edits in (
            ("positive", self.positive_prompt_edits),
            ("negative", self.negative_prompt_edits),
        ):
            if edit not in edits:
                continue

            rows, edits_list, fixed_controls, number_labels, layout, callback = (
                self._prompt_group_data(group)
            )
            index = edits_list.index(edit)
            target = index + delta
            if target < 0 or target >= len(edits_list):
                return False

            current_edit = edits_list[index]
            target_edit = edits_list[target]
            current_fixed = fixed_controls[index]
            target_fixed = fixed_controls[target]

            current_text = current_edit.toPlainText()
            target_text = target_edit.toPlainText()
            current_fixed_state = current_fixed.isChecked()
            target_fixed_state = target_fixed.isChecked()

            current_edit.blockSignals(True)
            target_edit.blockSignals(True)
            current_fixed.blockSignals(True)
            target_fixed.blockSignals(True)
            try:
                current_edit.setPlainText(target_text)
                target_edit.setPlainText(current_text)
                current_fixed.setChecked(target_fixed_state)
                target_fixed.setChecked(current_fixed_state)
            finally:
                current_edit.blockSignals(False)
                target_edit.blockSignals(False)
                current_fixed.blockSignals(False)
                target_fixed.blockSignals(False)

            # The rows and number labels never move. Only the content moves.
            self._renumber_prompt_group(group)
            callback()
            self._update_prompt_edit_heights()

            # Follow the moved prompt to its new numbered row.
            target_edit.setFocus()
            return True

        return False


    def _restore_prompt_group(
        self,
        group: str,
        prompts: list[PromptSlot],
    ) -> None:
        """Populate prompt editors from the loaded experiment definition."""
        if not prompts:
            return

        if group == "positive":
            edits = self.positive_prompt_edits
            fixed_controls = self.positive_prompt_fixed
            add_prompt = self.add_positive_prompt
            callback = self.positive_prompts_changed
        else:
            edits = self.negative_prompt_edits
            fixed_controls = self.negative_prompt_fixed
            add_prompt = self.add_negative_prompt
            callback = self.negative_prompts_changed

        while len(edits) < len(prompts):
            add_prompt()

        for edit, fixed_control, prompt in zip(
            edits,
            fixed_controls,
            prompts,
        ):
            edit.blockSignals(True)
            fixed_control.blockSignals(True)
            try:
                edit.setPlainText(prompt.text)
                fixed_control.setChecked(prompt.fixed)
            finally:
                edit.blockSignals(False)
                fixed_control.blockSignals(False)

        self._update_prompt_edit_heights()
        callback()


    def add_positive_prompt(self) -> None:
        row = self._create_prompt_row(
            self.positive_prompt_edits,
            self.positive_prompt_fixed,
            self.positive_prompt_numbers,
            self.positive_prompt_rows,
            self.positive_prompts_changed,
            70,
            "positive",
        )
        self.positive_prompt_layout.insertWidget(
            self.positive_prompt_layout.count() - 1, row
        )
        self._update_prompt_edit_heights()

    def add_negative_prompt(self) -> None:
        row = self._create_prompt_row(
            self.negative_prompt_edits,
            self.negative_prompt_fixed,
            self.negative_prompt_numbers,
            self.negative_prompt_rows,
            self.negative_prompts_changed,
            60,
            "negative",
        )
        self.negative_prompt_layout.insertWidget(
            self.negative_prompt_layout.count() - 1, row
        )
        self._update_prompt_edit_heights()

    # ------------------------------------------------------------------
    # TAB navigation
    # ------------------------------------------------------------------

    def _prompt_focus_order(
        self,
    ) -> list[QTextEdit]:
        return (
            self.positive_prompt_edits
            + self.negative_prompt_edits
        )

    def focus_next_prompt(
        self,
        current: QTextEdit,
    ) -> bool:
        order = self._prompt_focus_order()

        try:
            index = order.index(
                current
            )
        except ValueError:
            return False

        next_index = index + 1

        if next_index < len(order):
            order[next_index].setFocus()
            return True

        self.style_search.setFocus()
        return True

    def focus_previous_prompt(
        self,
        current: QTextEdit,
    ) -> bool:
        order = self._prompt_focus_order()

        try:
            index = order.index(
                current
            )
        except ValueError:
            return False

        previous_index = index - 1

        if previous_index >= 0:
            order[previous_index].setFocus()
            return True

        self.experiment_name.setFocus()
        return True

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Base model handling
    # ------------------------------------------------------------------
    def _base_model_name(self, choice: Any) -> str:
        """Extract a base-model name from a Fooocus runtime choice."""
        if isinstance(choice, (list, tuple)):
            if len(choice) >= 2:
                return str(choice[1])
            if len(choice) == 1:
                return str(choice[0])
        return str(choice)

    def _base_model_item_name(self, item: QListWidgetItem) -> str:
        """Return the real base-model name stored on a numbered list item."""
        return str(item.data(Qt.UserRole) or item.text())

    def set_base_model_choices(self, choices: Any) -> None:
        """Load available SDXL base models from the Fooocus runtime."""
        if choices is None:
            return

        self.base_model_names = [
            self._base_model_name(choice)
            for choice in choices
        ]
        available = sorted(
            set(self.base_model_names),
            key=str.casefold,
        )

        selected = set(
            getattr(self.experiment.generation, "base_models", [])
        )
        legacy = getattr(
            self.experiment.generation,
            "base_model",
            None,
        )
        if not selected and legacy:
            selected = {legacy}

        self.base_model_list.blockSignals(True)
        self.base_model_list.clear()
        for number, model_name in enumerate(available, start=1):
            item = QListWidgetItem(f"BM#{number}  {model_name}")
            item.setData(Qt.UserRole, model_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if model_name in selected else Qt.Unchecked
            )
            self.base_model_list.addItem(item)
        self.base_model_list.blockSignals(False)

        # Keep room for up to three model rows, but do not force empty rows
        # when fewer models are actually available.
        row_height = max(1, self.base_model_list.sizeHintForRow(0))
        visible_rows = min(3, max(1, self.base_model_list.count()))
        self.base_model_list.setMinimumHeight(row_height * visible_rows + 4)

        self._refresh_check_list_visuals(self.base_model_list)
        self._update_base_model_selection_display()

    def _refresh_check_list_visuals(self, widget: QListWidget) -> None:
        """Apply the shared checked/unchecked appearance without re-entering itemChanged."""
        checked_background = QColor("#123A4A")
        checked_foreground = QColor("#7DEBFF")
        unchecked_background = QColor(0, 0, 0, 0)
        unchecked_foreground = QColor("#DCE2E9")

        # setData()/setFont() can emit QListWidget.itemChanged.  The visual
        # refresh is a presentation-only operation and must not re-enter
        # styles_changed()/base_models_changed(), otherwise a single click can
        # recurse until Python exhausts the call stack.
        was_blocked = widget.blockSignals(True)
        try:
            for index in range(widget.count()):
                item = widget.item(index)
                is_checked = item.checkState() == Qt.Checked
                item.setData(
                    Qt.BackgroundRole,
                    QBrush(checked_background if is_checked else unchecked_background),
                )
                item.setData(
                    Qt.ForegroundRole,
                    QBrush(checked_foreground if is_checked else unchecked_foreground),
                )
                font = item.font()
                font.setBold(is_checked)
                item.setFont(font)
        finally:
            widget.blockSignals(was_blocked)

    def _update_base_model_selection_display(self) -> None:
        selected = [
            self._base_model_item_name(self.base_model_list.item(index))
            for index in range(self.base_model_list.count())
            if self.base_model_list.item(index).checkState() == Qt.Checked
        ]
        self.base_model_selection_label.setText(
            f"{len(selected)} base models selected"
        )

    def base_models_changed(self) -> None:
        selected = [
            self._base_model_item_name(self.base_model_list.item(index))
            for index in range(self.base_model_list.count())
            if self.base_model_list.item(index).checkState() == Qt.Checked
        ]
        self.experiment.generation.base_models = selected
        self.experiment.generation.base_model = selected[0] if selected else None
        self._refresh_check_list_visuals(self.base_model_list)
        self._update_base_model_selection_display()

    # Seed handling
    # ------------------------------------------------------------------

    def seeds_changed(
        self,
    ) -> None:
        seeds: list[int] = []

        for edit in self.seed_edits:
            text = edit.text().strip()

            if not text:
                continue

            try:
                seed = int(text)
            except ValueError:
                continue

            if 0 <= seed <= (1 << 63) - 1:
                seeds.append(seed)

        self.experiment.generation.seeds = seeds

        self.experiment.generation.seed = (
            seeds[0]
            if seeds
            else None
        )

        # Seed edits are generation-input changes too. Keep the matrix limits
        # and live queue preview synchronized when the fixed-seed pool changes.
        self._update_matrix_count_limits()
        self.prompt_inputs_changed.emit()

    def random_seed_changed(
        self,
        checked: bool,
    ) -> None:
        self.experiment.generation.seed_mode = (
            SeedMode.RANDOM
            if checked
            else SeedMode.FIXED
        )

        self.random_seed_count.setEnabled(
            checked
        )

        self.manual_seed_container.setVisible(
            not checked
        )

        self.seeds_changed()

        self._update_matrix_availability()

    def random_seed_count_changed(
        self,
        value: int,
    ) -> None:
        self.experiment.generation.random_seed_count = (
            value
        )

    def _create_seed_row(
        self,
    ) -> QWidget:
        row = QWidget()

        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        number_label = QLabel()
        number_label.setMinimumWidth(20)
        number_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        edit = QLineEdit()

        edit.setPlaceholderText(
            "Seed"
        )

        remove_button = QPushButton(
            "✕"
        )

        remove_button.setFixedWidth(
            32
        )

        remove_button.setFocusPolicy(
            Qt.NoFocus
        )
        remove_button.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                margin: 0px;
                font-family: "Segoe UI Symbol";
                font-size: 16px;
                font-weight: bold;
                color: #F044FF;
                border: 1px solid transparent;
            }
            QPushButton:hover {
                color: #FF8CFF;
                border: 1px solid #35E4FF;
            }
            QPushButton:pressed {
                color: #D62BFF;
                border: 1px solid #D62BFF;
            }
            """
        )

        self.seed_edits.append(
            edit
        )
        self.seed_numbers.append(
            number_label
        )
        self._renumber_seed_rows()

        edit.textChanged.connect(
            self.seeds_changed
        )

        def remove_row() -> None:
            if len(self.seed_edits) <= 1:
                edit.clear()
                return

            index = self.seed_edits.index(edit)
            self.seed_edits.pop(index)
            self.seed_numbers.pop(index)

            edit.deleteLater()
            number_label.deleteLater()
            remove_button.deleteLater()
            row.deleteLater()

            self._renumber_seed_rows()
            self.seeds_changed()

        remove_button.clicked.connect(
            remove_row
        )

        layout.addWidget(
            number_label
        )

        layout.addWidget(
            edit
        )

        layout.addWidget(
            remove_button
        )

        return row

    def _renumber_seed_rows(self) -> None:
        for index, label in enumerate(self.seed_numbers, start=1):
            label.setText(str(index))

    def add_seed(
        self,
    ) -> None:
        row = self._create_seed_row()

        self.seed_layout.insertWidget(
            self.seed_layout.count() - 1,
            row,
        )

        # Adding/removing a seed row does not emit QLineEdit.textChanged.
        # Explicitly synchronize the experiment and notify the live preview.
        self.seeds_changed()

    # ------------------------------------------------------------------
    # Style handling
    # ------------------------------------------------------------------
    @staticmethod
    def _style_name(
        choice: Any,
    ) -> str:
        """Extract a style name from a Fooocus runtime choice."""

        if isinstance(
            choice,
            (list, tuple),
        ):
            if len(choice) >= 2:
                return str(
                    choice[1]
                )

            if len(choice) == 1:
                return str(
                    choice[0]
                )

        return str(choice)

    def _style_item_name(self, item: QListWidgetItem) -> str:
        """Return the real style name stored on a numbered list item."""
        return str(item.data(Qt.UserRole) or item.text())

    def _update_random_style_count_limit(self) -> None:
        """Keep Random Selected count bounded by the selected style pool."""
        selected_count = len(self.experiment.styles)

        self.random_style_count.blockSignals(True)
        if self.experiment.random_style:
            # With no selected styles there is no valid random choice yet.
            # A zero value makes that state explicit instead of allowing an
            # impossible request such as "1 of 0".
            self.random_style_count.setMinimum(0)
            self.random_style_count.setMaximum(selected_count)
            if selected_count == 0:
                self.random_style_count.setValue(0)
            else:
                self.random_style_count.setValue(
                    min(max(1, self.random_style_count.value()), selected_count)
                )
        else:
            self.random_style_count.setMinimum(1)
            self.random_style_count.setMaximum(100)
            self.random_style_count.setValue(
                min(max(1, self.random_style_count.value()), 100)
            )
        self.random_style_count.blockSignals(False)

        self.experiment.random_style_count = self.random_style_count.value()

    def set_style_choices(
        self,
        choices: Any,
    ) -> None:
        """Load styles from the Fooocus runtime."""

        if choices is None:
            return

        self.style_names = [
            self._style_name(choice)
            for choice in choices
        ]

        self.experiment.available_styles = list(self.style_names)

        # Connecting to Fooocus loads the runtime style pool.
        # Preserve styles already selected in the current experiment.
        selected_styles: set[str] = set(self.experiment.styles)

        # Preserve the runtime/Fooocus style order.  Do not sort by the
        # display name: labels such as STY#10 must never jump ahead of STY#2.
        available_styles = list(dict.fromkeys(self.style_names))

        self.style_list.blockSignals(True)
        self.style_list.clear()

        for number, style in enumerate(available_styles, start=1):
            item = QListWidgetItem(f"STY#{number}  {style}")
            item.setData(Qt.UserRole, style)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setCheckState(
                Qt.Checked if style in selected_styles else Qt.Unchecked
            )
            self.style_list.addItem(item)

        self.style_list.blockSignals(False)
        self.style_list._update_grid_layout()
        self._refresh_check_list_visuals(self.style_list)

        self._update_style_selection_display()
        self._update_style_select_all_state()
        self._apply_style_filter()
        self._update_matrix_count_limits()

    def styles_changed(self) -> None:
        """Synchronize selected styles without rebuilding the widget."""
        selected_styles = {
            self._style_item_name(self.style_list.item(index))
            for index in range(self.style_list.count())
            if self.style_list.item(index).checkState() == Qt.Checked
        }

        canonical = {
            name: index
            for index, name in enumerate(self.style_names)
        }
        self.experiment.styles = sorted(
            selected_styles,
            key=lambda name: canonical.get(name, len(canonical)),
        )

        if self.style_sort_selected_top.isChecked():
            self._sort_selected_styles_to_top()

        self._refresh_check_list_visuals(self.style_list)
        self._update_style_selection_display()
        self._update_style_select_all_state()
        self._update_random_style_count_limit()
        self._update_matrix_count_limits()

    def _update_style_select_all_state(self) -> None:
        """Reflect whether none, some, or all styles are checked."""
        if not hasattr(self, "style_select_all"):
            return

        count = self.style_list.count()
        checked = sum(
            self.style_list.item(index).checkState() == Qt.Checked
            for index in range(count)
        )

        self.style_select_all.blockSignals(True)
        if count == 0 or checked == 0:
            state = Qt.Unchecked
        elif checked == count:
            state = Qt.Checked
        else:
            state = Qt.PartiallyChecked
        self.style_select_all.setCheckState(state)
        self.style_select_all.blockSignals(False)

    def style_select_all_changed(self, state: int) -> None:
        """Toggle the complete style pool: partial/none -> all, all -> none."""
        if self.style_list.count() == 0:
            return

        all_checked = all(
            self.style_list.item(index).checkState() == Qt.Checked
            for index in range(self.style_list.count())
        )
        # A click on Select All is intentionally a simple toggle.
        target = Qt.Unchecked if all_checked else Qt.Checked

        self.style_list.blockSignals(True)
        for index in range(self.style_list.count()):
            self.style_list.item(index).setCheckState(target)
        self.style_list.blockSignals(False)

        self.styles_changed()

    def _restore_style_order(self) -> None:
        """Restore the original runtime/Fooocus order without sorting names."""
        canonical = {
            name: index
            for index, name in enumerate(self.style_names)
        }
        items = [self.style_list.takeItem(0) for _ in range(self.style_list.count())]
        items.sort(
            key=lambda item: canonical.get(self._style_item_name(item), len(canonical))
        )
        self.style_list.blockSignals(True)
        for item in items:
            self.style_list.addItem(item)
        self.style_list.blockSignals(False)

    def _sort_selected_styles_to_top(self) -> None:
        """Move checked styles to the top while preserving canonical order."""
        count = self.style_list.count()
        if count == 0:
            return

        canonical = {
            name: index
            for index, name in enumerate(self.style_names)
        }
        items = [self.style_list.takeItem(0) for _ in range(count)]
        items.sort(
            key=lambda item: (
                item.checkState() != Qt.Checked,
                canonical.get(self._style_item_name(item), len(canonical)),
            )
        )
        self.style_list.blockSignals(True)
        for item in items:
            self.style_list.addItem(item)
        self.style_list.blockSignals(False)

    def style_sort_selected_top_changed(self, checked: bool) -> None:
        if checked:
            self._sort_selected_styles_to_top()
        else:
            self._restore_style_order()
        self._apply_style_filter()

    def random_style_changed(
        self,
        checked: bool,
    ) -> None:
        self.experiment.random_style = checked
        self.random_style_count.setEnabled(checked)
        # Random always operates on the currently selected styles.
        # Keep the style list usable so the user can define that pool.
        self.style_list.setEnabled(True)
        self.style_select_all.setEnabled(True)
        self.style_sort_selected_top.setEnabled(True)
        self._update_style_selection_display()
        self._update_random_style_count_limit()
        self._update_matrix_availability()
        self._update_matrix_count_limits()

    def _update_style_selection_display(self) -> None:
        """Show how many styles are in the current selection pool."""
        self.style_selection_label.setText(
            f"{len(self.experiment.styles)} styles selected"
        )
        self.style_selection_label.show()

    def random_style_count_changed(self, value: int) -> None:
        limit = len(self.experiment.styles)
        if self.experiment.random_style and limit > 0:
            value = min(max(1, value), limit)
        self.experiment.random_style_count = value

    def style_search_changed(self, text: str) -> None:
        self._apply_style_filter()

    def _apply_style_filter(self) -> None:
        query = self.style_search.text().strip().casefold()
        for index in range(self.style_list.count()):
            item = self.style_list.item(index)
            item.setHidden(bool(query) and query not in self._style_item_name(item).casefold())

    # ------------------------------------------------------------------
    # Matrix handling
    # ------------------------------------------------------------------

    def matrix_operator_changed(
        self,
        key: str,
        index: int,
    ) -> None:
        operators = [
            MatrixOperator.INDIVIDUAL,
            MatrixOperator.ALL,
            MatrixOperator.COMBINATION,
            MatrixOperator.PERMUTATION,
        ]

        operator = operators[index]

        selection = getattr(
            self.experiment.matrix,
            key,
        )

        selection.operator = operator

        self._update_matrix_availability()
        self._update_matrix_count_limits()

    def matrix_count_changed(
        self,
        key: str,
        minimum: int,
        maximum: int,
    ) -> None:
        selection = getattr(
            self.experiment.matrix,
            key,
        )

        selection.minimum = minimum
        selection.maximum = maximum

    def _update_matrix_availability(
        self,
    ) -> None:
        for key, control in (
            self.matrix_controls.items()
        ):
            selection = getattr(
                self.experiment.matrix,
                key,
            )

            enabled = (
                selection.operator
                in (
                    MatrixOperator.COMBINATION,
                    MatrixOperator.PERMUTATION,
                )
            )

            count_control = (
                self.matrix_count_controls.get(
                    key
                )
            )

            if count_control is not None:
                count_control.setEnabled(
                    enabled
                )

    def _update_matrix_count_limits(
        self,
    ) -> None:
        counts = {
            "positive_prompts": sum(
                not prompt.fixed
                for prompt in self.experiment.positive_prompts
            ),
            "negative_prompts": sum(
                not prompt.fixed
                for prompt in self.experiment.negative_prompts
            ),
            "styles": len(
                self.experiment.styles
            ),
            "seeds": len(
                self.experiment.generation.seeds
            ),
        }

        for key, count_control in (
            self.matrix_count_controls.items()
        ):
            count = max(
                1,
                counts.get(
                    key,
                    1,
                ),
            )

            count_control.setMaximum(
                count
            )

            selection = getattr(
                self.experiment.matrix,
                key,
            )

            minimum = (
                selection.minimum
                if selection.minimum is not None
                else 1
            )

            maximum = (
                selection.maximum
                if selection.maximum is not None
                else minimum
            )

            minimum = min(
                minimum,
                count,
            )

            maximum = min(
                maximum,
                count,
            )

            if maximum < minimum:
                maximum = minimum

            count_control.setValue(
                minimum
            )

            if (
                key == "seeds"
                and self.experiment.generation.seed_mode == SeedMode.FIXED
            ):
                seed_count = len(self.experiment.generation.seeds)
                if seed_count > 0:
                    count_control.setValue(seed_count)
                    selection.minimum = seed_count
                    selection.maximum = seed_count

    def _configure_numeric_matrix_dialog(self, key: str, label: str) -> None:
        """Edit a numeric matrix dimension from its corresponding settings row."""
        controls = self.numeric_matrix_controls.get(key)
        if controls is None:
            return
        source_enabled, source_minimum, source_maximum, source_steps = controls
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{label} Matrix")
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        enabled = QCheckBox(f"Use {label} as a matrix dimension", dialog)
        enabled.setChecked(source_enabled.isChecked())
        minimum = QDoubleSpinBox(dialog)
        maximum = QDoubleSpinBox(dialog)
        for target, source in ((minimum, source_minimum), (maximum, source_maximum)):
            target.setRange(source.minimum(), source.maximum())
            target.setDecimals(source.decimals())
            target.setSingleStep(source.singleStep())
        minimum.setValue(source_minimum.value())
        maximum.setValue(source_maximum.value())
        steps = QSpinBox(dialog)
        steps.setRange(1, 100)
        steps.setValue(source_steps.value())
        form.addRow(enabled)
        form.addRow("Minimum", minimum)
        form.addRow("Maximum", maximum)
        form.addRow("Steps", steps)
        layout.addLayout(form)
        def set_inputs_enabled(checked: bool) -> None:
            minimum.setEnabled(checked)
            maximum.setEnabled(checked)
            steps.setEnabled(checked)
        enabled.toggled.connect(set_inputs_enabled)
        set_inputs_enabled(enabled.isChecked())
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            source_enabled.setChecked(enabled.isChecked())
            source_minimum.setValue(minimum.value())
            source_maximum.setValue(maximum.value())
            source_steps.setValue(steps.value())
            self._numeric_matrix_changed(key)

    def _numeric_matrix_changed(self, key: str) -> None:
        checkbox, minimum, maximum, steps = self.numeric_matrix_controls[key]
        selection = getattr(self.experiment.matrix, key)

        selection.enabled = checkbox.isChecked()
        selection.minimum = float(minimum.value())
        selection.maximum = float(maximum.value())
        selection.steps = int(steps.value())

        self.prompt_inputs_changed.emit()

    def _numeric_matrix_toggled(self, key: str, checked: bool) -> None:
        checkbox, minimum, maximum, steps = self.numeric_matrix_controls[key]
        selection = getattr(self.experiment.matrix, key)

        selection.enabled = checked
        selection.minimum = float(minimum.value())
        selection.maximum = float(maximum.value())
        selection.steps = int(steps.value())

        minimum.setEnabled(checked)
        maximum.setEnabled(checked)
        steps.setEnabled(checked)

        self.prompt_inputs_changed.emit()

    def _create_numeric_matrix_row(
        self,
        key: str,
        label: str,
        default_minimum: float,
        default_maximum: float,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        selection = getattr(self.experiment.matrix, key)

        minimum_value = (
            float(selection.minimum)
            if selection.minimum is not None
            else default_minimum
        )
        maximum_value = (
            float(selection.maximum)
            if selection.maximum is not None
            else default_maximum
        )

        label_widget = QLabel(label)
        label_widget.setMinimumWidth(112)

        enabled = QCheckBox("Matrix")
        enabled.setChecked(selection.enabled)
        enabled.setToolTip(
            f"Use {label} as a matrix dimension. "
            "The range is sampled evenly from minimum to maximum."
        )

        minimum = QDoubleSpinBox()
        minimum.setRange(default_minimum, default_maximum)
        minimum.setSingleStep(0.5)
        minimum.setDecimals(1)
        minimum.setValue(minimum_value)
        minimum.setMinimumWidth(76)
        minimum.setToolTip(f"Minimum {label} value.")

        maximum = QDoubleSpinBox()
        maximum.setRange(default_minimum, default_maximum)
        maximum.setSingleStep(0.5)
        maximum.setDecimals(1)
        maximum.setValue(maximum_value)
        maximum.setMinimumWidth(76)
        maximum.setToolTip(f"Maximum {label} value.")

        steps = QSpinBox()
        steps.setRange(1, 100)
        steps.setValue(max(1, min(100, int(selection.steps)))
                      if selection.steps else 1)
        steps.setMinimumWidth(64)
        steps.setToolTip(
            "Number of evenly spaced values, including both endpoints."
        )

        self.numeric_matrix_controls[key] = (
            enabled,
            minimum,
            maximum,
            steps,
        )

        enabled.toggled.connect(
            lambda checked, matrix_key=key:
            self._numeric_matrix_toggled(matrix_key, checked)
        )
        minimum.valueChanged.connect(
            lambda _value, matrix_key=key:
            self._numeric_matrix_changed(matrix_key)
            if self.numeric_matrix_controls[matrix_key][0].isChecked()
            else None
        )
        maximum.valueChanged.connect(
            lambda _value, matrix_key=key:
            self._numeric_matrix_changed(matrix_key)
            if self.numeric_matrix_controls[matrix_key][0].isChecked()
            else None
        )
        steps.valueChanged.connect(
            lambda _value, matrix_key=key:
            self._numeric_matrix_changed(matrix_key)
            if self.numeric_matrix_controls[matrix_key][0].isChecked()
            else None
        )

        minimum.setEnabled(selection.enabled)
        maximum.setEnabled(selection.enabled)
        steps.setEnabled(selection.enabled)

        layout.addWidget(label_widget)
        layout.addWidget(enabled)
        layout.addWidget(QLabel("Min"))
        layout.addWidget(minimum)
        layout.addWidget(QLabel("Max"))
        layout.addWidget(maximum)
        layout.addWidget(QLabel("Steps"))
        layout.addWidget(steps)
        layout.addStretch(1)

        return row

    def _create_matrix_row(
        self,
        key: str,
        label: str,
    ) -> QWidget:
        row = QWidget()

        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            6,
            2,
            6,
            2,
        )
        layout.setSpacing(8)

        operator = QComboBox()
        operator.setMinimumWidth(112)
        operator.setMinimumHeight(28)

        operator.addItems(
            [
                "Individual",
                "All",
                "Combination",
                "Permutation",
            ]
        )

        operator_tooltips = [
            "Each selected item is tested individually.\n"
            "Example: A, B, C → 3 variants",

            "All selected items are used together.\n"
            "Example: A, B, C → 1 variant",

            "Creates combinations of the selected items.\n"
            "Order does not matter.\n"
            "Example: A, B, C with n=2 → AB, AC, BC",

            "Creates permutations of the selected items.\n"
            "Order matters.\n"
            "Example: A, B, C with n=2 → AB, AC, BA, BC, CA, CB",
        ]

        def update_operator_tooltip(index: int) -> None:
            if 0 <= index < len(operator_tooltips):
                operator.setToolTip(operator_tooltips[index])

        update_operator_tooltip(operator.currentIndex())

        selection = getattr(
            self.experiment.matrix,
            key,
        )

        operator.setCurrentIndex(
            [
                MatrixOperator.INDIVIDUAL,
                MatrixOperator.ALL,
                MatrixOperator.COMBINATION,
                MatrixOperator.PERMUTATION,
            ].index(
                selection.operator
            )
        )

        operator.currentIndexChanged.connect(
            lambda index, matrix_key=key:
            self.matrix_operator_changed(
                matrix_key,
                index,
            )
        )

        operator.currentIndexChanged.connect(
            update_operator_tooltip
        )

        count = QSpinBox()
        count.setMinimumWidth(72)
        count.setMinimumHeight(28)

        count.setToolTip(
            "Number of items used for each combination or permutation.\n"
            "For ranges, all sizes from minimum to maximum are generated."
        )

        count.setMinimum(
            1
        )

        count.setMaximum(
            100
        )

        count.setValue(
            selection.minimum
            if selection.minimum is not None
            else 1
        )

        count.valueChanged.connect(
            lambda value, matrix_key=key:
            self.matrix_count_changed(
                matrix_key,
                value,
                value,
            )
        )

        self.matrix_controls[key] = operator
        self.matrix_count_controls[key] = count

        label_widget = QLabel(label)
        label_widget.setMinimumWidth(112)
        n_label = QLabel("n:")
        n_label.setMinimumWidth(24)

        layout.addWidget(label_widget)
        layout.addWidget(operator)
        layout.addWidget(n_label)
        layout.addWidget(count)
        layout.addStretch(1)

        return row

    def _create_matrix_controls(
        self,
    ) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(
            container
        )

        layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )
        layout.setSpacing(4)

        keys = [
            (
                "positive_prompts",
                "Positive Prompts",
            ),
            (
                "negative_prompts",
                "Negative Prompts",
            ),
            (
                "styles",
                "Styles",
            ),
            (
                "seeds",
                "Seeds",
            ),
        ]

        for key, label in keys:
            layout.addWidget(
                self._create_matrix_row(
                    key,
                    label,
                )
            )

        layout.addSpacing(4)
        layout.addWidget(
            self._create_numeric_matrix_row(
                "guidance_scale",
                "Guidance Scale",
                1.0,
                30.0,
            )
        )
        layout.addWidget(
            self._create_numeric_matrix_row(
                "sharpness",
                "Sharpness",
                0.0,
                30.0,
            )
        )

        # Resolution is configured here centrally and also in the Resolution
        # section. Both entry points operate on the same experiment model.
        resolution_row = QWidget()
        resolution_row_layout = QHBoxLayout(resolution_row)
        resolution_row_layout.setContentsMargins(6, 4, 6, 2)
        resolution_row_layout.setSpacing(8)
        self.resolution_matrix_hub_enabled = QCheckBox("Resolution")
        self.resolution_matrix_hub_enabled.setChecked(self.experiment.matrix.resolution.enabled)
        self.resolution_matrix_hub_enabled.toggled.connect(self._resolution_matrix_hub_toggled)
        self.resolution_matrix_summary = QLabel()
        self.resolution_matrix_summary.setMinimumWidth(120)
        self.resolution_matrix_summary.setWordWrap(True)
        configure_resolution = QPushButton("Configure…")
        configure_resolution.setToolTip("Configure this matrix dimension here or in Resolution.")
        configure_resolution.clicked.connect(self._configure_resolution_matrix_dialog)
        resolution_row_layout.addWidget(self.resolution_matrix_hub_enabled)
        resolution_row_layout.addWidget(self.resolution_matrix_summary, 1)
        resolution_row_layout.addWidget(configure_resolution)
        layout.addWidget(resolution_row)
        self._update_resolution_matrix_summary()

        self._update_matrix_availability()

        return container

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def create_ui(
        self,
    ) -> None:
        container = QWidget()

        form = QVBoxLayout(container)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(7)
        # Keep sections packed at the top of the scroll area. Without an
        # explicit alignment, spare viewport height can be distributed as
        # large gaps between the fixed Experiment controls and collapsible
        # sections on some Qt layout configurations.
        form.setAlignment(Qt.AlignTop)

        def add_section(label: str, widget: QWidget) -> None:
            form.addWidget(CollapsibleSection(label, widget))

        def add_fixed_section(label: str, widget: QWidget) -> None:
            title = QLabel(label)
            title.setProperty("role", "sectionTitle")
            form.addWidget(title)
            form.addWidget(widget)

        def style_section(widget: QWidget) -> None:
            # Scope the frame styling to the section container itself; using
            # a generic QWidget selector would also frame every child control.
            widget.setObjectName("sectionFrame")
            widget.setStyleSheet(
                "#sectionFrame { border: 1px solid #263B62; "
                "border-radius: 6px; padding: 2px; }"
            )

        # --------------------------------------------------------------
        # Experiment name
        # --------------------------------------------------------------

        self.experiment_name = QLineEdit()

        self.experiment_name.setText(
            self.experiment.name
        )

        # --------------------------------------------------------------
        # Positive prompts
        # --------------------------------------------------------------

        positive_container = QWidget()

        self.positive_prompt_layout = (
            QVBoxLayout(
                positive_container
            )
        )

        self.positive_prompt_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        add_positive_button = QPushButton(
            "+ Prompt"
        )
        self._positive_add_button = add_positive_button

        add_positive_button.setMaximumWidth(
            100
        )

        add_positive_button.setFocusPolicy(
            Qt.NoFocus
        )

        add_positive_button.clicked.connect(
            self.add_positive_prompt
        )

        self.positive_prompt_layout.addWidget(
            add_positive_button
        )

        self.add_positive_prompt()
        self._restore_prompt_group(
            "positive",
            self.experiment.positive_prompts,
        )
        style_section(positive_container)

        # --------------------------------------------------------------
        # Negative prompts
        # --------------------------------------------------------------

        negative_container = QWidget()

        self.negative_prompt_layout = (
            QVBoxLayout(
                negative_container
            )
        )

        self.negative_prompt_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        add_negative_button = QPushButton(
            "+ Negative"
        )
        self._negative_add_button = add_negative_button

        add_negative_button.setMaximumWidth(
            100
        )

        add_negative_button.setFocusPolicy(
            Qt.NoFocus
        )

        add_negative_button.clicked.connect(
            self.add_negative_prompt
        )

        self.negative_prompt_layout.addWidget(
            add_negative_button
        )

        self.add_negative_prompt()
        self._restore_prompt_group(
            "negative",
            self.experiment.negative_prompts,
        )
        style_section(negative_container)

        # --------------------------------------------------------------
        # Styles
        # --------------------------------------------------------------

        styles_container = QWidget()

        styles_layout = QVBoxLayout(
            styles_container
        )

        styles_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.style_search = QLineEdit()

        self.style_search.setPlaceholderText(
            "Filter styles..."
        )

        self.style_search.textChanged.connect(
            self.style_search_changed
        )

        self.random_style_checkbox = (
            QCheckBox(
                "Random Selected"
            )
        )

        self.random_style_checkbox.setChecked(
            self.experiment.random_style
        )

        self.random_style_checkbox.setToolTip(
            "Randomly select styles from the currently "
            "selected styles."
        )

        self.random_style_checkbox.toggled.connect(
            self.random_style_changed
        )

        self.random_style_count = QSpinBox()

        self.random_style_count.setMinimum(
            1
        )

        self.random_style_count.setMaximum(
            100
        )

        self.random_style_count.setValue(
            self.experiment.random_style_count
        )

        self.random_style_count.valueChanged.connect(
            self.random_style_count_changed
        )

        self.random_style_count.setEnabled(
            self.experiment.random_style
        )

        self.random_style_count.setToolTip(
            "Number of random styles to select from the "
            "currently selected style pool for each configuration."
        )

        random_style_count_row = QWidget()

        random_style_count_layout = QHBoxLayout(
            random_style_count_row
        )

        random_style_count_layout.setContentsMargins(
            20,
            0,
            0,
            0
        )

        random_style_count_layout.addWidget(
            QLabel(
                "Number of styles:"
            )
        )

        random_style_count_layout.addWidget(
            self.random_style_count
        )

        random_style_count_layout.addStretch()

        self.style_list = StyleListWidget()
        self.style_list.setObjectName("styleList")
        self.style_list.setViewMode(QListView.IconMode)
        self.style_list.setFlow(QListView.LeftToRight)
        self.style_list.setWrapping(True)
        self.style_list.setResizeMode(QListView.Adjust)
        self.style_list.setMovement(QListView.Static)
        self.style_list.setUniformItemSizes(True)
        self.style_list.setGridSize(QSize(190, 28))
        self.style_list.setMinimumHeight(150)
        self.style_list.setSpacing(0)
        self.style_list.setSelectionMode(QListWidget.NoSelection)

        # No styles are selected before Fooocus connects.
        # The runtime supplies the actual style pool via set_style_choices().

        self.style_list.itemChanged.connect(
            self.styles_changed
        )

        self.style_select_all = QCheckBox("Select All")
        self.style_select_all.setTristate(True)
        self.style_select_all.setToolTip(
            "Select all styles; click again to deselect all."
        )
        self.style_select_all.stateChanged.connect(
            self.style_select_all_changed
        )
        self.style_select_all.setEnabled(
            not self.experiment.random_style
        )

        self.style_selection_label = QLabel("0 styles selected")

        self.style_sort_selected_top = QCheckBox(
            "Selected styles on top"
        )
        self.style_sort_selected_top.setChecked(False)
        self.style_sort_selected_top.setToolTip(
            "Keep selected styles at the top of the list."
        )
        self.style_sort_selected_top.toggled.connect(
            self.style_sort_selected_top_changed
        )

        style_actions_row = QWidget()
        style_actions_layout = QHBoxLayout(style_actions_row)
        style_actions_layout.setContentsMargins(0, 0, 0, 0)
        style_actions_layout.addWidget(self.style_selection_label)
        style_actions_layout.addStretch()
        style_actions_layout.addWidget(self.random_style_checkbox)
        style_actions_layout.addWidget(self.style_select_all)

        styles_layout.addWidget(self.style_search)
        styles_layout.addWidget(style_actions_row)
        styles_layout.addWidget(self.style_sort_selected_top)

        styles_layout.addWidget(
            random_style_count_row
        )

        styles_layout.addWidget(
            self.style_list
        )

        # During construction the runtime style pool has not necessarily
        # been supplied yet.  Do not call styles_changed() here because an
        # experiment loaded from disk may already contain selected styles;
        # an empty widget at this point would otherwise overwrite them with
        # an empty selection before set_style_choices() restores the pool.
        if self.style_list.count() > 0:
            self.styles_changed()
        else:
            self._update_style_selection_display()
            self._update_style_select_all_state()
            self._update_random_style_count_limit()

        style_section(styles_container)

        # --------------------------------------------------------------
        # Seeds
        # --------------------------------------------------------------

        seed_container = QWidget()

        seed_container_layout = QVBoxLayout(
            seed_container
        )

        seed_container_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.random_seed_checkbox = (
            QCheckBox(
                "Random seed"
            )
        )

        self.random_seed_checkbox.setChecked(
            self.experiment.generation.seed_mode
            == SeedMode.RANDOM
        )

        self.random_seed_checkbox.toggled.connect(
            self.random_seed_changed
        )

        self.random_seed_count = QSpinBox()

        self.random_seed_count.setMinimum(
            1
        )

        self.random_seed_count.setMaximum(
            100
        )

        self.random_seed_count.setValue(
            self.experiment.generation.random_seed_count
        )

        self.random_seed_count.valueChanged.connect(
            self.random_seed_count_changed
        )

        self.random_seed_count.setEnabled(
            self.experiment.generation.seed_mode
            == SeedMode.RANDOM
        )

        self.random_seed_count.setToolTip(
            "Number of random seeds to generate "
            "for each matrix combination."
        )

        random_seed_count_row = QWidget()

        random_seed_count_layout = QHBoxLayout(
            random_seed_count_row
        )

        random_seed_count_layout.setContentsMargins(
            20,
            0,
            0,
            0,
        )

        random_seed_count_layout.addWidget(
            QLabel(
                "Number of seeds:"
            )
        )

        random_seed_count_layout.addWidget(
            self.random_seed_count
        )

        random_seed_count_layout.addStretch()

        self.manual_seed_container = QWidget()

        self.seed_layout = QVBoxLayout(
            self.manual_seed_container
        )

        self.seed_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.add_seed_button = QPushButton(
            "+ Seed"
        )

        self.add_seed_button.setMaximumWidth(
            100
        )

        self.add_seed_button.setFocusPolicy(
            Qt.NoFocus
        )

        self.add_seed_button.clicked.connect(
            self.add_seed
        )

        self.seed_layout.addWidget(
            self.add_seed_button
        )

        # Capture persisted seeds BEFORE creating the initial row. add_seed()
        # now synchronizes the live queue, so calling it first would otherwise
        # overwrite the JSON-loaded seed pool with an empty list.
        loaded_seeds = list(self.experiment.generation.seeds)

        self.add_seed()

        # Restore all manually stored seeds into the editor without emitting
        # seeds_changed() during construction.
        if loaded_seeds:
            while len(self.seed_edits) < len(loaded_seeds):
                self.add_seed()

            for edit, seed in zip(self.seed_edits, loaded_seeds):
                edit.blockSignals(True)
                try:
                    edit.setText(str(seed))
                finally:
                    edit.blockSignals(False)

            # add_seed() synchronizes the live model. Put the persisted JSON
            # values back before Matrix controls are created so the matrix
            # sees the correct fixed-seed pool during initialization.
            self.experiment.generation.seeds = list(loaded_seeds)
            self.experiment.generation.seed = loaded_seeds[0]

        # In FIXED mode the visible seed count represents the persisted
        # manual seed pool. The random-seed count remains independent.
        if self.experiment.generation.seed_mode == SeedMode.FIXED:
            self.random_seed_count.blockSignals(True)
            self.random_seed_count.setValue(max(1, len(loaded_seeds)))
            self.random_seed_count.blockSignals(False)

        seed_container_layout.addWidget(
            self.random_seed_checkbox
        )

        seed_container_layout.addWidget(
            random_seed_count_row
        )

        seed_container_layout.addWidget(
            self.manual_seed_container
        )
        style_section(seed_container)

        # --------------------------------------------------------------
        # Matrix
        # --------------------------------------------------------------

        matrix_container = (
            self._create_matrix_controls()
        )
        style_section(matrix_container)

        # --------------------------------------------------------------
        # Base Models
        # --------------------------------------------------------------

        base_model_container = QWidget()
        base_model_layout = QVBoxLayout(base_model_container)
        base_model_layout.setContentsMargins(10, 10, 10, 10)
        base_model_layout.setSpacing(6)

        self.base_model_selection_label = QLabel(
            "0 base models selected"
        )

        self.base_model_list = BaseModelListWidget()
        self.base_model_list.setObjectName("baseModelList")
        self.base_model_list.setViewMode(QListView.ListMode)
        self.base_model_list.setFlow(QListView.TopToBottom)
        self.base_model_list.setWrapping(False)
        self.base_model_list.setMovement(QListView.Static)
        self.base_model_list.setUniformItemSizes(True)
        self.base_model_list.setGridSize(QSize(220, 28))
        self.base_model_list.setMaximumHeight(140)
        self.base_model_list.itemChanged.connect(
            self.base_models_changed
        )

        base_model_layout.addWidget(
            self.base_model_selection_label
        )
        base_model_layout.addWidget(
            self.base_model_list
        )
        style_section(base_model_container)

        # Keep the legacy attribute available for code that still reads it.
        self.model = QLineEdit()
        self.model.setVisible(False)

        # --------------------------------------------------------------
        # Fooocus Settings
        # --------------------------------------------------------------

        fooocus_settings_container = QWidget()
        fooocus_settings_layout = QFormLayout(fooocus_settings_container)
        fooocus_settings_layout.setContentsMargins(10, 10, 10, 10)
        fooocus_settings_layout.setVerticalSpacing(6)

        self.fooocus_performance_combo = QComboBox()
        self.fooocus_performance_combo.addItems([
            "Speed", "Quality", "Extreme Speed", "Lightning"
        ])
        current = self.experiment.generation.performance
        if current:
            index = self.fooocus_performance_combo.findText(current)
            if index >= 0:
                self.fooocus_performance_combo.setCurrentIndex(index)
        else:
            self.experiment.generation.performance = "Speed"
        self.fooocus_performance_combo.currentTextChanged.connect(self.fooocus_performance_changed)

        self.fooocus_guidance_spin = QDoubleSpinBox()
        self.fooocus_guidance_spin.setRange(1.0, 30.0)
        self.fooocus_guidance_spin.setSingleStep(0.5)
        self.fooocus_guidance_spin.setDecimals(1)
        self.fooocus_guidance_spin.setFixedWidth(100)
        guidance = 4.0 if self.experiment.generation.guidance_scale is None else float(self.experiment.generation.guidance_scale)
        self.experiment.generation.guidance_scale = guidance
        self.fooocus_guidance_spin.setValue(guidance)
        self.fooocus_guidance_spin.valueChanged.connect(self.fooocus_guidance_changed)

        self.fooocus_sharpness_spin = QDoubleSpinBox()
        self.fooocus_sharpness_spin.setRange(0.0, 30.0)
        self.fooocus_sharpness_spin.setSingleStep(0.5)
        self.fooocus_sharpness_spin.setDecimals(1)
        self.fooocus_sharpness_spin.setFixedWidth(100)
        sharpness = 2.0 if self.experiment.generation.sharpness is None else float(self.experiment.generation.sharpness)
        self.experiment.generation.sharpness = sharpness
        self.fooocus_sharpness_spin.setValue(sharpness)
        self.fooocus_sharpness_spin.valueChanged.connect(self.fooocus_sharpness_changed)

        self.fooocus_refiner_combo = QComboBox()
        self.fooocus_refiner_combo.addItem("None", "")
        if self.experiment.generation.refiner_model:
            self.fooocus_refiner_combo.addItem(self.experiment.generation.refiner_model, self.experiment.generation.refiner_model)
            self.fooocus_refiner_combo.setCurrentIndex(1)
        self.fooocus_refiner_combo.setFixedWidth(150)
        self.fooocus_refiner_combo.currentIndexChanged.connect(
            lambda _index: self.fooocus_refiner_changed(self.fooocus_refiner_combo.currentData() or "")
        )

        self.fooocus_refiner_switch_spin = QDoubleSpinBox()
        self.fooocus_refiner_switch_spin.setRange(0.0, 1.0)
        self.fooocus_refiner_switch_spin.setSingleStep(0.05)
        self.fooocus_refiner_switch_spin.setDecimals(2)
        self.fooocus_refiner_switch_spin.setFixedWidth(100)
        refiner_switch = 0.8 if self.experiment.generation.refiner_switch is None else float(self.experiment.generation.refiner_switch)
        self.experiment.generation.refiner_switch = refiner_switch
        self.fooocus_refiner_switch_spin.setValue(refiner_switch)
        self.fooocus_refiner_switch_spin.valueChanged.connect(self.fooocus_refiner_switch_changed)

        self.fooocus_output_format_combo = QComboBox()
        self.fooocus_output_format_combo.addItems(["png", "jpg", "webp"])
        index = self.fooocus_output_format_combo.findText(self.experiment.generation.output_format)
        if index >= 0:
            self.fooocus_output_format_combo.setCurrentIndex(index)
        self.fooocus_output_format_combo.setFixedWidth(90)
        self.fooocus_output_format_combo.currentTextChanged.connect(self.fooocus_output_format_changed)

        fooocus_settings_layout.addRow("Performance", self.fooocus_performance_combo)

        guidance_matrix_row = QWidget()
        guidance_matrix_layout = QHBoxLayout(guidance_matrix_row)
        guidance_matrix_layout.setContentsMargins(0, 0, 0, 0)
        guidance_matrix_layout.setSpacing(6)
        guidance_matrix_layout.addWidget(self.fooocus_guidance_spin)
        guidance_matrix_button = QPushButton("Matrix…")
        guidance_matrix_button.setToolTip("Configure Guidance Scale as an experiment dimension.")
        guidance_matrix_button.clicked.connect(lambda: self._configure_numeric_matrix_dialog("guidance_scale", "Guidance Scale"))
        guidance_matrix_layout.addWidget(guidance_matrix_button)
        guidance_matrix_layout.addStretch(1)

        sharpness_matrix_row = QWidget()
        sharpness_matrix_layout = QHBoxLayout(sharpness_matrix_row)
        sharpness_matrix_layout.setContentsMargins(0, 0, 0, 0)
        sharpness_matrix_layout.setSpacing(6)
        sharpness_matrix_layout.addWidget(self.fooocus_sharpness_spin)
        sharpness_matrix_button = QPushButton("Matrix…")
        sharpness_matrix_button.setToolTip("Configure Sharpness as an experiment dimension.")
        sharpness_matrix_button.clicked.connect(lambda: self._configure_numeric_matrix_dialog("sharpness", "Sharpness"))
        sharpness_matrix_layout.addWidget(sharpness_matrix_button)
        sharpness_matrix_layout.addStretch(1)

        fooocus_settings_layout.addRow("Guidance Scale", guidance_matrix_row)
        fooocus_settings_layout.addRow("Sharpness", sharpness_matrix_row)
        fooocus_settings_layout.addRow("Refiner", self.fooocus_refiner_combo)
        fooocus_settings_layout.addRow("Refiner Switch", self.fooocus_refiner_switch_spin)
        fooocus_settings_layout.addRow("Output Format", self.fooocus_output_format_combo)
        style_section(fooocus_settings_container)

        # --------------------------------------------------------------
        # Resolution
        # --------------------------------------------------------------

        self.width_slider = QSlider(
            Qt.Horizontal
        )

        self.height_slider = QSlider(
            Qt.Horizontal
        )

        self.width_slider.setMinimum(
            0
        )

        self.width_slider.setMaximum(
            (
                MAX_GENERATION_WIDTH
                - MIN_GENERATION_WIDTH
            )
            // GENERATION_SIZE_STEP
        )

        self.height_slider.setMinimum(
            0
        )

        self.height_slider.setMaximum(
            (
                MAX_GENERATION_HEIGHT
                - MIN_GENERATION_HEIGHT
            )
            // GENERATION_SIZE_STEP
        )

        self.width_slider.setSingleStep(
            1
        )

        self.width_slider.setPageStep(
            1
        )

        self.height_slider.setSingleStep(
            1
        )

        self.height_slider.setPageStep(
            1
        )

        self.width_value = QLabel()
        self.height_value = QLabel()

        self.width_value.setMinimumWidth(
            50
        )

        self.height_value.setMinimumWidth(
            50
        )

        self.width_slider.setValue(
            (
                self.experiment.generation.width
                - MIN_GENERATION_WIDTH
            )
            // GENERATION_SIZE_STEP
        )

        self.height_slider.setValue(
            (
                self.experiment.generation.height
                - MIN_GENERATION_HEIGHT
            )
            // GENERATION_SIZE_STEP
        )

        self.width_value.setText(
            str(
                self.experiment.generation.width
            )
        )

        self.height_value.setText(
            str(
                self.experiment.generation.height
            )
        )

        self._updating_resolution = False
        self._resolution_ratio = (
            self.experiment.generation.width / self.experiment.generation.height
            if self.experiment.generation.height > 0
            else 16 / 9
        )

        self.width_slider.valueChanged.connect(
            self.width_changed
        )

        self.height_slider.valueChanged.connect(
            self.height_changed
        )

        # --------------------------------------------------------------
        # Resolution section
        # --------------------------------------------------------------

        resolution_container = QWidget()
        resolution_layout = QVBoxLayout(resolution_container)
        resolution_layout.setContentsMargins(10, 10, 10, 10)
        resolution_layout.setSpacing(6)

        # --------------------------------------------------------------
        # Form
        # --------------------------------------------------------------

        add_fixed_section("Experiment", self.experiment_name)

        add_section("Matrix", matrix_container)

        add_section("Positive Prompts", positive_container)

        add_section("Negative Prompts", negative_container)

        add_section("Styles", styles_container)

        reference_container = self._create_reference_controls()
        add_section("Reference Images", reference_container)

        add_section("Seeds", seed_container)

        add_section("Base Models", base_model_container)

        add_section("Fooocus Settings", fooocus_settings_container)

        width_row = QWidget()

        width_layout = QHBoxLayout(
            width_row
        )

        width_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        width_layout.addWidget(
            self.width_slider
        )

        width_layout.addWidget(
            self.width_value
        )

        height_row = QWidget()

        height_layout = QHBoxLayout(
            height_row
        )

        height_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        height_layout.addWidget(
            self.height_slider
        )

        height_layout.addWidget(
            self.height_value
        )

        width_label_row = QWidget()
        width_label_layout = QHBoxLayout(width_label_row)
        width_label_layout.setContentsMargins(0, 0, 0, 0)
        width_label_layout.addWidget(QLabel("Width"))
        width_label_layout.addWidget(width_row, 1)

        height_label_row = QWidget()
        height_label_layout = QHBoxLayout(height_label_row)
        height_label_layout.setContentsMargins(0, 0, 0, 0)
        height_label_layout.addWidget(QLabel("Height"))
        height_label_layout.addWidget(height_row, 1)

        resolution_layout.addWidget(width_label_row)
        resolution_layout.addWidget(height_label_row)

        self.keep_aspect_ratio_checkbox = QCheckBox("Keep aspect ratio")
        self.keep_aspect_ratio_checkbox.setChecked(True)
        self.keep_aspect_ratio_checkbox.setToolTip(
            "Adjust width and height proportionally."
        )
        self.keep_aspect_ratio_checkbox.toggled.connect(
            self.keep_aspect_ratio_changed
        )
        resolution_layout.addWidget(self.keep_aspect_ratio_checkbox)

        # Optional resolution matrix. Fooocus receives each concrete size
        # directly; Desperate Render never resizes the resulting image.
        resolution_matrix = self.experiment.matrix.resolution
        self.resolution_matrix_enabled = QCheckBox("Resolution matrix")
        self.resolution_matrix_enabled.setChecked(resolution_matrix.enabled)
        self.resolution_matrix_enabled.setToolTip(
            "Render several resolutions directly in Fooocus while keeping the current aspect ratio."
        )
        resolution_layout.addWidget(self.resolution_matrix_enabled)

        resolution_matrix_form = QFormLayout()
        self.resolution_matrix_dimension = QComboBox()
        self.resolution_matrix_dimension.addItem("Width", "width")
        self.resolution_matrix_dimension.addItem("Height", "height")
        dimension_index = self.resolution_matrix_dimension.findData(resolution_matrix.dimension)
        if dimension_index >= 0:
            self.resolution_matrix_dimension.setCurrentIndex(dimension_index)

        selected_dimension = self.resolution_matrix_dimension.currentData() or "width"
        axis_minimum, axis_maximum, current_axis = (
            (MIN_GENERATION_WIDTH, MAX_GENERATION_WIDTH, self.experiment.generation.width)
            if selected_dimension == "width"
            else (MIN_GENERATION_HEIGHT, MAX_GENERATION_HEIGHT, self.experiment.generation.height)
        )
        self.resolution_matrix_minimum = QSpinBox()
        self.resolution_matrix_minimum.setRange(axis_minimum, axis_maximum)
        self.resolution_matrix_minimum.setSingleStep(GENERATION_SIZE_STEP)
        self.resolution_matrix_minimum.setValue(
            max(
                axis_minimum,
                min(
                    axis_maximum,
                    resolution_matrix.minimum
                    if resolution_matrix.minimum is not None
                    else current_axis - 160,
                ),
            )
        )
        self.resolution_matrix_maximum = QSpinBox()
        self.resolution_matrix_maximum.setRange(axis_minimum, axis_maximum)
        self.resolution_matrix_maximum.setSingleStep(GENERATION_SIZE_STEP)
        self.resolution_matrix_maximum.setValue(
            max(
                axis_minimum,
                min(
                    axis_maximum,
                    resolution_matrix.maximum
                    if resolution_matrix.maximum is not None
                    else current_axis + 160,
                ),
            )
        )
        self.resolution_matrix_steps = QSpinBox()
        self.resolution_matrix_steps.setRange(2, 20)
        self.resolution_matrix_steps.setValue(max(2, min(20, resolution_matrix.steps)))
        self.resolution_matrix_steps.setToolTip(
            "Number of evenly spaced sizes, including minimum and maximum."
        )

        resolution_matrix_form.addRow("Vary", self.resolution_matrix_dimension)
        resolution_matrix_form.addRow("Minimum", self.resolution_matrix_minimum)
        resolution_matrix_form.addRow("Maximum", self.resolution_matrix_maximum)
        resolution_matrix_form.addRow("Steps", self.resolution_matrix_steps)
        resolution_layout.addLayout(resolution_matrix_form)

        self.resolution_matrix_dimension.currentIndexChanged.connect(
            self.resolution_matrix_dimension_changed
        )
        self.resolution_matrix_enabled.toggled.connect(self.resolution_matrix_changed)
        self.resolution_matrix_minimum.valueChanged.connect(self.resolution_matrix_changed)
        self.resolution_matrix_maximum.valueChanged.connect(self.resolution_matrix_changed)
        self.resolution_matrix_steps.valueChanged.connect(self.resolution_matrix_changed)
        self.resolution_matrix_changed()
        style_section(resolution_container)
        add_section("Resolution", resolution_container)

        # The scroll-area content must follow the actual viewport width.
        # A fixed minimum width here makes the content wider than the viewport
        # as soon as the Properties panel is narrowed, which causes the right
        # side of rows to disappear underneath the vertical scrollbar.
        # Horizontal scrolling belongs to the main window, so the inner
        # Properties content itself must be allowed to shrink with its panel.
        container.setMinimumWidth(0)
        container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        # Horizontal scrolling belongs to the main window. The Properties
        # panel itself must never create a second horizontal scroll area.
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidget(container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Properties")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self.scroll_area, 1)

        self.random_seed_changed(
            self.random_seed_checkbox.isChecked()
        )

        self._update_matrix_availability()
        self._update_performance_parameter_availability()
