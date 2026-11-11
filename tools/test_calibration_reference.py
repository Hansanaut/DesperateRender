from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.image_generation_result import ImageGenerationResult
from services.calibration_service import CalibrationService


class FakeGenerationService:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return ImageGenerationResult((str(self.image_path),))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        reference = tmp_path / "last-job.png"
        reference.write_bytes(b"reference")
        generated = tmp_path / "generated.png"
        generated.write_bytes(b"generated")

        fake = FakeGenerationService(generated)
        profile = CalibrationService(fake).run(
            "http://127.0.0.1:7865",
            reference_image=reference,
        )

        assert len(fake.requests) == 3
        assert [(r.width, r.height) for r in fake.requests] == [
            (1024, 768),
            (1536, 1024),
            (2048, 2048),
        ]

        seeds = [r.seed for r in fake.requests]
        assert all(seed is not None for seed in seeds)
        assert all(0 <= seed < 2**64 for seed in seeds)
        assert len(set(seeds)) == 3

        assert all(r.image_prompts for r in fake.requests)
        assert all(r.image_prompts[0].image == str(reference) for r in fake.requests)
        assert profile.point_count == 3

        fallback = FakeGenerationService(generated)
        CalibrationService(fallback).run("http://127.0.0.1:7865")

        assert all(r.image_prompts is None for r in fallback.requests)
        fallback_seeds = [r.seed for r in fallback.requests]
        assert all(seed is not None for seed in fallback_seeds)
        assert all(0 <= seed < 2**64 for seed in fallback_seeds)
        assert len(set(fallback_seeds)) == 3

    print("Calibration reference image: OK")
    print("Random seed per calibration run: OK")
    print("Fallback without reference image: OK")
    print("=== CALIBRATION REFERENCE TEST PASSED ===")


if __name__ == "__main__":
    main()
