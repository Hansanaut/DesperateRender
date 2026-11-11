from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    print("=== DESPERATE RENDER SETTINGS DIAGNOSTICS ===")
    print()

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from models.application_settings import ApplicationSettings

        settings = ApplicationSettings()
        settings._settings.sync()

        print(f"Canonical settings path: {settings.settings_path}")
        print(f"Exists:                   {settings.settings_path.exists()}")
        print(f"Parent directory:        {settings.settings_path.parent}")
        print()

        print("=== QSETTINGS ===")
        print(f"Status:                   {settings._settings.status().name}")
        print(f"All keys:                 {settings._settings.allKeys()}")
        print()

        print("=== CALIBRATION ===")
        print(
            f"Contains key:             "
            f"{settings._settings.contains('calibration/profile')}"
        )
        raw = settings._settings.value("calibration/profile", None)
        print(f"Raw type:                 {type(raw).__name__}")
        print(f"Raw value:                {raw!r}")
        print()

        profile = settings.calibration_profile
        if profile is None:
            print("RESULT:                   No calibration profile readable.")
        else:
            print("RESULT:                   Calibration profile FOUND.")
            print(f"Created:                  {profile.created_at}")
            print(f"Platform:                 {profile.platform}")
            print(f"Machine:                  {profile.machine}")
            print(f"Processor:                {profile.processor}")
            print(f"Fooocus URL:              {profile.fooocus_url}")
            print(f"Measurements:             {profile.point_count}")
            print()
            for point in profile.points:
                print(
                    f"  {point.width}x{point.height}: "
                    f"{point.seconds:.3f} s, "
                    f"{point.storage_bytes} bytes"
                )

        print()
        print("=== SETTINGS FILE CONTENT ===")
        if settings.settings_path.exists():
            try:
                print(settings.settings_path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                print(
                    settings.settings_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                )
        else:
            print("(settings.ini does not exist)")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")

    print()
    print("=== END ===")


if __name__ == "__main__":
    main()
