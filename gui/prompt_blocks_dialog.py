from __future__ import annotations

from itertools import product
from typing import Callable

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.experiment import MatrixOperator, MatrixSelection, PromptSlot
from models.prompt_block import PromptBlock
from gui.windows_chrome import apply_desperate_render_titlebar


class PromptBlockDialog(QDialog):
    """Editor for the experiment's composable positive prompt blocks."""

    changed = Signal()

    def __init__(self, experiment, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.experiment = experiment
        self.setWindowTitle("Prompt Blocks")
        self.setMinimumSize(980, 700)
        self.resize(1120, 760)
        apply_desperate_render_titlebar(self)

        self._current_block_index = -1
        self._loading = False
        # Keep live queue feedback, but coalesce rapid keystrokes into one
        # rebuild after the user pauses typing briefly.
        self._change_timer = QTimer(self)
        self._change_timer.setSingleShot(True)
        self._change_timer.setInterval(250)
        self._change_timer.timeout.connect(self.changed.emit)
        self._row_edits: list[QTextEdit] = []
        self._row_fixed: list[QCheckBox] = []
        self._row_widgets: list[QWidget] = []

        self._build_ui()
        self._ensure_initial_block()
        self._refresh_block_list()
        if self.experiment.prompt_blocks:
            self._select_block(0)
        else:
            self._clear_editor()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        splitter_row = QHBoxLayout()
        root.addLayout(splitter_row, 1)

        left = QVBoxLayout()
        splitter_row.addLayout(left, 0)

        left.addWidget(QLabel("Blocks"))

        self.block_list = QListWidget()
        self.block_list.setMinimumWidth(210)
        self.block_list.currentRowChanged.connect(self._block_selected)
        left.addWidget(self.block_list, 1)

        block_buttons = QHBoxLayout()
        self.add_block_button = QPushButton("+ Block")
        self.remove_block_button = QPushButton("Remove")
        self.add_block_button.clicked.connect(self._add_block)
        self.remove_block_button.clicked.connect(self._remove_block)
        block_buttons.addWidget(self.add_block_button)
        block_buttons.addWidget(self.remove_block_button)
        left.addLayout(block_buttons)

        right = QVBoxLayout()
        splitter_row.addLayout(right, 1)

        form = QFormLayout()
        self.block_id = QLineEdit()
        self.block_id.setReadOnly(True)
        self.block_name = QLineEdit()
        self.block_name.setPlaceholderText("Optional block name")
        self.block_name.textChanged.connect(self._block_metadata_changed)

        self.mode = QComboBox()
        self.mode.addItem("Individual", MatrixOperator.INDIVIDUAL)
        self.mode.addItem("All", MatrixOperator.ALL)
        self.mode.addItem("Combination", MatrixOperator.COMBINATION)
        self.mode.addItem("Permutation", MatrixOperator.PERMUTATION)
        self.mode.currentIndexChanged.connect(self._matrix_changed)

        self.count_min = QSpinBox()
        self.count_min.setRange(1, 100)
        self.count_min.valueChanged.connect(self._matrix_changed)

        self.count_max = QSpinBox()
        self.count_max.setRange(1, 100)
        self.count_max.valueChanged.connect(self._matrix_changed)

        count_row = QWidget()
        count_layout = QHBoxLayout(count_row)
        count_layout.setContentsMargins(0, 0, 0, 0)
        count_layout.addWidget(QLabel("Min"))
        count_layout.addWidget(self.count_min)
        count_layout.addWidget(QLabel("Max"))
        count_layout.addWidget(self.count_max)
        count_layout.addStretch()

        form.addRow("Block ID", self.block_id)
        form.addRow("Name", self.block_name)
        form.addRow("Matrix", self.mode)
        form.addRow("Combination size", count_row)
        right.addLayout(form)

        right.addWidget(QLabel("Prompts in block"))

        self.prompt_scroll = QScrollArea()
        self.prompt_scroll.setWidgetResizable(True)
        self.prompt_container = QWidget()
        self.prompt_layout = QVBoxLayout(self.prompt_container)
        self.prompt_layout.setContentsMargins(4, 4, 4, 4)
        self.prompt_layout.setSpacing(6)
        self.prompt_scroll.setWidget(self.prompt_container)
        right.addWidget(self.prompt_scroll, 1)

        self.add_prompt_button = QPushButton("+ Prompt")
        self.add_prompt_button.clicked.connect(self._add_prompt)
        right.addWidget(self.add_prompt_button, 0)

        self.variant_label = QLabel()
        self.variant_label.setWordWrap(True)
        right.addWidget(self.variant_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _ensure_initial_block(self) -> None:
        """Initialize Prompt Blocks, migrating legacy positive prompts if needed.

        Older experiments store their positive prompt dimension in
        ``positive_prompts``. When the user opens Prompt Blocks for such an
        experiment, carry those actual prompt values into block A instead of
        creating an empty placeholder that can later overwrite the queue.
        Existing Prompt Blocks remain authoritative and are never replaced.
        """
        if self.experiment.prompt_blocks:
            return

        legacy_prompts = list(getattr(self.experiment, "positive_prompts", []) or [])
        prompts = [
            PromptSlot(
                slot_id=(slot.slot_id if slot.slot_id > 0 else index),
                text=slot.text,
                fixed=slot.fixed,
            )
            for index, slot in enumerate(legacy_prompts, start=1)
            if slot.text.strip()
        ]
        if not prompts:
            prompts = [PromptSlot(slot_id=1, text="", fixed=False)]

        self.experiment.prompt_blocks.append(
            PromptBlock(
                block_id="A",
                name="",
                prompts=prompts,
                matrix_selection=MatrixSelection(),
            )
        )

    def _next_block_id(self) -> str:
        used = {block.block_id.upper() for block in self.experiment.prompt_blocks}
        for code in range(ord("A"), ord("Z") + 1):
            candidate = chr(code)
            if candidate not in used:
                return candidate
        raise ValueError("Prompt Blocks currently support A-Z.")

    def _add_block(self) -> None:
        block_id = self._next_block_id()
        self._commit_current_block()
        self.experiment.prompt_blocks.append(
            PromptBlock(
                block_id=block_id,
                name="",
                prompts=[PromptSlot(slot_id=1, text="", fixed=False)],
                matrix_selection=MatrixSelection(),
            )
        )
        self._refresh_block_list()
        self._select_block(len(self.experiment.prompt_blocks) - 1)
        self._emit_changed()

    def _remove_block(self) -> None:
        index = self.block_list.currentRow()
        if not (0 <= index < len(self.experiment.prompt_blocks)):
            return
        if len(self.experiment.prompt_blocks) == 1:
            block = self.experiment.prompt_blocks[0]
            block.prompts = [PromptSlot(slot_id=1, text="", fixed=False)]
            block.name = ""
            block.matrix_selection = MatrixSelection()
        else:
            self.experiment.prompt_blocks.pop(index)
            self._renumber_block_ids()
        self._refresh_block_list()
        self._select_block(max(0, index - 1))
        self._emit_changed()

    def _renumber_block_ids(self) -> None:
        """Keep Prompt Block IDs contiguous after insertions/removals.

        Block IDs are user-facing provenance identifiers, so a deletion must
        never leave gaps such as A/C. Remaining blocks are compacted to A/B/C…
        in their current visual order.
        """
        for index, block in enumerate(self.experiment.prompt_blocks):
            block.block_id = chr(ord("A") + index)

    def _refresh_block_list(self) -> None:
        self.block_list.blockSignals(True)
        self.block_list.clear()
        for block in self.experiment.prompt_blocks:
            label = block.block_id
            if block.name.strip():
                label += f" — {block.name.strip()}"
            self.block_list.addItem(label)
        self.block_list.blockSignals(False)

    def _select_block(self, index: int) -> None:
        if 0 <= index < self.block_list.count():
            self.block_list.setCurrentRow(index)

    def _block_selected(self, index: int) -> None:
        if self._current_block_index >= 0:
            self._commit_current_block()
        self._current_block_index = index
        if 0 <= index < len(self.experiment.prompt_blocks):
            self._load_block(self.experiment.prompt_blocks[index])
        else:
            self._clear_editor()

    def _clear_prompt_rows(self) -> None:
        while self.prompt_layout.count():
            item = self.prompt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._row_edits.clear()
        self._row_fixed.clear()
        self._row_widgets.clear()

    def _clear_editor(self) -> None:
        self._loading = True
        try:
            self.block_id.clear()
            self.block_name.clear()
            self._clear_prompt_rows()
            self.variant_label.setText("")
        finally:
            self._loading = False

    def _load_block(self, block: PromptBlock) -> None:
        self._loading = True
        try:
            self.block_id.setText(block.block_id)
            self.block_name.setText(block.name)

            self.mode.setCurrentIndex(
                {
                    MatrixOperator.INDIVIDUAL: 0,
                    MatrixOperator.ALL: 1,
                    MatrixOperator.COMBINATION: 2,
                    MatrixOperator.PERMUTATION: 3,
                }[block.matrix_selection.operator]
            )

            minimum = block.matrix_selection.minimum or 1
            maximum = block.matrix_selection.maximum or minimum
            self.count_min.setValue(minimum)
            self.count_max.setValue(maximum)

            self._clear_prompt_rows()
            for prompt in block.prompts:
                self._add_prompt_row(prompt.text, prompt.fixed)

            if not block.prompts:
                self._add_prompt_row("", False)
        finally:
            self._loading = False

        self._update_matrix_controls()
        self._update_variant_label()

    def _add_prompt_row(self, text: str = "", fixed: bool = False) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        number = QLabel(str(len(self._row_edits) + 1))
        number.setMinimumWidth(24)
        number.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fixed_box = QCheckBox("Fixed")
        fixed_box.setChecked(fixed)
        fixed_box.setToolTip(
            "Keep this prompt at its exact position. "
            "Fixed prompts are included in every block variant."
        )

        edit = QTextEdit()
        edit.setMinimumHeight(62)
        edit.setPlainText(text)
        edit.setToolTip(text)
        edit.textChanged.connect(self._prompt_changed)
        fixed_box.toggled.connect(self._prompt_changed)

        remove = QPushButton("✕")
        remove.setFixedWidth(32)
        remove.setToolTip("Remove prompt")
        remove.clicked.connect(lambda: self._remove_prompt(row))

        layout.addWidget(number)
        layout.addWidget(fixed_box)
        layout.addWidget(edit, 1)
        layout.addWidget(remove)

        self._row_edits.append(edit)
        self._row_fixed.append(fixed_box)
        self._row_widgets.append(row)
        self.prompt_layout.addWidget(row)

    def _add_prompt(self) -> None:
        self._commit_current_block()
        self._add_prompt_row()
        self._commit_current_block()
        self._update_variant_label()
        self._emit_changed()

    def _remove_prompt(self, row: QWidget) -> None:
        if len(self._row_widgets) <= 1:
            self._row_edits[0].clear()
            self._row_fixed[0].setChecked(False)
            return

        index = self._row_widgets.index(row)
        self._row_widgets.pop(index)
        edit = self._row_edits.pop(index)
        fixed = self._row_fixed.pop(index)

        edit.deleteLater()
        fixed.deleteLater()
        row.deleteLater()

        self._renumber_rows()
        self._commit_current_block()
        self._update_variant_label()
        self._emit_changed()

    def _renumber_rows(self) -> None:
        for index, row in enumerate(self._row_widgets, start=1):
            labels = row.findChildren(QLabel)
            if labels:
                labels[0].setText(str(index))

    def _prompt_changed(self) -> None:
        if self._loading:
            return
        self._commit_current_block()
        self._update_variant_label()
        self._emit_changed()

    def _block_metadata_changed(self) -> None:
        if self._loading:
            return
        self._commit_current_block()
        self._refresh_block_list()
        self._select_block(self._current_block_index)
        self._emit_changed()

    def _matrix_changed(self) -> None:
        if self._loading:
            return
        self._commit_current_block()
        self._update_matrix_controls()
        self._update_variant_label()
        self._emit_changed()

    def _commit_current_block(self) -> None:
        index = self._current_block_index
        if not (0 <= index < len(self.experiment.prompt_blocks)):
            return

        block = self.experiment.prompt_blocks[index]
        block.name = self.block_name.text().strip()

        prompts: list[PromptSlot] = []
        for slot_id, (edit, fixed) in enumerate(
            zip(self._row_edits, self._row_fixed),
            start=1,
        ):
            prompts.append(
                PromptSlot(
                    slot_id=slot_id,
                    text=edit.toPlainText().strip(),
                    fixed=fixed.isChecked(),
                )
            )
        block.prompts = prompts

        operator = self.mode.currentData()
        block.matrix_selection.operator = MatrixOperator(operator)

        if operator in (
            MatrixOperator.COMBINATION,
            MatrixOperator.PERMUTATION,
        ):
            minimum = self.count_min.value()
            maximum = max(minimum, self.count_max.value())
            variable_count = max(1, len(block.variable_prompts))
            maximum = min(maximum, variable_count)
            minimum = min(minimum, maximum)
            block.matrix_selection.minimum = minimum
            block.matrix_selection.maximum = maximum
            self.count_min.setMaximum(variable_count)
            self.count_max.setMaximum(variable_count)
        else:
            block.matrix_selection.minimum = None
            block.matrix_selection.maximum = None

    def _update_matrix_controls(self) -> None:
        variable_count = 0
        if 0 <= self._current_block_index < len(self.experiment.prompt_blocks):
            variable_count = len(
                self.experiment.prompt_blocks[self._current_block_index].variable_prompts
            )
        variable_count = max(1, variable_count)

        ranged = self.mode.currentData() in (
            MatrixOperator.COMBINATION,
            MatrixOperator.PERMUTATION,
        )
        self.count_min.setEnabled(ranged)
        self.count_max.setEnabled(ranged)
        self.count_min.setMaximum(variable_count)
        self.count_max.setMaximum(variable_count)

        if self.count_min.value() > variable_count:
            self.count_min.setValue(variable_count)
        if self.count_max.value() > variable_count:
            self.count_max.setValue(variable_count)
        if self.count_max.value() < self.count_min.value():
            self.count_max.setValue(self.count_min.value())

    def _variant_count(self, block: PromptBlock) -> int:
        variables = block.variable_prompts
        n = len(variables)
        if n == 0:
            return 1 if any(p.text.strip() for p in block.prompts) else 0

        op = block.matrix_selection.operator
        if op == MatrixOperator.ALL:
            return 1
        if op == MatrixOperator.INDIVIDUAL:
            return n
        minimum = block.matrix_selection.minimum or 1
        maximum = block.matrix_selection.maximum or minimum

        if op == MatrixOperator.COMBINATION:
            from math import comb
            return sum(comb(n, r) for r in range(minimum, maximum + 1))
        if op == MatrixOperator.PERMUTATION:
            from math import factorial
            return sum(
                factorial(n) // factorial(n - r)
                for r in range(minimum, maximum + 1)
            )
        return 0

    def _update_variant_label(self) -> None:
        if not (0 <= self._current_block_index < len(self.experiment.prompt_blocks)):
            self.variant_label.clear()
            return

        self._commit_current_block()
        block = self.experiment.prompt_blocks[self._current_block_index]
        count = self._variant_count(block)

        non_empty = [
            b for b in self.experiment.prompt_blocks
            if any(p.text.strip() for p in b.prompts)
        ]
        total = 1
        for other in non_empty:
            total *= max(0, self._variant_count(other))

        self.variant_label.setText(
            f"Block {block.block_id}: {count} variant(s)  •  "
            f"Prompt Block matrix: {total} total variant combination(s)"
        )

    def _emit_changed(self) -> None:
        self.experiment.touch()
        # Restart the debounce timer so rapid text changes cause one queue
        # refresh after 250 ms of inactivity, rather than rebuilding on every
        # keystroke. The model is still updated immediately by the caller.
        self._change_timer.start()

    def closeEvent(self, event) -> None:
        # Ensure the final edit is committed and any pending live update is
        # delivered before the dialog disappears.
        self._commit_current_block()
        if self._change_timer.isActive():
            self._change_timer.stop()
            self.changed.emit()
        super().closeEvent(event)
