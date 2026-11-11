from __future__ import annotations

from gui.panels.preview_filter_metadata import (
    canonical_result_path_key,
    matches_metadata_filters,
    normalize_filter_metadata,
)


def main() -> None:
    # Queue request tooltips call this "Random Seed" while the Preview filter
    # uses the canonical key "seed".
    metadata = normalize_filter_metadata({"Random Seed": "123456", "Base Model": "model.safetensors"})
    assert metadata["seed"] == "123456"
    assert metadata["random seed"] == "123456"
    assert metadata["base model"] == "model.safetensors"
    assert matches_metadata_filters(metadata, {"seed": "123456"})
    assert not matches_metadata_filters(metadata, {"seed": "654321"})

    # Resolution choices must be available even when the source only provides
    # separate width and height fields.
    metadata = normalize_filter_metadata({"Width": "1024", "Height": "768"})
    assert metadata["resolution"] == "1024x768"
    assert matches_metadata_filters(metadata, {"resolution": "1024x768"})
    assert not matches_metadata_filters(metadata, {"resolution": "768x1024"})

    # Explicit resolution metadata wins over the derived dimensions.
    metadata = normalize_filter_metadata({
        "Width": "1024", "Height": "768", "Resolution": "1152x896"
    })
    assert metadata["resolution"] == "1152x896"

    # Underscored persisted keys normalize to the same keys used by filters.
    metadata = normalize_filter_metadata({"random_seed": 42, "base_model": "checkpoint.safetensors"})
    assert metadata["seed"] == "42"
    assert metadata["base model"] == "checkpoint.safetensors"

    # The same Windows file must be recognized across slash styles and case.
    path_a = canonical_result_path_key(r"C:\Fooocus\outputs\2026-10-21\image.png")
    path_b = canonical_result_path_key("c:/fooocus/OUTPUTS/2026-10-21/image.png")
    assert path_a == path_b

    print("Preview filter metadata and path identity: OK")


if __name__ == "__main__":
    main()
