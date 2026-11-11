from __future__ import annotations

import copy
import hashlib
import json
from PySide6.QtWidgets import QSizePolicy

from models.experiment import MatrixOperator, MatrixSelection, PromptSlot, SeedMode
from models.prompt_block import PromptBlock
from models.generation_job import GenerationJob
from services.generation_queue import GenerationQueue

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QMessageBox,
    QScrollArea,
    QFrame,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from controllers.connection_controller import ConnectionController
from controllers.generation_worker import GenerationWorker
from gui.panels.preview_panel import PreviewPanel
from gui.panels.properties_panel import PropertiesPanel
from gui.panels.queue_panel import QueuePanel
from gui.fooocus_settings_dialog import FooocusSettingsDialog
from models.application_settings import ApplicationSettings
from gui.toolbar import MainToolbar
from services.generation_service import GenerationService
from services.branding_asset import BRANDING_FILENAME, ensure_branding_asset
from services.experiment.experiment_store import ExperimentStore, _to_jsonable
from services.experiment.configuration_fingerprint import normalize_legacy_prompt_block_mirror
from services.experiment.result_store import ResultStore
from services.experiment.matrix_builder import MatrixBuilder
from services.generation.configuration_adapter import (
    GenerationConfigurationAdapter,
)
from pathlib import Path
from datetime import date
from uuid import uuid4


