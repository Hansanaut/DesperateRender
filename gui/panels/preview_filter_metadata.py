"""Normalize generation metadata used by Preview filtering and sorting.

Queue tooltips and persisted result records have historically used slightly
different labels for the same generation setting (notably ``Seed`` versus
``Random Seed``). Keep this module free of Qt so the normalization contract can
be regression-tested without launching the GUI.
"""
from __future__ import annotations

from typing import Any
import ntpath


def normalize_filter_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return metadata with canonical keys and a derived resolution value.

    Existing metadata is retained. Aliases are added only when the canonical
    field is absent, so an explicitly stored value remains authoritative.
    """
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in (metadata or {}).items():
        key = " ".join(str(raw_key).strip().casefold().replace("_", " ").split())
        if not key:
            continue
        if raw_value is None:
            continue
        value = str(raw_value).strip()
        if not value or value == "—":
            continue
        normalized[key] = value

    # Fooocus request tooltips label the field "Random Seed"; planned
    # configuration tooltips and the Preview filter call it simply "Seed".
    if not normalized.get("seed") and normalized.get("random seed"):
        normalized["seed"] = normalized["random seed"]

    # Queue tooltips provide dimensions separately, whereas the Overview filter
    # represents the generated image size as one value such as ``1024x768``.
    if not normalized.get("resolution"):
        width = normalized.get("width")
        height = normalized.get("height")
        if width and height:
            normalized["resolution"] = f"{width}x{height}"

    return normalized


def canonical_result_path_key(raw_path: str) -> str:
    """Normalize path spelling for image identity comparisons on Windows.

    Fooocus paths can arrive with different slash styles or letter casing even
    when they point to the same file. Use Windows path rules independent of the
    host running unit tests, since PromptLAB targets Windows.
    """
    return ntpath.normcase(ntpath.normpath(str(raw_path or "").strip()))


def matches_metadata_filters(
    metadata: dict[str, Any] | None,
    selected_filters: dict[str, Any],
) -> bool:
    """Return whether normalized metadata matches every active filter."""
    normalized = normalize_filter_metadata(metadata)
    for raw_key, raw_value in selected_filters.items():
        key = " ".join(str(raw_key).strip().casefold().replace("_", " ").split())
        expected = str(raw_value).strip()
        if not expected:
            continue
        if str(normalized.get(key, "")).strip() != expected:
            return False
    return True
