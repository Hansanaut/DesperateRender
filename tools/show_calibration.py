from __future__ import annotations

import sys
from pathlib import Path

# Running `python tools/show_calibration.py` sets sys.path[0] to `tools/`.
# Add the project root explicitly so package imports work cross-platform.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.application_settings import ApplicationSettings


def _format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def main() -> None:
    settings = ApplicationSettings()
    profile = settings.calibration_profile

    print("=== DESPERATE RENDER CALIBRATION ===")
    print(f"Settings:    {settings.settings_path}")

    if profile is None:
        print("Status:      NOT CALIBRATED")
        print("No calibration profile is stored for this installation.")
        return

    print("Status:      CALIBRATED")
    print(f"Created:     {profile.created_at}")
    print(f"Platform:    {profile.platform}")
    print(f"Machine:     {profile.machine}")
    print(f"Processor:   {profile.processor}")
    print(f"Fooocus:     {profile.fooocus_url}")
    print()
    print("Measured points:")

    for point in sorted(profile.points, key=lambda item: item.width * item.height):
        pixels = point.width * point.height
        print(
            f"  {point.width:4d} x {point.height:<4d}"
            f"  {point.seconds:8.3f} s"
            f"  {_format_bytes(point.storage_bytes):>10}"
            f"  {pixels:>12,}"
        )

    print()
    print(
        "These are the actual measured calibration values currently used "
        "as the basis for DR runtime/storage estimates."
    )


if __name__ == "__main__":
    main()
