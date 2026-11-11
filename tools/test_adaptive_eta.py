from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.adaptive_eta import AdaptiveEtaEstimator


def main() -> None:
    eta = AdaptiveEtaEstimator()

    assert eta.factor(1536, 1024) == 1.0
    assert eta.estimate(100.0, 1536, 1024) == 100.0

    # First completed job immediately corrects the estimate for the current
    # experiment: 80s actual versus 100s calibrated => factor 0.8.
    factor = eta.observe(1536, 1024, 100.0, 80.0)
    assert abs(factor - 0.8) < 1e-9
    assert abs(eta.estimate(100.0, 1536, 1024) - 80.0) < 1e-9

    # A second job stabilizes the cumulative ratio against the original
    # calibration: (80 + 90) / (100 + 100) = 0.85.
    factor = eta.observe(1536, 1024, 100.0, 90.0)
    assert abs(factor - 0.85) < 1e-9
    assert abs(eta.estimate(100.0, 1536, 1024) - 85.0) < 1e-9

    # Different resolutions learn independently.
    assert eta.factor(2048, 2048) == 1.0
    eta.observe(2048, 2048, 100.0, 120.0)
    assert abs(eta.factor(2048, 2048) - 1.2) < 1e-9

    eta.reset()
    assert eta.factor(1536, 1024) == 1.0
    assert eta.factor(2048, 2048) == 1.0

    print("=== ALL ADAPTIVE ETA TESTS PASSED ===")


if __name__ == "__main__":
    main()
