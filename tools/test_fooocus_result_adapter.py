from __future__ import annotations

from services.fooocus_result_adapter import FooocusResultAdapter


def assert_images(raw_result, expected: tuple[str, ...]) -> None:
    result = FooocusResultAdapter().adapt(raw_result)

    assert result.images == expected, (
        f"Expected {expected!r}, got {result.images!r}"
    )


def main() -> None:
    adapter = FooocusResultAdapter()

    # ------------------------------------------------------------
    # 1. Single image
    # ------------------------------------------------------------

    raw_single = (
        {"visible": False, "type": "update"},
        {"visible": False, "type": "update"},
        {"visible": False, "type": "update"},
        {
            "visible": True,
            "value": [
                {
                    "name": r"C:\Temp\image_001.png",
                    "data": None,
                    "is_file": True,
                }
            ],
            "type": "update",
        },
    )

    assert_images(
        raw_single,
        (r"C:\Temp\image_001.png",),
    )

    print("Single image: OK")

    # ------------------------------------------------------------
    # 2. Multiple images
    # ------------------------------------------------------------

    raw_multiple = (
        {
            "visible": True,
            "value": [
                {
                    "name": r"C:\Temp\image_001.png",
                    "data": None,
                    "is_file": True,
                },
                {
                    "name": r"C:\Temp\image_002.jpg",
                    "data": None,
                    "is_file": True,
                },
                {
                    "name": r"C:\Temp\image_003.webp",
                    "data": None,
                    "is_file": True,
                },
            ],
            "type": "update",
        },
    )

    assert_images(
        raw_multiple,
        (
            r"C:\Temp\image_001.png",
            r"C:\Temp\image_002.jpg",
            r"C:\Temp\image_003.webp",
        ),
    )

    print("Multiple images: OK")

    # ------------------------------------------------------------
    # 3. No images / UI updates only
    # ------------------------------------------------------------

    raw_empty = (
        {"visible": False, "type": "update"},
        {"visible": False, "type": "update"},
        {"visible": False, "type": "update"},
    )

    assert_images(
        raw_empty,
        (),
    )

    print("No images: OK")

    # ------------------------------------------------------------
    # 4. Duplicate images
    # ------------------------------------------------------------

    raw_duplicates = (
        {
            "visible": True,
            "value": [
                {
                    "name": r"C:\Temp\image_001.png",
                    "data": None,
                    "is_file": True,
                },
                {
                    "name": r"C:\Temp\image_001.png",
                    "data": None,
                    "is_file": True,
                },
            ],
            "type": "update",
        },
    )

    assert_images(
        raw_duplicates,
        (r"C:\Temp\image_001.png",),
    )

    print("Duplicate images: OK")

    # ------------------------------------------------------------
    # 5. Invalid / incomplete entries
    # ------------------------------------------------------------

    raw_invalid = (
        {
            "visible": True,
            "value": [
                {
                    "name": None,
                    "data": None,
                    "is_file": True,
                },
                {
                    "data": None,
                    "is_file": True,
                },
                {
                    "name": r"C:\Temp\not_a_file.png",
                    "data": None,
                    "is_file": False,
                },
                {
                    "name": "",
                    "data": None,
                    "is_file": True,
                },
                "not a dictionary",
            ],
            "type": "update",
        },
    )

    assert_images(
        raw_invalid,
        (),
    )

    print("Invalid entries: OK")

    # ------------------------------------------------------------
    # 6. Unsupported file extensions
    # ------------------------------------------------------------

    raw_unsupported = (
        {
            "visible": True,
            "value": [
                {
                    "name": r"C:\Temp\image.txt",
                    "data": None,
                    "is_file": True,
                },
                {
                    "name": r"C:\Temp\image.mp4",
                    "data": None,
                    "is_file": True,
                },
            ],
            "type": "update",
        },
    )

    assert_images(
        raw_unsupported,
        (),
    )

    print("Unsupported extensions: OK")

    # ------------------------------------------------------------
    # 7. Empty / arbitrary input
    # ------------------------------------------------------------

    assert adapter.adapt(None).images == ()
    assert adapter.adapt("unexpected").images == ()
    assert adapter.adapt(123).images == ()

    print("Unexpected input: OK")

    print()
    print("=== ALL RESULT ADAPTER TESTS PASSED ===")


if __name__ == "__main__":
    main()