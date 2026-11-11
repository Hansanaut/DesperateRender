from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from models.image_generation_result import ImageGenerationResult


class FooocusResultAdapter:
    """Convert raw Fooocus/Gradio generation results into PromptLAB results."""

    def adapt(self, raw_result: Any) -> ImageGenerationResult:
        images: list[str] = []

        self._collect_images(raw_result, images)

        return ImageGenerationResult(
            images=tuple(images),
        )

    def _collect_images(
        self,
        value: Any,
        images: list[str],
    ) -> None:
        if isinstance(value, Mapping):
            self._collect_mapping(value, images)
            return

        if isinstance(value, (list, tuple)):
            for item in value:
                self._collect_images(item, images)

    def _collect_mapping(
        self,
        value: Mapping[str, Any],
        images: list[str],
    ) -> None:
        image_value = value.get("value")

        if isinstance(image_value, (list, tuple)):
            for item in image_value:
                self._collect_file(item, images)

        elif isinstance(image_value, Mapping):
            self._collect_file(image_value, images)

    @staticmethod
    def _collect_file(
        value: Any,
        images: list[str],
    ) -> None:
        if not isinstance(value, Mapping):
            return

        name = value.get("name")

        if not isinstance(name, str) or not name:
            return

        if not value.get("is_file", False):
            return

        path = Path(name)

        if path.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            return

        if name not in images:
            images.append(name)