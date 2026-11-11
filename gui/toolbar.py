from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QToolBar

from gui.dialog_chrome import install_dialog_chrome

from gui.prompt_blocks_dialog import PromptBlockDialog


class MainToolbar(QToolBar):
    """Main application toolbar."""

    def __init__(self, parent: QMainWindow) -> None:
        super().__init__("Main Toolbar", parent)

        self.setMovable(False)
        install_dialog_chrome()

        self.action_new = QAction("New", self)
        self.action_open = QAction("Load", self)
        self.action_save = QAction("Save", self)
        self.action_prompt_blocks = QAction("Prompt Blocks", self)
        self.action_settings = QAction("Settings", self)

        self.addAction(self.action_new)
        self.addAction(self.action_open)
        self.addAction(self.action_save)

        self.addSeparator()

        self.addAction(self.action_prompt_blocks)
        self.addAction(self.action_settings)

        self.action_prompt_blocks.triggered.connect(
            self._open_prompt_blocks
        )

    def _properties_panel(self):
        parent = self.parentWidget()
        return getattr(parent, "properties_panel", None)

    def _sync_properties_prompt_blocks(self) -> None:
        """Show the active Prompt Block inputs in Properties as a read-only summary.

        Prompt Blocks are the authoritative positive-prompt source while at least
        one block contains text. The legacy Positive Prompts editor remains
        available when Prompt Blocks are empty.
        """
        panel = self._properties_panel()
        if panel is None:
            return

        blocks = getattr(panel.experiment, "prompt_blocks", [])
        active_blocks = [
            block
            for block in blocks
            if any(prompt.text.strip() for prompt in block.prompts)
        ]

        # Empty Prompt Blocks are a structure only, not an authoritative
        # positive-prompt source. Keep the legacy Properties editor usable
        # until at least one non-empty prompt exists.
        if not active_blocks or not any(
            prompt.text.strip()
            for block in active_blocks
            for prompt in getattr(block, "prompts", [])
        ):
            self._restore_legacy_positive_prompts(panel)
            return

        if not hasattr(panel, "_prompt_blocks_legacy_positive_prompts"):
            panel._prompt_blocks_legacy_positive_prompts = [
                (
                    prompt.text,
                    prompt.fixed,
                )
                for prompt in getattr(panel.experiment, "positive_prompts", [])
            ]

        rows = panel.positive_prompt_rows
        edits = panel.positive_prompt_edits
        fixed_controls = panel.positive_prompt_fixed

        prompt_entries: list[tuple[str, bool]] = []
        for block in active_blocks:
            block_name = block.name.strip()
            for prompt in block.prompts:
                text = prompt.text.strip()
                if not text:
                    continue
                prefix = f"[{block.block_id}{prompt.slot_id}]"
                if block_name:
                    prefix = f"[{block.block_id} / {block_name} / {prompt.slot_id}]"
                prompt_entries.append((f"{prefix}  {text}", prompt.fixed))

        while len(edits) < len(prompt_entries):
            panel.add_positive_prompt()
            rows = panel.positive_prompt_rows
            edits = panel.positive_prompt_edits
            fixed_controls = panel.positive_prompt_fixed

        for index, (text, fixed) in enumerate(prompt_entries):
            edit = edits[index]
            fixed_control = fixed_controls[index]
            edit.blockSignals(True)
            fixed_control.blockSignals(True)
            try:
                if edit.toPlainText() != text:
                    edit.setPlainText(text)
                fixed_control.setChecked(fixed)
            finally:
                edit.blockSignals(False)
                fixed_control.blockSignals(False)
            edit.setReadOnly(True)
            fixed_control.setEnabled(False)
            if index < len(rows):
                rows[index].setVisible(True)

        for index in range(len(prompt_entries), len(rows)):
            edit = edits[index]
            fixed_control = fixed_controls[index]
            edit.blockSignals(True)
            fixed_control.blockSignals(True)
            try:
                edit.clear()
                fixed_control.setChecked(False)
            finally:
                edit.blockSignals(False)
                fixed_control.blockSignals(False)
            edit.setReadOnly(True)
            fixed_control.setEnabled(False)
            rows[index].setVisible(False)

        add_button = getattr(panel, "_positive_add_button", None)
        if add_button is not None:
            add_button.setEnabled(False)
            add_button.setToolTip("Positive prompts are managed by Prompt Blocks.")

        info = getattr(panel, "_prompt_blocks_info_label", None)
        if info is None:
            info = QLabel("Prompt Blocks active — edit via the Prompt Blocks toolbar.")
            info.setObjectName("promptBlocksInfo")
            panel._prompt_blocks_info_label = info
            panel.positive_prompt_layout.insertWidget(0, info)
        info.setText(
            f"Prompt Blocks active — {len(active_blocks)} block(s), "
            f"{len(prompt_entries)} prompt(s). Edit via the Prompt Blocks toolbar."
        )
        info.show()

    def _restore_legacy_positive_prompts(self, panel) -> None:
        rows = panel.positive_prompt_rows
        edits = panel.positive_prompt_edits
        fixed_controls = panel.positive_prompt_fixed
        saved = getattr(panel, "_prompt_blocks_legacy_positive_prompts", None)

        if saved is not None:
            while len(edits) < max(1, len(saved)):
                panel.add_positive_prompt()
                rows = panel.positive_prompt_rows
                edits = panel.positive_prompt_edits
                fixed_controls = panel.positive_prompt_fixed

            for index, (text, fixed) in enumerate(saved):
                edit = edits[index]
                fixed_control = fixed_controls[index]
                edit.blockSignals(True)
                fixed_control.blockSignals(True)
                try:
                    edit.setPlainText(text)
                    fixed_control.setChecked(fixed)
                finally:
                    edit.blockSignals(False)
                    fixed_control.blockSignals(False)

        for index, row in enumerate(rows):
            row.setVisible(index < max(1, len(saved or [])))
            edits[index].setReadOnly(False)
            fixed_controls[index].setEnabled(True)

        add_button = getattr(panel, "_positive_add_button", None)
        if add_button is not None:
            add_button.setEnabled(True)
            add_button.setToolTip("")

        info = getattr(panel, "_prompt_blocks_info_label", None)
        if info is not None:
            info.hide()

        if hasattr(panel, "_prompt_blocks_legacy_positive_prompts"):
            delattr(panel, "_prompt_blocks_legacy_positive_prompts")

    def _prompt_blocks_changed(self) -> None:
        """Refresh Properties and Queue in one deterministic update."""
        parent = self.parentWidget()
        refresh = getattr(parent, "_refresh_queue_preview", None)
        if callable(refresh):
            refresh()
        self._sync_properties_prompt_blocks()

    def _open_prompt_blocks(self) -> None:
        parent = self.parentWidget()
        experiment = getattr(parent, "experiment", None)
        if experiment is None:
            return

        # Prompt Blocks become the authoritative positive-prompt source once
        # they contain text. If legacy Properties prompts still contain text
        # and the blocks do not, ask before replacing those legacy values.
        # Do not ask when the current block prompts are already populated:
        # those values belong to Prompt Blocks and must be preserved.
        legacy_prompts = list(getattr(experiment, "positive_prompts", []) or [])
        has_legacy_text = any(
            getattr(prompt, "text", "").strip()
            for prompt in legacy_prompts
        )
        has_block_text = any(
            getattr(prompt, "text", "").strip()
            for block in getattr(experiment, "prompt_blocks", []) or []
            for prompt in getattr(block, "prompts", []) or []
        )

        if has_legacy_text and not has_block_text:
            answer = QMessageBox.question(
                parent,
                "Replace positive prompts?",
                "Positive prompts are currently entered in Properties. "
                "Activating Prompt Blocks will replace those prompts with the "
                "Prompt Block contents. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            # Clear only the legacy positive-prompt text after explicit
            # confirmation. Keep slot metadata and all other experiment data.
            for prompt in legacy_prompts:
                prompt.text = ""

            # Keep the visible Properties editor in sync immediately; otherwise
            # stale widget contents could be written back to the model later.
            panel = self._properties_panel()
            if panel is not None:
                for edit in getattr(panel, "positive_prompt_edits", []):
                    edit.blockSignals(True)
                    try:
                        edit.clear()
                    finally:
                        edit.blockSignals(False)
                for fixed_control in getattr(panel, "positive_prompt_fixed", []):
                    fixed_control.blockSignals(True)
                    try:
                        fixed_control.setChecked(False)
                    finally:
                        fixed_control.blockSignals(False)

        dialog = PromptBlockDialog(experiment, parent)
        dialog.changed.connect(self._prompt_blocks_changed)
        dialog.exec()
