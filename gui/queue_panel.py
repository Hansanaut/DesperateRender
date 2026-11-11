from __future__ import annotations

import time
from typing import Sequence

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from gui.queue_job_details import (
    format_generation_configuration_tooltip,
    format_generation_job_tooltip,
)
from models.generation_configuration import GenerationConfiguration
from models.generation_job import GenerationJob
from services.adaptive_eta import AdaptiveEtaEstimator
from services.generation_queue import GenerationQueue
from services.runtime_estimator import RuntimeEstimator


class QueuePanel(QGroupBox):
    """Displays the planned generation queue and its controls."""

    # Connection waver: deliberately calm while Fooocus is starting.
    _CONNECT_PHASES = (
        ("#00E5FF", "#2878FF", "#7A4DFF"),
        ("#00D9FF", "#3D6FFF", "#8B4CFF"),
        ("#00C8FF", "#5262FF", "#A13FFF"),
        ("#18B5FF", "#704EFF", "#C53CFF"),
        ("#43C7FF", "#754FFF", "#C94AFF"),
        ("#16E2FF", "#3C73FF", "#8C61FF"),
    )

    # Success sequence: two fast blinks in ~1 second, followed by a
    # smooth 1-second fade from a dark cyan/green into the final color.
    _SUCCESS_BRIGHT = "#72FFD3"
    _SUCCESS_DIM = "#08766B"
    _SUCCESS_FINAL = "#27D7B0"
    _SUCCESS_BLINKS = (
        (_SUCCESS_BRIGHT, 250),
        (_SUCCESS_DIM, 250),
        (_SUCCESS_BRIGHT, 250),
        (_SUCCESS_DIM, 250),
    )
    _SUCCESS_FADE_INTERVAL_MS = 40
    _SUCCESS_FADE_DURATION_MS = 1000

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("mainPanel")

        self._connected_state = False
        self._connect_animating = False
        self._connect_phase = 0
        self._success_pulsing = False
        self._success_blink_index = 0
        self._success_blink_bright = True
        self._success_fade_elapsed_ms = 0

        self._success_fade_timer = QTimer(self)
        self._success_fade_timer.setInterval(self._SUCCESS_FADE_INTERVAL_MS)
        self._success_fade_timer.timeout.connect(self._advance_success_fade)

        self._connect_animation_timer = QTimer(self)
        self._connect_animation_timer.setInterval(320)
        self._connect_animation_timer.timeout.connect(
            self._advance_connect_animation
        )

        self._success_pulse_timer = QTimer(self)
        self._success_pulse_timer.setSingleShot(True)
        self._success_pulse_timer.timeout.connect(
            self._advance_success_pulse
        )

        self.create_ui()
        self.set_idle_state()

    def create_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Queue")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.jobs = QListWidget()
        self.jobs.setWordWrap(False)
        self.jobs.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.jobs.setUniformItemSizes(True)
        self.jobs.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.jobs.setMouseTracking(True)

        self.progress = QProgressBar()
        self.progress.setValue(0)

        self.progress_label = QLabel("0 / 0")
        self.current_job_label = QLabel("Current: —")
        self.estimate_label = QLabel("Estimate: —")
        self.remaining_label = QLabel("Remaining: —")

        self._job_estimates: dict[int, float] = {}
        self._job_baseline_estimates: dict[int, float] = {}
        self._job_resolutions: dict[int, tuple[int, int]] = {}
        self._adaptive_eta = AdaptiveEtaEstimator()
        self._completed_job_ids: set[int] = set()
        self._current_job_id: int | None = None
        self._current_job_started_at: float | None = None
        self._experiment_started_at: float | None = None
        self._estimated_total_seconds = 0.0
        self._estimated_total_storage = 0
        self._actual_total_seconds: float | None = None
        self._total_jobs = 0
        self._job_signatures: dict[int, str] = {}
        self._job_configurations: dict[int, GenerationConfiguration] = {}
        self._seed_labels_by_value: dict[int, str] = {}
        self._style_labels_by_name: dict[str, str] = {}
        self._base_model_labels_by_name: dict[str, str] = {}
        self._resolution_labels_by_size: dict[tuple[int, int], str] = {}

        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._refresh_remaining_time)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.setMinimumWidth(96)

        self.run_button = QPushButton("Run")
        self.run_button.setMinimumWidth(96)
        self.cancel_button = self.run_button

        self.pause_button = QPushButton("Pause")
        self.pause_button.setMinimumWidth(96)
        self.resume_button = self.pause_button

        button_layout.addWidget(self.connect_button, 1)
        button_layout.addWidget(self.run_button, 1)
        button_layout.addWidget(self.pause_button, 1)

        self.setMinimumWidth(330)

        layout.addWidget(QLabel("Generation Jobs"))
        layout.addWidget(self.jobs)
        layout.addWidget(self.progress)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.current_job_label)
        layout.addWidget(self.estimate_label)
        layout.addWidget(self.remaining_label)
        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Connection animation
    # ------------------------------------------------------------------

    def start_connect_animation(self) -> None:
        """Start the animated connection state and lock the button."""

        self._connect_animating = True
        self._connect_phase = 0
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting…")
        self._apply_connect_visual()
        self._connect_animation_timer.start()

    def stop_connect_animation(self, success: bool = False) -> None:
        """Finish connecting, optionally with a success celebration."""

        self._connect_animation_timer.stop()
        self._connect_animating = False

        if success:
            self._start_success_pulse()
            return

        self._success_pulse_timer.stop()
        self._success_pulsing = False
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        self.connect_button.setStyleSheet("")

    def _advance_connect_animation(self) -> None:
        if not self._connect_animating:
            return

        self._connect_phase = (
            self._connect_phase + 1
        ) % len(self._CONNECT_PHASES)
        self._apply_connect_visual()

    def _apply_connect_visual(self) -> None:
        first, second, third = self._CONNECT_PHASES[self._connect_phase]

        # A deliberately local animated style: the central theme remains
        # authoritative everywhere else. The moving gradient makes the
        # connection state feel alive without adding permanent neon.
        self.connect_button.setStyleSheet(
            "QPushButton#connectButton:disabled {"
            f"background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {first}, stop:0.48 {second}, stop:1 {third});"
            "color: #ffffff;"
            "border: 1px solid rgba(120, 230, 255, 190);"
            "border-radius: 7px;"
            "font-weight: 700;"
            "}"
        )

    def _start_success_pulse(self) -> None:
        """Two quick blinks, then a one-second fade into the final color."""

        self._success_pulsing = True
        self._success_blink_index = 0
        self._success_blink_bright = True
        self._success_fade_elapsed_ms = 0
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connected")
        self._apply_success_blink_visual()
        self._success_pulse_timer.start(self._SUCCESS_BLINKS[0][1])

    def _advance_success_pulse(self) -> None:
        if not self._success_pulsing:
            return

        self._success_blink_index += 1
        if self._success_blink_index >= len(self._SUCCESS_BLINKS):
            self._start_success_fade()
            return

        self._success_blink_bright = self._success_blink_index % 2 == 0
        self._apply_success_blink_visual()
        self._success_pulse_timer.start(
            self._SUCCESS_BLINKS[self._success_blink_index][1]
        )

    def _apply_success_blink_visual(self) -> None:
        color = (
            self._SUCCESS_BRIGHT
            if self._success_blink_bright
            else self._SUCCESS_DIM
        )
        self.connect_button.setStyleSheet(
            "QPushButton#connectButton:disabled {"
            f"background: {color};"
            "color: #031A17;"
            "border: 1px solid #8AFFD7;"
            "border-radius: 7px;"
            "font-weight: 800;"
            "}"
        )

    def _start_success_fade(self) -> None:
        """Fade smoothly from the dark success state to final green-cyan."""

        self._success_pulse_timer.stop()
        self._success_fade_elapsed_ms = 0
        self._apply_success_fade_visual(0.0)
        self._success_fade_timer.start()

    def _advance_success_fade(self) -> None:
        if not self._success_pulsing:
            self._success_fade_timer.stop()
            return

        self._success_fade_elapsed_ms += self._SUCCESS_FADE_INTERVAL_MS
        progress = min(
            1.0,
            self._success_fade_elapsed_ms / self._SUCCESS_FADE_DURATION_MS,
        )
        self._apply_success_fade_visual(progress)

        if progress >= 1.0:
            self._finish_success_pulse()

    def _apply_success_fade_visual(self, progress: float) -> None:
        def channel(start: int, end: int) -> int:
            return round(start + (end - start) * progress)

        start_rgb = (8, 118, 107)
        final_rgb = (39, 215, 176)
        rgb = tuple(
            channel(start, end)
            for start, end in zip(start_rgb, final_rgb)
        )
        color = "#%02X%02X%02X" % rgb

        self.connect_button.setStyleSheet(
            "QPushButton#connectButton:disabled {"
            f"background: {color};"
            "color: #031A17;"
            "border: 1px solid #70FFE0;"
            "border-radius: 7px;"
            "font-weight: 800;"
            "}"
        )

    def _finish_success_pulse(self) -> None:
        self._success_pulse_timer.stop()
        self._success_fade_timer.stop()
        self._success_pulsing = False
        self._success_blink_index = 0
        self._success_blink_bright = True
        self._success_fade_elapsed_ms = 0

        # Permanent connected state: cool cyan/green, no animation.
        self.connect_button.setStyleSheet(
            "QPushButton#connectButton {"
            "background: #27D7B0;"
            "color: #031A17;"
            "border: 1px solid #70FFE0;"
            "border-radius: 7px;"
            "font-weight: 800;"
            "}"
        )
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connected")

    # ------------------------------------------------------------------
    # Button states
    # ------------------------------------------------------------------

    def set_idle_state(self) -> None:
        self._connected_state = False
        if not self._connect_animating:
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Connect")
        self.run_button.setText("Run")
        self.run_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)

    def set_preview_estimate(
        self,
        seconds: float,
        storage_bytes: int,
    ) -> None:
        self.estimate_label.setText(
            "Estimate: "
            f"~{self._format_duration(seconds)}  |  "
            f"~{self._format_storage(storage_bytes)}"
        )

    def clear_preview_estimate(self) -> None:
        self.estimate_label.setText("Estimate: —")
        self.remaining_label.setText("Remaining: —")
        self._stop_eta_timer()

    def set_connected_state(self) -> None:
        self._connected_state = True
        self.stop_connect_animation(success=True)
        self.run_button.setText("Run")
        self.run_button.setEnabled(self.jobs.count() > 0)
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)

    def set_running_state(self) -> None:
        self._connected_state = True
        self.stop_connect_animation(success=False)
        self.connect_button.setEnabled(False)
        self.run_button.setText("Cancel")
        self.run_button.setEnabled(True)
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(True)

    def set_paused_state(self) -> None:
        self.connect_button.setEnabled(False)
        self.run_button.setText("Cancel")
        self.run_button.setEnabled(True)
        self.pause_button.setText("Resume")
        self.pause_button.setEnabled(True)

    def set_cancelling_state(self) -> None:
        self.connect_button.setEnabled(False)
        self.run_button.setText("Cancel")
        self.run_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def set_preview_configurations(
        self,
        configurations: Sequence[GenerationConfiguration],
        style_pool: Sequence[str] | None = None,
    ) -> None:
        configurations = list(configurations)

        self.jobs.clear()
        self._job_signatures.clear()
        self._seed_labels_by_value.clear()
        self._style_labels_by_name.clear()
        self._base_model_labels_by_name.clear()

        all_styles = sorted(
            set(style_pool or ())
            or {
                style_name
                for configuration in configurations
                for style_name in configuration.styles
            },
            key=str.casefold,
        )
        self._style_labels_by_name = {
            style_name: f"STY#{number}"
            for number, style_name in enumerate(all_styles, start=1)
        }

        all_base_models = sorted(
            {
                configuration.base_model
                for configuration in configurations
                if configuration.base_model
            },
            key=str.casefold,
        )
        self._base_model_labels_by_name = {
            model_name: f"BM{number}"
            for number, model_name in enumerate(all_base_models, start=1)
        }

        self._resolution_labels_by_size = {}
        for configuration in configurations:
            size = (configuration.width, configuration.height)
            if size not in self._resolution_labels_by_size:
                self._resolution_labels_by_size[size] = (
                    f"R{len(self._resolution_labels_by_size) + 1}"
                )
        if len(self._resolution_labels_by_size) < 2:
            self._resolution_labels_by_size.clear()

        for index, configuration in enumerate(
            configurations,
            start=1,
        ):
            signature = (
                self._format_block_variant_signature(configuration.prompt_block_variant_id)
                if configuration.prompt_block_variant_id
                else self.format_prompt_signature(
                    configuration.positive_prompt_slots,
                    configuration.negative_prompt_slots,
                )
            )
            self._job_signatures[index] = signature

            for style_name in configuration.styles:
                self._register_style_label(style_name)

            if (
                configuration.seed is not None
                and self._seed_key(configuration.seed) not in self._seed_labels_by_value
            ):
                self._seed_labels_by_value[self._seed_key(configuration.seed)] = (
                    f"S{len(self._seed_labels_by_value) + 1}"
                )

            self.jobs.addItem(
                self._format_preview_configuration(
                    index,
                    configuration,
                    self._seed_labels_by_value.get(
                        self._seed_key(configuration.seed),
                        f"S{index}",
                    ) if configuration.seed is not None else None,
                )
            )
            self.jobs.item(self.jobs.count() - 1).setToolTip(
                format_generation_configuration_tooltip(
                    configuration,
                    job_id=index,
                    status="PLANNED",
                )
            )

        total = len(configurations)

        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(0)
        self.progress_label.setText(f"0 / {total}")

        estimate = RuntimeEstimator.estimate_configurations(
            configurations
        )
        self.set_preview_estimate(
            estimate.seconds,
            estimate.storage_bytes,
        )

        self.run_button.setEnabled(
            self.connect_button.isEnabled()
            and self.jobs.count() > 0
            and self._looks_connected()
        )

    def set_preview_error(self, message: str) -> None:
        self.jobs.clear()
        self.jobs.addItem(f"Preview error: {message}")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress_label.setText("invalid")
        self.clear_preview_estimate()
        self.run_button.setEnabled(False)

    def _looks_connected(self) -> bool:
        return self._connected_state

    def set_queue(
        self,
        queue: GenerationQueue,
        configurations: Sequence[GenerationConfiguration] | None = None,
    ) -> None:
        """Start a fresh experiment and freeze its original estimate."""
        self._stop_eta_timer()
        self._job_estimates.clear()
        self._job_baseline_estimates.clear()
        self._job_resolutions.clear()
        self._adaptive_eta.reset()
        self._completed_job_ids.clear()
        self._current_job_id = None
        self._current_job_started_at = None
        self._experiment_started_at = None
        self._estimated_total_seconds = 0.0
        self._estimated_total_storage = 0
        self._actual_total_seconds = None

        self._job_signatures.clear()
        self._job_configurations.clear()
        self._job_rows = {}
        self.jobs.clear()

        # The runtime queue contains FooocusRequest objects. Prompt-slot
        # provenance lives on the original GenerationConfiguration, not on
        # FooocusRequest, so keep the already-built configurations alongside
        # the runtime jobs when switching from preview to execution.
        if configurations is not None:
            configurations = list(configurations)
            self._seed_labels_by_value.clear()
            for configuration in configurations:
                if (
                    configuration.seed is not None
                    and self._seed_key(configuration.seed) not in self._seed_labels_by_value
                ):
                    self._seed_labels_by_value[self._seed_key(configuration.seed)] = (
                        f"S{len(self._seed_labels_by_value) + 1}"
                    )

        if configurations is not None:
            self._resolution_labels_by_size = {}
            for configuration in configurations:
                size = (configuration.width, configuration.height)
                if size not in self._resolution_labels_by_size:
                    self._resolution_labels_by_size[size] = (
                        f"R{len(self._resolution_labels_by_size) + 1}"
                    )
        else:
            self._resolution_labels_by_size = {}
            for queued_job in queue.jobs:
                size = (
                    queued_job.request.width or 1024,
                    queued_job.request.height or 768,
                )
                if size not in self._resolution_labels_by_size:
                    self._resolution_labels_by_size[size] = (
                        f"R{len(self._resolution_labels_by_size) + 1}"
                    )
            all_models = sorted(
                {
                    queued_job.request.base_model
                    for queued_job in queue.jobs
                    if queued_job.request.base_model
                },
                key=str.casefold,
            )
            self._base_model_labels_by_name = {
                model_name: f"BM{number}"
                for number, model_name in enumerate(all_models, start=1)
            }

        if len(self._resolution_labels_by_size) < 2:
            self._resolution_labels_by_size.clear()

        for index, job in enumerate(queue.jobs):
            configuration = (
                configurations[index]
                if configurations is not None and index < len(configurations)
                else None
            )
            if configuration is not None:
                self._job_signatures[job.job_id] = (
                    self._format_block_variant_signature(configuration.prompt_block_variant_id)
                    if configuration.prompt_block_variant_id
                    else self.format_prompt_signature(
                        configuration.positive_prompt_slots,
                        configuration.negative_prompt_slots,
                    )
                )
            else:
                self._job_signatures[job.job_id] = (
                    self._format_block_variant_signature(job.prompt_block_variant_id)
                    if job.prompt_block_variant_id
                    else "<no prompts>"
                )
            if configuration is not None:
                self._job_configurations[job.job_id] = configuration
                tooltip = format_generation_configuration_tooltip(
                    configuration,
                    job_id=job.job_id,
                    status=job.status.value,
                )
                self.jobs.addItem(self._format_job(job))
                self.jobs.item(self.jobs.count() - 1).setToolTip(tooltip)
            else:
                self._add_job_item(job)
            self._job_rows[job.job_id] = self.jobs.count() - 1
            baseline = self._estimate_job_seconds(job)
            width = job.request.width or 1024
            height = job.request.height or 768
            self._job_baseline_estimates[job.job_id] = baseline
            self._job_resolutions[job.job_id] = (width, height)
            self._job_estimates[job.job_id] = self._adaptive_eta.estimate(
                baseline, width, height
            )
            if job.status.value == "COMPLETED":
                self._completed_job_ids.add(job.job_id)

        total = len(queue)
        self._total_jobs = total

        # This is the immutable baseline shown as "Estimate" for the whole
        # experiment.  Adaptive observations may change Remaining/Projection,
        # but never this value.
        self._estimated_total_seconds = sum(
            self._job_baseline_estimates.values()
        )
        self._estimated_total_storage = self._estimate_remaining_storage()

        self.estimate_label.setText(
            "Estimated: ~"
            f"{self._format_duration(self._estimated_total_seconds)}  |  "
            f"~{self._format_storage(self._estimated_total_storage)}"
        )

        self.progress.setRange(0, max(total, 1))
        completed = len(self._completed_job_ids)
        self.progress.setValue(min(completed, total))
        self.progress_label.setText(f"{completed} / {total}")
        self.remaining_label.setText(
            "Remaining: ~"
            f"{self._format_duration(sum(self._job_estimates.values()))}"
            if total
            else "Remaining: —"
        )

    def add_job(
        self,
        job: GenerationJob,
        total: int | None = None,
    ) -> None:
        self._job_signatures.setdefault(
            job.job_id,
            self._format_block_variant_signature(job.prompt_block_variant_id) if job.prompt_block_variant_id else "<no prompts>",
        )
        self._add_job_item(job)
        baseline = self._estimate_job_seconds(job)
        width = job.request.width or 1024
        height = job.request.height or 768
        self._job_baseline_estimates[job.job_id] = baseline
        self._job_resolutions[job.job_id] = (width, height)
        self._job_estimates[job.job_id] = self._adaptive_eta.estimate(
            baseline, width, height
        )

        if self._experiment_started_at is None:
            self._estimated_total_seconds = sum(
                self._job_baseline_estimates.values()
            )
            self._estimated_total_storage = self._estimate_remaining_storage()
            self.estimate_label.setText(
                "Estimated: ~"
                f"{self._format_duration(self._estimated_total_seconds)}  |  "
                f"~{self._format_storage(self._estimated_total_storage)}"
            )

        if total is None:
            total = self.jobs.count()
        self._total_jobs = total

        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(min(len(self._completed_job_ids), total))
        self.progress_label.setText(
            f"{len(self._completed_job_ids)} / {total}"
        )

    def update_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self._total_jobs = total

        completed = max(
            len(self._completed_job_ids),
            current - 1,
        )
        completed = min(completed, total)

        self.progress.setRange(0, max(total, 1) * 1000)
        self.progress.setValue(completed * 1000)
        self.progress_label.setText(f"{completed} / {total}")

        if 0 < current <= self.jobs.count():
            self.jobs.setCurrentRow(current - 1)

    def update_job_status(self, job: GenerationJob) -> None:
        row = getattr(self, "_job_rows", {}).get(job.job_id, job.job_id - 1)

        if 0 <= row < self.jobs.count():
            item = self.jobs.item(row)
            item.setText(self._format_job(job))
            configuration = self._job_configurations.get(job.job_id)
            if configuration is not None:
                item.setToolTip(
                    format_generation_configuration_tooltip(
                        configuration,
                        job_id=job.job_id,
                        status=job.status.value,
                    )
                )
            else:
                item.setToolTip(format_generation_job_tooltip(job))

        if job.status.value == "RUNNING":
            if job.job_id not in self._job_baseline_estimates:
                baseline = self._estimate_job_seconds(job)
                width = job.request.width or 1024
                height = job.request.height or 768
                self._job_baseline_estimates[job.job_id] = baseline
                self._job_resolutions[job.job_id] = (width, height)
                self._job_estimates[job.job_id] = self._adaptive_eta.estimate(
                    baseline, width, height
                )
            self._current_job_id = job.job_id
            self._current_job_started_at = time.monotonic()
            if self._experiment_started_at is None:
                self._experiment_started_at = self._current_job_started_at
            total = max(self._total_jobs, self.jobs.count(), 1)
            completed = min(len(self._completed_job_ids), total)
            self.progress.setRange(0, total * 1000)
            self.progress.setValue(completed * 1000)
            self.current_job_label.setText(
                f"Current: #{job.job_id} — RUNNING"
            )
            self._start_eta_timer()
            self._refresh_remaining_time()
            return

        if job.status.value in {"COMPLETED", "FAILED", "CANCELLED"}:
            completed_runtime: float | None = None
            if (
                job.status.value == "COMPLETED"
                and self._current_job_id == job.job_id
                and self._current_job_started_at is not None
            ):
                completed_runtime = max(
                    0.0, time.monotonic() - self._current_job_started_at
                )
                width = job.request.width or 1024
                height = job.request.height or 768
                baseline = self._job_baseline_estimates.get(
                    job.job_id, self._estimate_job_seconds(job)
                )
                self._adaptive_eta.observe(
                    width, height, baseline, completed_runtime
                )
                self._refresh_pending_estimates(job.job_id)
                if self._experiment_started_at is not None:
                    self._actual_total_seconds = max(
                        0.0,
                        time.monotonic() - self._experiment_started_at,
                    )

            if job.status.value == "COMPLETED":
                self._completed_job_ids.add(job.job_id)
            else:
                self._completed_job_ids.discard(job.job_id)

            if self._current_job_id == job.job_id:
                self._current_job_id = None
                self._current_job_started_at = None

            self.current_job_label.setText(
                f"Current: #{job.job_id} — {job.status.value}"
            )

            total = self.jobs.count()
            self._total_jobs = total
            completed = min(len(self._completed_job_ids), total)
            self.progress.setRange(0, max(total, 1))
            self.progress.setValue(completed)
            self.progress_label.setText(f"{completed} / {total}")

            self._refresh_remaining_time()

            if not any(
                self.jobs.item(index).text().endswith("— RUNNING")
                for index in range(self.jobs.count())
            ):
                self._stop_eta_timer()

    def _add_job_item(self, job: GenerationJob) -> None:
        """Add one queue item and attach its complete hover details."""

        self.jobs.addItem(self._format_job(job))
        queue_item = self.jobs.item(self.jobs.count() - 1)
        queue_item.setToolTip(format_generation_job_tooltip(job))

    def _estimate_job_seconds(self, job: GenerationJob) -> float:
        width = job.request.width or 1024
        height = job.request.height or 768
        return RuntimeEstimator.estimate_image(width, height).seconds

    def _refresh_pending_estimates(self, completed_job_id: int) -> None:
        """Apply the latest current-experiment factor to future jobs."""

        for job_id, baseline in self._job_baseline_estimates.items():
            if job_id <= completed_job_id or job_id in self._completed_job_ids:
                continue
            resolution = self._job_resolutions.get(job_id)
            if resolution is None:
                continue
            width, height = resolution
            self._job_estimates[job_id] = self._adaptive_eta.estimate(
                baseline, width, height
            )

    def _remaining_seconds(self) -> float:
        remaining = 0.0

        for job_id, seconds in self._job_estimates.items():
            if job_id in self._completed_job_ids:
                continue
            if self._current_job_id is not None and job_id < self._current_job_id:
                continue
            remaining += seconds

        if (
            self._current_job_id is not None
            and self._current_job_started_at is not None
        ):
            elapsed = max(
                0.0,
                time.monotonic() - self._current_job_started_at,
            )
            current_estimate = self._job_estimates.get(
                self._current_job_id,
                0.0,
            )
            remaining -= min(elapsed, current_estimate)

        return max(0.0, remaining)

    def _update_time_based_progress(self) -> None:
        total = max(self._total_jobs, self.jobs.count(), 0)
        if total <= 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            return

        completed = min(len(self._completed_job_ids), total)

        if (
            self._current_job_id is None
            or self._current_job_started_at is None
        ):
            self.progress.setRange(0, max(total, 1))
            self.progress.setValue(completed)
            return

        fraction = float(completed)

        elapsed = max(
            0.0,
            time.monotonic() - self._current_job_started_at,
        )
        estimate = self._job_estimates.get(self._current_job_id, 0.0)
        if estimate > 0:
            fraction += min(elapsed / estimate, 0.999)

        self.progress.setRange(0, total * 1000)
        self.progress.setValue(
            min(int(round(fraction * 1000)), total * 1000)
        )

    def _estimate_remaining_storage(self) -> int:
        """Estimate storage for unfinished jobs from the runtime calibration."""
        total = 0
        for job_id in self._job_estimates:
            if job_id in self._completed_job_ids:
                continue
            job_row = job_id - 1
            if 0 <= job_row < self.jobs.count():
                # Queue items do not retain the request object, so use the
                # baseline resolution captured for adaptive ETA.
                resolution = self._job_resolutions.get(job_id)
                if resolution is not None:
                    width, height = resolution
                    total += RuntimeEstimator.estimate_image(width, height).storage_bytes
        return total

    def _refresh_remaining_time(self) -> None:
        self._update_time_based_progress()

        if self._experiment_started_at is None:
            return

        now = time.monotonic()
        elapsed_total = max(
            0.0,
            now - self._experiment_started_at,
        )

        total = max(self._total_jobs, self.jobs.count(), 0)
        completed = len(self._completed_job_ids)

        if total > 0 and completed >= total:
            actual = self._actual_total_seconds
            if actual is None:
                actual = elapsed_total
            self._actual_total_seconds = actual

            difference = self._estimated_total_seconds - actual
            if difference >= 0:
                result = (
                    f"Finished — {self._format_duration(difference)} ahead"
                )
            else:
                result = (
                    f"Finished — {self._format_duration(abs(difference))} behind"
                )
            self.remaining_label.setText(
                "Actual Time: "
                f"{self._format_duration(actual)}  |  {result}"
            )
            return

        remaining = self._remaining_seconds()
        projected_total = elapsed_total + remaining
        delta = self._estimated_total_seconds - projected_total

        if delta >= 0:
            timing = f"Ahead by {self._format_duration(delta)}"
        else:
            timing = f"Behind by {self._format_duration(abs(delta))}"

        self.remaining_label.setText(
            "Remaining: ~"
            f"{self._format_duration(remaining)}  |  {timing}"
        )

    def _start_eta_timer(self) -> None:
        if not self._eta_timer.isActive():
            self._eta_timer.start()

    def _stop_eta_timer(self) -> None:
        if self._eta_timer.isActive():
            self._eta_timer.stop()

    @staticmethod
    def _format_block_variant_signature(signature: str) -> str:
        """Display prompt-block IDs in stable natural order, without changing prompts."""
        import re

        parts = [part.strip() for part in str(signature).split("+") if part.strip()]
        def sort_key(part: str):
            match = re.fullmatch(r"([A-Za-z]+)(\d+)", part)
            if match:
                return (0, match.group(1).casefold(), int(match.group(2)), part.casefold())
            return (1, part.casefold(), 0, part.casefold())
        return "+".join(sorted(parts, key=sort_key))

    def _seed_label_for_value(self, seed: object) -> str:
        """Return a stable label for a seed, registering it if needed."""
        key = self._seed_key(seed)
        if key not in self._seed_labels_by_value:
            self._seed_labels_by_value[key] = f"S{len(self._seed_labels_by_value) + 1}"
        return self._seed_labels_by_value[key]

    @staticmethod
    def format_prompt_signature(
        positive_slots: Sequence[int],
        negative_slots: Sequence[int],
    ) -> str:
        parts = [
            *(f"PP{slot_id}" for slot_id in positive_slots),
            *(f"NP{slot_id}" for slot_id in negative_slots),
        ]
        return "+".join(parts) or "<no prompts>"

    def _format_preview_configuration(
        self,
        job_id: int,
        configuration: GenerationConfiguration,
        seed_label: str | None = None,
    ) -> str:
        signature = (
            self._format_block_variant_signature(configuration.prompt_block_variant_id)
            if configuration.prompt_block_variant_id
            else QueuePanel.format_prompt_signature(
                configuration.positive_prompt_slots,
                configuration.negative_prompt_slots,
            )
        )
        tokens = [f"#{job_id}", signature]
        size = (configuration.width, configuration.height)
        resolution_label = self._resolution_labels_by_size.get(size)
        if resolution_label:
            tokens.append(resolution_label)

        base_model_label = self._format_base_model_label(
            configuration.base_model,
            self._base_model_labels_by_name,
        )
        if base_model_label:
            tokens.append(base_model_label)

        if seed_label is not None:
            tokens.append(seed_label)

        for style_name in configuration.styles:
            self._register_style_label(style_name)
        style_labels = self._format_style_labels(
            configuration.styles,
            self._style_labels_by_name,
        )
        if style_labels:
            tokens.append(style_labels)

        return " ".join(tokens + ["—", "PLANNED"])

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))

        if total_seconds < 60:
            return f"{total_seconds} s"

        minutes, remaining_seconds = divmod(total_seconds, 60)

        if minutes < 60:
            if remaining_seconds == 0:
                return f"{minutes} min"
            return f"{minutes} min {remaining_seconds} s"

        hours, remaining_minutes = divmod(minutes, 60)

        if remaining_minutes == 0:
            return f"{hours} h"

        return f"{hours} h {remaining_minutes} min"

    @staticmethod
    def _format_storage(storage_bytes: int) -> str:
        value = max(0, storage_bytes)

        if value < 1024 * 1024:
            return f"{value / 1024:.0f} KB"
        if value < 1024 * 1024 * 1024:
            return f"{value / (1024 * 1024):.1f} MB"
        return f"{value / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def _seed_key(seed: object) -> str:
        """Normalize seed values shared between configurations and requests."""
        return str(seed).strip()

    def _format_job(self, job: GenerationJob) -> str:
        signature = self._job_signatures.get(
            job.job_id,
            self._format_block_variant_signature(job.prompt_block_variant_id) if job.prompt_block_variant_id else "<no prompts>",
        )
        tokens = [f"#{job.job_id}", signature]

        size = (
            job.request.width or 1024,
            job.request.height or 768,
        )
        resolution_label = self._resolution_labels_by_size.get(size)
        if resolution_label:
            tokens.append(resolution_label)

        base_model_label = self._format_base_model_label(
            job.request.base_model,
            self._base_model_labels_by_name,
        )
        if base_model_label:
            tokens.append(base_model_label)

        if job.request.seed is not None:
            tokens.append(self._seed_label_for_value(job.request.seed))

        for style_name in job.request.styles:
            self._register_style_label(style_name)
        style_labels = self._format_style_labels(
            job.request.styles,
            self._style_labels_by_name,
        )
        if style_labels:
            tokens.append(style_labels)

        return " ".join(tokens + ["—", job.status.value])

    def _register_style_label(self, style_name: str) -> str:
        if style_name not in self._style_labels_by_name:
            self._style_labels_by_name[style_name] = (
                f"STY#{len(self._style_labels_by_name) + 1}"
            )
        return self._style_labels_by_name[style_name]

    @staticmethod
    def _format_style_labels(
        styles: Sequence[str],
        labels_by_name: dict[str, str],
    ) -> str:
        return "".join(
            labels_by_name[style_name]
            for style_name in styles
            if style_name in labels_by_name
        )

    @staticmethod
    def _format_base_model_label(
        base_model: str | None,
labels_by_name: dict[str, str],
    ) -> str:
        if not base_model:
            return ""
        # Model filenames are technical runtime details, not queue labels.
        # Never fall back to exposing the full safetensors filename.
        label = labels_by_name.get(base_model, "BM1")
        return f"+{label}"
