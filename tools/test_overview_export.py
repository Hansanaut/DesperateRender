"""Regression checks for the non-destructive Overview export helper."""

from __future__ import annotations

import tempfile
from pathlib import Path

from services.overview_export import export_overview_images


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        day_a = root / "outputs" / "2026-10-26"
        day_b = root / "outputs" / "2026-10-27"
        target = root / "export"
        day_a.mkdir(parents=True)
        day_b.mkdir(parents=True)

        image_a = day_a / "image_00001.png"
        image_b = day_a / "image_00002.jpg"
        duplicate_name = day_b / "image_00001.png"
        branding = day_a / "DesperateRender.png"
        image_a.write_bytes(b"png-original-a")
        image_b.write_bytes(b"jpeg-original")
        duplicate_name.write_bytes(b"png-original-b")
        branding.write_bytes(b"branding-not-a-result")

        # Original names and bytes are retained; branding and missing paths are ignored.
        summary = export_overview_images(
            [image_a, image_b, branding, root / "missing.png", duplicate_name],
            target,
        )
        assert summary.copied == 2
        assert summary.skipped_existing == 1  # duplicate basename from a second day folder
        assert summary.skipped_missing == 1
        assert not summary.errors
        assert (target / image_a.name).read_bytes() == b"png-original-a"
        assert (target / image_b.name).read_bytes() == b"jpeg-original"
        assert not (target / branding.name).exists()

        # Existing target files are never overwritten.
        (target / image_a.name).write_bytes(b"user-file")
        second = export_overview_images([image_a], target)
        assert second.copied == 0
        assert second.skipped_existing == 1
        assert (target / image_a.name).read_bytes() == b"user-file"

        # A destination can be created if the user chooses a new directory path.
        fresh_target = root / "new" / "nested" / "export"
        third = export_overview_images([image_b], fresh_target)
        assert third.copied == 1
        assert (fresh_target / image_b.name).read_bytes() == b"jpeg-original"

    print("=== OVERVIEW EXPORT TEST PASSED ===")


if __name__ == "__main__":
    main()
