from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from gui.reference_image_widget import ReferenceImagePanel


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        first = root / "style.png"
        second = root / "composition.jpg"
        first.write_bytes(b"style")
        second.write_bytes(b"composition")

        app = QApplication.instance() or QApplication([])
        style = ReferenceImagePanel("Style")
        composition = ReferenceImagePanel("Composition")

        style.set_paths([str(first)])
        composition.set_paths([str(second)])

        assert style.paths() == [str(first.resolve())]
        assert composition.paths() == [str(second.resolve())]
        assert style.acceptDrops()
        assert composition.acceptDrops()
        assert style.list_widget.acceptDrops()
        assert composition.list_widget.acceptDrops()

        style.list_widget.add_paths([first, second])
        assert style.paths() == [str(first.resolve()), str(second.resolve())]

        style.list_widget.setCurrentRow(0)
        style.list_widget.remove_selected()
        assert style.paths() == [str(second.resolve())]

        style.close()
        composition.close()
        app.quit()

    print("=== REFERENCE IMAGE WIDGET TEST PASSED ===")


if __name__ == "__main__":
    main()
