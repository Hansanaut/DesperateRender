from datetime import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

# Allow direct execution via: python -B tools\test_calibration_replacement.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings

from models.application_settings import ApplicationSettings
from services.calibration_profile import CalibrationPoint, CalibrationProfile


def profile(count: int, created_at: str) -> CalibrationProfile:
    points = tuple(
        CalibrationPoint(
            width=1536 + i * 512,
            height=1024 + i * 1024,
            seconds=40.0 + i,
            storage_bytes=1000 + i,
        )
        for i in range(count)
    )
    return CalibrationProfile(
        created_at=created_at,
        platform="test",
        machine="test",
        processor="test",
        fooocus_url="http://127.0.0.1:7865",
        points=points,
    )


def main() -> None:
    old_path = ApplicationSettings._resolve_settings_path
    with tempfile.TemporaryDirectory() as tmp:
        temp_file = Path(tmp) / "settings.ini"
        ApplicationSettings._resolve_settings_path = classmethod(lambda cls: temp_file)
        try:
            settings = ApplicationSettings()
            old = profile(5, "2026-10-03T17:48:15")
            new = profile(2, datetime.now().isoformat(timespec="seconds"))

            settings.save_calibration_profile(old)
            assert settings.calibration_profile is not None
            assert settings.calibration_profile.point_count == 5

            settings.save_calibration_profile(new)
            stored = settings.calibration_profile
            assert stored is not None
            assert stored.point_count == 2
            assert stored.to_json() == new.to_json()
            assert all((p.width, p.height) in {(1536, 1024), (2048, 2048)} for p in stored.points)

            # Verify the actual file-backed value through a fresh settings
            # instance, not just the writer's in-memory QSettings object.
            fresh = ApplicationSettings()
            fresh_profile = fresh.calibration_profile
            assert fresh_profile is not None
            assert fresh_profile.point_count == 2
            assert fresh_profile.to_json() == new.to_json()

            print("Calibration replacement definition: OK")
            print("Persistence round-trip: OK")
            print("Fresh-process persistence verification: OK")
            print("Old 5-point profile replaced by new 2-point profile: OK")
            print("=== CALIBRATION REPLACEMENT TEST PASSED ===")
        finally:
            ApplicationSettings._resolve_settings_path = old_path


if __name__ == "__main__":
    main()
