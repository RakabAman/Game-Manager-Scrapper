# widgets.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QStyledItemDelegate, QSizePolicy
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QSortFilterProxyModel
from PyQt5.QtGui import QColor, QPainter, QMovie, QPixmap, QDesktopServices
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
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._child_container = QWidget(self)
        self._child_layout = QVBoxLayout(self._child_container)
        self._child_layout.setContentsMargins(0, 0, 0, 0)
        self._child_layout.addWidget(self._child)
        self._layout.addWidget(self._child_container)
        QTimer.singleShot(0, self._update_child_geometry)

    def _update_child_geometry(self):
        available_width = max(1, self._child_container.width())
        available_height = max(1, self._child_container.height())
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

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(100, self._update_child_geometry)


class ClickableImageViewer(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._url = ""
        self._local_path = ""
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #111; border-radius: 4px;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.ArrowCursor)

    def set_url(self, url: str, local_path: str = ""):
        self._url = url or ""
        self._local_path = local_path or ""
        self.setToolTip("")

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)

    def wheelEvent(self, ev):
        parent = self.parent()
        if hasattr(parent, "on_viewer_wheel"):
            parent.on_viewer_wheel(ev)
        else:
            super().wheelEvent(ev)

    def resizeEvent(self, ev):
        parent = self.parent()
        if hasattr(parent, "_display_image") and getattr(parent, "_current_image_index", None) is not None:
            try:
                parent._display_image(parent._current_image_index)
            except Exception:
                pass
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
        self.parent = parent
        # No caching – we'll read colors from config each time

    def paint(self, painter, option, index):
        # Read fresh colors and desaturation from config module each time
        duplicate_color = QColor(config.desaturate_color(config.DUPLICATE_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))
        played_color = QColor(config.desaturate_color(config.PLAYED_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))
        unplayed_color = QColor(config.desaturate_color(config.UNPLAYED_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))
        favorite_color = QColor(config.desaturate_color(config.FAVORITE_COLOR, config.HIGHLIGHT_DESATURATE_PERCENT))

        model = index.model()
        source_index = index
        if hasattr(self.parent, 'proxy') and isinstance(model, QSortFilterProxyModel):
            source_index = self.parent.proxy.mapToSource(index)
            model = self.parent.model

        game = None
        if source_index.isValid():
            row = source_index.row()
            if row < len(self.parent.games):
                game = self.parent.games[row]

        if game:
            title_val = (game.get("title") or "").strip().lower()
            orig_val = (game.get("original_title") or "").strip().lower()
            steam_val = str(game.get("app_id") or "").strip().lower()
            has_title_duplicate = title_val and title_val in getattr(self.parent, '_dup_title_set', set())
            has_original_duplicate = orig_val and orig_val in getattr(self.parent, '_dup_title_set', set())
            has_steam_duplicate = steam_val and steam_val in getattr(self.parent, '_dup_steamid_set', set())
            igdb_val = str(game.get("igdb_id") or "").strip().lower()
            has_igdb_duplicate = igdb_val and igdb_val in getattr(self.parent, '_dup_igdbid_set', set())

            is_duplicate_cell = False
            if self.parent:
                col = source_index.column()
                is_duplicate_cell = (
                    (col == self.parent.COL_TITLE and has_title_duplicate) or
                    (col == self.parent.COL_ORIGINAL and has_original_duplicate) or
                    (col == self.parent.COL_STEAMID and has_steam_duplicate) or
                    (col == self.parent.COL_IGDB_ID and has_igdb_duplicate)
                )

            # Priority: duplicate > favourite > played > unplayed
            if is_duplicate_cell:
                painter.fillRect(option.rect, duplicate_color)
            elif game.get("fav", False):
                painter.fillRect(option.rect, favorite_color)
            elif game.get("played", False):
                painter.fillRect(option.rect, played_color)
            else:
                painter.fillRect(option.rect, unplayed_color)

        super().paint(painter, option, index)