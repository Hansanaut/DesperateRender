from models.experiment import (
    Experiment,
    MatrixOperator,
    MatrixSelection,
    NumericMatrixSelection,
    PromptSlot,
    SeedMode,
)
from services.experiment.matrix_builder import MatrixBuilder


def check(
    name: str,
    actual,
    expected,
) -> None:
    assert actual == expected, (
        f"{name} failed:\n"
        f"Expected: {expected}\n"
        f"Actual:   {actual}"
    )

    print(
        f"{name}: OK"
    )


def main() -> None:

    # --------------------------------------------------
    # Basic matrix operators
    # --------------------------------------------------

    values = [
        "A",
        "B",
        "C",
    ]

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.INDIVIDUAL,
        ),
    )

    check(
        "Individual",
        result,
        [
            ("A",),
            ("B",),
            ("C",),
        ],
    )

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.ALL,
        ),
    )

    check(
        "All",
        result,
        [
            (
                "A",
                "B",
                "C",
            ),
        ],
    )

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.PERMUTATION,
        ),
    )

    check(
        "Permutation count",
        len(result),
        15,
    )

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.COMBINATION,
            minimum=2,
            maximum=3,
        ),
    )

    check(
        "Combination",
        result,
        [
            ("A", "B"),
            ("A", "C"),
            ("B", "C"),
            (
                "A",
                "B",
                "C",
            ),
        ],
    )

    # --------------------------------------------------
    # Numeric matrix dimensions
    # --------------------------------------------------

    guidance = MatrixBuilder.build_numeric(
        NumericMatrixSelection(
            enabled=True,
            minimum=2.0,
            maximum=8.0,
            steps=4,
        )
    )

    check(
        "Guidance numeric values",
        guidance,
        [2.0, 4.0, 6.0, 8.0],
    )

    sharpness = MatrixBuilder.build_numeric(
        NumericMatrixSelection(
            enabled=True,
            minimum=0.0,
            maximum=3.0,
            steps=4,
        )
    )

    check(
        "Sharpness numeric values",
        sharpness,
        [0.0, 1.0, 2.0, 3.0],
    )

    check(
        "Disabled numeric matrix",
        MatrixBuilder.build_numeric(
            NumericMatrixSelection(
                enabled=False,
                minimum=2.0,
                maximum=8.0,
                steps=4,
            )
        ),
        [],
    )

    # --------------------------------------------------
    # Cartesian product
    # --------------------------------------------------

    result = MatrixBuilder.build_product(
        [
            (
                ["P1", "P2"],
                MatrixSelection(
                    operator=MatrixOperator.INDIVIDUAL,
                ),
            ),
            (
                ["S1", "S2"],
                MatrixSelection(
                    operator=MatrixOperator.INDIVIDUAL,
                ),
            ),
        ]
    )

    check(
        "Cartesian product count",
        len(result),
        4,
    )

    check(
        "Cartesian product order",
        result,
        [
            (
                ("P1",),
                ("S1",),
            ),
            (
                ("P1",),
                ("S2",),
            ),
            (
                ("P2",),
                ("S1",),
            ),
            (
                ("P2",),
                ("S2",),
            ),
        ],
    )

    # --------------------------------------------------
    # Exact-size combination
    # --------------------------------------------------

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.COMBINATION,
            minimum=2,
            maximum=2,
        ),
    )

    check(
        "Combination size 2",
        result,
        [
            ("A", "B"),
            ("A", "C"),
            ("B", "C"),
        ],
    )

    # --------------------------------------------------
    # Exact-size permutation
    # --------------------------------------------------

    result = MatrixBuilder.build(
        values,
        MatrixSelection(
            operator=MatrixOperator.PERMUTATION,
            minimum=2,
            maximum=2,
        ),
    )

    check(
        "Permutation size 2",
        result,
        [
            ("A", "B"),
            ("A", "C"),
            ("B", "A"),
            ("B", "C"),
            ("C", "A"),
            ("C", "B"),
        ],
    )

    # --------------------------------------------------
    # Experiment integration
    # --------------------------------------------------

    experiment = Experiment(
        experiment_id="20260923-matrix",
    )

    experiment.positive_prompts = [
        PromptSlot(
            1,
            "Prompt 1",
        ),
        PromptSlot(
            2,
            "Prompt 2",
        ),
        PromptSlot(
            3,
            "Prompt 3",
        ),
    ]

    experiment.styles = [
        "Style 1",
        "Style 2",
        "Style 3",
    ]

    experiment.generation.seed_mode = (
        SeedMode.FIXED
    )

    experiment.generation.seeds = [
        101,
        202,
    ]

    experiment.matrix.guidance_scale = NumericMatrixSelection(
        enabled=True,
        minimum=2.0,
        maximum=8.0,
        steps=4,
    )
    experiment.matrix.sharpness = NumericMatrixSelection(
        enabled=True,
        minimum=0.0,
        maximum=3.0,
        steps=4,
    )

    # --------------------------------------------------
    # Numeric dimensions included
    #
    # 3 prompts × 3 styles × 2 seeds × 4 guidance × 4 sharpness = 288
    # --------------------------------------------------

    configurations = MatrixBuilder.build_experiment(experiment)

    check(
        "Numeric matrix configuration count",
        len(configurations),
        288,
    )

    check(
        "First numeric matrix values",
        (
            configurations[0].guidance_scale,
            configurations[0].sharpness,
        ),
        (2.0, 0.0),
    )

    check(
        "Last numeric matrix values",
        (
            configurations[-1].guidance_scale,
            configurations[-1].sharpness,
        ),
        (8.0, 3.0),
    )

    # Disable numeric dimensions before continuing the legacy matrix tests.
    experiment.matrix.guidance_scale.enabled = False
    experiment.matrix.sharpness.enabled = False

    # --------------------------------------------------
    # Individual
    #
    # 3 prompts × 3 styles × 2 seeds = 18
    # --------------------------------------------------

    configurations = (
        MatrixBuilder.build_experiment(
            experiment
        )
    )

    check(
        "Individual configuration count",
        len(configurations),
        18,
    )

    # --------------------------------------------------
    # All prompts
    #
    # 1 prompt group × 3 styles × 2 seeds = 6
    # --------------------------------------------------

    experiment.matrix.positive_prompts = (
        MatrixSelection(
            operator=MatrixOperator.ALL,
        )
    )

    configurations = (
        MatrixBuilder.build_experiment(
            experiment
        )
    )

    check(
        "All prompt configuration count",
        len(configurations),
        6,
    )

    check(
        "All prompt group",
        configurations[0].positive_prompt,
        "Prompt 1 Prompt 2 Prompt 3",
    )

    # --------------------------------------------------
    # All prompts + All styles
    #
    # 1 × 1 × 2 = 2
    # --------------------------------------------------

    experiment.matrix.styles = (
        MatrixSelection(
            operator=MatrixOperator.ALL,
        )
    )

    configurations = (
        MatrixBuilder.build_experiment(
            experiment
        )
    )

    check(
        "All prompt and style configuration count",
        len(configurations),
        2,
    )

    check(
        "All style group",
        configurations[0].styles,
        [
            "Style 1",
            "Style 2",
            "Style 3",
        ],
    )

    # --------------------------------------------------
    # Prompt permutation, exactly 2
    #
    # 6 prompt variants × 3 styles × 2 seeds = 36
    # --------------------------------------------------

    experiment.matrix.positive_prompts = (
        MatrixSelection(
            operator=MatrixOperator.PERMUTATION,
            minimum=2,
            maximum=2,
        )
    )

    experiment.matrix.styles = (
        MatrixSelection(
            operator=MatrixOperator.INDIVIDUAL,
        )
    )

    configurations = (
        MatrixBuilder.build_experiment(
            experiment
        )
    )

    check(
        "Prompt permutation size 2 configuration count",
        len(configurations),
        36,
    )

    check(
        "First prompt permutation",
        configurations[0].positive_prompt,
        "Prompt 1 Prompt 2",
    )

    check(
        "Second prompt permutation",
        configurations[1].positive_prompt,
        "Prompt 1 Prompt 2",
    )

    # --------------------------------------------------
    # Prompt combination, exactly 2
    #
    # 3 prompt variants × 3 styles × 2 seeds = 18
    # --------------------------------------------------

    experiment.matrix.positive_prompts = (
        MatrixSelection(
            operator=MatrixOperator.COMBINATION,
            minimum=2,
            maximum=2,
        )
    )

    configurations = (
        MatrixBuilder.build_experiment(
            experiment
        )
    )

    check(
        "Prompt combination size 2 configuration count",
        len(configurations),
        18,
    )

    check(
        "First prompt combination",
        configurations[0].positive_prompt,
        "Prompt 1 Prompt 2",
    )

    check(
        "Second prompt combination",
        configurations[3].positive_prompt,
        "Prompt 1 Prompt 3",
    )

    print()
    print(
        "=== ALL MATRIX BUILDER TESTS PASSED ==="
    )


if __name__ == "__main__":
    main()