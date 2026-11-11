from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QCoreApplication

from models.application_settings import ApplicationSettings
from services.calibration_profile import CalibrationPoint, CalibrationProfile


def main() -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    old_resolver = ApplicationSettings._resolve_settings_path
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.ini"
        ApplicationSettings._resolve_settings_path = classmethod(lambda cls: path)
        try:
            old_settings = ApplicationSettings()
            old_profile = CalibrationProfile.create(
                "http://127.0.0.1:7865",
                [
                    CalibrationPoint(480, 320, 10.0, 100),
                    CalibrationPoint(1024, 768, 20.0, 200),
                    CalibrationPoint(1280, 768, 30.0, 300),
                    CalibrationPoint(1536, 1024, 40.0, 400),
                    CalibrationPoint(2048, 2048, 120.0, 500),
                ],
            )
            old_settings.save_calibration_profile(old_profile)

            new_profile = CalibrationProfile.create(
                "http://127.0.0.1:7865",
                [
                    CalibrationPoint(1536, 1024, 41.0, 410),
                    CalibrationPoint(2048, 2048, 121.0, 510),
                ],
            )

            # This mirrors the live dialog: save with a fresh settings object,
            # then verify with another fresh object.
            writer = ApplicationSettings()
            writer.save_calibration_profile(new_profile)
            verifier = ApplicationSettings()
            stored = verifier.calibration_profile
            assert stored is not None
            assert stored.to_json() == new_profile.to_json()
            assert stored.point_count == 2
            assert {(p.width, p.height) for p in stored.points} == {
                (1536, 1024), (2048, 2048)
            }

            print("Fresh live-GUI writer: OK")
            print("Fresh live-GUI verifier: OK")
            print("5-point profile replaced by 2-point profile: OK")
            print("=== GUI CALIBRATION PERSISTENCE TEST PASSED ===")
        finally:
            ApplicationSettings._resolve_settings_path = old_resolver


if __name__ == "__main__":
    main()
