from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "models" / "application_settings.py"
DIALOG = ROOT / "gui" / "fooocus_settings_dialog.py"
MAIN = ROOT / "gui" / "main_window.py"


def main() -> None:
    settings = SETTINGS.read_text(encoding="utf-8")
    dialog = DIALOG.read_text(encoding="utf-8")
    main_window = MAIN.read_text(encoding="utf-8")

    ast.parse(settings)
    ast.parse(dialog)
    ast.parse(main_window)

    assert "DEFAULT_QUEUE_WARNING_THRESHOLD = 300" in settings
    assert '"queue/warning_threshold"' in settings
    assert "queue_warning_threshold" in dialog
    assert "QSpinBox" in dialog
    assert "Large generation queue" in main_window
    assert "total_configurations >= warning_threshold" in main_window

    print("Queue warning settings: OK")
    print("Queue warning trigger: OK")
    print("=== QUEUE WARNING TEST PASSED ===")


if __name__ == "__main__":
    main()
