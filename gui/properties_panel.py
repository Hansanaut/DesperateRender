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
    QGraphicsOpacityEffect,
    QComboBox,
    QDoubleSpinBox,
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
    QSlider,
    QSpinBox,
    QTextEdit,
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


class PropertiesPanel(QGroupBox):
    """Displays and edits the properties of the selected experiment."""

    prompt_inputs_changed = Signal()

    def __init__(
        self,
        experiment: Experiment,
    ) -> None:
        super().__init__("Properties")
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
        edit.setMinimumHeight(minimum_height)

        remove_button = QPushButton("✕")
        remove_button.setFixedWidth(32)
        remove_button.setFocusPolicy(Qt.NoFocus)
        remove_button.setToolTip("Remove prompt")
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
        edit.textChanged.connect(lambda: edit.setToolTip(edit.toPlainText()))
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

            # Follow the moved prompt to its new numbered row.
            target_edit.setFocus()
            return True

        return False


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
        # Nothing is selected implicitly; style selection is explicit.
        self.experiment.styles = []
        selected_styles: set[str] = set()

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

        self._update_matrix_availability()

        return container

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def create_ui(
        self,
    ) -> None:
        container = QWidget()

        form = QVBoxLayout(
            container
        )
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(7)

        def add_section(label: str, widget: QWidget) -> None:
            title = QLabel(label)
            title.setContentsMargins(0, 0, 0, 0)
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
            0,
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

        self.styles_changed()
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

        self.add_seed()

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
        base_model_layout.setContentsMargins(8, 8, 8, 8)
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
        fooocus_settings_layout.setContentsMargins(8, 8, 8, 8)
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
        self.fooocus_guidance_spin.setFixedWidth(76)
        guidance = 4.0 if self.experiment.generation.guidance_scale is None else float(self.experiment.generation.guidance_scale)
        self.experiment.generation.guidance_scale = guidance
        self.fooocus_guidance_spin.setValue(guidance)
        self.fooocus_guidance_spin.valueChanged.connect(self.fooocus_guidance_changed)

        self.fooocus_sharpness_spin = QDoubleSpinBox()
        self.fooocus_sharpness_spin.setRange(0.0, 30.0)
        self.fooocus_sharpness_spin.setSingleStep(0.5)
        self.fooocus_sharpness_spin.setDecimals(1)
        self.fooocus_sharpness_spin.setFixedWidth(76)
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
        self.fooocus_refiner_switch_spin.setFixedWidth(76)
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
        fooocus_settings_layout.addRow("Guidance Scale", self.fooocus_guidance_spin)
        fooocus_settings_layout.addRow("Sharpness", self.fooocus_sharpness_spin)
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
        resolution_layout.setContentsMargins(8, 8, 8, 8)
        resolution_layout.setSpacing(6)

        # --------------------------------------------------------------
        # Form
        # --------------------------------------------------------------

        add_section("Experiment", self.experiment_name)

        add_section("Positive Prompts", positive_container)

        add_section("Negative Prompts", negative_container)

        add_section("Styles", styles_container)

        reference_container = self._create_reference_controls()
        add_section("Reference Images", reference_container)

        add_section("Seeds", seed_container)

        add_section("Matrix", matrix_container)

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

        self.keep_aspect_ratio_checkbox = QCheckBox("Seitenverhältnis beibehalten")
        self.keep_aspect_ratio_checkbox.setChecked(True)
        self.keep_aspect_ratio_checkbox.setToolTip(
            "Breite und Höhe proportional gemeinsam ändern."
        )
        self.keep_aspect_ratio_checkbox.toggled.connect(
            self.keep_aspect_ratio_changed
        )
        resolution_layout.addWidget(self.keep_aspect_ratio_checkbox)
        style_section(resolution_container)
        add_section("Resolution", resolution_container)

        # The Properties panel has a fixed minimum width. If the monitor is
        # too narrow, the main-window scroll area (not this panel) provides
        # the required horizontal scrolling for the complete DR layout.
        container.setMinimumWidth(660)

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
        layout.addWidget(self.scroll_area)

        self.random_seed_changed(
            self.random_seed_checkbox.isChecked()
        )

        self._update_matrix_availability()
