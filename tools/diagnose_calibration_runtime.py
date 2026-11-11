from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.fooocus_settings_dialog import FooocusSettingsDialog
from models.application_settings import ApplicationSettings
from services.calibration_service import CalibrationService

print("=== DESPERATE RENDER CALIBRATION RUNTIME ===")
print(f"Dialog source:  {Path(__import__('gui.fooocus_settings_dialog', fromlist=['__file__']).__file__).resolve()}")
print(f"Service source: {Path(__import__('services.calibration_service', fromlist=['__file__']).__file__).resolve()}")
settings = ApplicationSettings()
print(f"Settings path:  {settings.settings_path}")
print(f"Stored points:  {settings.calibration_profile.point_count if settings.calibration_profile else 0}")
print(f"Calibration sizes: {CalibrationService.DEFAULT_SIZES}")
