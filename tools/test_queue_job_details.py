from models.fooocus_request import FooocusRequest
from models.generation_configuration import GenerationConfiguration
from models.generation_job import GenerationJob, GenerationJobStatus
from gui.queue_job_details import format_generation_job_tooltip


def test_generation_job_tooltip_contains_job_and_request_values() -> None:
    request = FooocusRequest(
        prompt="horse",
        negative_prompt="blurry",
        styles=["Fooocus Sharp"],
        performance="Speed",
        width=1024,
        height=768,
        seed=4515871030991447548,
        base_model="juggernautXL_v8Rundiffusion.safetensors",
    )
    job = GenerationJob(7, request, GenerationJobStatus.WAITING)

    tooltip = format_generation_job_tooltip(job)

    assert "JOB #7" in tooltip
    assert "horse" in tooltip
    assert "blurry" in tooltip
    assert "Fooocus Sharp" in tooltip
    assert "4515871030991447548" in tooltip
    assert "juggernautXL_v8Rundiffusion.safetensors" in tooltip


def test_generation_configuration_tooltip_contains_planned_values():
    from gui.queue_job_details import format_generation_configuration_tooltip

    configuration = GenerationConfiguration(
        configuration_id=7,
        positive_prompt="horse",
        negative_prompt="blurry",
        styles=["Fooocus Sharp"],
        base_model="juggernautXL_v8Rundiffusion.safetensors",
        width=1024,
        height=768,
        seed=12345,
    )
    html = format_generation_configuration_tooltip(configuration, job_id=7)
    assert "JOB #7" in html
    assert "horse" in html
    assert "Fooocus Sharp" in html
    assert "12345" in html


def test_generation_configuration_tooltip_shows_prompt_not_compact_block_ids():
    from gui.queue_job_details import format_generation_configuration_tooltip

    configuration = GenerationConfiguration(
        configuration_id=3,
        positive_prompt="cinematic portrait of a red-haired astronaut, soft rim lighting",
        negative_prompt="blurry, low detail",
        positive_prompt_slots=[1, 1],
        negative_prompt_slots=[2],
        prompt_block_variant_id="A1+B1",
        width=1024,
        height=768,
    )

    tooltip = format_generation_configuration_tooltip(configuration, job_id=3)

    assert "cinematic portrait of a red-haired astronaut, soft rim lighting" in tooltip
    assert "blurry, low detail" in tooltip
    assert "Prompt Block Variant" not in tooltip
    assert "Positive Prompt Slots" not in tooltip
    assert "Negative Prompt Slots" not in tooltip
    assert "A1+B1" not in tooltip
