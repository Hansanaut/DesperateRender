from __future__ import annotations

from dataclasses import dataclass, field

from models.experiment import MatrixSelection, PromptSlot


@dataclass
class PromptBlock:
    """One independent positive-prompt matrix dimension."""

    block_id: str
    name: str = ""
    prompts: list[PromptSlot] = field(default_factory=list)
    matrix_selection: MatrixSelection = field(
        default_factory=MatrixSelection
    )

    def __post_init__(self) -> None:
        self.block_id = self.block_id.strip().upper()
        if not self.block_id:
            raise ValueError("Prompt block ID cannot be empty.")
        if len(self.block_id) != 1 or not self.block_id.isalpha():
            raise ValueError(
                "Prompt block ID must be a single alphabetic character."
            )

    @property
    def variable_prompts(self) -> list[PromptSlot]:
        """Return prompts affected by the block matrix operator."""
        return [
            prompt for prompt in self.prompts if not prompt.fixed
        ]

    @property
    def has_prompt(self) -> bool:
        """Return whether the block contains at least one prompt."""
        return bool(self.prompts)

    def variant_id(self, selected_values: tuple[PromptSlot, ...]) -> str:
        """Return the compact provenance ID including fixed prompts.

        Fixed prompts are part of every generated variant and therefore must
        remain visible in queue/provenance labels. Variable prompts use the
        matrix-selected order (important for permutation variants).
        """
        selected_ids = {prompt.slot_id for prompt in selected_values}
        if not selected_ids and not any(prompt.fixed for prompt in self.prompts):
            return ""

        selected_by_id = {
            prompt.slot_id: prompt for prompt in selected_values
        }
        variant_prompts: list[PromptSlot] = []

        # Keep fixed prompts visible in their canonical block position.
        # Variable prompts follow the matrix selection order so permutation
        # provenance remains meaningful.
        for prompt in self.prompts:
            if prompt.fixed:
                variant_prompts.append(prompt)

        for prompt in selected_values:
            if prompt.slot_id in selected_ids:
                variant_prompts.append(selected_by_id[prompt.slot_id])

        # Deduplicate while retaining the intended order.
        seen: set[int] = set()
        ordered = []
        for prompt in variant_prompts:
            if prompt.slot_id in seen:
                continue
            seen.add(prompt.slot_id)
            ordered.append(prompt)

        return "+".join(
            f"{self.block_id}{prompt.slot_id}"
            for prompt in ordered
        )