class MainWindow(QMainWindow):
    """Main application window."""

    CONNECT_TIMEOUT_SECONDS = 30
    CONNECT_POLL_INTERVAL_MS = 250

    def __init__(self) -> None:
        super().__init__()

        self.application_settings = ApplicationSettings()
        self.experiment_store = ExperimentStore(self.application_settings.experiment_directory)
        self.result_store = ResultStore(self.application_settings.experiment_directory)
        self._result_manifest: dict = {"schema_version": 1, "runs": []}
        self._active_run_id: str | None = None
        self._experiment_path: Path | None = None
        self._active_job_statuses: dict[str, str] = {}
        self._active_run_fingerprint: str | None = None
        self._active_run_random_seeds: list[int] = []
        self._active_job_seeds: dict[str, int | None] = {}
        self._active_run_planned_jobs = 0
        self._active_run_state: str | None = None
        self._has_executed_run = False
        self._saved_properties_fingerprint: str | None = None
        self.experiment = self.experiment_store.create()
        self.connection_controller = ConnectionController(self.application_settings)

        self.generation_service = GenerationService(
            self.connection_controller.client
        )

        self.generation_thread: QThread | None = None
        self.generation_worker: GenerationWorker | None = None
        self._fooocus_connect_timer: QTimer | None = None
        self._fooocus_connect_started_at: float | None = None
        self._queue_preview_refreshing = False

        self.setWindowTitle("Desperate Render™")
        icon_path = Path(__file__).resolve().parents[1] / "icon.ico"
        if icon_path.is_file():
            app_icon = QIcon(str(icon_path))
            QApplication.instance().setWindowIcon(app_icon)
            self.setWindowIcon(app_icon)
        self.resize(1800, 1000)

        self.create_toolbar()
        self.create_view_menu()
        self.create_statusbar()
        self.create_layout()
        # Resolve persisted Gradio temp paths against Fooocus' durable outputs.
        self.preview_panel.set_fooocus_path(self.application_settings.fooocus_path)
        self._connect_live_preview_signals()
        self._refresh_queue_preview()
        self._saved_properties_fingerprint = self._properties_fingerprint()

    def create_toolbar(self) -> None:
        self.toolbar = MainToolbar(self)
        self.toolbar.action_new.triggered.connect(self.new_experiment)
        self.toolbar.action_open.triggered.connect(self.open_experiment)
        self.toolbar.action_save.triggered.connect(self.save_experiment)
        self.toolbar.action_settings.triggered.connect(self.open_settings)
        self.addToolBar(self.toolbar)

    def create_view_menu(self) -> None:
        """Create panel visibility actions directly in the main toolbar."""
        self.preview_toggle_action = QAction("Preview", self)
        self.preview_toggle_action.setCheckable(True)
        self.preview_toggle_action.setChecked(True)
        self.preview_toggle_action.setShortcut("V")
        self.preview_toggle_action.setStatusTip("Show or hide the Preview panel")
        self.preview_toggle_action.triggered.connect(self._toggle_preview)

        self.properties_toggle_action = QAction("Properties", self)
        self.properties_toggle_action.setCheckable(True)
        self.properties_toggle_action.setChecked(True)
        self.properties_toggle_action.setShortcut("P")
        self.properties_toggle_action.setStatusTip("Show or hide the Properties panel")
        self.properties_toggle_action.triggered.connect(self._toggle_properties)

        self.queue_toggle_action = QAction("Queue", self)
        self.queue_toggle_action.setCheckable(True)
        self.queue_toggle_action.setChecked(True)
        self.queue_toggle_action.setShortcut("Q")
        self.queue_toggle_action.setStatusTip("Show or hide the Queue panel")
        self.queue_toggle_action.triggered.connect(self._toggle_queue)

        # Keep the three panel toggles directly beside Settings in the main
        # toolbar.  They are deliberately top-level toolbar actions rather
        # than a separate View menu so the most frequently used layout
        # controls remain immediately accessible.
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.preview_toggle_action)
        self.toolbar.addAction(self.properties_toggle_action)
        self.toolbar.addAction(self.queue_toggle_action)

    def _confirm_state_transition(self, title: str, message: str) -> bool:
        """Offer to save the current experiment and result history before replacing it."""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        save_button = dialog.addButton(
            "Save and continue", QMessageBox.ButtonRole.AcceptRole
        )
        continue_button = dialog.addButton(
            "Continue without saving", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = dialog.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDefaultButton(save_button)
        dialog.exec()
        choice = dialog.clickedButton()
        if choice is cancel_button or choice not in (save_button, continue_button):
            return False
        if choice is save_button:
            return self.save_experiment()
        return True

    def new_experiment(self) -> None:
        """Create a fresh experiment after confirming replacement when needed."""
        if self.generation_thread is not None:
            QMessageBox.information(
                self,
                "Generation running",
                "Create a new experiment after the current generation has finished.",
            )
            return

        if self._experiment_has_content() or self.preview_panel.thumbnails.count():
            if not self._confirm_state_transition(
                "Create new experiment?",
                "Creating a new experiment replaces the current configuration and clears its result overview.\n\n"
                "Save the current experiment and result history before continuing?",
            ):
                return

        experiment = self.experiment_store.create()
        self._replace_experiment(experiment)
        self._active_run_id = None
        self._experiment_path = None
        self._active_job_statuses = {}
        self._active_run_fingerprint = None
        self._active_run_random_seeds = []
        self._active_job_seeds = {}
        self._active_run_planned_jobs = 0
        self._active_run_state = None
        self._result_manifest = {"schema_version": 1, "experiment_id": experiment.experiment_id, "runs": []}
        self.preview_panel.clear_history()
        self.preview_panel.active_run_id = None
        self._has_executed_run = False
        self._saved_properties_fingerprint = self._properties_fingerprint()
        self.status.showMessage(f"New experiment created: {experiment.experiment_id}")

    def save_experiment(self) -> bool:
        """Persist the experiment definition and current result-history snapshot."""
        if self.generation_thread is not None:
            QMessageBox.information(
                self,
                "Generation running",
                "Save the experiment after the current generation has finished.",
            )
            return False

        self.experiment.name = self.properties_panel.experiment_name.text().strip()
        self._sync_matrix_settings_from_properties()
        current_fingerprint = self._configuration_fingerprint(None)
        properties_changed = (
            self._saved_properties_fingerprint is None
            or current_fingerprint != self._saved_properties_fingerprint
        )
        if self._experiment_path is not None and not properties_changed:
            # An unchanged definition is already immutable on disk. Saving it
            # again would create an unnecessary revision; result metadata has
            # its own immediate persistence path.
            self._persist_result_metadata()
            self.status.showMessage(f"Experiment definition unchanged: {self._experiment_path}")
            return True
        try:
            path = self.experiment_store.save(self.experiment)
            self._experiment_path = path
            result_path = self.result_store.paired_path(path)
            snapshot = self.preview_panel.result_run_snapshot()
            has_images = any(run.get("images") for run in snapshot)
            # A changed definition must not inherit results from the previous
            # definition. Existing result files remain paired with their original
            # _exp.json; the new revision starts without a result manifest.
            if has_images and not properties_changed:
                self.result_store.merge_snapshot(
                    self.experiment.experiment_id,
                    snapshot,
                    existing_manifest=self._result_manifest,
                    target_path=result_path,
                )
                self._result_manifest = self.result_store.load_for_experiment_path(
                    path, self.experiment.experiment_id
                )
            else:
                self._result_manifest = {
                    "schema_version": 1,
                    "experiment_id": self.experiment.experiment_id,
                    "runs": [],
                }
                if properties_changed:
                    self.preview_panel.clear_history()
                    self.preview_panel.active_run_id = None
                    self._active_run_id = None
            self._saved_properties_fingerprint = self._properties_fingerprint()
        except Exception as exc:
            QMessageBox.critical(self, "Save experiment failed", str(exc))
            return False
        self.status.showMessage(f"Experiment definition saved: {path}")
        return True

    def _experiment_has_content(self) -> bool:
        """Return whether the current editor contains user-entered data."""
        experiment = self.experiment

        if experiment.name.strip():
            return True

        if any(slot.text.strip() for slot in experiment.positive_prompts):
            return True
        if any(slot.text.strip() for slot in experiment.negative_prompts):
            return True

        for block in experiment.prompt_blocks:
            if block.name.strip():
                return True
            if any(prompt.text.strip() for prompt in block.prompts):
                return True

        if experiment.styles or experiment.random_style:
            return True
        if experiment.style_references or experiment.composition_references:
            return True

        generation = experiment.generation
        if generation.seed is not None or generation.seeds:
            return True
        if generation.base_model or generation.base_models:
            return True
        if generation.refiner_model is not None:
            return True
        if generation.performance is not None:
            return True
        if generation.guidance_scale is not None or generation.sharpness is not None:
            return True
        if generation.width != 1024 or generation.height != 768:
            return True
        if generation.aspect_ratio != "4:3" or generation.output_format != "png":
            return True
        if generation.random_seed_count != 1:
            return True

        # A changed matrix definition is also meaningful experiment content.
        for selection in vars(experiment.matrix).values():
            if (
                selection.operator != MatrixOperator.INDIVIDUAL
                or selection.minimum is not None
                or selection.maximum is not None
            ):
                return True

        return False

    def open_experiment(self) -> None:
        """Load an experiment definition from a selected JSON revision."""
        if self.generation_thread is not None:
            QMessageBox.information(
                self,
                "Generation running",
                "Open another experiment after the current generation has finished.",
            )
            return

        # A freshly launched editor may contain default generation values
        # (for example, the selected base model) without any user edits.
        # Only warn when Properties actually differ from the last saved/editor
        # baseline, or when the current session already has result thumbnails.
        current_fingerprint = self._properties_fingerprint()
        properties_changed = (
            self._saved_properties_fingerprint is None
            or current_fingerprint != self._saved_properties_fingerprint
        )
        if properties_changed or self.preview_panel.thumbnails.count():
            if not self._confirm_state_transition(
                "Load another experiment?",
                "Loading another experiment replaces the current configuration and result overview.\n\n"
                "Save the current experiment and result history before continuing?",
            ):
                return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Desperate Render Experiment",
            str(self.experiment_store.root),
            "DR experiment files (*_exp.json)",
        )
        if not filename:
            return

        selected = Path(filename)
        # Result manifests are JSON too, but they are not experiment
        # definitions. They may appear in the generic *.json file picker;
        # reject them explicitly rather than trying to parse them as an
        # experiment and showing a misleading load failure.
        if selected.name.lower().endswith((".results.json", "_rslt.json")):
            QMessageBox.information(
                self,
                "Select an experiment",
                "This is a result-history file, not an experiment definition.\n\n"
                "Please select the experiment JSON file instead.",
            )
            return

        try:
            # Load the exact file selected by the user. This supports
            # timestamped revisions as well as legacy experiment.json files.
            experiment = self.experiment_store.load(selected)
        except Exception as exc:
            QMessageBox.critical(self, "Load experiment failed", str(exc))
            return

        self._replace_experiment(experiment)
        self._experiment_path = selected
        try:
            manifest = self.result_store.load_for_experiment_path(
                selected, experiment.experiment_id
            )
            self._result_manifest = manifest
            self.preview_panel.restore_result_runs(manifest.get("runs", []))
            self._has_executed_run = False
            self._saved_properties_fingerprint = self._properties_fingerprint()
            self.status.showMessage(
                f"Experiment loaded: {experiment.experiment_id} — "
                f"{sum(len(run.get('images', [])) for run in manifest.get('runs', []))} result(s)"
            )
        except Exception as exc:
            self.preview_panel.clear_history()
            QMessageBox.warning(
                self,
                "Result history unavailable",
                "The experiment was loaded, but its result history could not be restored.\n\n"
                f"{exc}",
            )
            self.status.showMessage(f"Experiment loaded: {experiment.experiment_id}")

    def _replace_experiment(self, experiment) -> None:
        """Replace the live experiment and rebuild the Properties editor.

        Preserve the user's current splitter proportions when the Properties
        widget is rebuilt. Inserting a fresh panel can otherwise make Qt
        recalculate the splitter sizes and visibly change the three-panel
        layout after New or Load.
        """
        old_panel = self.properties_panel
        splitter_sizes = self.splitter.sizes()
        style_choices = list(getattr(old_panel, "style_names", []))
        base_model_choices = list(getattr(old_panel, "base_model_names", []))

        # Migrate legacy positive prompts as soon as an experiment becomes
        # active, before the first queue preview is built. This ensures the
        # queue uses Prompt Block IDs (A1, A2, ...) from the first display,
        # rather than switching from legacy PP1/PP2 labels only after the
        # Prompt Blocks dialog is opened.
        self._migrate_legacy_positive_prompts(experiment)
        self.experiment = experiment
        new_panel = PropertiesPanel(experiment)
        new_panel.setMinimumHeight(300)
        new_panel.setMinimumWidth(680)
        if style_choices:
            new_panel.set_style_choices(style_choices)
        elif experiment.available_styles:
            new_panel.set_style_choices(experiment.available_styles)
        if base_model_choices:
            new_panel.set_base_model_choices(base_model_choices)

        self.properties_panel = new_panel
        self.splitter.insertWidget(1, new_panel)
        old_panel.setParent(None)
        old_panel.deleteLater()
        self._connect_live_preview_signals()
        self._refresh_queue_preview()
        self.toolbar._sync_properties_prompt_blocks()

        # Reapply after the replacement has participated in a layout pass.
        # Keep the current proportions rather than resetting to startup sizes.
        QTimer.singleShot(
            0,
            lambda sizes=splitter_sizes: self.splitter.setSizes(sizes),
        )

    @staticmethod
    def _migrate_legacy_positive_prompts(experiment) -> None:
        """Convert legacy positive prompts to Block A before UI/queue setup.

        Existing non-empty Prompt Blocks are authoritative and are never
        replaced. The migration is in-memory only; saving remains an explicit
        user action. Legacy prompt text and Fixed flags are preserved.
        """
        active_blocks = [
            block
            for block in getattr(experiment, "prompt_blocks", [])
            if any(prompt.text.strip() for prompt in block.prompts)
        ]
        if active_blocks or not getattr(experiment, "positive_prompts", []):
            return

        legacy_prompts = [
            PromptSlot(
                slot_id=prompt.slot_id,
                text=prompt.text,
                fixed=prompt.fixed,
            )
            for prompt in experiment.positive_prompts
        ]
        legacy_selection = experiment.matrix.positive_prompts
        experiment.prompt_blocks = [
            PromptBlock(
                block_id="A",
                name="",
                prompts=legacy_prompts,
                matrix_selection=MatrixSelection(
                    operator=legacy_selection.operator,
                    minimum=legacy_selection.minimum,
                    maximum=legacy_selection.maximum,
                ),
            )
        ]

    def open_settings(self) -> None:
        """Open Fooocus settings and apply changes to future connections."""
        dialog = FooocusSettingsDialog(self.application_settings, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.connection_controller.reload_settings()
            self.preview_panel.set_fooocus_path(self.application_settings.fooocus_path)
            self.experiment_store = ExperimentStore(
                self.application_settings.experiment_directory
            )
            self.result_store = ResultStore(
                self.application_settings.experiment_directory
            )
            self.status.showMessage(
                "Settings saved — experiment folder: "
                f"{self.experiment_store.root}"
            )

    def create_statusbar(self) -> None:
        self.status = QStatusBar()
        self.status.showMessage("Ready")

        self.fooocus_status_label = QLabel(
            "⚪ Fooocus: not connected"
        )
        self.fooocus_status_label.setMinimumWidth(230)
        self.status.addPermanentWidget(self.fooocus_status_label)
        self.setStatusBar(self.status)

    def create_layout(self) -> None:
        # DESPERATE RENDER needs a stable minimum content width so that the
        # three main panels never become unusably narrow.  On a monitor that
        # is narrower than this width, the *whole application content* is
        # horizontally scrollable instead of individual panels.
        # Minimum widths for the three main areas. The complete DR content
        # uses these widths; only a monitor narrower than their combined
        # width gets a horizontal scrollbar at main-window level.
        panel_min_widths = (668, 700, 360)
        self._collapsed_panel_width = 32
        self._preview_min_width = panel_min_widths[0] - self._collapsed_panel_width
        self._properties_min_width = panel_min_widths[1]
        self._queue_min_width = panel_min_widths[2]
        self._splitter_handle_margin = 32
        self._minimum_content_width = sum(panel_min_widths) + self._splitter_handle_margin
        self._compact_content_width = (
            self._properties_min_width
            + self._queue_min_width
            + self._splitter_handle_margin
        )

        self.splitter = QSplitter()

        self.preview_panel = PreviewPanel()
        self.properties_panel = PropertiesPanel(self.experiment)
        self.queue_panel = QueuePanel()

        self.queue_container = QWidget()
        queue_layout = QHBoxLayout(self.queue_container)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.setSpacing(0)

        self.queue_toggle_area = QWidget()
        self.queue_toggle_area.setMinimumWidth(32)
        self.queue_toggle_area.setMaximumWidth(32)

        queue_toggle_layout = QHBoxLayout(self.queue_toggle_area)
        queue_toggle_layout.setContentsMargins(1, 0, 7, 0)
        queue_toggle_layout.setSpacing(0)

        self.queue_toggle_button = QToolButton()
        self.queue_toggle_button.setObjectName("panelToggleButton")
        self.queue_toggle_button.setCheckable(True)
        self.queue_toggle_button.setChecked(True)
        self.queue_toggle_button.setText("▶")
        self.queue_toggle_button.setToolTip("Collapse Queue")
        self.queue_toggle_button.setMinimumWidth(24)
        self.queue_toggle_button.setMaximumWidth(24)
        self.queue_toggle_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding
        )
        self.queue_toggle_button.clicked.connect(self._toggle_queue)

        queue_toggle_layout.addWidget(self.queue_toggle_button)
        queue_layout.addWidget(self.queue_toggle_area)
        queue_layout.addWidget(self.queue_panel)

        # The Preview is a side panel like Lightroom's auxiliary panels: it
        # can collapse to a narrow tab without removing the Preview feature.
        self.preview_container = QWidget()
        preview_layout = QHBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self.preview_panel)

        self.preview_toggle_area = QWidget()
        self.preview_toggle_area.setMinimumWidth(32)
        self.preview_toggle_area.setMaximumWidth(32)

        preview_toggle_layout = QHBoxLayout(self.preview_toggle_area)
        preview_toggle_layout.setContentsMargins(7, 0, 1, 0)
        preview_toggle_layout.setSpacing(0)

        self.preview_toggle_button = QToolButton()
        self.preview_toggle_button.setObjectName("panelToggleButton")
        self.preview_toggle_button.setCheckable(True)
        self.preview_toggle_button.setChecked(True)
        self.preview_toggle_button.setText("◀")
        self.preview_toggle_button.setToolTip("Collapse Preview")
        self.preview_toggle_button.setMinimumWidth(24)
        self.preview_toggle_button.setMaximumWidth(24)
        self.preview_toggle_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding
        )
        self.preview_toggle_button.clicked.connect(self._toggle_preview)
        preview_toggle_layout.addWidget(self.preview_toggle_button)
        preview_layout.addWidget(self.preview_toggle_area)

        self.queue_panel.connect_button.clicked.connect(
            self.connect_to_fooocus
        )
        self.queue_panel.run_button.clicked.connect(
            self.run_cancel_generation
        )
        self.queue_panel.pause_button.clicked.connect(
            self.pause_resume_generation
        )

        self.splitter.addWidget(self.preview_container)
        self.splitter.addWidget(self.properties_panel)
        self.splitter.addWidget(self.queue_container)

        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([668, 700, 360])

        for panel, minimum_width in zip(
            (
                self.preview_container,
                self.properties_panel,
                self.queue_container,
            ),
            panel_min_widths,
        ):
            panel.setMinimumWidth(minimum_width)

        self.preview_panel.setMinimumSize(self._preview_min_width, 300)
        self.preview_container.setMinimumWidth(panel_min_widths[0])
        self.properties_panel.setMinimumHeight(300)
        self.queue_panel.setMinimumHeight(300)
        self.queue_container.setMinimumWidth(self._queue_min_width)

        self.splitter.setMinimumWidth(self._minimum_content_width)
        self.splitter.setChildrenCollapsible(False)

        # Keep the window itself usable on low-resolution monitors.  If the
        # available screen width is smaller than DR's minimum content width,
        # the central scroll area provides the missing horizontal space.
        screen = QApplication.primaryScreen()
        available_width = (
            screen.availableGeometry().width()
            if screen is not None
            else self._minimum_content_width
        )
        available_height = (
            screen.availableGeometry().height()
            if screen is not None
            else 700
        )
        window_min_width = min(
            self._minimum_content_width,
            available_width,
        )

        self._minimum_content_height = 700
        self.splitter.setMinimumHeight(self._minimum_content_height)
        window_min_height = min(self._minimum_content_height, available_height)
        self.setMinimumSize(window_min_width, window_min_height)

        self._main_content_margin = 8

        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setObjectName("mainScrollArea")
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.main_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        self.main_scroll_area.setFrameShape(QFrame.NoFrame)

        # Keep all three main panels visually separated from the main window
        # by exactly 8 px on every side, including when the content scrolls.
        self.main_content = QWidget()
        self.main_content_layout = QVBoxLayout(self.main_content)
        self.main_content_layout.setContentsMargins(
            self._main_content_margin,
            self._main_content_margin,
            self._main_content_margin,
            self._main_content_margin,
        )
        self.main_content_layout.setSpacing(0)
        self.main_content_layout.addWidget(self.splitter)
        self.main_scroll_area.setWidget(self.main_content)

        self.setCentralWidget(self.main_scroll_area)

        # On a sufficiently large screen the window itself must never shrink
        # below DR's minimum content width. Only low-resolution screens are
        # allowed to show the main horizontal scrollbar.
        self.setMinimumWidth(window_min_width)

        # Do not auto-collapse Preview while the MainWindow is still being
        # constructed. At this point Qt may report the temporary central-widget
        # width instead of the final window width. The first real layout pass
        # is handled after construction.
        QTimer.singleShot(0, self._update_main_scroll_behavior)
        if self.windowHandle() is not None:
            self.windowHandle().screenChanged.connect(
                self._update_main_scroll_behavior
            )

    def _toggle_preview(self, checked: bool) -> None:
        """Manually show or hide the Preview panel."""
        self._set_preview_visible(checked)
        self._update_main_scroll_behavior()

    def _set_preview_visible(self, visible: bool) -> None:
        """Collapse/expand the Preview side panel without removing it."""
        if visible:
            self.preview_panel.setVisible(True)
            self.preview_container.setMinimumWidth(
                self._preview_min_width + self._collapsed_panel_width
            )
            self.preview_container.setMaximumWidth(16777215)
            self.preview_toggle_button.setChecked(True)
            self.preview_toggle_button.setText("◀")
            self.preview_toggle_button.setToolTip("Collapse Preview")
            self.preview_toggle_action.setChecked(True)
            self.splitter.setSizes([
                self._preview_min_width + self._collapsed_panel_width,
                (
                    self._properties_min_width
                    if self.properties_toggle_action.isChecked()
                    else 0
                ),
                (
                    self._queue_min_width
                    if self.queue_toggle_button.isChecked()
                    else self._collapsed_panel_width
                ),
            ])
        else:
            self.preview_panel.setVisible(False)
            self.preview_container.setMinimumWidth(self._collapsed_panel_width)
            self.preview_container.setMaximumWidth(self._collapsed_panel_width)
            self.preview_toggle_button.setChecked(False)
            self.preview_toggle_button.setText("▶")
            self.preview_toggle_button.setToolTip("Expand Preview")
            self.preview_toggle_action.setChecked(False)
            self.splitter.setSizes([
                self._collapsed_panel_width,
                (
                    self._properties_min_width
                    if self.properties_toggle_action.isChecked()
                    else 0
                ),
                (
                    self._queue_min_width
                    if self.queue_toggle_button.isChecked()
                    else self._collapsed_panel_width
                ),
            ])

    def _toggle_properties(self, checked: bool) -> None:
        self._set_properties_visible(checked)
        self._update_main_scroll_behavior()

    def _set_properties_visible(self, visible: bool) -> None:
        """Show or hide the central Properties panel."""
        self.properties_panel.setVisible(visible)
        self.properties_toggle_action.setChecked(visible)
        self.properties_panel.setMinimumWidth(
            self._properties_min_width if visible else 0
        )

        preview_width = (
            self._preview_min_width + self._collapsed_panel_width
            if self.preview_toggle_button.isChecked()
            else self._collapsed_panel_width
        )
        properties_width = self._properties_min_width if visible else 0
        queue_width = (
            self._queue_min_width
            if self.queue_toggle_button.isChecked()
            else self._collapsed_panel_width
        )
        self.splitter.setSizes([preview_width, properties_width, queue_width])

    def _toggle_queue(self, checked: bool) -> None:
        self._set_queue_visible(checked)
        self._update_main_scroll_behavior()

    def _set_queue_visible(self, visible: bool) -> None:
        """Collapse/expand the Queue side panel without removing it."""
        if visible:
            self.queue_panel.setVisible(True)
            self.queue_container.setMinimumWidth(self._queue_min_width)
            self.queue_container.setMaximumWidth(16777215)
            self.queue_toggle_button.setChecked(True)
            self.queue_toggle_action.setChecked(True)
            self.queue_toggle_button.setText("▶")
            self.queue_toggle_button.setToolTip("Collapse Queue")
            self.splitter.setSizes([
                (
                    self._preview_min_width + self._collapsed_panel_width
                    if self.preview_toggle_button.isChecked()
                    else self._collapsed_panel_width
                ),
                (
                    self._properties_min_width
                    if self.properties_toggle_action.isChecked()
                    else 0
                ),
                self._queue_min_width,
            ])
        else:
            self.queue_panel.setVisible(False)
            self.queue_container.setMinimumWidth(self._collapsed_panel_width)
            self.queue_container.setMaximumWidth(self._collapsed_panel_width)
            self.queue_toggle_button.setChecked(False)
            self.queue_toggle_action.setChecked(False)
            self.queue_toggle_button.setText("◀")
            self.queue_toggle_button.setToolTip("Expand Queue")
            self.splitter.setSizes([
                (
                    self._preview_min_width + self._collapsed_panel_width
                    if self.preview_toggle_button.isChecked()
                    else self._collapsed_panel_width
                ),
                (
                    self._properties_min_width
                    if self.properties_toggle_action.isChecked()
                    else 0
                ),
                self._collapsed_panel_width,
            ])

    def _update_main_scroll_behavior(self, *args) -> None:
        """Adapt the main layout to the monitor instead of forcing scrolling."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        available_width = available.width()
        available_height = available.height()

        # First response to a narrow monitor: collapse Preview. Properties and
        # Queue remain immediately usable. Only if even those two panels do not
        # fit do we introduce horizontal scrolling.
        auto_collapse_preview = available_width < self._minimum_content_width
        preview_visible = self.preview_toggle_action.isChecked()
        if auto_collapse_preview and preview_visible:
            self._set_preview_visible(False)
            preview_visible = False
        elif not auto_collapse_preview and not preview_visible:
            # A manually hidden Preview stays hidden; automatic collapse is not
            # a one-way override. The toolbar action lets the user restore it.
            pass

        queue_visible = self.queue_toggle_button.isChecked()
        properties_visible = self.properties_toggle_action.isChecked()
        preview_width = (
            self._preview_min_width + self._collapsed_panel_width
            if preview_visible
            else self._collapsed_panel_width
        )
        properties_width = self._properties_min_width if properties_visible else 0
        queue_width = (
            self._queue_min_width
            if queue_visible
            else self._collapsed_panel_width
        )
        visible_panel_count = sum((preview_visible, properties_visible, queue_visible))
        handle_width = max(0, visible_panel_count - 1) * self._splitter_handle_margin
        content_min_width = preview_width + properties_width + queue_width + handle_width
        self.splitter.setMinimumWidth(content_min_width)
        outer_content_width = content_min_width + 2 * self._main_content_margin
        outer_content_height = self._minimum_content_height + 2 * self._main_content_margin
        needs_horizontal_scroll = available_width < outer_content_width
        needs_vertical_scroll = available_height < outer_content_height

        self.setMinimumWidth(min(outer_content_width, available_width))
        self.setMinimumHeight(min(outer_content_height, available_height))

        if needs_horizontal_scroll or needs_vertical_scroll:
            self.main_scroll_area.setWidgetResizable(False)
            content_width = max(
                content_min_width if needs_horizontal_scroll else self.main_scroll_area.viewport().width() - 2 * self._main_content_margin,
                content_min_width,
            )
            content_height = max(
                self._minimum_content_height if needs_vertical_scroll else self.main_scroll_area.viewport().height() - 2 * self._main_content_margin,
                self._minimum_content_height,
            )
            self.splitter.setFixedSize(content_width, content_height)
            self.main_content.setFixedSize(
                content_width + 2 * self._main_content_margin,
                content_height + 2 * self._main_content_margin,
            )
        else:
            self.main_scroll_area.setWidgetResizable(True)
            self.splitter.setMinimumSize(content_min_width, self._minimum_content_height)
            self.main_content.setMinimumSize(
                content_min_width + 2 * self._main_content_margin,
                self._minimum_content_height + 2 * self._main_content_margin,
            )
            self.splitter.setMaximumWidth(16777215)
            self.splitter.setMaximumHeight(16777215)

        self.main_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn if needs_horizontal_scroll else Qt.ScrollBarAlwaysOff
        )
        self.main_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn if needs_vertical_scroll else Qt.ScrollBarAlwaysOff
        )

    def _connect_live_preview_signals(self) -> None:
        panel = self.properties_panel
        self.preview_panel.on_result_metadata_changed = self._persist_result_metadata

        for edit in (
            panel.positive_prompt_edits
            + panel.negative_prompt_edits
            + panel.seed_edits
        ):
            edit.textChanged.connect(self._refresh_queue_preview)

        panel.prompt_inputs_changed.connect(self._refresh_queue_preview)
        panel.style_list.itemChanged.connect(self._refresh_queue_preview)
        panel.base_model_list.itemChanged.connect(
            self._refresh_queue_preview
        )
        panel.random_style_checkbox.toggled.connect(
            self._refresh_queue_preview
        )
        panel.random_style_count.valueChanged.connect(
            self._refresh_queue_preview
        )
        panel.random_seed_checkbox.toggled.connect(
            self._refresh_queue_preview
        )
        panel.random_seed_count.valueChanged.connect(
            self._refresh_queue_preview
        )

        for control in panel.matrix_controls.values():
            control.currentIndexChanged.connect(
                self._refresh_queue_preview
            )

        for control in panel.matrix_count_controls.values():
            control.valueChanged.connect(self._refresh_queue_preview)

        panel.width_slider.valueChanged.connect(
            self._refresh_queue_preview
        )
        panel.height_slider.valueChanged.connect(
            self._refresh_queue_preview
        )

        panel.resolution_matrix_enabled.toggled.connect(
            self._refresh_queue_preview
        )
        panel.resolution_matrix_dimension.currentIndexChanged.connect(
            self._refresh_queue_preview
        )

        for control in (
            panel.resolution_matrix_minimum,
            panel.resolution_matrix_maximum,
            panel.resolution_matrix_steps,
        ):
            control.valueChanged.connect(self._refresh_queue_preview)

    def _refresh_queue_preview(self, *args) -> None:
        if self.generation_thread is not None:
            return

        # Several property widgets are connected directly to this method.
        # Updating one control can synchronously emit another Qt signal (for
        # example when matrix count limits are clamped).  Ignore nested
        # refreshes; the outer refresh already rebuilds the complete preview.
        if self._queue_preview_refreshing:
            return

        self._queue_preview_refreshing = True
        try:
            self._sync_matrix_settings_from_properties()

            try:
                configurations = MatrixBuilder.build_experiment(
                    self.experiment
                )
            except (ValueError, TypeError) as exc:
                self.queue_panel.set_preview_error(str(exc))
                return

            self.queue_panel.set_preview_configurations(
                configurations,
                style_pool=self.experiment.available_styles,
            )
            self.experiment.set_configuration_count(len(configurations))
        finally:
            self._queue_preview_refreshing = False

    def _set_fooocus_status(self, text: str) -> None:
        self.fooocus_status_label.setText(text)

    # ------------------------------------------------------------------
    # Fooocus connection / startup
    # ------------------------------------------------------------------

    def connect_to_fooocus(self) -> bool:
        """Connect to Fooocus, starting it first when necessary."""

        if self._fooocus_connect_timer is not None:
            return True

        self.queue_panel.start_connect_animation()
        self._fooocus_connect_started_at = __import__("time").monotonic()

        if self.connection_controller.is_fooocus_available():
            self.status.showMessage("Connecting to Fooocus...")
            self._set_fooocus_status("🟡 Fooocus: connecting...")
            return self._connect_to_available_fooocus()

        self.status.showMessage("Starting Fooocus...")
        self._set_fooocus_status("🟠 Fooocus: starting...")

        if not self.connection_controller.start_fooocus():
            self._fooocus_connection_failed(
                "Could not start Fooocus"
            )
            return False

        self._fooocus_connect_timer = QTimer(self)
        self._fooocus_connect_timer.setInterval(
            self.CONNECT_POLL_INTERVAL_MS
        )
        self._fooocus_connect_timer.timeout.connect(
            self._poll_fooocus_startup
        )
        self._fooocus_connect_timer.start()

        # Check immediately rather than waiting for the first 250 ms tick.
        self._poll_fooocus_startup()

        return True

    def _poll_fooocus_startup(self) -> None:
        if self._fooocus_connect_started_at is None:
            return

        import time

        elapsed = time.monotonic() - self._fooocus_connect_started_at
        remaining = max(
            0,
            self.CONNECT_TIMEOUT_SECONDS - int(elapsed),
        )

        if self.connection_controller.is_fooocus_available():
            self._stop_fooocus_connect_timer()
            self.status.showMessage("Connecting to Fooocus...")
            self._set_fooocus_status("🟡 Fooocus: connecting...")
            self._connect_to_available_fooocus()
            return

        if elapsed >= self.CONNECT_TIMEOUT_SECONDS:
            self._stop_fooocus_connect_timer()
            self._fooocus_connection_failed(
                f"Connection timed out after "
                f"{self.CONNECT_TIMEOUT_SECONDS} seconds"
            )
            return

        self.status.showMessage(
            f"Starting Fooocus... ({elapsed:.1f} s)"
        )
        self._set_fooocus_status(
            f"🟡 Fooocus: waiting... ({remaining}s)"
        )

    def _stop_fooocus_connect_timer(self) -> None:
        if self._fooocus_connect_timer is not None:
            self._fooocus_connect_timer.stop()
            self._fooocus_connect_timer.deleteLater()
            self._fooocus_connect_timer = None
        self._fooocus_connect_started_at = None

    def _fooocus_connection_failed(self, message: str) -> None:
        self._stop_fooocus_connect_timer()
        self.queue_panel.stop_connect_animation(success=False)
        self.status.showMessage(message)
        self._set_fooocus_status("🔴 Fooocus: connection failed")

    def _connect_to_available_fooocus(self) -> bool:
        self.status.showMessage("Connecting to Fooocus...")
        self._set_fooocus_status("🟡 Fooocus: connecting...")

        if not self.connection_controller.connect():
            self._fooocus_connection_failed(
                "Could not connect to Fooocus"
            )
            return False

        runtime_spec = self.connection_controller.client.runtime_spec

        if runtime_spec is None:
            self._fooocus_connection_failed(
                "Connected, but no runtime specification available"
            )
            self._set_fooocus_status(
                "🟠 Fooocus: connected, runtime unavailable"
            )
            return False

        style_input = next(
            (
                input_spec
                for input_spec in runtime_spec.inputs
                if input_spec.label == "Selected Styles"
            ),
            None,
        )

        if (
            style_input is not None
            and style_input.choices is not None
        ):
            self.properties_panel.set_style_choices(
                style_input.choices
            )

        base_model_input = next(
            (
                input_spec
                for input_spec in runtime_spec.inputs
                if "base model" in (input_spec.label or "").lower()
            ),
            None,
        )

        if (
            base_model_input is not None
            and base_model_input.choices is not None
        ):
            self.properties_panel.set_base_model_choices(
                base_model_input.choices
            )

        self._stop_fooocus_connect_timer()
        self.queue_panel.set_connected_state()
        self.status.showMessage("Connected to Fooocus")
        self._set_fooocus_status("🟢 Fooocus: connected")

        # Fooocus may open its browser immediately after connecting.
        # Give it a moment to launch, then return the user to PromptLAB.
        QTimer.singleShot(350, self._bring_to_front)
        QTimer.singleShot(1200, self._bring_to_front)
        return True

    def _bring_to_front(self) -> None:
        """Return focus to DESPERATE RENDER without changing its geometry."""
        self.raise_()
        self.activateWindow()


    # ------------------------------------------------------------------
    # Matrix synchronization
    # ------------------------------------------------------------------

    def _sync_matrix_settings_from_properties(self) -> None:
        matrix_controls = getattr(
            self.properties_panel,
            "matrix_controls",
            {},
        )
        matrix_count_controls = getattr(
            self.properties_panel,
            "matrix_count_controls",
            {},
        )

        for dimension, combo in matrix_controls.items():
            selection = getattr(self.experiment.matrix, dimension)

            operator_value = combo.currentData()
            if operator_value is None:
                operator_value = combo.currentText().strip().upper()

            selection.operator = MatrixOperator(operator_value)

            count_control = matrix_count_controls.get(dimension)

            if (
                count_control is not None
                and selection.operator
                in (
                    MatrixOperator.COMBINATION,
                    MatrixOperator.PERMUTATION,
                )
            ):
                count = count_control.value()
                selection.minimum = count
                selection.maximum = count
            else:
                selection.minimum = None
                selection.maximum = None

    def _properties_fingerprint(self) -> str:
        """Fingerprint the current editable experiment properties for close prompts."""
        self.experiment.name = self.properties_panel.experiment_name.text().strip()
        self._sync_matrix_settings_from_properties()
        return self._configuration_fingerprint(None)

    def _persist_result_metadata(self) -> None:
        """Persist rating/exclusion changes immediately without requiring a running job."""
        if self._experiment_path is None:
            return
        snapshot = self.preview_panel.result_run_snapshot()
        if not any(run.get("images") for run in snapshot):
            return
        result_path = self.result_store.paired_path(self._experiment_path)
        try:
            self.result_store.merge_snapshot(
                self.experiment.experiment_id,
                snapshot,
                existing_manifest=self._result_manifest,
                target_path=result_path,
            )
            self._result_manifest = self.result_store.load_for_experiment_path(
                self._experiment_path, self.experiment.experiment_id
            )
        except Exception as exc:
            self.status.showMessage(f"Warning: could not save result metadata: {exc}")

    def _configuration_fingerprint(self, random_seeds: list[int] | None = None) -> str:
        """Hash all persisted experiment settings, optionally pinning run seeds."""
        snapshot = copy.deepcopy(self.experiment)
        if random_seeds is not None:
            snapshot.generation.random_seeds = list(random_seeds)
        data = _to_jsonable(snapshot)
        # Normalize a synthetic legacy Block A that mirrors positive_prompts,
        # so loading an old experiment does not change its run fingerprint.
        normalize_legacy_prompt_block_mirror(data)
        # These fields describe persistence/UI bookkeeping, not generation inputs.
        for key in (
            "updated_at", "status", "configuration_count", "total_image_count",
            "estimated_runtime_seconds", "estimated_storage_bytes", "test_run_completed",
        ):
            data.pop(key, None)
        payload = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _find_resumable_run(self) -> dict | None:
        """Return the latest run only when it has a durable, unfinished job ledger."""
        runs = list(self._result_manifest.get("runs", []))
        if not runs:
            return None
        latest = max(
            runs,
            key=lambda run: str(run.get("updated_at", run.get("created_at", ""))),
        )
        statuses = latest.get("job_statuses")
        planned = int(latest.get("planned_job_count", 0) or 0)
        if not latest.get("run_id") or not isinstance(statuses, dict) or planned < 1:
            return None
        completed = sum(1 for status in statuses.values() if status == "COMPLETED")
        if completed >= planned or latest.get("run_state") == "completed":
            return None
        return latest

    def _persist_active_run_state(self) -> None:
        """Persist the active run ledger once a result file exists or an image arrived."""
        if not self._active_run_id or self._experiment_path is None:
            return
        result_path = self.result_store.paired_path(self._experiment_path)
        snapshot = self.preview_panel.result_run_snapshot()
        active_run_has_images = any(
            str(run.get("run_id") or "") == self._active_run_id and run.get("images")
            for run in snapshot
        )
        # Do not create an empty _rslt.json before the first successful image.
        # A continued run already has a result file and may update its ledger.
        if not active_run_has_images and not result_path.is_file():
            return
        try:
            self.result_store.merge_snapshot(
                self.experiment.experiment_id,
                snapshot,
                existing_manifest=self._result_manifest,
                target_path=result_path,
            )
            manifest = self.result_store.load_for_experiment_path(
                self._experiment_path, self.experiment.experiment_id
            )
            run_record = next(
                (run for run in manifest.get("runs", []) if run.get("run_id") == self._active_run_id),
                None,
            )
            if run_record is None:
                run_record = {
                    "run_id": self._active_run_id,
                    "created_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
                    "images": [],
                }
                manifest.setdefault("runs", []).append(run_record)
            run_record.update({
                "job_statuses": dict(self._active_job_statuses),
                "planned_job_count": self._active_run_planned_jobs,
                "configuration_fingerprint": self._active_run_fingerprint,
                "random_seeds": list(self._active_run_random_seeds),
                "job_seeds": dict(self._active_job_seeds),
                "run_state": self._active_run_state or "running",
                "updated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            self.result_store.save_to_path(
                self.experiment.experiment_id, manifest, result_path
            )
            self._result_manifest = manifest
        except Exception as exc:
            self.status.showMessage(f"Warning: could not persist run progress: {exc}")

    def _record_job_status(self, job: GenerationJob) -> None:
        """Persist job transitions; a completed status is provisional until its image arrives."""
        if not self._active_run_id:
            return
        status = job.status.value
        self._active_job_statuses[str(job.job_id)] = (
            "COMPLETED_PENDING_RESULT" if status == "COMPLETED" else status
        )
        self._persist_active_run_state()

    def _choose_run_mode(self, run: dict, current_fingerprint: str) -> str:
        """Return continue, new, or cancel; continuation is offered only for matching settings."""
        saved_fingerprint = str(run.get("configuration_fingerprint") or "")
        if not saved_fingerprint or saved_fingerprint != current_fingerprint:
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Information)
            dialog.setWindowTitle("Continue Run unavailable")
            dialog.setText(
                "The experiment Properties no longer match the saved run.\n\n"
                "Continue Run is disabled for safety. Choose New Run to start with the current settings."
            )
            ok_button = dialog.addButton("OK, new run", QMessageBox.ButtonRole.AcceptRole)
            cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
            dialog.setDefaultButton(ok_button)
            dialog.exec()
            return "new" if dialog.clickedButton() is ok_button else "cancel"

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Continue or start a new run?")
        completed = sum(1 for status in run.get("job_statuses", {}).values() if status == "COMPLETED")
        planned = int(run.get("planned_job_count", 0) or 0)
        dialog.setText(
            f"A saved run is incomplete ({completed}/{planned} jobs completed).\n\n"
            "Continue Run resumes the unfinished jobs in this same run.\n"
            "New Run starts a separate run with the current configuration."
        )
        continue_button = dialog.addButton("Continue Run", QMessageBox.ButtonRole.AcceptRole)
        new_button = dialog.addButton("New Run", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(continue_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is continue_button:
            return "continue"
        if clicked is new_button:
            return "new"
        return "cancel"

    def _ensure_branding_output_asset(self) -> None:
        """Copy the root branding card into today's Fooocus output folder at run start."""
        source = Path(__file__).resolve().parents[1] / BRANDING_FILENAME
        outputs_root = self.preview_panel.fooocus_outputs_dir
        if outputs_root is None:
            print("[DR-BRANDING] Fooocus outputs directory is not configured.")
            return
        # Fooocus writes generated images under outputs/YYYY-MM-DD/. Keep the
        # branding asset alongside that day's results so the normal output
        # discovery can see it. Never overwrite an existing daily copy.
        daily_output = outputs_root / date.today().isoformat()
        destination = ensure_branding_asset(daily_output, source)
        if destination is None:
            print(
                "[DR-BRANDING] Could not copy DesperateRender.png to the Fooocus daily output folder; "
                "check that the root asset exists and the configured output path is writable."
            )

    def generate_image(self) -> None:
        if self.generation_thread is not None:
            self.status.showMessage("Generation already running.")
            return

        self._sync_matrix_settings_from_properties()
        self.experiment.name = self.properties_panel.experiment_name.text().strip()

        # Do not auto-save here. Starting a New Run asks whether to save the
        # current experiment/history; saving before that dialog created an
        # unnecessary first revision and then a second revision from the
        # dialog's "Save and continue" action. Persist once, after all run
        # confirmations, if the user chose to continue without saving.
        resumable = self._find_resumable_run()
        continue_run = False
        if resumable is not None:
            saved_seeds = [int(seed) for seed in resumable.get("random_seeds", [])]
            current_fingerprint = self._configuration_fingerprint(saved_seeds)
            choice = self._choose_run_mode(resumable, current_fingerprint)
            if choice == "cancel":
                self.status.showMessage("Run cancelled")
                return
            continue_run = choice == "continue"

        if continue_run:
            # Random seeds belong to the original run and are restored from _rslt.json.
            self.experiment.generation.random_seeds = list(saved_seeds)
            configurations = MatrixBuilder.build_experiment(self.experiment)
            if len(configurations) != int(resumable.get("planned_job_count", 0) or 0):
                QMessageBox.warning(
                    self, "Continue Run unavailable",
                    "The reconstructed job list does not match the saved run. Start a New Run instead.",
                )
                return
            self._active_run_id = str(resumable["run_id"])
            self._active_job_statuses = {
                str(job_id): str(status)
                for job_id, status in resumable.get("job_statuses", {}).items()
            }
            self._active_run_random_seeds = list(saved_seeds)
            self._active_job_seeds = {
                str(job_id): (int(seed) if seed is not None else None)
                for job_id, seed in resumable.get("job_seeds", {}).items()
            }
            for job_id, configuration in enumerate(configurations, start=1):
                if str(job_id) in self._active_job_seeds:
                    configuration.seed = self._active_job_seeds[str(job_id)]
            self._active_run_planned_jobs = len(configurations)
            self._active_run_fingerprint = current_fingerprint
            self._active_run_state = "running"
            self.preview_panel.active_run_id = self._active_run_id
        else:
            # A New Run always gets a fresh immutable experiment definition.
            # There is no general save prompt before Run; only an eligible,
            # unchanged incomplete run can offer Continue Run above.
            # In Random seed mode, generate a fresh seed set for each new Run.
            if (
                self.experiment.generation.seed_mode == SeedMode.RANDOM
                and self.experiment.generation.random_seed_fixed
            ):
                self.experiment.generation.random_seeds = []
            configurations = MatrixBuilder.build_experiment(self.experiment)
            if not configurations:
                self.status.showMessage("No generation configuration available.")
                return
            self.preview_panel.clear_history()
            self._active_run_id = uuid4().hex
            self.preview_panel.active_run_id = self._active_run_id
            self._active_job_statuses = {str(job_id): "WAITING" for job_id in range(1, len(configurations) + 1)}
            self._active_run_random_seeds = list(self.experiment.generation.random_seeds)
            self._active_job_seeds = {
                str(job_id): configuration.seed
                for job_id, configuration in enumerate(configurations, start=1)
            }
            self._active_run_planned_jobs = len(configurations)
            self._active_run_fingerprint = self._configuration_fingerprint(self._active_run_random_seeds)
            self._active_run_state = "running"

        if not configurations:
            self.status.showMessage(
                "No generation configuration available."
            )
            return

        # Warn before creating/starting a large generation queue.
        # The threshold is configured in Settings → Queue and persisted by
        # ApplicationSettings. Keep this check here, immediately before queue
        # creation, so every normal generation start goes through the warning.
        warning_threshold = self.application_settings.queue_warning_threshold
        total_configurations = len(configurations)
        if total_configurations >= warning_threshold:
            dialog = QMessageBox(
                QMessageBox.Icon.Warning,
                "Large generation queue",
                (
                    f"This experiment contains {total_configurations} jobs.\n\n"
                    f"Your warning threshold is {warning_threshold} jobs.\n\n"
                    "Large queues can take a long time and require substantial "
                    "disk space.\n\n"
                    "Start the generation anyway?"
                ),
                QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes,
                self,
            )
            dialog.setDefaultButton(QMessageBox.StandardButton.No)
            if dialog.exec() != QMessageBox.StandardButton.Yes:
                self.status.showMessage("Generation not started")
                return

        # Every New Run gets its own immutable _exp.json, regardless of whether
        # the previous definition was manually saved. Continue Run retains its
        # original definition and paired result file. _rslt.json is intentionally
        # deferred until the first successful image.
        if not continue_run:
            try:
                self._experiment_path = self.experiment_store.save(self.experiment)
                self._result_manifest = {
                    "schema_version": 1,
                    "experiment_id": self.experiment.experiment_id,
                    "runs": [],
                }
                self._saved_properties_fingerprint = self._properties_fingerprint()
            except Exception as exc:
                QMessageBox.critical(self, "Save experiment failed", str(exc))
                return

        # The branding card is a reserved Preview item (#0), not a generation
        # result. Copy it into Fooocus outputs only when that file is absent.
        self._ensure_branding_output_asset()
        self.preview_panel.set_generation_active(True)
        queue = GenerationQueue()
        queued_configurations = []
        for job_id, configuration in enumerate(configurations, start=1):
            if continue_run and self._active_job_statuses.get(str(job_id)) == "COMPLETED":
                continue
            request = GenerationConfigurationAdapter.to_fooocus_request(configuration)
            queue.add(GenerationJob(
                job_id=job_id,
                request=request,
                prompt_block_variant_id=configuration.prompt_block_variant_id,
            ))
            queued_configurations.append(configuration)
            self._active_job_statuses[str(job_id)] = "WAITING"

        if len(queue) == 0:
            self._active_run_state = "completed"
            self._persist_active_run_state()
            self.status.showMessage("All jobs in this run are already completed.")
            self.preview_panel.set_generation_active(False)
            return

        queue.close()
        self.queue_panel.set_queue(queue, queued_configurations)
        self._persist_active_run_state()

        total = len(queue)
        self.experiment.set_configuration_count(total)
        self.status.showMessage(f"Generating 0/{total}...")
        self.queue_panel.set_running_state()

        self.generation_thread = QThread(self)
        self.generation_worker = GenerationWorker(
            self.generation_service,
            queue,
        )
        self.generation_worker.moveToThread(self.generation_thread)

        self.generation_thread.started.connect(
            self.generation_worker.run
        )
        self.generation_worker.finished.connect(self.generation_finished)
        self.generation_worker.error.connect(self.generation_failed)
        self.generation_worker.progress.connect(self.generation_progress)
        self.generation_worker.progress.connect(
            self.queue_panel.update_progress
        )
        self.generation_worker.job_status.connect(
            self.queue_panel.update_job_status
        )
        self.generation_worker.job_status.connect(self._record_job_status)
        self.generation_worker.completed.connect(self.generation_completed)
        self.generation_worker.cancelled.connect(self.generation_cancelled)
        self.generation_worker.paused.connect(self.generation_paused)
        self.generation_worker.resumed.connect(self.generation_resumed)

        self.generation_worker.error.connect(
            self.generation_thread.quit
        )
        self.generation_worker.completed.connect(
            self.generation_thread.quit
        )
        self.generation_worker.cancelled.connect(
            self.generation_thread.quit
        )
        self.generation_thread.finished.connect(
            self.generation_cleanup
        )

        self.generation_thread.start()
        self._has_executed_run = True

    def run_cancel_generation(self) -> None:
        if self.queue_panel.run_button.text() == "Cancel":
            self.cancel_generation()
            return
        self.generate_image()

    def pause_resume_generation(self) -> None:
        if self.queue_panel.pause_button.text() == "Resume":
            self.resume_generation()
            return
        self.pause_generation()

    def pause_generation(self) -> None:
        if self.generation_worker is None:
            return
        print("MainWindow: Pause button pressed.")
        self.generation_worker.pause()
        self.queue_panel.set_paused_state()
        self.status.showMessage("🟡 Pausing after current image...")

    def resume_generation(self) -> None:
        if self.generation_worker is None:
            return
        print("MainWindow: Resume button pressed.")
        self.generation_worker.resume()
        self.queue_panel.set_running_state()
        self.status.showMessage("🟢 Resuming generation...")

    def generation_paused(self) -> None:
        self.queue_panel.set_paused_state()
        self.status.showMessage("🟡 Generation paused")

    def generation_resumed(self) -> None:
        self.queue_panel.set_running_state()
        self.status.showMessage("🟢 Generation resumed")

    def cancel_generation(self) -> None:
        if self.generation_worker is None:
            self.status.showMessage("No generation is running.")
            return

        print("MainWindow: Cancel button pressed.")

        dialog = QMessageBox(
            QMessageBox.Icon.Question,
            "Cancel Generation",
            "Are you sure you want to cancel the generation?",
            parent=self,
        )
        no_button = dialog.addButton("No", QMessageBox.ButtonRole.RejectRole)
        yes_button = dialog.addButton("Yes, cancel", QMessageBox.ButtonRole.AcceptRole)
        dialog.setDefaultButton(no_button)
        dialog.exec()

        if dialog.clickedButton() is not yes_button:
            return

        self.status.showMessage("🟠 Cancelling generation...")
        self.queue_panel.set_cancelling_state()
        self.generation_worker.cancel()

    def generation_finished(self, result) -> None:
        # Reuse the exact parameter tooltip HTML already shown for each queue job.
        job_tooltips = [
            self.queue_panel.jobs.item(index).toolTip()
            for index in range(self.queue_panel.jobs.count())
        ]
        self.preview_panel.set_job_tooltips(job_tooltips)
        self.preview_panel.set_images(result)
        if result.job_id is not None:
            self._active_job_statuses[str(result.job_id)] = "COMPLETED"
            self._persist_active_run_state()
        self.status.showMessage(f"🟢 Generated {len(result.images)} image(s)")

    def generation_progress(self, current: int, total: int) -> None:
        self.status.showMessage(f"Generating {current}/{total}...")

    def generation_completed(self) -> None:
        self.preview_panel.set_generation_active(False)
        self._active_run_state = "completed"
        self._persist_active_run_state()
        self.status.showMessage("🟢 All generations completed")

    def generation_cancelled(self) -> None:
        self.preview_panel.set_generation_active(False)
        self._active_run_state = "cancelled"
        self._persist_active_run_state()
        self.status.showMessage("🟠 Generation cancelled")

    def generation_failed(self, message: str) -> None:
        self.preview_panel.set_generation_active(False)
        self._active_run_state = "failed"
        self._persist_active_run_state()
        self.status.showMessage(f"🔴 Generation failed: {message}")
        print()
        print("Generation failed:")
        print(message)

    def generation_cleanup(self) -> None:
        if self.generation_worker is not None:
            self.generation_worker.deleteLater()
        if self.generation_thread is not None:
            self.generation_thread.deleteLater()
        self.generation_worker = None
        self.generation_thread = None
        self.queue_panel.set_connected_state()

    def closeEvent(self, event) -> None:
        # Once a Run has actually started, its immutable experiment definition
        # and result ledger are managed automatically. Only unsaved Properties
        # in a session with no executed Run need a close-time save prompt.
        if not self._has_executed_run:
            try:
                current_fingerprint = self._properties_fingerprint()
            except Exception:
                current_fingerprint = None
            properties_dirty = (
                current_fingerprint is not None
                and current_fingerprint != self._saved_properties_fingerprint
            )
            if properties_dirty:
                dialog = QMessageBox(self)
                dialog.setIcon(QMessageBox.Icon.Question)
                dialog.setWindowTitle("Save changed Properties?")
                dialog.setText(
                    "Properties have changed since the last saved experiment definition.\n\n"
                    "Do you want to save these Properties before exiting?"
                )
                save_button = dialog.addButton(
                    "Save and exit", QMessageBox.ButtonRole.AcceptRole
                )
                discard_button = dialog.addButton(
                    "Exit without saving", QMessageBox.ButtonRole.DestructiveRole
                )
                cancel_button = dialog.addButton(
                    "Cancel", QMessageBox.ButtonRole.RejectRole
                )
                dialog.setDefaultButton(save_button)
                dialog.exec()
                choice = dialog.clickedButton()
                if choice is cancel_button or choice not in (save_button, discard_button):
                    event.ignore()
                    return
                if choice is save_button and not self.save_experiment():
                    event.ignore()
                    return

        if self._fooocus_connect_timer is not None:
            self._stop_fooocus_connect_timer()
        if self.generation_worker is not None:
            self.generation_worker.cancel()
        if self.generation_thread is not None:
            self.generation_thread.quit()
            self.generation_thread.wait()
        self.connection_controller.stop_fooocus_if_started()
        event.accept()
