from __future__ import annotations


class AdaptiveEtaEstimator:
    """Adapt queue runtime estimates during the current experiment only."""

    def __init__(self) -> None:
        # Track cumulative baseline/actual time per resolution. This makes the
        # first completed job immediately useful and avoids the deliberately
        # slow convergence of an EWMA when the hardware calibration is far off.
        self._observations: dict[tuple[int, int], tuple[float, float]] = {}

    def reset(self) -> None:
        """Forget all observations from the previous experiment."""
        self._observations.clear()

    def factor(self, width: int, height: int) -> float:
        baseline, actual = self._observations.get((int(width), int(height)), (0.0, 0.0))
        if baseline <= 0.0:
            return 1.0
        return max(0.0, actual / baseline)

    def estimate(self, baseline_seconds: float, width: int, height: int) -> float:
        """Return the current experiment-adjusted estimate."""
        return max(0.0, float(baseline_seconds) * self.factor(width, height))

    def observe(
        self,
        width: int,
        height: int,
        baseline_seconds: float,
        actual_seconds: float,
    ) -> float:
        """Record one completed job and return the updated ratio.

        The ratio is cumulative for the current experiment and is always
        calculated against the original hardware-calibration estimate. This
        means the very first completed job immediately corrects the ETA for
        subsequent jobs, while later jobs naturally stabilize the ratio.
        """
        baseline = float(baseline_seconds)
        actual = max(0.0, float(actual_seconds))
        if baseline <= 0.0:
            return self.factor(width, height)

        key = (int(width), int(height))
        old_baseline, old_actual = self._observations.get(key, (0.0, 0.0))
        total_baseline = old_baseline + baseline
        total_actual = old_actual + actual
        self._observations[key] = (total_baseline, total_actual)
        return max(0.0, total_actual / total_baseline)
