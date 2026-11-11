from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import QSettings, QStandardPaths

from services.calibration_profile import CalibrationProfile
from services.runtime_estimator import RuntimeEstimator


class ApplicationSettings:
    """Persistent, platform-neutral DESPERATE RENDER application settings."""

    ORGANIZATION = "Desperate Engineering Industries"
    APPLICATION = "Desperate Render"

    DEFAULT_FOOOCUS_URL = "http://127.0.0.1:7865"
    DEFAULT_QUEUE_WARNING_THRESHOLD = 300
    DEFAULT_EXPERIMENT_DIRECTORY = str(Path.cwd() / "experiments")

    def __init__(self) -> None:
        self._settings_path = self._resolve_settings_path()
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)

        self._settings = QSettings(
            str(self._settings_path),
            QSettings.Format.IniFormat,
        )
        self._settings.sync()

        RuntimeEstimator.set_calibration(self.calibration_profile)

    @classmethod
    def _resolve_settings_path(cls) -> Path:
        """Return the canonical per-application settings path.

        QStandardPaths gives us the platform-specific user configuration root:
        - Windows: typically %LOCALAPPDATA%
        - Linux: typically ~/.config
        - macOS: typically ~/Library/Application Support

        DR then adds its own organization/application directories so settings
        cannot collide with unrelated Qt applications.
        """
        base_dir = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
        )

        # On some platforms Qt already includes organization/application in
        # AppConfigLocation once QApplication has been configured. On a
        # standalone tools invocation it may instead return the user config
        # root. Handle both forms so GUI and CLI tools use exactly the same
        # canonical settings file.
        if (
            base_dir.name == cls.APPLICATION
            and base_dir.parent.name == cls.ORGANIZATION
        ):
            canonical_dir = base_dir
        else:
            canonical_dir = base_dir / cls.ORGANIZATION / cls.APPLICATION

        canonical_path = canonical_dir / "settings.ini"

        # Migrate older DR locations. The duplicated path is included because
        # an earlier implementation appended organization/application even
        # when Qt had already supplied those components. Prefer that path when
        # it exists so an actually calibrated installation is not discarded.
        legacy_paths = [
            base_dir / cls.ORGANIZATION / cls.APPLICATION / "settings.ini",
            base_dir / "settings.ini",
        ]

        if not canonical_path.exists():
            for legacy_path in legacy_paths:
                if legacy_path == canonical_path:
                    continue
                if legacy_path.exists() and legacy_path.is_file():
                    canonical_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(legacy_path, canonical_path)
                    except OSError:
                        pass
                    break

        return canonical_path

    @property
    def settings_path(self) -> Path:
        """Canonical settings.ini path used by DESPERATE RENDER."""
        return self._settings_path

    @property
    def experiment_directory(self) -> str:
        value = str(
            self._settings.value(
                "experiments/directory",
                self.DEFAULT_EXPERIMENT_DIRECTORY,
            )
        ).strip()
        return value or self.DEFAULT_EXPERIMENT_DIRECTORY

    @experiment_directory.setter
    def experiment_directory(self, value: str) -> None:
        directory = str(value).strip()
        if not directory:
            directory = self.DEFAULT_EXPERIMENT_DIRECTORY
        self._settings.setValue("experiments/directory", directory)
        self._settings.sync()

    @property
    def fooocus_url(self) -> str:
        return str(
            self._settings.value("fooocus/url", self.DEFAULT_FOOOCUS_URL)
        ).strip() or self.DEFAULT_FOOOCUS_URL

    @fooocus_url.setter
    def fooocus_url(self, value: str) -> None:
        self._settings.setValue("fooocus/url", value.strip())
        self._settings.sync()

    @property
    def fooocus_path(self) -> str:
        return str(self._settings.value("fooocus/path", "")).strip()

    @fooocus_path.setter
    def fooocus_path(self, value: str) -> None:
        self._settings.setValue("fooocus/path", value.strip())
        self._settings.sync()

    @property
    def fooocus_auto_start(self) -> bool:
        value = self._settings.value("fooocus/auto_start", True)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    @fooocus_auto_start.setter
    def fooocus_auto_start(self, value: bool) -> None:
        self._settings.setValue("fooocus/auto_start", bool(value))
        self._settings.sync()

    @property
    def queue_warning_threshold(self) -> int:
        value = self._settings.value(
            "queue/warning_threshold",
            self.DEFAULT_QUEUE_WARNING_THRESHOLD,
        )
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            threshold = self.DEFAULT_QUEUE_WARNING_THRESHOLD
        return max(1, threshold)

    @queue_warning_threshold.setter
    def queue_warning_threshold(self, value: int) -> None:
        threshold = max(1, int(value))
        self._settings.setValue("queue/warning_threshold", threshold)
        self._settings.sync()

    @property
    def calibration_profile(self) -> CalibrationProfile | None:
        raw = str(self._settings.value("calibration/profile", "")).strip()
        if not raw:
            return None
        try:
            return CalibrationProfile.from_json(raw)
        except (TypeError, ValueError, KeyError):
            return None

    def save_calibration_profile(self, profile: CalibrationProfile) -> None:
        """Replace the active calibration atomically and verify the round-trip."""
        # Always remove the previous profile first. This makes a calibration
        # run a replacement, never an accumulation of historical points.
        self._settings.remove("calibration/profile")
        self._settings.sync()

        self._settings.setValue("calibration/profile", profile.to_json())
        self._settings.sync()

        # Verify that the exact settings backend we just wrote can read the
        # new profile back immediately. A silent persistence failure must not
        # be reported to the user as a successful calibration.
        stored = self.calibration_profile
        if stored is None:
            raise RuntimeError("Calibration profile could not be persisted.")
        if stored.to_json() != profile.to_json():
            raise RuntimeError("Persisted calibration profile does not match the new profile.")

        # Verify the actual file-backed settings from a fresh QSettings
        # instance as well. The live application instance can otherwise see
        # its own in-memory value even when another process would still read
        # the previous value from disk.
        disk_settings = QSettings(
            str(self._settings_path),
            QSettings.Format.IniFormat,
        )
        disk_settings.sync()
        disk_raw = str(disk_settings.value("calibration/profile", "")).strip()
        if not disk_raw:
            raise RuntimeError("Calibration profile was not written to disk.")
        disk_profile = CalibrationProfile.from_json(disk_raw)
        if disk_profile.to_json() != profile.to_json():
            raise RuntimeError("Calibration profile on disk does not match the new profile.")

    @calibration_profile.setter
    def calibration_profile(self, value: CalibrationProfile | None) -> None:
        if value is None:
            self._settings.remove("calibration/profile")
            self._settings.sync()
            RuntimeEstimator.set_calibration(None)
            return
        self.save_calibration_profile(value)
        RuntimeEstimator.set_calibration(value)
