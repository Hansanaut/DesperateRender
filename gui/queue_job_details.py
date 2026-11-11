from __future__ import annotations

from dataclasses import fields, is_dataclass
from html import escape
from typing import Any

from models.fooocus_request import FooocusRequest
from models.generation_configuration import GenerationConfiguration
from models.generation_job import GenerationJob


_FIELD_LABELS = {
    "prompt": "Prompt",
    "negative_prompt": "Negative Prompt",
    "styles": "Styles",
    "image_prompts": "Image Prompts",
    "performance": "Performance",
    "aspect_ratio": "Aspect Ratio",
    "width": "Width",
    "height": "Height",
    "image_count": "Image Count",
    "output_format": "Output Format",
    "random_seed": "Random Seed",
    "seed": "Seed",
    "read_wildcards_in_order": "Read wildcards in order",
    "sharpness": "Sharpness",
    "guidance_scale": "Guidance Scale",
    "base_model": "Base Model",
    "refiner_model": "Refiner Model",
    "refiner_switch": "Refiner Switch",
    "loras": "LoRAs",
}


def format_generation_configuration_tooltip(
    configuration: GenerationConfiguration,
    job_id: int | None = None,
    status: str = "PLANNED",
) -> str:
    """Return the complete hover details for a planned queue configuration."""

    rows = [("Status", status)]
    for field in fields(configuration):
        # Compact prompt-block/slot IDs are useful in queue labels but not in
        # the hover details: the full prompt text below is what users need.
        if field.name in {"prompt_block_variant_id", "positive_prompt_slots", "negative_prompt_slots"}:
            continue
        value = getattr(configuration, field.name)
        if value is None:
            continue
        rows.append((_CONFIGURATION_FIELD_LABELS.get(field.name, field.name), _format_value(value)))

    return _build_html(job_id, rows)


_CONFIGURATION_FIELD_LABELS = {
    "configuration_id": "Configuration ID",
    "positive_prompt": "Prompt",
    "negative_prompt": "Negative Prompt",
    "styles": "Styles",
    "style_references": "Style References",
    "composition_references": "Composition References",
    "loras": "LoRAs",
    "base_model": "Base Model",
    "refiner_model": "Refiner Model",
    "refiner_switch": "Refiner Switch",
    "performance": "Performance",
    "width": "Width",
    "height": "Height",
    "aspect_ratio": "Aspect Ratio",
    "seed": "Seed",
    "guidance_scale": "Guidance Scale",
    "sharpness": "Sharpness",
    "output_format": "Output Format",
}


def format_generation_job_tooltip(job: GenerationJob) -> str:
    """Return a compact, Fooocus-inspired HTML summary of one queued job."""

    rows = [("Status", job.status.value)]
    if job.prompt_block_variant_id:
        rows.append(("Prompt Block Variant", job.prompt_block_variant_id))
    request = job.request
    for field in fields(request):
        value = getattr(request, field.name)
        if value is None:
            continue
        rows.append((_FIELD_LABELS.get(field.name, field.name), _format_value(value)))

    return _build_html(job.job_id, rows)


def format_fooocus_request_tooltip(
    request: FooocusRequest,
    job_id: int | None = None,
) -> str:
    """Return a tooltip for a Fooocus request without requiring a queue job."""

    rows = []
    for field in fields(request):
        value = getattr(request, field.name)
        if value is None:
            continue
        rows.append((_FIELD_LABELS.get(field.name, field.name), _format_value(value)))
    return _build_html(job_id, rows)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        if not value:
            return "—"
        return f"<pre>{escape(value)}</pre>" if "\n" in value else escape(value)

    if isinstance(value, (list, tuple, dict)) or is_dataclass(value):
        return escape(repr(_to_plain(value)))

    return escape(str(value))


def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {
            field.name: _to_plain(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_plain(item) for item in value)
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    return value


def _build_html(job_id: int | None, rows: list[tuple[str, str]]) -> str:
    title = f"JOB #{job_id}" if job_id is not None else "GENERATION JOB"
    body = [
        "<div style='min-width:520px; max-width:760px;'>",
        f"<div style='font-size:14px; font-weight:700; padding:2px 0 8px 0;'>{escape(title)}</div>",
        "<table cellspacing='0' cellpadding='4' style='border-collapse:collapse; width:100%;'>",
    ]

    for label, value in rows:
        body.append(
            "<tr>"
            f"<td style='font-weight:600; vertical-align:top; padding-right:18px; white-space:nowrap;'>{escape(label)}</td>"
            f"<td style='vertical-align:top;'>{value}</td>"
            "</tr>"
        )

    body.extend(["</table>", "</div>"])
    return "".join(body)
