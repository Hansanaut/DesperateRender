"""Focused checks for copying the DR branding card into Fooocus outputs."""

from __future__ import annotations

import tempfile
from pathlib import Path

from services.branding_asset import BRANDING_FILENAME, ensure_branding_asset, is_branding_asset_path


def main() -> None:
    assert is_branding_asset_path(r"C:\Fooocus\outputs\DesperateRender.png")
    assert is_branding_asset_path("/fooocus/outputs/desperaterender.PNG")
    assert not is_branding_asset_path("/fooocus/outputs/image_00001.png")

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "project" / BRANDING_FILENAME
        outputs = root / "fooocus" / "outputs"
        daily_outputs = outputs / "2026-10-26"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"branding-image-v1")

        # DR targets the same date-named subfolder Fooocus uses for generated images.
        copied = ensure_branding_asset(daily_outputs, source)
        assert copied == daily_outputs / BRANDING_FILENAME
        assert copied is not None and copied.read_bytes() == b"branding-image-v1"

        # Existing output is intentionally left untouched on subsequent runs.
        source.write_bytes(b"branding-image-v2")
        copied_again = ensure_branding_asset(daily_outputs, source)
        assert copied_again == copied
        assert copied_again.read_bytes() == b"branding-image-v1"

        assert ensure_branding_asset(daily_outputs, root / "missing.png") is None
        assert ensure_branding_asset(None, source) is None

    print("=== BRANDING ASSET TEST PASSED ===")


if __name__ == "__main__":
    main()
