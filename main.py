import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow
from gui.theme import apply_theme
from gui.windows_chrome import apply_desperate_render_titlebar


app = QApplication(sys.argv)
app.setApplicationName("Desperate Render")
app.setOrganizationName("Desperate Engineering Industries")

# Set the application icon before any window is created.
icon_path = Path(__file__).resolve().with_name("icon.ico")
if icon_path.is_file():
    app.setWindowIcon(QIcon(str(icon_path)))

apply_theme(app)

window = MainWindow()
window.show()
apply_desperate_render_titlebar(window)

sys.exit(app.exec())
