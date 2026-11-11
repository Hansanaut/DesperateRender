from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
)

from models.application_settings import ApplicationSettings
from services.calibration_service import CalibrationService
from services.calibration_profile import CalibrationPoint, CalibrationProfile
from services.generation_service import GenerationService
from services.runtime_estimator import RuntimeEstimator


class CalibrationWorker(QThread):
    progress = Signal(int, int, object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: CalibrationService,
        fooocus_url: str,
        reference_image: str | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.fooocus_url = fooocus_url
        self.reference_image = reference_image

    def run(self) -> None:
        try:
            profile = self.service.run(
                self.fooocus_url,
                progress=lambda current, total, point: self.progress.emit(
                    current, total, point
                ),
                reference_image=self.reference_image,
            )
            self.succeeded.emit(profile)
        except Exception as exc:
            self.failed.emit(str(exc))


class FooocusSettingsDialog(QDialog):
    """Edit Fooocus settings and calibrate local generation performance."""

    def __init__(
        self,
        settings: ApplicationSettings,
        generation_service: GenerationService | None = None,
        parent=None,
    ) -> None:
        # Backward-compatible with the previous constructor: (settings, parent).
        if generation_service is not None and parent is None and hasattr(generation_service, "generation_service"):
            parent = generation_service
            generation_service = generation_service.generation_service
        super().__init__(parent)
        self.settings = settings
        self.generation_service = generation_service
        self.worker: CalibrationWorker | None = None
        self._connection_wait_timer: QTimer | None = None
        self._connection_wait_started_at: float | None = None
        self._busy_cursor_active = False

        self.setWindowTitle("DESPERATE RENDER Settings")
        self.setMinimumWidth(680)

        self.url_edit = QLineEdit(settings.fooocus_url)
        self.url_edit.setPlaceholderText("http://127.0.0.1:7865")

        self.path_edit = QLineEdit(settings.fooocus_path)
        self.path_edit.setPlaceholderText("Fooocus installation folder")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)

        self.auto_start = QCheckBox("Start Fooocus automatically")
        self.auto_start.setChecked(settings.fooocus_auto_start)

        self.experiment_directory_edit = QLineEdit(settings.experiment_directory)
        self.experiment_directory_edit.setPlaceholderText("Experiment storage folder")
        experiment_browse_button = QPushButton("Browse…")
        experiment_browse_button.clicked.connect(self._browse_experiment_directory)

        experiment_directory_row = QHBoxLayout()
        experiment_directory_row.setContentsMargins(0, 0, 0, 0)
        experiment_directory_row.addWidget(self.experiment_directory_edit, 1)
        experiment_directory_row.addWidget(experiment_browse_button)

        form = QFormLayout()
        form.addRow("Fooocus URL", self.url_edit)
        form.addRow("Fooocus path", path_row)
        form.addRow("Experiment folder", experiment_directory_row)
        form.addRow("", self.auto_start)

        fooocus_group = QGroupBox("Fooocus")
        fooocus_layout = QVBoxLayout(fooocus_group)
        fooocus_layout.addLayout(form)

        self.queue_warning_threshold = QSpinBox()
        self.queue_warning_threshold.setRange(1, 100000)
        self.queue_warning_threshold.setValue(settings.queue_warning_threshold)
        self.queue_warning_threshold.setSuffix(" jobs")

        queue_form = QFormLayout()
        queue_form.addRow("Warn at", self.queue_warning_threshold)

        queue_group = QGroupBox("Queue")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.addWidget(
            QLabel(
                "Show a warning before starting an experiment with this many "
                "or more generation jobs in the queue."
            )
        )
        queue_layout.addLayout(queue_form)

        self.calibration_status = QLabel()
        self.calibration_button = QPushButton("Run Desperate Render™ Calibration")
        self.calibration_button.clicked.connect(self._start_calibration)
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setVisible(False)

        calibration_group = QGroupBox("Performance Calibration")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_layout.addWidget(
            QLabel(
                "Generate three real DESPERATE RENDER™ logo test images at different "
                "resolutions. DESPERATE RENDER stores the measured runtime and PNG "
                "size for this installation."
            )
        )
        calibration_layout.addWidget(self.calibration_status)
        calibration_layout.addWidget(self.calibration_progress)
        calibration_layout.addWidget(self.calibration_button)
        self._refresh_calibration_status()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.buttons = buttons

        layout = QVBoxLayout(self)
        layout.addWidget(fooocus_group)
        layout.addWidget(queue_group)
        layout.addWidget(calibration_group)
        layout.addWidget(buttons)

    def _refresh_calibration_status(self) -> None:
        profile = self.settings.calibration_profile
        if profile is None:
            self.calibration_status.setText("Status: Not calibrated")
            return
        self.calibration_status.setText(
            f"Status: calibrated — {profile.point_count} measurements, "
            f"{profile.created_at}"
        )

    def _browse(self) -> None:
        current = self.path_edit.text().strip()
        start_dir = current if Path(current).is_dir() else ""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Fooocus installation folder",
            start_dir,
        )
        if selected:
            self.path_edit.setText(selected)

    def _browse_experiment_directory(self) -> None:
        current = self.experiment_directory_edit.text().strip()
        start_dir = current if Path(current).is_dir() else ""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select DESPERATE RENDER experiment folder",
            start_dir,
        )
        if selected:
            self.experiment_directory_edit.setText(selected)

    def _start_calibration(self) -> None:
        if self.generation_service is None:
            QMessageBox.information(
                self,
                "Generation service unavailable",
                "The generation service is not available. Restart DESPERATE RENDER and try again.",
            )
            return

        self.calibration_button.setText("Calibration running…")
        self.calibration_button.setEnabled(False)
        self.calibration_progress.setVisible(True)
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.buttons.setEnabled(False)
        self._start_busy_state()

        main_window = self.parentWidget()
        controller = getattr(main_window, "connection_controller", None)
        connect_method = getattr(main_window, "connect_to_fooocus", None)

        if controller is not None and controller.is_connected():
            self._start_calibration_worker()
            return

        if not callable(connect_method):
            self._start_calibration_worker()
            return

        self.calibration_status.setText("Connecting to Fooocus…")
        try:
            if connect_method() is False:
                self._calibration_connection_failed(
                    "Could not connect to Fooocus. Calibration was not started."
                )
                return
        except Exception as exc:
            self._calibration_connection_failed(f"Could not connect to Fooocus: {exc}")
            return

        self._connection_wait_started_at = __import__("time").monotonic()
        self._connection_wait_timer = QTimer(self)
        self._connection_wait_timer.setInterval(100)
        self._connection_wait_timer.timeout.connect(self._poll_calibration_connection)
        self._connection_wait_timer.start()

    def _start_busy_state(self) -> None:
        if not self._busy_cursor_active:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._busy_cursor_active = True

    def _stop_busy_state(self) -> None:
        if self._busy_cursor_active:
            QApplication.restoreOverrideCursor()
            self._busy_cursor_active = False

    def _poll_calibration_connection(self) -> None:
        main_window = self.parentWidget()
        controller = getattr(main_window, "connection_controller", None)
        if controller is not None and controller.is_connected():
            self._stop_calibration_connection_wait()
            self._start_calibration_worker()
            return

        started = self._connection_wait_started_at
        if started is None:
            return
        import time
        timeout = float(getattr(main_window, "CONNECT_TIMEOUT_SECONDS", 30)) + 2.0
        if time.monotonic() - started >= timeout:
            self._stop_calibration_connection_wait()
            self._calibration_connection_failed(
                "Fooocus connection timed out. Calibration was not started."
            )

    def _stop_calibration_connection_wait(self) -> None:
        if self._connection_wait_timer is not None:
            self._connection_wait_timer.stop()
            self._connection_wait_timer.deleteLater()
            self._connection_wait_timer = None
        self._connection_wait_started_at = None

    def _calibration_connection_failed(self, message: str) -> None:
        self._stop_busy_state()
        self.calibration_status.setText(f"Calibration failed: {message}")
        self.calibration_button.setText("Run Desperate Render™ Calibration")
        self.calibration_button.setEnabled(True)
        self.buttons.setEnabled(True)
        QMessageBox.critical(self, "Calibration connection failed", message)

    def _start_calibration_worker(self) -> None:
        self.calibration_status.setText(
            "DESPERATE RENDER™ is calibrating — generating test image 1/3…"
        )
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        reference_image = None
        main_window = self.parentWidget()
        preview_panel = getattr(main_window, "preview_panel", None)
        current_image_path = getattr(preview_panel, "current_image_path", None)
        if current_image_path is not None:
            reference_image = str(current_image_path)

        reference_label = "last completed job" if reference_image else "built-in DR test prompt"
        self.calibration_status.setText(
            "DESPERATE RENDER™ is calibrating — generating test image 1/3… "
            f"(reference: {reference_label})"
        )
        self.worker = CalibrationWorker(
            CalibrationService(self.generation_service),
            self.url_edit.text().strip(),
            reference_image=reference_image,
        )
        self.worker.progress.connect(self._calibration_progress)
        self.worker.succeeded.connect(self._calibration_succeeded)
        self.worker.failed.connect(self._calibration_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _calibration_progress(self, current: int, total: int, point: object) -> None:
        # Calibration progress is intentionally discrete: 33% after the first
        # real generation, 67% after the second, and 100% after the third.
        # It never counts down or animates independently of completed work.
        completed_percent = int(round((current / total) * 100)) if total else 0
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(completed_percent)
        if isinstance(point, CalibrationPoint):
            self.calibration_status.setText(
                f"Measured {current}/{total}: {point.width}×{point.height} — "
                f"{point.seconds:.1f} s, {point.storage_bytes / 1024:.0f} KB"
            )

    def _calibration_succeeded(self, profile: object) -> None:
        if not isinstance(profile, CalibrationProfile):
            self._calibration_failed("Calibration returned an invalid profile.")
            return
        try:
            # Use a fresh ApplicationSettings instance for the live GUI save.
            # The dialog may hold a long-lived QSettings handle that was opened
            # before the calibration run. A fresh file-backed instance makes the
            # replacement operation independent of that handle and lets us
            # verify what a new DR process will read.
            disk_settings = ApplicationSettings()
            disk_settings.save_calibration_profile(profile)
            verified_settings = ApplicationSettings()
            verified = verified_settings.calibration_profile
            if verified is None or verified.to_json() != profile.to_json():
                raise RuntimeError(
                    "Calibration was measured successfully, but the new profile "
                    "could not be verified from the saved settings file."
                )
            self.settings = verified_settings
        except Exception as exc:
            self._calibration_failed(str(exc))
            return
        RuntimeEstimator.set_calibration(profile)
        self._refresh_calibration_status()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(100)
        self.calibration_status.setText(
            f"Calibration complete — {profile.point_count} measurements stored."
        )

    def _calibration_failed(self, message: str) -> None:
        self.calibration_status.setText(f"Calibration failed: {message}")
        QMessageBox.critical(self, "Calibration failed", message)

    def _worker_finished(self) -> None:
        self._stop_calibration_connection_wait()
        self._stop_busy_state()
        self.calibration_button.setText("Run Desperate Render™ Calibration")
        self.calibration_button.setEnabled(True)
        self.buttons.setEnabled(True)
        self.worker = None

    def _accept(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Invalid settings", "Fooocus URL must not be empty.")
            return
        experiment_directory = self.experiment_directory_edit.text().strip()
        if not experiment_directory:
            QMessageBox.warning(
                self,
                "Invalid settings",
                "Experiment folder must not be empty.",
            )
            return

        self.settings.fooocus_url = url
        self.settings.fooocus_path = self.path_edit.text().strip()
        self.settings.experiment_directory = str(Path(experiment_directory).expanduser().resolve())
        self.settings.fooocus_auto_start = self.auto_start.isChecked()
        self.settings.queue_warning_threshold = self.queue_warning_threshold.value()
        self.accept()
