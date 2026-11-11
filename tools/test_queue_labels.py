from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from models.experiment import Experiment, MatrixOperator, PromptSlot
from models.generation_job import GenerationJob
from models.fooocus_request import FooocusRequest
from services.experiment.matrix_builder import MatrixBuilder
from gui.panels.queue_panel import QueuePanel


def main() -> None:
    print("=== Queue Label Tests ===")

    experiment = Experiment(experiment_id="queue-label-test")
    experiment.positive_prompts = [
        PromptSlot(1, "fixed A", fixed=True),
        PromptSlot(2, "fixed B", fixed=True),
        PromptSlot(3, "variant C"),
        PromptSlot(4, "variant D"),
    ]
    experiment.negative_prompts = [
        PromptSlot(1, "negative", fixed=True)
    ]

    experiment.matrix.positive_prompts.operator = MatrixOperator.INDIVIDUAL
    experiment.matrix.negative_prompts.operator = MatrixOperator.INDIVIDUAL

    configurations = MatrixBuilder.build_experiment(experiment)

    assert [c.positive_prompt_slots for c in configurations] == [
        [1, 2, 3],
        [1, 2, 4],
    ]
    assert [c.negative_prompt_slots for c in configurations] == [
        [1],
        [1],
    ]

    print("Prompt slot metadata: OK")

    app = QApplication.instance() or QApplication([])

    configurations[0].seed = 111
    configurations[1].seed = 222
    configurations[0].width, configurations[0].height = 600, 450
    configurations[1].width, configurations[1].height = 900, 675
    model_filename = "juggernautXL_v8Rundiffusion.safetensors"
    configurations[0].base_model = model_filename
    configurations[1].base_model = model_filename

    panel = QueuePanel()
    panel.set_preview_configurations(configurations)

    label_1 = panel.jobs.item(0).text()
    label_2 = panel.jobs.item(1).text()

    # Spacing is intentionally not part of the queue-label contract.
    assert "#1" in label_1
    assert "PP1+PP2+PP3+NP1" in label_1
    assert "S1" in label_1
    assert "PLANNED" in label_1
    assert "R1" in label_1
    assert "+BM1" in label_1
    assert model_filename not in label_1

    assert "#2" in label_2
    assert "PP1+PP2+PP4+NP1" in label_2
    assert "S2" in label_2
    assert "PLANNED" in label_2
    assert "R2" in label_2
    assert "+BM1" in label_2
    assert model_filename not in label_2

    assert "111" not in label_1
    assert "222" not in label_2

    print("Queue prompt + seed signature: OK")

    configurations[0].prompt_block_variant_id = "A1+B1"
    configurations[1].prompt_block_variant_id = "A2+B1"

    panel.set_preview_configurations(configurations)

    assert "A1+B1" in panel.jobs.item(0).text()
    assert "A2+B1" in panel.jobs.item(1).text()

    print("Prompt Block preview signature: OK")

    job = GenerationJob(
        job_id=1,
        request=FooocusRequest(
            seed=111,
            styles=[],
            width=600,
            height=450,
            base_model=model_filename,
        ),
        prompt_block_variant_id="A1+B1",
    )

    job2 = GenerationJob(
        job_id=2,
        request=FooocusRequest(
            seed=222,
            styles=[],
            width=900,
            height=675,
            base_model=model_filename,
        ),
        prompt_block_variant_id="A2+B1",
    )

    panel.set_queue(
        type(
            "QueueStub",
            (),
            {
                "jobs": [job, job2],
                "__len__": lambda self: 2,
            },
        )()
    )

    assert "A1+B1" in panel.jobs.item(0).text()
    assert "A1+B1" in panel._format_job(job)
    assert "S1" in panel._format_job(job)
    assert "111" not in panel._format_job(job)
    assert "+BM1" in panel._format_job(job)
    assert model_filename not in panel._format_job(job)
    assert "R1" in panel._format_job(job)

    assert "A2+B1" in panel.jobs.item(1).text()
    assert "A2+B1" in panel._format_job(job2)
    assert "S2" in panel._format_job(job2)
    assert "222" not in panel._format_job(job2)
    assert "+BM1" in panel._format_job(job2)
    assert model_filename not in panel._format_job(job2)
    assert "R2" in panel._format_job(job2)

    assert panel.jobs.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert "seed=" not in panel._format_job(job)

    print("Compact seed label: OK")
    print("=== ALL QUEUE LABEL TESTS PASSED ===")


if __name__ == "__main__":
    main()