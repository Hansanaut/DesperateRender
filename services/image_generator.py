"""Backward-compatible import for the former ImageGenerator interface."""

from services.generation_backend import GenerationBackend


# Kept as an alias so existing integrations and tests do not need to change
# in the same architectural step. New code should depend on GenerationBackend.
ImageGenerator = GenerationBackend

__all__ = ["ImageGenerator"]
