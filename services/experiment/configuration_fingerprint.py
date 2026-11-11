from __future__ import annotations

from typing import Any


def normalize_legacy_prompt_block_mirror(data: dict[str, Any]) -> None:
    """Remove a synthetic legacy Block A that exactly mirrors positive prompts.

    Older experiment definitions store positive prompts only. Loading them
    migrates those prompts in memory into an unnamed Block A, while retaining
    the legacy positive_prompts field. The block is redundant for fingerprinting
    only when its prompts and matrix selection exactly mirror the legacy fields.
    """
    blocks = data.get("prompt_blocks")
    if not isinstance(blocks, list) or len(blocks) != 1:
        return

    block = blocks[0]
    if not isinstance(block, dict):
        return
    if str(block.get("block_id", "")).upper() != "A" or str(block.get("name", "")):
        return

    positive_prompts = data.get("positive_prompts")
    if not isinstance(positive_prompts, list) or block.get("prompts") != positive_prompts:
        return

    matrix = data.get("matrix")
    if not isinstance(matrix, dict):
        return
    legacy_selection = matrix.get("positive_prompts")
    block_selection = block.get("matrix_selection")
    if not isinstance(legacy_selection, dict) or not isinstance(block_selection, dict):
        return

    selection_keys = ("operator", "minimum", "maximum")
    if any(block_selection.get(key) != legacy_selection.get(key) for key in selection_keys):
        return

    data["prompt_blocks"] = []
