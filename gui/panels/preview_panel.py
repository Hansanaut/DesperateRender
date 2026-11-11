from __future__ import annotations

from pathlib import Path
from datetime import date
from html.parser import HTMLParser
from html import unescape

from PySide6.QtCore import QSize, Qt, QRect, QEvent, QTimer, QItemSelectionModel
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QPainter, QColor, QPen, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QSplitter, QStyledItemDelegate,
    QStyle, QStyleOptionViewItem, QSlider, QWidget, QStackedLayout, QSizePolicy, QDialog, QComboBox, QLineEdit, QGridLayout, QToolTip, QApplication, QFileDialog, QMessageBox,
)

from models.image_generation_result import ImageGenerationResult
from gui.panels.preview_filter_metadata import (
    canonical_result_path_key,
    matches_metadata_filters,
    normalize_filter_metadata,
)
from services.branding_asset import BRANDING_FILENAME, is_branding_asset_path
from services.overview_export import export_overview_images

RATING_ROLE = Qt.ItemDataRole.UserRole + 1
EXCLUDED_ROLE = Qt.ItemDataRole.UserRole + 2
METADATA_ROLE = Qt.ItemDataRole.UserRole + 3
JOB_ID_ROLE = Qt.ItemDataRole.UserRole + 4
SELECTED_ROLE = Qt.ItemDataRole.UserRole + 5
POSITION_ROLE = Qt.ItemDataRole.UserRole + 6
ROW_ROLE = Qt.ItemDataRole.UserRole + 7
COLUMN_ROLE = Qt.ItemDataRole.UserRole + 8
RUN_ID_ROLE = Qt.ItemDataRole.UserRole + 9
BRANDING_ROLE = Qt.ItemDataRole.UserRole + 10


class _TooltipTableParser(HTMLParser):
    """Extract label/value pairs from the HTML table used by queue tooltips."""
    def __init__(self):
        super().__init__()
        self.cells = []
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "td":
            self._cell = []
        elif tag.lower() == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "td" and self._cell is not None:
            self.cells.append(" ".join("".join(self._cell).split()))
            self._cell = None

    def metadata(self):
        result = {}
        for index in range(0, len(self.cells) - 1, 2):
            key = self.cells[index].strip().lower()
            value = unescape(self.cells[index + 1]).strip()
            if key and value and value != "—":
                result[key] = value
        return result


