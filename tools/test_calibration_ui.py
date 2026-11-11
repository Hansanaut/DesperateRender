from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "gui" / "fooocus_settings_dialog.py"
SERVICE = ROOT / "services" / "calibration_service.py"
PROMPT = ROOT / "services" / "calibration_prompt.py"
VIEWER = ROOT / "tools" / "show_calibration.py"


def main() -> None:
    dialog = DIALOG.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")
    prompt = PROMPT.read_text(encoding="utf-8")
    viewer = VIEWER.read_text(encoding="utf-8")

    assert "Run Desperate Render™ Calibration" in dialog
    assert 'setText("Calibration running…")' in dialog
    assert "WaitCursor" in dialog
    assert "_start_busy_state" in dialog
    assert "Qt.CursorShape.WaitCursor" in dialog
    assert "setRange(0, 100)" in dialog
    assert "completed_percent = int(round((current / total) * 100))" in dialog
    assert "setValue(100)" in dialog
    assert "generating test image 1/3…" in dialog
    assert "33% after the first" in dialog
    assert "67% after the second" in dialog
    assert "100% after the third" in dialog
    assert "1/2" not in dialog
    assert "setRange(0, 0)" not in dialog
    assert "activity" not in dialog
    assert "Cancel Calibration" not in dialog
    assert "_calibration_cancelled" not in dialog

    assert "CALIBRATION_PROMPT" in service
    assert "(1024, 768)" in service
    assert "(1536, 1024)" in service
    assert "(2048, 2048)" in service
    assert "activity" not in service
    assert "cancel_requested" not in service
    assert "def cancel(" not in service

    assert 'CALIBRATION_PROMPT = (' in prompt
    assert '"cow in space"' in prompt
    assert 'CALIBRATION_NEGATIVE_PROMPT = (' in prompt
    assert "flags, banners, text, logos, symbols" in prompt

    assert "Measured points:" in viewer

    compile(viewer, str(VIEWER), "exec")
    compile(dialog, str(DIALOG), "exec")
    compile(service, str(SERVICE), "exec")

    print("Calibration UI definition: OK")
    print("Calibration viewer syntax: OK")
    print("Canonical calibration prompt: OK")
    print("=== CALIBRATION UI TEST PASSED ===")


if __name__ == "__main__":
    main()
