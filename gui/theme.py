from PySide6.QtWidgets import QApplication


# DESPERATE RENDER™ — Canonical color tokens
SPACE_950 = "#050817"
SPACE_900 = "#080D20"
SPACE_850 = "#0C1228"
SPACE_800 = "#111936"

CYAN_500 = "#00D9FF"
CYAN_400 = "#35E4FF"
CYAN_300 = "#7CEEFF"

BLUE_500 = "#1769FF"
BLUE_400 = "#3B82FF"
BLUE_300 = "#72A7FF"

VIOLET_500 = "#7040FF"
VIOLET_400 = "#925FFF"
VIOLET_300 = "#B89CFF"

MAGENTA_500 = "#D62BFF"
MAGENTA_400 = "#F044FF"
MAGENTA_300 = "#FF8CFF"

SUCCESS = "#35E58A"
WARNING = "#FFC857"
ERROR = "#FF4D67"

TEXT_PRIMARY = "#F4F7FF"
TEXT_SECONDARY = "#AAB4D0"
TEXT_MUTED = "#697493"

BORDER = "#1D2A4A"
BORDER_HOVER = "#30456F"


DESPERATE_RENDER_STYLE = """
QMainWindow,
QDialog {
    background: {SPACE_950};
    color: {TEXT_PRIMARY};
    border: 1px solid {CYAN_400};
}

QWidget {
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}

QAbstractScrollArea {
    background: transparent;
    border: none;
}

QAbstractScrollArea::viewport {
    background: transparent;
    border: none;
}


QFrame {
    background: transparent;
    color: {TEXT_PRIMARY};
}

QAbstractItemView {
    background: {SPACE_850};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {VIOLET_500};
    selection-color: {TEXT_PRIMARY};
}

QToolTip {
    background: {SPACE_850};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_HOVER};
    padding: 5px 7px;
}

QGroupBox {
    background: {SPACE_900};
    border: 1px solid {BORDER};
    border-radius: 7px;
    margin-top: 0px;
    padding: 8px 12px 12px 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: padding;
    subcontrol-position: top left;
    left: 0px;
    top: 0px;
    padding: 0px;
    color: transparent;
}

QLabel#panelTitle {
    background: {SPACE_850};
    color: {CYAN_300};
    font-weight: 700;
    padding: 2px 6px 4px 6px;
    border-bottom: 1px solid {BORDER};
    border-radius: 3px;
    margin-bottom: 4px;
    min-height: 18px;
    border: none;
}

QLabel {
    color: {TEXT_SECONDARY};
    padding: 1px 0;
}

QLabel[role="sectionTitle"] {
    color: {CYAN_300};
    font-weight: 700;
}

QLabel#queueMeta {
    color: {TEXT_MUTED};
    font-size: 12px;
}

QLabel#currentJob {
    color: {CYAN_300};
    font-weight: 600;
    padding: 2px 0;
}

QLineEdit,
QPlainTextEdit,
QTextEdit {
    background: {SPACE_800};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 9px;
    min-height: 22px;
    selection-background-color: {VIOLET_500};
}

QLineEdit:hover,
QPlainTextEdit:hover,
QTextEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QComboBox:hover {
    border-color: {BORDER_HOVER};
}

QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus {
    border: 1px solid {CYAN_500};
}

QSpinBox,
QDoubleSpinBox {
    padding: 5px 28px 5px 9px;
    min-height: 22px;
}

QComboBox::drop-down {
    width: 24px;
    border: none;
    border-left: 1px solid {BORDER};
    margin: 1px;
}

QComboBox::down-arrow {
    width: 9px;
    height: 11px;
}

QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    width: 20px;
    border: 1px solid {BORDER};
    background: {SPACE_850};
}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover {
    background: {SPACE_800};
    border-color: {CYAN_500};
}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {
    image: url(artwork/spin_up.svg);
    width: 12px;
    height: 8px;
}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {
    image: url(artwork/spin_down.svg);
    width: 12px;
    height: 8px;
}

QComboBox QAbstractItemView {
    background: {SPACE_850};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {VIOLET_500};
}

QListWidget {
    background: {SPACE_800};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    outline: none;
    padding: 3px;
}

QListWidget::item {
    padding: 6px 8px;
    margin: 1px 2px;
    color: {TEXT_SECONDARY};
}

QListWidget::item:hover {
    background: {SPACE_850};
    color: {TEXT_PRIMARY};
}

QListWidget::item:selected {
    background: #173A52;
    color: {CYAN_300};
    border: none;
}

QListWidget#baseModelList::item {
    padding: 2px 8px;
    margin: 0 2px;
}

QCheckBox {
    spacing: 7px;
    color: {TEXT_SECONDARY};
}

QCheckBox:hover {
    color: {TEXT_PRIMARY};
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid {CYAN_300};
    border-radius: 3px;
    background: {SPACE_800};
}

QCheckBox::indicator:checked {
    background: {CYAN_500};
    border: 1px solid {CYAN_300};
}

QCheckBox::indicator:unchecked:hover {
    border: 1px solid {CYAN_400};
    background: {SPACE_850};
}

QRadioButton {
    color: {TEXT_SECONDARY};
}

QPushButton {
    background: {SPACE_800};
    color: {TEXT_PRIMARY};
    border: 1px solid {BLUE_500};
    border-radius: 5px;
    min-height: 30px;
    padding: 5px 13px;
    font-weight: 600;
    margin: 2px;
}

QPushButton:hover {
    background: {SPACE_850};
    border-color: {CYAN_400};
    color: {CYAN_300};
}

QPushButton:pressed {
    background: {SPACE_900};
}

QPushButton:disabled {
    background: {SPACE_800};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}

QProgressBar {
    background: {SPACE_800};
    border: 1px solid {BORDER};
    border-radius: 5px;
    min-height: 10px;
    text-align: center;
    color: {TEXT_PRIMARY};
}

QProgressBar::chunk {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {CYAN_500},
        stop: 0.45 {BLUE_500},
        stop: 0.75 {VIOLET_500},
        stop: 1 {MAGENTA_500}
    );
    border-radius: 4px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: {SPACE_800};
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: {CYAN_500};
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {CYAN_500};
}

QSplitter::handle {
    width: 6px;
    height: 6px;
    background: transparent;
}

QScrollArea {
    background: transparent;
    border: none;
    padding: 0 10px 0 0;
}

QScrollArea#mainScrollArea {
    padding: 0px;
}

QScrollArea::viewport {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: {SPACE_900};
    width: 13px;
    margin: 4px 0 4px 4px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: {SPACE_850};
    border: none;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
}

QScrollBar::handle:vertical {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {SPACE_850},
        stop: 0.5 {CYAN_400},
        stop: 1 {SPACE_850}
    );
    min-height: 18px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {SPACE_850},
        stop: 0.5 {CYAN_300},
        stop: 1 {SPACE_850}
    );
}

QScrollBar::handle:vertical:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {SPACE_800},
        stop: 0.5 {CYAN_300},
        stop: 1 {SPACE_800}
    );
}

QListWidget#styleList::item:hover {
    background: #123A4A;
    color: {CYAN_300};
}

QListWidget#styleList::item:selected {
    background: #123A4A;
    color: {CYAN_300};
    border: none;
}

QListWidget#styleList QScrollBar::handle:vertical {
    min-height: 36px;
}

QScrollBar:horizontal {
    background: {SPACE_900};
    height: 13px;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: {SPACE_850};
    border: none;
}

QScrollBar::handle:horizontal {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {SPACE_850},
        stop: 0.5 {CYAN_400},
        stop: 1 {SPACE_850}
    );
    min-width: 18px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {SPACE_850},
        stop: 0.5 {CYAN_300},
        stop: 1 {SPACE_850}
    );
}

QScrollBar::handle:horizontal:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 {SPACE_800},
        stop: 0.5 {CYAN_300},
        stop: 1 {SPACE_800}
    );
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

QToolBar {
    background: {SPACE_900};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 4px 8px;
}

QToolButton {
    background: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 5px 9px;
}

QToolButton#panelToggleButton {
    padding: 0px;
    margin: 0px;
}

QToolButton:hover {
    background: {SPACE_800};
    border-color: {BORDER_HOVER};
    color: {TEXT_PRIMARY};
}

QToolButton:pressed {
    background: {SPACE_850};
    border-color: {CYAN_500};
    color: {CYAN_300};
}

QStatusBar {
    background: {SPACE_900};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
}
"""

