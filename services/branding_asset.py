"""Helpers for the Desperate Render branding image."""

from __future__ import annotations

import shutil
from pathlib import Path


BRANDING_FILENAME = "DesperateRender.png"


def is_branding_asset_path(path: str | Path | None) -> bool:
    """Return whether a path names the reserved branding asset."""
    normalized = str(path or "").replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1]
    return filename.casefold() == BRANDING_FILENAME.casefold()


def ensure_branding_asset(output_directory: str | Path | None, source_path: str | Path) -> Path | None:
    """Copy the branding image into Fooocus outputs only when it is absent.

    Existing files are deliberately never overwritten, matching DR's run-start
    behavior and avoiding changes to a user's already-present output asset.
    Returns the destination path, or ``None`` when the source/output is invalid.
    """
    if output_directory is None:
        return None

    source = Path(source_path).expanduser()
    output_root = Path(output_directory).expanduser()
    if not source.is_file():
        return None

    target = output_root / BRANDING_FILENAME
    try:
        if target.is_file():
            return target
        output_root.mkdir(parents=True, exist_ok=True)
        # Avoid copying a file onto itself if a user configured unusual paths.
        if source.resolve() == target.resolve():
            return target
        shutil.copy2(source, target)
    except OSError:
        return None
    return target