class _ThumbnailDelegate(QStyledItemDelegate):
    """Paint ratings and non-destructive exclusion controls over thumbnails."""
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        rating = int(index.data(RATING_ROLE) or 0)
        excluded = bool(index.data(EXCLUDED_ROLE))
        painter.save()
        # Paint normal icon and selection background first.
        style = opt.widget.style() if opt.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        rect = option.rect
        if excluded:
            painter.fillRect(rect, QColor(5, 8, 18, 155))
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1))
            painter.drawText(rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, "EXCLUDED")
        # High-contrast selection frame: clearly distinguish the active image
        # against dark UI backgrounds and varied thumbnail colors.
        list_widget = self.parent()
        # DR owns persistent selection explicitly on each thumbnail. Qt's
        # transient/current selection state is not the source of truth.
        is_selected = bool(index.data(SELECTED_ROLE))
        is_current = (
            isinstance(list_widget, _ThumbnailList)
            and list_widget.overview_active
            and list_widget.currentIndex().isValid()
            and list_widget.currentIndex() == index
        )
        if is_selected:
            # Persistent multi-selection is blue, except when the current item
            # is outside Overview. In that context use a neutral grey frame so
            # the current image does not look actively selected in the filmstrip.
            if (
                isinstance(list_widget, _ThumbnailList)
                and list_widget.currentIndex().isValid()
                and list_widget.currentIndex() == index
                and not list_widget.overview_active
            ):
                frame_color = QColor(150, 158, 174)
            else:
                frame_color = QColor(45, 135, 255)
            painter.setPen(QPen(frame_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        if is_current:
            # Current keyboard/mouse position is distinct from persistent
            # selection: brighter cyan and thicker, whether selected or not.
            # Draw it last so the active position remains immediately visible.
            painter.setPen(QPen(QColor(105, 245, 255), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(6, 6, -7, -7))
        is_branding = bool(index.data(BRANDING_ROLE))
        job_id = index.data(JOB_ID_ROLE)
        if is_branding:
            number_rect = QRect(rect.left() + 9, rect.top() + 9, 48, 19)
            painter.fillRect(number_rect, QColor(0, 155, 205, 235))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, "#0")
        elif job_id is not None:
            number_rect = QRect(rect.left() + 9, rect.top() + 9, 48, 19)
            painter.fillRect(number_rect, QColor(5, 8, 18, 220))
            painter.setPen(QColor(235, 245, 255))
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, f"#{job_id}")
        if not is_branding:
            # Compact, centered control strip: only wide enough for three stars and X.
            strip_width = 88
            band = QRect(
                rect.center().x() - strip_width // 2,
                rect.bottom() - 35,
                strip_width,
                20,
            )
            painter.fillRect(band, QColor(5, 8, 18, 205))
            painter.setPen(QColor(255, 210, 55))
            star_slot = 20
            for star_index in range(3):
                glyph = "★" if rating >= star_index + 1 else "☆"
                painter.drawText(
                    QRect(band.left() + 2 + star_index * star_slot, band.top(), star_slot, band.height()),
                    Qt.AlignmentFlag.AlignCenter, glyph,
                )
            painter.setPen(QColor(255, 115, 115) if excluded else QColor(230, 235, 245))
            painter.drawText(QRect(band.right() - 20, band.top(), 18, band.height()), Qt.AlignmentFlag.AlignCenter, "×" if excluded else "X")
        painter.restore()


class _ThumbnailList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_ThumbnailDelegate(self))
        self.setMouseTracking(True)
        self.on_user_navigation = None
        self.overview_active = False
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
    def _notify_user_navigation(self) -> None:
        callback = getattr(self, "on_user_navigation", None)
        if callable(callback):
            callback()

    def selectedItems(self):
        """Return DR-selected thumbnails, independent of Qt's selection model."""
        return [self.item(i) for i in range(self.count()) if bool(self.item(i).data(SELECTED_ROLE))]

    def is_item_selected(self, item) -> bool:
        return item is not None and bool(item.data(SELECTED_ROLE))

    def set_item_selected(self, item, selected: bool) -> None:
        if item is None:
            return
        item.setData(SELECTED_ROLE, bool(selected))
        # Keep Qt's native selection model empty so it cannot mutate DR state
        # as a side effect of current-index navigation.
        index = self.indexFromItem(item)
        if index.isValid() and self.selectionModel().isSelected(index):
            self.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Deselect)
        self.viewport().update(self.visualItemRect(item))

    def clearSelection(self) -> None:
        for item in self.selectedItems():
            item.setData(SELECTED_ROLE, False)
        super().clearSelection()
        self.viewport().update()

    def selectAll(self) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if not item.isHidden():
                item.setData(SELECTED_ROLE, True)
        super().clearSelection()
        self.viewport().update()

    def mousePressEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and item is not None:
            # Any deliberate interaction with a result means the user is browsing
            # the filmstrip; stop auto-following the newest generated image.
            self._notify_user_navigation()
            rect = self.visualItemRect(item)
            y = event.position().y()
            x = event.position().x()
            # Must match the compact centered 20 px strip painted by the delegate.
            strip_width = 88
            band_left = rect.center().x() - strip_width // 2
            band_right = band_left + strip_width
            in_control_band = rect.bottom() - 35 <= y <= rect.bottom() - 16 and band_left <= x <= band_right
            if in_control_band and x >= band_right - 20:
                # Apply the X control to the whole selection when the clicked
                # thumbnail is already selected; otherwise act on that item only.
                targets = self.selectedItems() if item in self.selectedItems() else [item]
                excluded = not bool(item.data(EXCLUDED_ROLE))
                for target in targets:
                    target.setData(EXCLUDED_ROLE, excluded)
                    self.viewport().update(self.visualItemRect(target))
                callback = getattr(self, "on_exclusion_changed", None)
                if callable(callback):
                    callback(item)
                return
            # Same 16 px slots and origin as _ThumbnailDelegate.paint().
            star_left = band_left + 2
            star_slot = 20
            if in_control_band and star_left <= x < star_left + 3 * star_slot:
                rating = max(1, min(3, int((x - star_left) / star_slot) + 1))
                targets = self.selectedItems() if item in self.selectedItems() else [item]
                if not targets:
                    targets = [item]
                all_already_rated = all(int(target.data(RATING_ROLE) or 0) == rating for target in targets)
                new_rating = 0 if all_already_rated else rating
                for target in targets:
                    target.setData(RATING_ROLE, new_rating)
                    self.viewport().update(self.visualItemRect(target))
                if callable(getattr(self, "on_rating_changed", None)):
                    self.on_rating_changed(self.currentItem())
                return
        if event.button() == Qt.MouseButton.LeftButton and item is not None:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.set_item_selected(item, not self.is_item_selected(item))
            elif not (modifiers & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)):
                self.clearSelection()
                self.set_item_selected(item, True)
            self.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._notify_user_navigation()
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, watched, event):
        # Keep the bright cyan current-item frame visible only while the user is
        # interacting with the Overview thumbnails. A click elsewhere in the
        # same DR window deactivates the visual cursor without changing identity,
        # row/column metadata, or persistent selection.
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(watched, QWidget):
            try:
                same_window = watched.window() is self.window()
                inside_overview = watched is self or self.isAncestorOf(watched)
                if same_window:
                    active = bool(inside_overview)
                    if active != self.overview_active:
                        self.overview_active = active
                        self.viewport().update()
            except RuntimeError:
                pass
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space:
            # Ignore Qt key-repeat events: a held Space must not toggle twice.
            if event.isAutoRepeat():
                event.accept()
                return
            item = self.currentItem()
            if item is not None:
                self._notify_user_navigation()
                index = self.indexFromItem(item)
                # Toggle exactly this index once. Do not reset currentItem or
                # invoke a second selection API: both can cause Qt's item view
                # to re-apply selection after the key event.
                self.set_item_selected(item, not self.is_item_selected(item))
                self.viewport().update()
                event.accept()
                return

        navigation_keys = {
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Home, Qt.Key.Key_End,
        }
        if key in navigation_keys:
            current = self.currentItem()
            visible = [
                self.item(i) for i in range(self.count())
                if not self.item(i).isHidden()
            ]
            if not visible:
                event.accept()
                return
            if current not in visible:
                target = visible[0]
            elif key == Qt.Key.Key_Home:
                target = visible[0]
            elif key == Qt.Key.Key_End:
                target = visible[-1]
            else:
                current_rect = self.visualItemRect(current)
                cx = current_rect.center().x()
                cy = current_rect.center().y()
                candidates = []
                for item in visible:
                    if item is current:
                        continue
                    rect = self.visualItemRect(item)
                    x, y = rect.center().x(), rect.center().y()
                    if key == Qt.Key.Key_Up and y < cy:
                        candidates.append((cy - y, abs(cx - x), item))
                    elif key == Qt.Key.Key_Down and y > cy:
                        candidates.append((y - cy, abs(cx - x), item))
                    elif key == Qt.Key.Key_Left and y == cy and x < cx:
                        candidates.append((cx - x, abs(cy - y), item))
                    elif key == Qt.Key.Key_Right and y == cy and x > cx:
                        candidates.append((x - cx, abs(cy - y), item))
                if candidates:
                    candidates.sort(key=lambda entry: (entry[0], entry[1]))
                    target = candidates[0][2]
                else:
                    target = current
            self._notify_user_navigation()
            # Move only the current keyboard cursor. NoUpdate is essential:
            # navigation must not add, remove, or replace the multi-selection.
            self.setCurrentItem(target, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.scrollToItem(target, QAbstractItemView.ScrollHint.EnsureVisible)
            self.viewport().update()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        # Scrolling the result strip means the user is browsing older results;
        # don't pull the selection back to each newly completed image.
        self._notify_user_navigation()
        super().wheelEvent(event)


class _FullscreenPreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None, key_callback=None):
        super().__init__(parent)
        self._source_pixmap = pixmap
        self._key_callback = key_callback
        self.setWindowTitle("Desperate Render — Preview")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("QDialog { background: #050914; }")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.feedback_label = QLabel(self)
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setStyleSheet(
            "QLabel { color: #ffd237; background: rgba(5, 9, 20, 205); "
            "border: 1px solid #35e4ff; border-radius: 10px; "
            "font-size: 36px; font-weight: bold; padding: 12px 22px; }"
        )
        self.feedback_label.hide()
        self._feedback_token = 0
        self._refresh_image()

    def show_feedback(self, text: str) -> None:
        self._feedback_token += 1
        token = self._feedback_token
        self.feedback_label.setText(text)
        self.feedback_label.adjustSize()
        self.feedback_label.move(
            max(12, (self.width() - self.feedback_label.width()) // 2),
            max(12, (self.height() - self.feedback_label.height()) // 2),
        )
        self.feedback_label.show()
        self.feedback_label.raise_()
        QTimer.singleShot(900, lambda: self.feedback_label.hide() if token == self._feedback_token else None)

    def _refresh_image(self) -> None:
        self.image_label.setGeometry(self.rect())
        self.image_label.setPixmap(self._source_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        if self.feedback_label.isVisible():
            self.feedback_label.move(
                max(12, (self.width() - self.feedback_label.width()) // 2),
                max(12, (self.height() - self.feedback_label.height()) // 2),
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_image()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_F, Qt.Key.Key_Escape):
            self.close()
            return
        if callable(self._key_callback) and self._key_callback(event.key()):
            event.accept()
            return
        super().keyPressEvent(event)


class PreviewPanel(QGroupBox):
    """Generated image preview and Lightroom-style result browser filmstrip."""
    THUMBNAIL_WIDTH = 112
    THUMBNAIL_HEIGHT = 84
    FILMSTRIP_HEIGHT = 112

    def __init__(self) -> None:
        super().__init__()
        self._fooocus_outputs_dir: Path | None = None
        self._branding_path = Path(__file__).resolve().parents[2] / BRANDING_FILENAME
        self.setObjectName("mainPanel")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._original_pixmap: QPixmap | None = None
        self._current_image_path: Path | None = None
        self.current_job_id: int | None = None
        self._logo_pixmap = self._load_logo()
        self._zoom = 1.0
        self._job_tooltips_by_id: dict[int, str] = {}
        self._generation_active = False
        self.active_run_id: str | None = None
        self.on_result_metadata_changed = None
        self._auto_follow_new_images = True
        self._fullscreen_dialog = None

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(320, 240)
        self.image.setMouseTracking(True)

        # Rating/exclusion controls are overlaid on the actual displayed image
        # and appear only while the pointer is over the preview.
        self.preview_overlay = QWidget(self.image)
        self.preview_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        overlay_layout = QVBoxLayout(self.preview_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        overlay_layout.addStretch(1)
        overlay_controls = QHBoxLayout()
        overlay_controls.setContentsMargins(15, 0, 15, 15)
        overlay_controls.setSpacing(4)
        self.preview_rating_buttons: list[QPushButton] = []
        for rating in range(1, 4):
            button = QPushButton("☆", self.preview_overlay)
            button.setFixedSize(30, 30)
            button.setStyleSheet(
                "QPushButton { background: transparent; color: #ffd237; "
                "border: none; border-radius: 0px; "
                "font-size: 22px; font-weight: bold; padding: 0px; }"
                "QPushButton:hover { background: rgba(8, 15, 35, 85); }"
            )
            button.setToolTip(f"Rate {rating} star(s)")
            button.clicked.connect(lambda checked=False, value=rating: self._rate_current(value))
            self.preview_rating_buttons.append(button)
            overlay_controls.addWidget(button)
        overlay_controls.addStretch(1)
        self.preview_exclude_button = QPushButton("X", self.preview_overlay)
        self.preview_exclude_button.setFixedSize(30, 30)
        self.preview_exclude_button.setStyleSheet(
            "QPushButton { background: transparent; color: #ff7777; "
            "border: none; border-radius: 0px; "
            "font-size: 21px; font-weight: bold; padding: 0px; }"
            "QPushButton:hover { background: rgba(8, 15, 35, 85); }"
        )
        self.preview_exclude_button.setToolTip("Exclude this image (K to keep it)")
        self.preview_exclude_button.clicked.connect(lambda: self._toggle_current_excluded())
        overlay_controls.addWidget(self.preview_exclude_button)
        overlay_layout.addLayout(overlay_controls)
        self.preview_overlay.hide()
        self.image.installEventFilter(self)
        self.preview_overlay.installEventFilter(self)

        self.thumbnails = _ThumbnailList()
        self.thumbnails.on_rating_changed = self._thumbnail_rating_changed
        self.thumbnails.on_exclusion_changed = self._thumbnail_exclusion_changed
        self.thumbnails.on_user_navigation = self._user_navigated_filmstrip
        self.thumbnails.setObjectName("previewThumbnailStrip")
        self.thumbnails.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbnails.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbnails.setWrapping(False)
        self.thumbnails.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbnails.setMovement(QListWidget.Movement.Static)
        self.thumbnails.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.thumbnails.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumbnails.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumbnails.setIconSize(self._thumbnail_size())
        self.thumbnails.setFixedHeight(self.FILMSTRIP_HEIGHT)
        self.thumbnails.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.thumbnails.setSpacing(4)
        self.thumbnails.currentItemChanged.connect(self._thumbnail_selected)

        self.previous_action = QAction("Previous image", self)
        self.previous_action.setShortcut(QKeySequence(Qt.Key.Key_Left))
        self.previous_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.previous_action.triggered.connect(self.select_previous)
        self.addAction(self.previous_action)
        self.next_action = QAction("Next image", self)
        self.next_action.setShortcut(QKeySequence(Qt.Key.Key_Right))
        self.next_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.next_action.triggered.connect(self.select_next)
        self.addAction(self.next_action)

        fullscreen_action = QAction("Toggle fullscreen preview", self)
        fullscreen_action.setShortcut(QKeySequence(Qt.Key.Key_F))
        fullscreen_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        fullscreen_action.triggered.connect(self.toggle_fullscreen_preview)
        self.addAction(fullscreen_action)

        # Keyboard controls remain active while either the preview or filmstrip has focus.
        for digit in range(4):
            action = QAction(f"Rate {digit} stars", self)
            action.setShortcut(QKeySequence(str(digit)))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda checked=False, value=digit: self._rate_current(value))
            self.addAction(action)
        for key, excluded in ((Qt.Key.Key_X, True), (Qt.Key.Key_K, False)):
            action = QAction("Exclude image" if excluded else "Keep image", self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda checked=False, value=excluded: self._exclude_current(value))
            self.addAction(action)
        select_all_action = QAction("Select all thumbnails", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        select_all_action.triggered.connect(self.thumbnails.selectAll)
        self.addAction(select_all_action)

        self.overview_button = QPushButton("▴  Overview")
        self.overview_button.setObjectName("previewOverviewButton")
        self.overview_button.setToolTip("Expand the filmstrip into a multi-row overview")
        self.overview_button.setCheckable(True)
        self.overview_button.toggled.connect(self._set_overview_mode)

        self.filter_button = QPushButton("Filter")
        self.filter_button.setCheckable(True)
        self.filter_button.setToolTip("Show or hide the result filters")
        self.filter_button.toggled.connect(self._toggle_filter_panel)
        self.filter_count_label = QLabel("")
        self.filter_count_label.setMinimumWidth(68)
        self.reset_filters_button = QPushButton("Reset")
        self.reset_filters_button.setToolTip("Reset all result filters")
        self.reset_filters_button.clicked.connect(self._reset_filters)

        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("previewExportButton")
        self.export_button.setToolTip("Copy the currently visible Overview images to a folder")
        self.export_button.clicked.connect(self._export_visible_overview)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("previewFilterCombo")
        self.filter_combo.setMinimumHeight(30)
        self.filter_combo.setStyleSheet(
            "QComboBox { background: #111b38; color: #e8f2ff; "
            "border: 1px solid #263b66; border-radius: 4px; padding: 5px 8px; }"
            "QComboBox:hover { border-color: #00cfff; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background: #111b38; color: #e8f2ff; "
            "selection-background-color: #16435a; border: 1px solid #263b66; }"
        )
        self.filter_combo.setToolTip("Filter by rating and exclusion state")
        for label, value in [
            ("Any rating / status", "all"), ("Not excluded", "kept"),
            ("Excluded", "excluded"), ("Unrated", "unrated"),
            ("Rated", "rated"), ("★ 1", "rating1"), ("★★ 2", "rating2"),
            ("★★★ 3", "rating3"), ("Rating > 0", "rating_gt0"),
            ("Rating > 1", "rating_gt1"), ("Rating > 2", "rating_gt2"),
            ("Rating < 1", "rating_lt1"), ("Rating < 2", "rating_lt2"),
            ("Rating < 3", "rating_lt3"),
        ]:
            self.filter_combo.addItem(label, value)
        self.filter_combo.currentIndexChanged.connect(self._apply_thumbnail_filter)

        self.metadata_filters = {}
        filter_grid = QGridLayout()
        filter_grid.setContentsMargins(0, 0, 0, 0)
        filter_grid.setHorizontalSpacing(6)
        filter_grid.setVerticalSpacing(4)
        filter_specs = [
            ("Base Model", "base model"), ("Styles", "styles"),
            ("Seed", "seed"), ("Guidance Scale", "guidance scale"),
            ("Sharpness", "sharpness"), ("Resolution", "resolution"),
            ("Performance", "performance"),
        ]
        for index, (label, key) in enumerate(filter_specs):
            combo = QComboBox()
            combo.setMinimumWidth(105)
            combo.setMinimumHeight(30)
            combo.setStyleSheet(
                "QComboBox { background: #111b38; color: #e8f2ff; "
                "border: 1px solid #263b66; border-radius: 4px; padding: 5px 8px; }"
                "QComboBox:hover { border-color: #00cfff; }"
                "QComboBox::drop-down { border: none; width: 20px; }"
                "QComboBox QAbstractItemView { background: #111b38; color: #e8f2ff; "
                "selection-background-color: #16435a; border: 1px solid #263b66; }"
            )
            combo.setToolTip(f"Filter by {label}")
            combo.addItem(f"Any {label}", "")
            combo.currentIndexChanged.connect(self._apply_thumbnail_filter)
            self.metadata_filters[key] = combo
            filter_grid.addWidget(combo, index // 4, index % 4)
        self.prompt_filter = QLineEdit()
        self.prompt_filter.setPlaceholderText("Search prompt text…")
        self.prompt_filter.setToolTip("Show results whose positive or negative prompt contains this text")
        self.prompt_filter.textChanged.connect(self._apply_thumbnail_filter)
        filter_grid.addWidget(self.prompt_filter, 2, 0, 1, 4)
        self.filter_panel = QWidget()
        self.filter_panel.setLayout(filter_grid)
        self.filter_panel.hide()

        self.sort_combo = QComboBox()
        self.sort_combo.setMinimumHeight(30)
        self.sort_combo.setMinimumWidth(135)
        self.sort_combo.setStyleSheet(
            "QComboBox { background: #111b38; color: #e8f2ff; "
            "border: 1px solid #263b66; border-radius: 4px; padding: 5px 8px; }"
            "QComboBox:hover { border-color: #00cfff; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background: #111b38; color: #e8f2ff; "
            "selection-background-color: #16435a; border: 1px solid #263b66; }"
        )
        self.sort_combo.setToolTip("Sort the visible results")
        for label, key in [
            ("Order: newest", "newest"), ("Oldest", "oldest"),
            ("Prompt", "prompt"), ("Seed", "seed"), ("Base Model", "base model"),
            ("Styles", "styles"), ("Guidance Scale", "guidance scale"),
            ("Sharpness", "sharpness"), ("Rating", "rating"), ("Filename", "filename"),
        ]:
            self.sort_combo.addItem(label, key)
        self.sort_combo.currentIndexChanged.connect(self._sort_thumbnails)

        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setToolTip("Zoom thumbnails out")
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom thumbnails in")
        self.zoom_out_button.clicked.connect(lambda: self._set_zoom(self._zoom / 1.2))
        self.zoom_in_button.clicked.connect(lambda: self._set_zoom(self._zoom * 1.2))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(42)
        # Responsive, multi-row toolbar: a single horizontal row caused
        # buttons and combo boxes to overlap when the Preview panel was narrow.
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(6)
        controls.addWidget(self.overview_button, 0, 0)
        controls.addWidget(self.filter_button, 0, 1)
        controls.addWidget(self.filter_count_label, 0, 2)
        controls.addWidget(self.reset_filters_button, 0, 3)
        controls.addWidget(self.export_button, 0, 4)
        controls.addWidget(self.filter_combo, 1, 0, 1, 2)
        controls.addWidget(self.sort_combo, 1, 2, 1, 2)
        zoom_controls = QWidget()
        zoom_layout = QHBoxLayout(zoom_controls)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(8)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(self.zoom_in_button)
        controls.addWidget(zoom_controls, 0, 5, 2, 1, Qt.AlignmentFlag.AlignRight)
        controls.setColumnStretch(5, 1)

        # Keep labels readable and allow the panel to shrink without collisions.
        self.overview_button.setMinimumWidth(126)
        self.filter_button.setMinimumWidth(104)
        self.reset_filters_button.setMinimumWidth(72)
        self.export_button.setMinimumWidth(92)
        self.filter_combo.setMinimumWidth(150)
        self.sort_combo.setMinimumWidth(138)
        self.zoom_out_button.setFixedSize(38, 36)
        self.zoom_in_button.setFixedSize(38, 36)
        self.zoom_label.setMinimumWidth(46)

        filmstrip_widget = QWidget()
        filmstrip_layout = QVBoxLayout(filmstrip_widget)
        filmstrip_layout.setContentsMargins(0, 0, 0, 0)
        filmstrip_layout.setSpacing(4)
        filmstrip_layout.addLayout(controls)
        filmstrip_layout.addWidget(self.filter_panel)
        filmstrip_layout.addWidget(self.thumbnails)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.image)
        self.splitter.addWidget(filmstrip_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([600, self.FILMSTRIP_HEIGHT + 42])

        layout = QVBoxLayout(self)
        title = QLabel("Preview")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self.splitter, 1)
        self._show_logo()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._fullscreen_dialog and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_F, Qt.Key.Key_Escape):
                watched.close()
                return True
        if watched is self.image:
            if event.type() == QEvent.Type.Resize:
                if self._original_pixmap is not None:
                    self._update_preview()
                else:
                    self._update_logo()
            elif event.type() == QEvent.Type.Enter and self._original_pixmap is not None:
                current = self.thumbnails.currentItem()
                if current is not None and current.data(BRANDING_ROLE):
                    self.preview_overlay.hide()
                else:
                    self._position_preview_overlay()
                    self.preview_overlay.show()
                    self.preview_overlay.raise_()
            elif event.type() == QEvent.Type.Leave:
                self.preview_overlay.hide()
        elif watched is self.preview_overlay:
            if event.type() == QEvent.Type.Enter and self._original_pixmap is not None:
                self.preview_overlay.show()
            elif event.type() == QEvent.Type.Leave:
                # Moving between the image and its overlay should not leave controls stuck on.
                from PySide6.QtGui import QCursor
                if not self.image.rect().contains(self.image.mapFromGlobal(QCursor.pos())):
                    self.preview_overlay.hide()
        return super().eventFilter(watched, event)

    def _position_preview_overlay(self) -> None:
        if self._original_pixmap is None or self._original_pixmap.isNull():
            self.preview_overlay.hide()
            return
        displayed = self._original_pixmap.scaled(
            self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).size()
        left = (self.image.width() - displayed.width()) // 2
        top = (self.image.height() - displayed.height()) // 2
        self.preview_overlay.setGeometry(left, top, displayed.width(), displayed.height())
        self.preview_overlay.raise_()

    def _set_overview_mode(self, enabled: bool) -> None:
        if enabled:
            self.overview_button.setText("▾  Close Overview")
            self.overview_button.setToolTip("Return to the single-row filmstrip")
            self.thumbnails.setWrapping(True)
            self.thumbnails.setFlow(QListWidget.Flow.LeftToRight)
            self.thumbnails.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.thumbnails.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.thumbnails.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.thumbnails.setMinimumHeight(190)
            self.thumbnails.setMaximumHeight(16777215)
            self.thumbnails.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.splitter.setSizes([max(260, int(self.splitter.height() * 0.58)), max(220, int(self.splitter.height() * 0.42))])
        else:
            self.overview_button.setText("▴  Overview")
            self.overview_button.setToolTip("Expand the filmstrip into a multi-row overview")
            self.thumbnails.setWrapping(False)
            self.thumbnails.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.thumbnails.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.thumbnails.setMinimumHeight(self.FILMSTRIP_HEIGHT)
            self.thumbnails.setMaximumHeight(self.FILMSTRIP_HEIGHT)
            self.thumbnails.setFixedHeight(self.FILMSTRIP_HEIGHT)
            self.thumbnails.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.splitter.setSizes([max(300, self.splitter.height() - 160), 160])
        self.thumbnails.doItemsLayout()
        self._refresh_thumbnail_positions()
        self.thumbnails.viewport().update()

    def _set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.55, min(2.2, zoom))
        width = int(self.THUMBNAIL_WIDTH * self._zoom)
        height = int(self.THUMBNAIL_HEIGHT * self._zoom)
        self.thumbnails.setIconSize(QSize(width, height))
        self.thumbnails.setGridSize(QSize(width + 12, height + 32))
        for i in range(self.thumbnails.count()):
            item = self.thumbnails.item(i)
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(QSize(width, height), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            item.setSizeHint(QSize(width + 8, height + 8))
        self.zoom_label.setText(f"{int(self._zoom * 100)}%")
        self.thumbnails.doItemsLayout()

    def _thumbnail_size(self) -> QSize:
        return QSize(int(self.THUMBNAIL_WIDTH * self._zoom), int(self.THUMBNAIL_HEIGHT * self._zoom))

    @staticmethod
    def _load_logo() -> QPixmap:
        logo_path = Path(__file__).resolve().parents[2] / "preview.png"
        pixmap = QPixmap(str(logo_path))
        return pixmap if not pixmap.isNull() else QPixmap()

    def _show_logo(self) -> None:
        """Reset result history and show only the standard startup preview."""
        self._original_pixmap = None
        self._current_image_path = None
        self.current_job_id = None
        self.thumbnails.clear()
        self._job_tooltips_by_id = {}
        self._sync_preview_controls(None)
        self.preview_overlay.hide()
        self.image.setToolTip("")
        if self._logo_pixmap.isNull():
            self.image.setPixmap(QPixmap())
            self.image.setText("No image selected")
        else:
            self._update_logo()

    @property
    def fooocus_outputs_dir(self) -> Path | None:
        return self._fooocus_outputs_dir

    def _create_branding_item(self) -> QListWidgetItem | None:
        """Insert the non-result branding card at the fixed first position."""
        if not self._branding_path.is_file():
            return None
        pixmap = QPixmap(str(self._branding_path))
        if pixmap.isNull():
            return None
        item = QListWidgetItem(QIcon(pixmap.scaled(
            self._thumbnail_size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )), "")
        item.setToolTip("Desperate Render branding card — reserved image #0, not a generation result")
        item.setData(Qt.ItemDataRole.UserRole, str(self._branding_path))
        item.setData(RATING_ROLE, 0)
        item.setData(EXCLUDED_ROLE, False)
        item.setData(METADATA_ROLE, {})
        item.setData(JOB_ID_ROLE, 0)
        item.setData(RUN_ID_ROLE, None)
        item.setData(SELECTED_ROLE, False)
        item.setData(BRANDING_ROLE, True)
        item.setData(POSITION_ROLE, 0)
        item.setData(ROW_ROLE, 0)
        item.setData(COLUMN_ROLE, 0)
        item.setSizeHint(QSize(self._thumbnail_size().width() + 8, self._thumbnail_size().height() + 8))
        self.thumbnails.insertItem(0, item)
        return item

    def ensure_branding_thumbnail(self, select_if_missing: bool = False) -> None:
        """Show the reserved branding card after at least one real result exists."""
        if not any(
            not self.thumbnails.item(i).data(BRANDING_ROLE)
            for i in range(self.thumbnails.count())
        ):
            return
        branding_item = next(
            (self.thumbnails.item(i) for i in range(self.thumbnails.count())
             if self.thumbnails.item(i).data(BRANDING_ROLE)),
            None,
        )
        if branding_item is None:
            branding_item = self._create_branding_item()
        elif self.thumbnails.row(branding_item) != 0:
            self.thumbnails.takeItem(self.thumbnails.row(branding_item))
            self.thumbnails.insertItem(0, branding_item)
        if branding_item is not None:
            self._refresh_thumbnail_positions()
            if select_if_missing and self.thumbnails.currentItem() is None:
                self.thumbnails.setCurrentItem(branding_item, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _update_logo(self) -> None:
        if self._logo_pixmap.isNull():
            return
        self.image.setPixmap(self._logo_pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.image.setText("")

    def set_fooocus_path(self, fooocus_path: str | Path | None) -> None:
        """Configure Fooocus' canonical outputs directory from its install path."""
        raw = str(fooocus_path or "").strip()
        if not raw:
            self._fooocus_outputs_dir = None
            return
        root = Path(raw).expanduser()
        candidates = [root] if root.name.lower() == "outputs" else [root / "outputs", root / "Fooocus" / "outputs"]
        self._fooocus_outputs_dir = next(
            (candidate.resolve() for candidate in candidates if candidate.is_dir()),
            candidates[0].resolve(),
        )

    def _resolve_generated_output_path(self, raw_path: str | Path) -> Path | None:
        """Resolve a newly generated Gradio path only inside today's Fooocus output folder.

        Persisted paths are never searched or rewritten: each saved result must point
        directly to its canonical output file, including its original date folder.
        """
        original = Path(str(raw_path or "")).expanduser()
        outputs = self._fooocus_outputs_dir
        if is_branding_asset_path(original):
            return None
        if outputs is None or not original.name:
            return None

        # Fooocus writes generated images to a date-named subfolder. Only inspect
        # today's folder for newly generated results; never search other days.
        dated_output = outputs / date.today().isoformat()
        candidates = (dated_output / original.name, outputs / original.name)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        # If Fooocus itself supplied a path already inside outputs, keep that exact
        # path (including an older date folder) only if the file exists.
        try:
            resolved = original.resolve()
            resolved.relative_to(outputs.resolve())
            if resolved.is_file():
                return resolved
        except (OSError, ValueError):
            pass
        return None

    def set_images(self, result: ImageGenerationResult) -> None:
        """Append completed-job images; a new run clears history explicitly."""
        self.add_images(result)

    def add_images(self, result: ImageGenerationResult) -> None:
        """Append completed images and auto-follow only while the user hasn't browsed away."""
        last_item = None
        for image_name in result.images:
            if is_branding_asset_path(image_name):
                continue
            image_path = self._resolve_generated_output_path(image_name)
            if image_path is None or not image_path.is_file():
                continue
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                continue
            existing = self._find_path(image_path)
            if existing is not None:
                last_item = existing
                continue
            job_tooltip = self._job_tooltips_by_id.get(result.job_id, "") if result.job_id is not None else ""
            if not job_tooltip and result.job_id is None:
                position = self.thumbnails.count()
                job_tooltip = self._job_tooltips_by_id.get(position + 1, "")
            # The branding card becomes Preview item #0 only once an actual
            # generated image has been validated and is ready to enter history.
            record = {
                "path": str(image_path), "job_id": result.job_id,
                "run_id": self.active_run_id, "rating": 0,
                "excluded": False, "metadata": {}, "tooltip": job_tooltip,
            }
            last_item = self._create_result_item(record, pixmap=pixmap)
            # The first valid generated result now exists in the filmstrip;
            # insert branding at #0 only after this point.
            self.ensure_branding_thumbnail()
        if last_item is not None:
            # Queue details are often registered just before this image is
            # appended. Re-apply them now that the new thumbnail exists, so
            # its metadata participates in the same sort/filter pass as every
            # older thumbnail. This also prevents the newest item from being
            # left at the end after the previous list was sorted.
            self.set_job_tooltips(self._job_tooltips_by_id)
        else:
            self._refresh_thumbnail_positions()
        if last_item is not None and self._auto_follow_new_images:
            # Auto-follow selects only the newest result. As soon as the user
            # browses or makes a selection, preserve that selection instead.
            self.thumbnails.setCurrentItem(last_item, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.thumbnails.scrollToItem(last_item, QAbstractItemView.ScrollHint.PositionAtCenter)
            if self._generation_active:
                self.thumbnails.setFocus(Qt.FocusReason.OtherFocusReason)

    def _create_result_item(self, record: dict, pixmap: QPixmap | None = None) -> QListWidgetItem:
        """Create a thumbnail entry, retaining a visible placeholder if the file is missing."""
        image_path = Path(str(record.get("path", "")))
        exists = image_path.is_file()
        if pixmap is None and exists:
            pixmap = QPixmap(str(image_path))
        valid_pixmap = pixmap is not None and not pixmap.isNull()
        if valid_pixmap:
            item = QListWidgetItem(QIcon(pixmap.scaled(self._thumbnail_size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)), "")
        else:
            item = QListWidgetItem("result file missing")
            item.setToolTip(f"<b>result file missing</b><br>{image_path}")
        details = str(record.get("tooltip", "") or "")
        job_id = record.get("job_id")
        if exists:
            run_id = record.get("run_id")
            run_line = f"<b>Run</b> {run_id}<br>" if run_id else ""
            item.setToolTip((details + f"<hr>{run_line}<b>Job</b> #{job_id}<br><b>Image</b><br>{image_path}") if details else f"{run_line}<b>Job</b> #{job_id}<br><b>Image</b><br>{image_path}")
        item.setData(Qt.ItemDataRole.UserRole, str(image_path))
        item.setData(RATING_ROLE, int(record.get("rating", 0) or 0))
        item.setData(EXCLUDED_ROLE, bool(record.get("excluded", False)))
        item.setData(METADATA_ROLE, normalize_filter_metadata(record.get("metadata", {}) or {}))
        item.setData(JOB_ID_ROLE, job_id)
        item.setData(RUN_ID_ROLE, record.get("run_id"))
        item.setData(SELECTED_ROLE, bool(record.get("selected", False)))
        item.setData(BRANDING_ROLE, False)
        item.setData(POSITION_ROLE, self.thumbnails.count() + 1)
        item.setData(ROW_ROLE, 0)
        item.setData(COLUMN_ROLE, 0)
        item.setSizeHint(QSize(self._thumbnail_size().width() + 8, self._thumbnail_size().height() + 8))
        self.thumbnails.addItem(item)
        return item

    def restore_result_runs(self, runs: list[dict]) -> None:
        """Rebuild from canonical saved paths, clearing and deduplicating the view."""
        self.thumbnails.clear()
        self._show_logo()
        self.active_run_id = None
        self._auto_follow_new_images = False
        seen_paths: set[str] = set()
        for run in runs:
            run_id = run.get("run_id")
            for record in run.get("images", []):
                restored = dict(record)
                restored.setdefault("run_id", run_id)
                raw_path = str(restored.get("path", "") or "")
                # The branding copy in Fooocus outputs is reserved and never a result.
                if is_branding_asset_path(raw_path):
                    continue
                # No legacy Temp-path resolution and no cross-day searching.
                canonical_path = Path(raw_path)
                key = canonical_result_path_key(str(canonical_path))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                self._create_result_item(restored)
        # Restoring a history with real results reactivates the reserved #0 card;
        # an empty/new experiment keeps only the standard preview placeholder.
        self.ensure_branding_thumbnail()
        self._refresh_filter_choices()
        if self.sort_combo.currentData():
            self._sort_thumbnails()
        else:
            self._apply_thumbnail_filter()
        self._refresh_thumbnail_positions()
        if self.thumbnails.count():
            self.thumbnails.setCurrentRow(0)

    def result_run_snapshot(self) -> list[dict]:
        """Serialize the visible history by stable run ID, including missing files."""
        grouped: dict[str, dict] = {}
        for index in range(self.thumbnails.count()):
            item = self.thumbnails.item(index)
            if item.data(BRANDING_ROLE) or is_branding_asset_path(
                item.data(Qt.ItemDataRole.UserRole)
            ):
                continue
            run_id = item.data(RUN_ID_ROLE) or self.active_run_id
            if not run_id:
                # Legacy/untracked thumbnail: keep it in a dedicated stable bucket.
                run_id = "legacy-imported-results"
            run = grouped.setdefault(str(run_id), {"run_id": str(run_id), "created_at": "", "images": []})
            run["images"].append({
                "path": str(item.data(Qt.ItemDataRole.UserRole) or ""),
                "job_id": item.data(JOB_ID_ROLE),
                "run_id": str(run_id),
                "rating": int(item.data(RATING_ROLE) or 0),
                "excluded": bool(item.data(EXCLUDED_ROLE)),
                "metadata": dict(item.data(METADATA_ROLE) or {}),
                "tooltip": str(item.toolTip() or ""),
                "selected": bool(item.data(SELECTED_ROLE)),
            })
        from datetime import datetime
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        for run in grouped.values():
            run["created_at"] = now
        return list(grouped.values())

    def set_generation_active(self, active: bool) -> None:
        """Enable/disable live auto-follow for the current generation run."""
        self._generation_active = bool(active)
        if active:
            self._auto_follow_new_images = True

    def _user_navigated_filmstrip(self) -> None:
        # Manual navigation takes precedence even if generation has just ended.
        self._auto_follow_new_images = False

    def _find_path(self, image_path: Path) -> QListWidgetItem | None:
        target = canonical_result_path_key(str(image_path))
        for index in range(self.thumbnails.count()):
            item = self.thumbnails.item(index)
            if canonical_result_path_key(str(item.data(Qt.ItemDataRole.UserRole) or "")) == target:
                return item
        return None

    def _thumbnail_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        self.current_job_id = current.data(JOB_ID_ROLE) if current is not None else None
        if current is None:
            return
        image_path = Path(current.data(Qt.ItemDataRole.UserRole))
        if not image_path.is_file():
            self._original_pixmap = None
            self._current_image_path = image_path
            self.image.setPixmap(QPixmap())
            self.image.setText("result file missing")
            self.image.setToolTip(current.toolTip())
            self._sync_preview_controls(current)
            return
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self._original_pixmap = None
            self._current_image_path = image_path
            self.image.setPixmap(QPixmap())
            self.image.setText("result file missing")
            self.image.setToolTip(current.toolTip())
            self._sync_preview_controls(current)
            return
        self._original_pixmap = pixmap
        self._current_image_path = image_path
        tooltip = current.toolTip()
        self.image.setToolTip(tooltip)
        self._sync_preview_controls(current)
        self._update_preview()
        # Qt does not refresh an already visible tooltip just because its text
        # changed. Re-show it when keyboard navigation changes the image under
        # a stationary pointer over the large preview.
        if self.image.rect().contains(self.image.mapFromGlobal(QCursor.pos())):
            QToolTip.hideText()
            if tooltip:
                QToolTip.showText(QCursor.pos(), tooltip, self.image)

    def set_job_tooltips(self, tooltips: list[str] | dict[int, str]) -> None:
        """Attach parameter details by durable Job#, never by thumbnail position."""
        if isinstance(tooltips, dict):
            self._job_tooltips_by_id = {int(key): value for key, value in tooltips.items()}
        else:
            self._job_tooltips_by_id = {index: value for index, value in enumerate(tooltips, start=1)}
        for index in range(self.thumbnails.count()):
            item = self.thumbnails.item(index)
            if item.data(BRANDING_ROLE):
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            job_id = item.data(JOB_ID_ROLE)
            details = self._job_tooltips_by_id.get(job_id, "")
            run_id = item.data(RUN_ID_ROLE)
            run_line = f"<b>Run</b> {run_id}<br>" if run_id else ""
            item.setToolTip((details + f"<hr>{run_line}<b>Job</b> #{job_id}<br><b>Image</b><br>{path}") if details else f"{run_line}<b>Job</b> #{job_id}<br><b>Image</b><br>{path}")
            parser = _TooltipTableParser()
            parser.feed(details or "")
            metadata = normalize_filter_metadata(parser.metadata())
            metadata["filename"] = Path(path).name
            metadata["path"] = str(path)
            metadata["job id"] = str(job_id) if job_id is not None else ""
            metadata["prompt"] = metadata.get("prompt", "")
            metadata["negative prompt"] = metadata.get("negative prompt", "")
            item.setData(METADATA_ROLE, metadata)
        self._refresh_filter_choices()
        # A completed job can change both the active filter result and the
        # requested order. Re-apply the selected sort after the new image's
        # metadata has been attached, so sorting never uses stale metadata.
        if self.sort_combo.currentData():
            self._sort_thumbnails()
        else:
            self._apply_thumbnail_filter()
        current = self.thumbnails.currentItem()
        if current is not None:
            self.image.setToolTip(current.toolTip())

    def _refresh_thumbnail_positions(self) -> None:
        """Store display position and visual row/column without changing Job# identity."""
        self.thumbnails.doItemsLayout()
        visible = []
        for index in range(self.thumbnails.count()):
            item = self.thumbnails.item(index)
            item.setData(POSITION_ROLE, 0 if item.data(BRANDING_ROLE) else index + 1)
            if not item.isHidden():
                rect = self.thumbnails.visualItemRect(item)
                visible.append((item, rect.center().x(), rect.center().y()))
        # Group items by their actual rendered y-coordinate; this works for both
        # the single-row filmstrip and the wrapping overview after resize/filter.
        row_centers = []
        tolerance = max(4, self.thumbnails.gridSize().height() // 3)
        for _, _, y in sorted(visible, key=lambda entry: entry[2]):
            if not row_centers or abs(y - row_centers[-1]) > tolerance:
                row_centers.append(y)
        for item, x, y in visible:
            row_index = min(range(len(row_centers)), key=lambda i: abs(row_centers[i] - y))
            same_row = sorted((entry for entry in visible if abs(entry[2] - row_centers[row_index]) <= tolerance), key=lambda entry: entry[1])
            column_index = next((i for i, entry in enumerate(same_row) if entry[0] is item), 0)
            item.setData(ROW_ROLE, row_index + 1)
            item.setData(COLUMN_ROLE, column_index + 1)

    def _notify_result_metadata_changed(self) -> None:
        callback = getattr(self, "on_result_metadata_changed", None)
        if callable(callback):
            callback()

    def _thumbnail_rating_changed(self, item: QListWidgetItem | None = None) -> None:
        self._sync_preview_controls(item)
        self._notify_result_metadata_changed()

    def _thumbnail_exclusion_changed(self, item: QListWidgetItem | None = None) -> None:
        self._sync_preview_controls(item)
        self._notify_result_metadata_changed()

    def _sync_preview_controls(self, item: QListWidgetItem | None = None) -> None:
        item = item or self.thumbnails.currentItem()
        is_branding = bool(item.data(BRANDING_ROLE)) if item is not None else False
        rating = int(item.data(RATING_ROLE) or 0) if item is not None else 0
        excluded = bool(item.data(EXCLUDED_ROLE)) if item is not None else False
        for index, button in enumerate(self.preview_rating_buttons, start=1):
            button.setText("★" if rating >= index else "☆")
            button.setEnabled(not is_branding)
        self.preview_exclude_button.setText("×" if excluded else "X")
        self.preview_exclude_button.setEnabled(not is_branding)
        if is_branding:
            self.preview_overlay.hide()

    def _toggle_current_excluded(self) -> None:
        item = self.thumbnails.currentItem()
        if item is not None:
            self._exclude_current(not bool(item.data(EXCLUDED_ROLE)))

    def _visible_rows(self) -> list[int]:
        return [row for row in range(self.thumbnails.count()) if not self.thumbnails.isRowHidden(row)]

    def _export_visible_overview(self) -> None:
        """Export the currently filter-visible result thumbnails, excluding branding."""
        source_paths = []
        for row in range(self.thumbnails.count()):
            item = self.thumbnails.item(row)
            if self.thumbnails.isRowHidden(row) or item.data(BRANDING_ROLE):
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and not is_branding_asset_path(path):
                source_paths.append(str(path))

        if not source_paths:
            QMessageBox.information(
                self,
                "Export Overview",
                "There are no visible result images to export.",
            )
            return

        destination = QFileDialog.getExistingDirectory(
            self,
            "Export Overview images",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not destination:
            return

        summary = export_overview_images(source_paths, destination)
        lines = [f"Exported: {summary.copied} image(s)"]
        if summary.skipped_existing:
            lines.append(f"Skipped (filename already exists): {summary.skipped_existing}")
        if summary.skipped_missing:
            lines.append(f"Skipped (source file missing): {summary.skipped_missing}")
        if summary.errors:
            lines.append(f"Errors: {len(summary.errors)}")
            lines.extend(summary.errors[:5])
            if len(summary.errors) > 5:
                lines.append(f"… and {len(summary.errors) - 5} more")
        QMessageBox.information(
            self,
            "Export Overview",
            "\n".join(lines) + f"\n\nDestination:\n{destination}",
        )

    def _toggle_filter_panel(self, visible: bool) -> None:
        self.filter_panel.setVisible(visible)
        self.filter_button.setText("Hide filters" if visible else "Filter")

    def _refresh_filter_choices(self) -> None:
        for key, combo in self.metadata_filters.items():
            current = combo.currentData()
            values = sorted({
                str((item.data(METADATA_ROLE) or {}).get(key, "")).strip()
                for row in range(self.thumbnails.count())
                for item in [self.thumbnails.item(row)]
                if str((item.data(METADATA_ROLE) or {}).get(key, "")).strip()
            }, key=str.casefold)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"Any {key.title()}", "")
            for value in values:
                combo.addItem(value, value)
            idx = combo.findData(current)
            combo.setCurrentIndex(max(0, idx))
            combo.blockSignals(False)

    def _reset_filters(self) -> None:
        self.filter_combo.setCurrentIndex(0)
        self.prompt_filter.clear()
        for combo in self.metadata_filters.values():
            combo.setCurrentIndex(0)
        self._apply_thumbnail_filter()

    def _active_filter_count(self) -> int:
        count = int(self.filter_combo.currentData() not in (None, "all"))
        count += sum(combo.currentData() not in (None, "") for combo in self.metadata_filters.values())
        count += int(bool(self.prompt_filter.text().strip()))
        return count

    def _apply_thumbnail_filter(self, *_args) -> None:
        mode = self.filter_combo.currentData()
        prompt_query = self.prompt_filter.text().strip().casefold()
        selected_metadata = {key: combo.currentData() for key, combo in self.metadata_filters.items() if combo.currentData()}
        current = self.thumbnails.currentItem()
        for row in range(self.thumbnails.count()):
            item = self.thumbnails.item(row)
            if item.data(BRANDING_ROLE):
                self.thumbnails.setRowHidden(row, False)
                continue
            rating = int(item.data(RATING_ROLE) or 0)
            excluded = bool(item.data(EXCLUDED_ROLE))
            metadata = item.data(METADATA_ROLE) or {}
            visible = (
                mode == "all"
                or (mode == "kept" and not excluded)
                or (mode == "excluded" and excluded)
                or (mode == "unrated" and rating == 0)
                or (mode == "rated" and rating > 0)
                or (mode == "rating1" and rating == 1)
                or (mode == "rating2" and rating == 2)
                or (mode == "rating3" and rating == 3)
                or (mode == "rating_gt0" and rating > 0)
                or (mode == "rating_gt1" and rating > 1)
                or (mode == "rating_gt2" and rating > 2)
                or (mode == "rating_lt1" and rating < 1)
                or (mode == "rating_lt2" and rating < 2)
                or (mode == "rating_lt3" and rating < 3)
            )
            if visible and not matches_metadata_filters(metadata, selected_metadata):
                visible = False
            if prompt_query:
                prompt_text = f"{metadata.get('prompt', '')} {metadata.get('negative prompt', '')}".casefold()
                visible = visible and prompt_query in prompt_text
            self.thumbnails.setRowHidden(row, not visible)
        visible_rows = self._visible_rows()
        if visible_rows and (current is None or self.thumbnails.isRowHidden(self.thumbnails.row(current))):
            self.thumbnails.setCurrentItem(self.thumbnails.item(visible_rows[0]), QItemSelectionModel.SelectionFlag.NoUpdate)
        elif not visible_rows:
            self._original_pixmap = None
            self._current_image_path = None
            self.image.setPixmap(QPixmap())
            self.image.setText("No images match these filters")
        active_count = self._active_filter_count()
        self.filter_count_label.setText("")
        self.filter_button.setText(("Hide filters" if self.filter_button.isChecked() else "Filter") + (f" ({active_count})" if active_count else ""))
        self.thumbnails.doItemsLayout()

    def _sort_thumbnails(self, *_args) -> None:
        key = self.sort_combo.currentData()
        if not key:
            return

        # Preserve the active image by identity, not by its former row/index.
        current_job_id = self.current_job_id
        current_path = self._current_image_path
        items = [self.thumbnails.takeItem(0) for _ in range(self.thumbnails.count())]

        def job_id_value(item):
            value = item.data(JOB_ID_ROLE)
            try:
                return int(value)
            except (TypeError, ValueError):
                # Items without a job id remain deterministic and follow
                # numbered jobs, rather than inheriting their former position.
                return 2**63 - 1

        def sort_value(item):
            metadata = item.data(METADATA_ROLE) or {}
            if key == "newest":
                return job_id_value(item)
            if key == "oldest":
                return job_id_value(item)
            if key == "rating":
                return int(item.data(RATING_ROLE) or 0)
            value = metadata.get(key, "")
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                return (1, str(value).casefold())

        branding_items = [item for item in items if item.data(BRANDING_ROLE)]
        result_items = [item for item in items if not item.data(BRANDING_ROLE)]
        if key == "oldest":
            ordered = sorted(result_items, key=sort_value)
        elif key == "newest":
            ordered = sorted(result_items, key=sort_value, reverse=True)
        else:
            ordered = sorted(result_items, key=sort_value)
        ordered = branding_items + ordered

        for item in ordered:
            self.thumbnails.addItem(item)

        # Row/column are presentation state, so recalculate after reordering.
        self._refresh_thumbnail_positions()
        target = None
        if current_job_id is not None:
            target = next(
                (item for item in ordered if item.data(JOB_ID_ROLE) == current_job_id),
                None,
            )
        if target is None and current_path is not None:
            target = self._find_path(current_path)
        if target is not None:
            self.thumbnails.setCurrentItem(target, QItemSelectionModel.SelectionFlag.NoUpdate)
        self._apply_thumbnail_filter()

    def select_previous(self) -> None:
        self._user_navigated_filmstrip()
        rows = self._visible_rows()
        if not rows:
            return
        row = self.thumbnails.currentRow()
        prior = [candidate for candidate in rows if candidate < row]
        target = prior[-1] if prior else rows[0]
        self.thumbnails.setCurrentItem(self.thumbnails.item(target), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.thumbnails.scrollToItem(self.thumbnails.currentItem(), QAbstractItemView.ScrollHint.PositionAtCenter)

    def select_next(self) -> None:
        self._user_navigated_filmstrip()
        rows = self._visible_rows()
        if not rows:
            return
        row = self.thumbnails.currentRow()
        later = [candidate for candidate in rows if candidate > row]
        target = later[0] if later else rows[-1]
        self.thumbnails.setCurrentItem(self.thumbnails.item(target), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.thumbnails.scrollToItem(self.thumbnails.currentItem(), QAbstractItemView.ScrollHint.PositionAtCenter)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        rating_keys = {Qt.Key.Key_0: 0, Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3}
        if key in rating_keys:
            self._rate_current(rating_keys[key])
            return
        if key == Qt.Key.Key_X:
            self._exclude_current(True)
            return
        if key == Qt.Key.Key_K:
            self._exclude_current(False)
            return
        if key == Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.thumbnails.selectAll()
            return
        super().keyPressEvent(event)

    def _rate_current(self, rating: int) -> None:
        item = self.thumbnails.currentItem()
        if item is None or item.data(BRANDING_ROLE):
            return
        targets = self.thumbnails.selectedItems() if self.thumbnails.is_item_selected(item) else [item]
        targets = [target for target in targets if not target.data(BRANDING_ROLE)]
        if not targets:
            targets = [item]
        if rating == 0:
            new_rating = 0
        else:
            all_already_rated = all(int(target.data(RATING_ROLE) or 0) == rating for target in targets)
            new_rating = 0 if all_already_rated else rating
        for target in targets:
            target.setData(RATING_ROLE, new_rating)
            self.thumbnails.viewport().update(self.thumbnails.visualItemRect(target))
        self._sync_preview_controls(item)
        self._apply_thumbnail_filter()
        self._notify_result_metadata_changed()

    def _exclude_current(self, excluded: bool) -> None:
        item = self.thumbnails.currentItem()
        if item is None or item.data(BRANDING_ROLE):
            return
        selected = self.thumbnails.selectedItems()
        targets = selected if self.thumbnails.is_item_selected(item) else [item]
        targets = [target for target in targets if not target.data(BRANDING_ROLE)]
        for target in targets:
            target.setData(EXCLUDED_ROLE, excluded)
            self.thumbnails.viewport().update(self.thumbnails.visualItemRect(target))
        self._sync_preview_controls(item)
        self._apply_thumbnail_filter()
        self._notify_result_metadata_changed()

    def _select_only_current_thumbnail(self) -> QListWidgetItem | None:
        """In fullscreen mode, the visible image is the only selected image."""
        item = self.thumbnails.currentItem()
        if item is None:
            return None
        self.thumbnails.clearSelection()
        self.thumbnails.set_item_selected(item, True)
        self.thumbnails.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
        return item

    def _handle_fullscreen_key(self, key: int) -> bool:
        """Handle browsing and per-image actions while fullscreen is active."""
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.select_previous()
            self._select_only_current_thumbnail()
            self._refresh_fullscreen_image()
            return True
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.select_next()
            self._select_only_current_thumbnail()
            self._refresh_fullscreen_image()
            return True
        rating_keys = {Qt.Key.Key_0: 0, Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3}
        if key in rating_keys:
            self._select_only_current_thumbnail()
            self._rate_current(rating_keys[key])
            self._refresh_fullscreen_image()
            feedback = "☆ 0" if rating_keys[key] == 0 else "★" * rating_keys[key]
            if self._fullscreen_dialog is not None:
                self._fullscreen_dialog.show_feedback(feedback)
            return True
        if key == Qt.Key.Key_X:
            item = self._select_only_current_thumbnail()
            if item is not None:
                # X is a one-way action in fullscreen: exclude only.
                # K is the sole shortcut that restores/keeps an image.
                self._exclude_current(True)
                self._refresh_fullscreen_image()
                if self._fullscreen_dialog is not None:
                    self._fullscreen_dialog.show_feedback("× EXCLUDED")
            return True
        if key == Qt.Key.Key_K:
            self._select_only_current_thumbnail()
            self._exclude_current(False)
            self._refresh_fullscreen_image()
            if self._fullscreen_dialog is not None:
                self._fullscreen_dialog.show_feedback("X KEPT")
            return True
        return False

    def _refresh_fullscreen_image(self) -> None:
        item = self.thumbnails.currentItem()
        if item is None or self._fullscreen_dialog is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self._fullscreen_dialog._source_pixmap = pixmap
            self._fullscreen_dialog._refresh_image()

    def toggle_fullscreen_preview(self) -> None:
        """Show the current image fullscreen; F or Esc returns to the previous view."""
        if self._fullscreen_dialog is not None and self._fullscreen_dialog.isVisible():
            self._fullscreen_dialog.close()
            return
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return
        self._select_only_current_thumbnail()
        dialog = _FullscreenPreviewDialog(self._original_pixmap, self.window(), self._handle_fullscreen_key)
        self._fullscreen_dialog = dialog
        dialog.showFullScreen()
        dialog.activateWindow()
        dialog.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def clear_history(self) -> None:
        self._show_logo()
        self._auto_follow_new_images = True

    @property
    def current_image_path(self) -> Path | None:
        return self._current_image_path

    def _update_preview(self) -> None:
        if self._original_pixmap is None:
            if self._current_image_path is not None and not self._current_image_path.is_file():
                self.image.setPixmap(QPixmap())
                self.image.setText("result file missing")
            else:
                self._update_logo()
            return
        self.image.setPixmap(self._original_pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._position_preview_overlay()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._original_pixmap is not None:
            self._update_preview()
        else:
            self._update_logo()
