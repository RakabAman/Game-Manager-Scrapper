# widgets.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QStyledItemDelegate, QSizePolicy, QComboBox, QToolButton
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QSortFilterProxyModel, QEvent
from PyQt5.QtGui import QColor, QPainter, QMovie, QPixmap, QDesktopServices, QStandardItemModel, QStandardItem, QPalette
from PyQt5.QtMultimediaWidgets import QVideoWidget
import config
import re

class AspectRatioWidget(QWidget):
    def __init__(self, child_widget: QWidget, parent=None, aspect_w=16, aspect_h=9):
        super().__init__(parent)
        self._child = child_widget
        self._aspect_w = aspect_w
        self._aspect_h = aspect_h
        self._child.setParent(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet(f"background: {config.VIDEO_WIDGET_BACKGROUND};")
        self._child.show()
        QTimer.singleShot(0, self._update_child_geometry)

    def apply_theme(self):
        """Re-apply config-driven background color.

        Called automatically by config.refresh_all() -- no manual wiring
        needed from gui_main.
        """
        self.setStyleSheet(f"background: {config.VIDEO_WIDGET_BACKGROUND};")

    def _update_child_geometry(self):
        if not self._child:
            return
        available_width = max(1, self.width())
        available_height = max(1, self.height())
        target_width = available_width
        target_height = int(available_width * self._aspect_h / self._aspect_w)
        if target_height > available_height:
            target_height = available_height
            target_width = int(available_height * self._aspect_w / self._aspect_h)
        x = (available_width - target_width) // 2
        y = (available_height - target_height) // 2
        self._child.setGeometry(x, y, target_width, target_height)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._update_child_geometry()
        if hasattr(self._child, 'resizeEvent'):
            self._child.resizeEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(100, self._update_child_geometry)

class CheckableComboBox(QComboBox):
    selectionChanged = pyqtSignal()

    def __init__(self, parent=None, placeholder=""):
        super().__init__(parent)
        self.setEditable(True)
        if placeholder:
            self.lineEdit().setPlaceholderText(placeholder)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setModel(QStandardItemModel(self))
        self.view().viewport().installEventFilter(self)

        self._clear_btn = QToolButton(self)
        self._clear_btn.setText("\u2715")
        self._clear_btn.setCursor(Qt.ArrowCursor)
        self._clear_btn.setFixedSize(16, 16)
        self._clear_btn.clicked.connect(self.clear_all)
        self._clear_btn.hide()
        self._clear_btn.raise_()

        self.lineEdit().textChanged.connect(self._sync_checks_from_text)
        self.lineEdit().textChanged.connect(self._update_clear_button_visibility)

        self._apply_style()
        self._position_clear_button()

    def apply_theme(self):
        """Re-apply config-driven colors/fonts to the combo and clear button.

        Called automatically by config.refresh_all() -- no manual wiring
        needed from gui_main.
        """
        self._apply_style()
        self._position_clear_button()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_clear_button()

    def _position_clear_button(self):
        arrow_width = 22
        margin = 4
        btn = self._clear_btn.width()
        x = self.width() - arrow_width - btn - margin
        y = (self.height() - self._clear_btn.height()) // 2
        self._clear_btn.move(max(0, x), max(0, y))

    def _update_clear_button_visibility(self, text):
        self._clear_btn.setVisible(bool((text or "").strip()))

    def _apply_style(self):
        border_color = config.BORDER_COLOR
        hover_border = config.SECONDARY_COLOR
        bg_color = config.INPUT_BACKGROUND
        text_color = config.TABLE_TEXT_COLOR          # ← changed from PRIMARY_COLOR
        selection_bg = config.SELECTED_COLOR
        hover_bg = config.HOVER_COLOR

        self.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 3px 46px 3px 8px;
                background: {bg_color};
                color: {text_color};
            }}
            QComboBox:hover {{
                border-color: {hover_border};
            }}
            QComboBox:focus {{
                border-color: {hover_border};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}
            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {border_color};
                border-radius: 6px;
                background: {bg_color};
                color: {text_color};
                outline: none;
                padding: 4px;
                selection-background-color: {selection_bg};
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 6px;
                border-radius: 4px;
                min-height: 20px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {hover_bg};
            }}
        """)

        # Clear button – always bright red
        scaled_clear = int(11 * config.GLOBAL_FONT_SCALE)

        self._clear_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background: transparent;
                color: {config.ACCENT_COLOR};       /* ← bright red */
                font-weight: bold;
                font-size: {scaled_clear}px;
                padding: 0px;
            }}
            QToolButton:hover {{
                color: {config.ACCENT_COLOR};       /* keep red on hover */
            }}
        """)

    def eventFilter(self, obj, event):
        if obj is self.view().viewport() and event.type() == QEvent.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                item = self.model().itemFromIndex(index)
                now_checked = item.checkState() != Qt.Checked
                item.setCheckState(Qt.Checked if now_checked else Qt.Unchecked)
                self._merge_toggle_into_line_edit(item.text(), now_checked)
                self.selectionChanged.emit()
                return True
        return super().eventFilter(obj, event)

    def _sync_checks_from_text(self, text):
        terms_lower = {t.strip().lower() for t in (text or "").split(",") if t.strip()}
        model = self.model()
        for r in range(model.rowCount()):
            item = model.item(r)
            desired = Qt.Checked if item.text().lower() in terms_lower else Qt.Unchecked
            if item.checkState() != desired:
                item.setCheckState(desired)

    def _current_terms(self):
        text = self.lineEdit().text() if self.lineEdit() else ""
        return [t.strip() for t in text.split(",") if t.strip()]

    def _merge_toggle_into_line_edit(self, term, checked):
        terms = self._current_terms()
        terms_lower = [t.lower() for t in terms]
        if checked:
            if term.lower() not in terms_lower:
                terms.append(term)
        else:
            terms = [t for t in terms if t.lower() != term.lower()]
        self.lineEdit().setText(", ".join(terms))

    def set_options(self, values):
        current_text = self.lineEdit().text()
        self.lineEdit().blockSignals(True)

        current_terms_lower = {t.lower() for t in self._current_terms()}
        model = self.model()
        model.clear()
        for text in values:
            item = QStandardItem(text)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if text.lower() in current_terms_lower else Qt.Unchecked)
            model.appendRow(item)

        self.setCurrentIndex(-1)
        self.lineEdit().setText(current_text)
        self.lineEdit().blockSignals(False)

    def clear_all(self):
        model = self.model()
        for r in range(model.rowCount()):
            model.item(r).setCheckState(Qt.Unchecked)
        self.lineEdit().clear()
        self.setCurrentIndex(-1)
        self.selectionChanged.emit()


