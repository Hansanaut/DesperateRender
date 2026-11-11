from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Callable

from models.fooocus_request import FooocusImagePrompt, FooocusRequest
from services.calibration_profile import CalibrationPoint, CalibrationProfile
from services.calibration_prompt import CALIBRATION_NEGATIVE_PROMPT, CALIBRATION_PROMPT
from services.generation_service import GenerationService


class CalibrationService:
    """Run a small real Fooocus benchmark for the current installation."""

    DEFAULT_SIZES = (
        (1024, 768),
        (1536, 1024),
        (2048, 2048),
    )
    TEST_PROMPT = CALIBRATION_PROMPT
    TEST_NEGATIVE = CALIBRATION_NEGATIVE_PROMPT

    def __init__(self, generation_service: GenerationService) -> None:
        self.generation_service = generation_service

    def run(
        self,
        fooocus_url: str,
        progress: Callable[[int, int, CalibrationPoint], None] | None = None,
        reference_image: str | Path | None = None,
    ) -> CalibrationProfile:
        points: list[CalibrationPoint] = []
        total = len(self.DEFAULT_SIZES)
        reference_path = Path(reference_image) if reference_image else None
        use_reference = reference_path is not None and reference_path.is_file()
        for index, (width, height) in enumerate(self.DEFAULT_SIZES, start=1):
            calibration_seed = secrets.randbelow(2**64)
            request = FooocusRequest(
                prompt=self.TEST_PROMPT,
                negative_prompt=self.TEST_NEGATIVE,
                performance="Speed",
                width=width,
                height=height,
                aspect_ratio=None,
                image_count=1,
                output_format="png",
                seed=calibration_seed,
                image_prompts=(
                    [FooocusImagePrompt(image=str(reference_path))]
                    if use_reference
                    else None
                ),
            )

            started = time.perf_counter()
            result = self.generation_service.generate(request)
            seconds = time.perf_counter() - started

            if not result.images:
                raise RuntimeError(
                    f"Calibration produced no image at {width}x{height}."
                )

            storage_bytes = 0
            for image in result.images:
                try:
                    storage_bytes += os.path.getsize(Path(image))
                except OSError:
                    pass

            point = CalibrationPoint(
                width=width,
                height=height,
                seconds=seconds,
                storage_bytes=storage_bytes,
            )
            points.append(point)

            if progress is not None:
                progress(index, total, point)

        return CalibrationProfile.create(fooocus_url, points)