# Inject color tokens without using an f-string: QSS braces stay literal.
for _token, _value in {
    "SPACE_950": SPACE_950, "SPACE_900": SPACE_900, "SPACE_850": SPACE_850, "SPACE_800": SPACE_800,
    "CYAN_500": CYAN_500, "CYAN_400": CYAN_400, "CYAN_300": CYAN_300,
    "BLUE_500": BLUE_500, "BLUE_400": BLUE_400, "BLUE_300": BLUE_300,
    "VIOLET_500": VIOLET_500, "VIOLET_400": VIOLET_400, "VIOLET_300": VIOLET_300,
    "MAGENTA_500": MAGENTA_500, "MAGENTA_400": MAGENTA_400, "MAGENTA_300": MAGENTA_300,
    "TEXT_PRIMARY": TEXT_PRIMARY, "TEXT_SECONDARY": TEXT_SECONDARY, "TEXT_MUTED": TEXT_MUTED,
    "BORDER": BORDER, "BORDER_HOVER": BORDER_HOVER,
}.items():
    DESPERATE_RENDER_STYLE = DESPERATE_RENDER_STYLE.replace("{" + _token + "}", _value)


def apply_theme(app: QApplication) -> None:
    """Apply the canonical Desperate Render™ theme globally."""
    app.setStyleSheet(DESPERATE_RENDER_STYLE)


# Backward-compatible name used by older entry points.
def apply_promptlab_theme(app: QApplication) -> None:
    apply_theme(app)
