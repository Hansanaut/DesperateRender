from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "tools" / "show_calibration.py"
PROMPT = ROOT / "services" / "calibration_prompt.py"


def main() -> None:
    viewer = VIEWER.read_text(encoding="utf-8")
    prompt = PROMPT.read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(ROOT))" in viewer
    assert "settings.settings_path" in viewer

    compile(viewer, str(VIEWER), "exec")
    compile(prompt, str(PROMPT), "exec")

    assert 'CALIBRATION_PROMPT = (' in prompt
    assert '"cow in space"' in prompt
    assert 'CALIBRATION_NEGATIVE_PROMPT = (' in prompt
    assert "flags, banners, text, logos, symbols" in prompt

    print("Calibration viewer import path: OK")
    print("Canonical calibration prompt: OK")
    print("=== CALIBRATION VIEWER/PROMPT TEST PASSED ===")


if __name__ == "__main__":
    main()
