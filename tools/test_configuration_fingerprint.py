from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.experiment.configuration_fingerprint import normalize_legacy_prompt_block_mirror


def fingerprint(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    legacy = {
        "positive_prompts": [
            {"slot_id": 1, "text": "command center,", "fixed": False},
            {"slot_id": 2, "text": "reactor room,", "fixed": False},
        ],
        "matrix": {"positive_prompts": {"operator": "INDIVIDUAL", "minimum": None, "maximum": None}},
        "prompt_blocks": [],
        "generation": {"random_seeds": [101, 202]},
    }
    migrated = copy.deepcopy(legacy)
    migrated["prompt_blocks"] = [{
        "block_id": "A",
        "name": "",
        "prompts": copy.deepcopy(legacy["positive_prompts"]),
        "matrix_selection": {"operator": "INDIVIDUAL", "minimum": None, "maximum": None},
    }]

    before = fingerprint(legacy)
    normalize_legacy_prompt_block_mirror(migrated)
    assert migrated["prompt_blocks"] == []
    assert fingerprint(migrated) == before

    changed_prompt = copy.deepcopy(legacy)
    changed_prompt["prompt_blocks"] = copy.deepcopy(migrated["prompt_blocks"])
    changed_prompt["prompt_blocks"] = [{
        "block_id": "A", "name": "", "prompts": [
            {"slot_id": 1, "text": "different prompt", "fixed": False},
            {"slot_id": 2, "text": "reactor room,", "fixed": False},
        ], "matrix_selection": {"operator": "INDIVIDUAL", "minimum": None, "maximum": None},
    }]
    normalize_legacy_prompt_block_mirror(changed_prompt)
    assert len(changed_prompt["prompt_blocks"]) == 1, "A genuinely different block must remain fingerprinted"

    changed_matrix = copy.deepcopy(legacy)
    changed_matrix["prompt_blocks"] = [{
        "block_id": "A", "name": "", "prompts": copy.deepcopy(legacy["positive_prompts"]),
        "matrix_selection": {"operator": "ALL", "minimum": None, "maximum": None},
    }]
    normalize_legacy_prompt_block_mirror(changed_matrix)
    assert len(changed_matrix["prompt_blocks"]) == 1, "A different matrix selection must remain fingerprinted"

    print("Configuration fingerprint legacy prompt migration: OK")


if __name__ == "__main__":
    main()
