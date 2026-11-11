from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import platform
from typing import Any


@dataclass(frozen=True)
class CalibrationPoint:
    width: int
    height: int
    seconds: float
    storage_bytes: int


@dataclass(frozen=True)
class CalibrationProfile:
    """Measured performance profile for one DESPERATE RENDER installation."""

    created_at: str
    platform: str
    machine: str
    processor: str
    fooocus_url: str
    points: tuple[CalibrationPoint, ...]

    @property
    def point_count(self) -> int:
        return len(self.points)

    @classmethod
    def current_identity(cls, fooocus_url: str) -> dict[str, str]:
        return {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "Unknown",
            "fooocus_url": fooocus_url,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["points"] = [asdict(point) for point in self.points]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationProfile":
        return cls(
            created_at=str(data["created_at"]),
            platform=str(data.get("platform", "Unknown")),
            machine=str(data.get("machine", "Unknown")),
            processor=str(data.get("processor", "Unknown")),
            fooocus_url=str(data.get("fooocus_url", "")),
            points=tuple(
                CalibrationPoint(
                    width=int(point["width"]),
                    height=int(point["height"]),
                    seconds=float(point["seconds"]),
                    storage_bytes=int(point["storage_bytes"]),
                )
                for point in data.get("points", [])
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> "CalibrationProfile":
        return cls.from_dict(json.loads(value))

    @classmethod
    def create(
        cls,
        fooocus_url: str,
        points: list[CalibrationPoint],
    ) -> "CalibrationProfile":
        identity = cls.current_identity(fooocus_url)
        return cls(
            created_at=datetime.now().isoformat(timespec="seconds"),
            platform=identity["platform"],
            machine=identity["machine"],
            processor=identity["processor"],
            fooocus_url=fooocus_url,
            points=tuple(points),
        )
