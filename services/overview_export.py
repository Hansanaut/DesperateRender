"""Copy the currently visible Overview results to a user-selected folder."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from services.branding_asset import is_branding_asset_path


@dataclass
class OverviewExportSummary:
    copied: int = 0
    skipped_existing: int = 0
    skipped_missing: int = 0
    errors: list[str] = field(default_factory=list)


def export_overview_images(
    source_paths: Iterable[str | Path | None],
    destination_directory: str | Path,
) -> OverviewExportSummary:
    """Copy image files without re-encoding, preserving original filenames.

    Branding assets are never exported. Existing destination filenames are not
    overwritten; this also handles same-name files from different Fooocus day
    folders safely. Missing source files and individual copy errors are counted
    so the UI can report a truthful summary.
    """
    destination = Path(destination_directory).expanduser()
    summary = OverviewExportSummary()

    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        summary.errors.append(f"Could not create destination folder: {exc}")
        return summary

    for raw_path in source_paths:
        if raw_path is None or is_branding_asset_path(raw_path):
            continue
        source = Path(str(raw_path)).expanduser()
        if not source.is_file():
            summary.skipped_missing += 1
            continue

        target = destination / source.name
        try:
            # Never overwrite existing files, including files copied earlier in
            # this same export when two day folders contain the same filename.
            if target.exists():
                summary.skipped_existing += 1
                continue
            if source.resolve() == target.resolve():
                summary.skipped_existing += 1
                continue
            shutil.copy2(source, target)
            summary.copied += 1
        except OSError as exc:
            summary.errors.append(f"{source.name}: {exc}")

    return summary