class ClickableImageViewer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._url = ""
        self._local_path = ""
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background-color: {config.IMAGE_VIEWER_BACKGROUND}; border-radius: 4px;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.ArrowCursor)
        self.setScaledContents(False)

    def apply_theme(self):
        """Re-apply config-driven background color.

        Called automatically by config.refresh_all() -- no manual wiring
        needed from gui_main.
        """
        self.setStyleSheet(f"background-color: {config.IMAGE_VIEWER_BACKGROUND}; border-radius: 4px;")

    def setPixmap(self, pixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            super().setPixmap(scaled)
        else:
            super().setPixmap(QPixmap())

    def set_url(self, url: str, local_path: str = ""):
        self._url = url or ""
        self._local_path = local_path or ""
        self.setToolTip("")

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)

    def wheelEvent(self, ev):
        parent = self.parent()
        image_display = getattr(parent, "image_display", None)
        if image_display is not None and getattr(image_display, "_image_items", None):
            if ev.angleDelta().y() > 0:
                image_display.prev_image()
            else:
                image_display.next_image()
        else:
            super().wheelEvent(ev)

    def resizeEvent(self, ev):
        if self.pixmap() and not self.pixmap().isNull():
            scaled = self.pixmap().scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            super().setPixmap(scaled)
        super().resizeEvent(ev)

class ClickableVideoWidget(QVideoWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._url = ""
        self.setCursor(Qt.PointingHandCursor)

    def set_url(self, url: str):
        self._url = url or ""
        if self._url:
            self.setToolTip(f"Click to open: {self._url}")
        else:
            self.setToolTip("")

    def mousePressEvent(self, ev):
        if self._url:
            try:
                QDesktopServices.openUrl(QUrl(self._url))
            except Exception:
                import webbrowser
                webbrowser.open(self._url)
        else:
            super().mousePressEvent(ev)
        self.clicked.emit()


class HighlightDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    def paint(self, painter, option, index):
        duplicate_color = QColor(config.desaturate_color(config.DUPLICATE_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))
        played_color = QColor(config.desaturate_color(config.PLAYED_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))
        favorite_color = QColor(config.desaturate_color(config.FAVORITE_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))

        model = index.model()
        source_index = index
        if hasattr(self.main_window, 'proxy') and isinstance(model, QSortFilterProxyModel):
            source_index = self.main_window.proxy.mapToSource(index)
            model = self.main_window.model

        game = None
        if source_index.isValid():
            row = source_index.row()
            if row < len(self.main_window.games):
                game = self.main_window.games[row]

        if game:
            title_val = (game.get("title") or "").strip().lower()
            orig_val = (game.get("original_title") or "").strip().lower()
            steam_val = str(game.get("app_id") or "").strip().lower()
            has_title_duplicate = title_val and title_val in getattr(self.main_window, '_dup_title_set', set())
            has_original_duplicate = orig_val and orig_val in getattr(self.main_window, '_dup_title_set', set())
            has_steam_duplicate = steam_val and steam_val in getattr(self.main_window, '_dup_steamid_set', set())
            igdb_val = str(game.get("igdb_id") or "").strip().lower()
            has_igdb_duplicate = igdb_val and igdb_val in getattr(self.main_window, '_dup_igdbid_set', set())

            is_duplicate_cell = False
            if self.main_window:
                col = source_index.column()
                is_duplicate_cell = (
                    (col == self.main_window.COL_TITLE and has_title_duplicate) or
                    (col == self.main_window.COL_ORIGINAL and has_original_duplicate) or
                    (col == self.main_window.COL_STEAMID and has_steam_duplicate) or
                    (col == self.main_window.COL_IGDB_ID and has_igdb_duplicate)
                )


            bg_color = None
            if is_duplicate_cell:
                bg_color = duplicate_color
            elif game.get("fav", False):
                bg_color = favorite_color
            elif game.get("played", False):
                bg_color = played_color

            if bg_color is not None:
                painter.fillRect(option.rect, bg_color)
                if config.AUTO_CONTRAST_TABLE_TEXT:
                    # Compute relative luminance
                    luminance = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255.0
                    text_color = Qt.black if luminance > 0.5 else Qt.white
                    option.palette.setColor(QPalette.Text, text_color)
                    option.palette.setColor(QPalette.HighlightedText, text_color)
                else:
                    option.palette.setColor(QPalette.Text, QColor(config.TABLE_TEXT_COLOR))
            else:
                option.palette.setColor(QPalette.Text, QColor(config.TABLE_TEXT_COLOR))

            super().paint(painter, option, index)