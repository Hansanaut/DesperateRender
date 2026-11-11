from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoRA:
    """Represents a single Fooocus LoRA."""

    enabled: bool = False
    filename: str = "None"
    weight: float = 1.0