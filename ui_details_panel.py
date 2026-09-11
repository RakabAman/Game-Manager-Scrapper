#!/usr/bin/env python3
# ui_details_panel.py – Fully configurable details panel with viewer reuse

import re
import os
from typing import List, Dict, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QPixmap, QKeyEvent, QDesktopServices
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

import config
from widgets import ClickableImageViewer, ClickableVideoWidget
from cache_utils import resolve_cover_art_cache_path
from image_display import ImageDisplayManager
from widgets import AspectRatioWidget
from image_display import ImageDisplayManager, ScreenshotViewerDialog


class ModernDetailsPanel(QWidget):
    BASE_COVER_WIDTH = 100   # fixed base width for v3 cover art 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setObjectName("modern_details")
        self._apply_panel_style()

        self.dummy_viewer = ClickableImageViewer()
        self.dummy_viewer.hide()
        self.image_display = ImageDisplayManager(self.main_window, self.dummy_viewer)

        self.media_player = None
        self._trailer_connected = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        main_layout.addWidget(self.scroll)

        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(16, 16, 16, 16)
        self.scroll_layout.setSpacing(12)
        self.scroll.setWidget(self.scroll_widget)

        # ---- Header ----
        self.header_widget = QWidget()
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(12)

        # Cover art – 3:4 ratio, width = COVER_ART_SIZE * 1.2 (increased)
 
        cover_width = int(self.BASE_COVER_WIDTH * config.DETAILS_COVER_MULTIPLIER)
        cover_height = int(cover_width * 4 / 3)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(cover_width, cover_height)
        self.cover_label.setScaledContents(False)
        self.cover_label.setStyleSheet(f"""
            border-radius: {min(8, cover_width//10)}px;
            background-color: {config.COVER_PLACEHOLDER_BACKGROUND};
            border: 1px solid {config.BORDER_COLOR};
        """)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.header_layout.addWidget(self.cover_label)

        title_rating_widget = QWidget()
        title_rating_layout = QVBoxLayout(title_rating_widget)
        title_rating_layout.setContentsMargins(0, 0, 0, 0)
        title_rating_layout.setSpacing(2)

        self.title_label = QLabel()
        self.title_label.setStyleSheet(f"""
            font-size: {config.DETAILS_TITLE_FONT_SIZE}px;
            font-weight: bold;
            color: {config.PRIMARY_COLOR};
        """)
        self.title_label.setWordWrap(True)

        self.original_title_label = QLabel()
        self.original_title_label.setStyleSheet(f"""
            font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px;
            color: {config.DETAILS_METADATA_LABEL_COLOR};
            font-weight: normal;
        """)
        self.original_title_label.setWordWrap(True)
        self.original_title_label.hide()

        self.rating_label = QLabel()
        self.rating_label.setStyleSheet(f"""
            font-size: {config.DETAILS_RATING_FONT_SIZE}px;
            color: {config.DETAILS_RATING_COLOR};
        """)
        self.rating_label.setWordWrap(True)

        title_rating_layout.addWidget(self.title_label)
        title_rating_layout.addWidget(self.original_title_label)
        title_rating_layout.addWidget(self.rating_label)
        self.header_layout.addWidget(title_rating_widget, 1)

        self.scroll_layout.addWidget(self.header_widget)

        # ---- Metadata ----
        self.metadata_widget = QWidget()
        self.metadata_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.metadata_layout = QGridLayout(self.metadata_widget)
        self.metadata_layout.setContentsMargins(0, 0, 0, 0)
        self.metadata_layout.setVerticalSpacing(6)
        self.metadata_layout.setHorizontalSpacing(20)
        self.scroll_layout.addWidget(self.metadata_widget)

        # ---- Description ----
        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(120)
        self.desc_text.setStyleSheet(f"""
            border: none;
            background: transparent;
            font-size: {config.DETAILS_DESC_FONT_SIZE}px;
            color: {config.DETAILS_DESCRIPTION_COLOR};
        """)
        self.scroll_layout.addWidget(self.desc_text)

        # ---- Gallery ----
        self.gallery_label = QLabel("📸 Gallery & Trailer")
        self.gallery_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px;
            color: {config.PRIMARY_COLOR};
        """)
        self.scroll_layout.addWidget(self.gallery_label)

        self.gallery_widget = QWidget()
        self.gallery_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setSpacing(config.GALLERY_SPACING)
        self.scroll_layout.addWidget(self.gallery_widget)

        # ---- External Links ----
        links_label = QLabel(f"{config.ICON_LINKS} External Links")
        links_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px;
            color: {config.PRIMARY_COLOR};
        """)
        self.scroll_layout.addWidget(links_label)

        self.links_widget = QWidget()
        self.links_layout = QHBoxLayout(self.links_widget)
        self.links_layout.setContentsMargins(0, 0, 0, 0)
        self.links_layout.setSpacing(8)
        self.links_layout.setAlignment(Qt.AlignLeft)
        self.scroll_layout.addWidget(self.links_widget)

        # ---- Save locations ----
        self.save_widget = QWidget()
        self.save_layout = QVBoxLayout(self.save_widget)
        self.save_layout.setContentsMargins(0, 0, 0, 0)
        self.save_layout.setSpacing(4)

        save_label = QLabel(f"{config.ICON_SAVE} Savegame Locations")
        save_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px;
            color: {config.PRIMARY_COLOR};
        """)
        self.save_layout.addWidget(save_label)

        self.save_container = QWidget()
        self.save_container_layout = QVBoxLayout(self.save_container)
        self.save_container_layout.setContentsMargins(0, 0, 0, 0)
        self.save_container_layout.setSpacing(2)
        self.save_layout.addWidget(self.save_container)

        self.scroll_layout.addWidget(self.save_widget)
        self.scroll_layout.addStretch()

        self.current_game = None
        self._gallery_containers = []
        self._gallery_pixmaps = {}
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._on_resize_finished)
        self._last_metadata_cols = None

        self.cover_fetcher = None

    # ------------------------------------------------------------------
    def _apply_panel_style(self):
        self.setStyleSheet(f"""
            QWidget#modern_details {{
                background-color: {config.DETAILS_PANEL_BACKGROUND};
                border-radius: {config.DETAILS_PANEL_BORDER_RADIUS}px;
            }}
        """)

    # ------------------------------------------------------------------
    def apply_theme(self):
        """Re-apply fonts/colors/thumbnail visibility from current config.

        Called automatically by config.refresh_all() -- no manual wiring
        needed from gui_main.
        """
        self._apply_panel_style()

        # Remove the local BASE_COVER_WIDTH = 80 line
        cover_width = int(self.BASE_COVER_WIDTH * config.DETAILS_COVER_MULTIPLIER)
        cover_height = int(cover_width * 4 / 3)
        self.cover_label.setFixedSize(cover_width, cover_height)
        self.cover_label.setFixedSize(cover_width, cover_height)

        self.title_label.setStyleSheet(f"""
            font-size: {config.DETAILS_TITLE_FONT_SIZE}px;
            font-weight: bold;
            color: {config.PRIMARY_COLOR};
        """)
        self.original_title_label.setStyleSheet(f"""
            font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px;
            color: {config.DETAILS_METADATA_LABEL_COLOR};
            font-weight: normal;
        """)
        self.rating_label.setStyleSheet(f"""
            font-size: {config.DETAILS_RATING_FONT_SIZE}px;
            color: {config.DETAILS_RATING_COLOR};
        """)
        self.desc_text.setStyleSheet(f"""
            border: none;
            background: transparent;
            font-size: {config.DETAILS_DESC_FONT_SIZE}px;
            color: {config.DETAILS_DESCRIPTION_COLOR};
        """)
        self.gallery_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px;
            color: {config.PRIMARY_COLOR};
        """)
        for child in self.findChildren(QLabel):
            if child.text().startswith("🔗") or child.text().startswith("💾"):
                child.setStyleSheet(f"""
                    font-weight: bold;
                    font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px;
                    color: {config.PRIMARY_COLOR};
                """)

        self.gallery_layout.setSpacing(config.GALLERY_SPACING)

        if self.current_game:
            self._build_metadata_grid(self.current_game)
            if config.SHOW_THUMBNAILS_IN_DETAILS:
                self.cover_label.show()
                self._load_cover_thumbnail(self.current_game)
            else:
                self.cover_label.hide()
            self._load_gallery(self.current_game)

        self.scroll_widget.updateGeometry()
        self.scroll_layout.invalidate()
        self.scroll_layout.activate()

    # ------------------------------------------------------------------
    def update_game(self, game: Dict):
        self.current_game = game

        title_text = game.get("title", "Untitled")
        symbols = []
        if game.get("played"):
            symbols.append("✅")
        if game.get("fav"):
            symbols.append("♥")
        if symbols:
            title_text = f"{title_text} {' '.join(symbols)}"
        self.title_label.setText(title_text)

        orig = game.get("original_title", "")
        if orig:
            self.original_title_label.setText(orig)
            self.original_title_label.show()
        else:
            self.original_title_label.hide()

        rating = game.get("user_rating", "")
        if rating:
            try:
                stars = min(5, float(rating) / 20)
                full = int(stars)
                half = 1 if stars - full >= 0.5 else 0
                empty = 5 - full - half
                stars_str = "★" * full + "½" * half + "☆" * empty
                self.rating_label.setText(f"{stars_str}  {rating}/100")
            except:
                self.rating_label.setText(f"Rating: {rating}/100")
        else:
            self.rating_label.setText("")

        if config.SHOW_THUMBNAILS_IN_DETAILS:
            self.cover_label.show()
            self._load_cover_thumbnail(game)
        else:
            self.cover_label.hide()

        self._build_metadata_grid(game)

        desc = game.get("description", "").strip()
        self.desc_text.setHtml(desc.replace("\n", "<br>") if desc else f"<i>{config.LABEL_NO_DESCRIPTION}</i>")

        self._load_gallery(game)
        self._build_links(game)
        self._build_save_locations(game)

    # ------------------------------------------------------------------
    # Cover art loading – ONLY IGDB cover art, no fallback to Steam
    # ------------------------------------------------------------------
    def _load_cover_thumbnail(self, game):
        if not config.SHOW_THUMBNAILS_IN_DETAILS:
            self.cover_label.hide()
            return

        self.cover_label.show()

        # Only use IGDB cover art
        cover_url = game.get("igdb_cover_art")
        if not cover_url:
            print("[COVER DEBUG] No IGDB cover art found for this game.")
            self._set_cover_placeholder()
            return

        print(f"[COVER DEBUG] Using IGDB cover art: {cover_url}")

        # Try to load from cache
        try:
            # Pass the IGDB URL explicitly to look for the dedicated file
            cover_path = resolve_cover_art_cache_path(game, cover_url=cover_url)
            if cover_path and cover_path.exists():
                pixmap = QPixmap(str(cover_path))
                if not pixmap.isNull():
                    print(f"[COVER DEBUG] Loaded from cache: {cover_path}")
                    self._set_cover_pixmap(pixmap)
                    return
                else:
                    print(f"[COVER DEBUG] Cache file exists but pixmap is null: {cover_path}")
            else:
                print(f"[COVER DEBUG] Cache file not found for {cover_url}")
        except Exception as e:
            print(f"[COVER DEBUG] Error accessing cache: {e}")

        # Fetch from network
        print(f"[COVER DEBUG] Fetching IGDB cover from network: {cover_url}")
        temp_viewer = ClickableImageViewer()
        temp_viewer.hide()
        if self.cover_fetcher is None:
            self.cover_fetcher = ImageDisplayManager(self.main_window, temp_viewer)
        else:
            self.cover_fetcher.viewer = temp_viewer

        def cover_callback(url, pixmap, movie, index):
            if url == cover_url and pixmap and not pixmap.isNull():
                print(f"[COVER DEBUG] Network fetch succeeded for {url}")
                self._set_cover_pixmap(pixmap)
            else:
                print(f"[COVER DEBUG] Network fetch failed or empty for {url}")
                self._set_cover_placeholder()

        self.cover_fetcher.fetch_and_display_images(
            0, [cover_url],
            on_image_ready=cover_callback,
            save_to_cache=config.AUTO_CACHE   # <-- add this
        )

    def _set_cover_pixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            # Scale to fit inside the label without cropping (KeepAspectRatio)
            scaled = pixmap.scaled(self.cover_label.width(), self.cover_label.height(),
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover_label.setPixmap(scaled)
            self.cover_label.setAlignment(Qt.AlignCenter)
        else:
            self._set_cover_placeholder()

    def _set_cover_placeholder(self):
        scaled_emoji = int(28 * config.GLOBAL_FONT_SCALE)
        self.cover_label.setText(config.LABEL_COVER_PLACEHOLDER)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet(f"""
            font-size: {scaled_emoji}px;
            background: {config.COVER_PLACEHOLDER_BACKGROUND};
            border-radius: {min(8, self.cover_label.width()//10)}px;
        """)

    # ------------------------------------------------------------------
    def _build_metadata_grid(self, game):
        viewport_width = self.scroll.viewport().width()
        avail_width = viewport_width - 32
        if avail_width <= 0:
            avail_width = 400

        self.metadata_widget.setMaximumWidth(avail_width)

        cols = 2 if avail_width > 400 else 1

        while self.metadata_layout.count():
            child = self.metadata_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        fields = [
            (config.ICON_STEAM, "Steam ID", "app_id"),
            (config.ICON_IGDB, "IGDB ID", "igdb_id"),
            (config.ICON_VERSION, "Version", "patch_version", "original_title_version"),
            (config.ICON_RELEASE, "Release", "release_date"),
            (config.ICON_THEMES, "Themes", "themes"),
            (config.ICON_GENRES, "Genres", "genres"),
            (config.ICON_MODES, "Modes", "game_modes"),
            (config.ICON_PERSPECTIVE, "Perspective", "player_perspective"),
            (config.ICON_DEVELOPER, "Developer", "developer"),
            (config.ICON_PUBLISHER, "Publisher", "publisher"),
            (config.ICON_DRIVE, "Drive", "game_drive"),
            (config.ICON_SCENE, "Scene/Repack", "scene_repack"),
        ]

        row = 0
        col = 0
        for field in fields:
            val = game.get(field[2], "")
            if len(field) > 3:
                fallback_key = field[3]
                if not val:
                    val = game.get(fallback_key, "")
            if not val:
                continue

            label = QLabel(f"{field[0]}  {field[1]}")
            label.setStyleSheet(f"""
                font-weight: 600;
                color: {config.DETAILS_METADATA_LABEL_COLOR};
                font-size: {config.DETAILS_METADATA_LABEL_FONT_SIZE}px;
            """)
            label.setWordWrap(True)

            value = QLabel(str(val))
            value.setStyleSheet(f"""
                color: {config.DETAILS_METADATA_VALUE_COLOR};
                font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px;
            """)
            value.setWordWrap(True)

            self.metadata_layout.addWidget(label, row, col * 2)
            self.metadata_layout.addWidget(value, row, col * 2 + 1)

            self.metadata_layout.setColumnStretch(col * 2, 0)
            self.metadata_layout.setColumnStretch(col * 2 + 1, 1)

            col += 1
            if col >= cols:
                col = 0
                row += 1

        self.metadata_layout.setRowStretch(row + 1, 1)

    # ------------------------------------------------------------------
    # Gallery methods – always shown
    # ------------------------------------------------------------------
    def _clear_gallery(self):
        while self.gallery_layout.count():
            child = self.gallery_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._gallery_containers = []
        self._gallery_pixmaps.clear()
        self.gallery_widget.setFixedHeight(0)

    def _load_gallery(self, game):
        if self.main_window is None:
            return

        try:
            row_index = self.main_window.games.index(game)
        except ValueError:
            return

        if self.media_player:
            self.media_player.stop()
            self.media_player.setMedia(QMediaContent())

        trailer_url = None
        if config.GALLERY_SHOW_TRAILER:
            trailer_url = game.get("trailer_webm") or ""
            if not trailer_url:
                micros = game.get("microtrailers") or []
                if micros and isinstance(micros, list) and len(micros):
                    trailer_url = micros[0]

        items = []
        if trailer_url:
            items.append(("trailer", trailer_url))

        screens = game.get("screenshots") or []
        if isinstance(screens, str):
            screens = [s.strip() for s in screens.split(",") if s.strip()]
        for scr in screens[:config.MAX_IMAGES_TO_DISPLAY]:
            items.append(("image", scr))

        while self.gallery_layout.count():
            child = self.gallery_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._gallery_containers = []
        self._gallery_pixmaps.clear()

        if not items:
            label = QLabel("No media available")
            label.setStyleSheet(f"color: {config.GALLERY_EMPTY_TEXT_COLOR}; font-size: 10px;")
            self.gallery_layout.addWidget(label, 0, 0)
            self.gallery_layout.invalidate()
            self.gallery_widget.setFixedHeight(0)
            return

        viewport_width = self.scroll.viewport().width()
        avail_width = viewport_width - 32
        if avail_width <= 0:
            avail_width = 400

        spacing = config.GALLERY_SPACING
        thumb_width = config.THUMBNAIL_SIZE
        if thumb_width < 80:
            thumb_width = 80
        col_width = thumb_width + spacing
        cols = avail_width // col_width
        if cols < 1:
            cols = 1
        if cols > 4:
            cols = 4

        cell_width = (avail_width - (cols - 1) * spacing) // cols
        cell_height = int(cell_width * 9 / 16)
        if cell_height < 60:
            cell_height = 60

        image_urls = []
        image_index_map = {}
        for typ, url in items:
            if typ == "image":
                image_index_map[url] = len(image_urls)
                image_urls.append(url)

        for idx, (typ, url) in enumerate(items):
            container = QWidget()
            container.setFixedSize(cell_width, cell_height)
            container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            container.setStyleSheet(f"""
                background: {config.GALLERY_THUMBNAIL_BACKGROUND};
                border-radius: {config.GALLERY_THUMBNAIL_CORNER_RADIUS}px;
                border: 1px solid {config.GALLERY_BORDER_COLOR};
            """)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)

            if typ == "trailer":
                video_widget = QVideoWidget()
                video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                video_widget.setStyleSheet(f"background: {config.VIDEO_WIDGET_BACKGROUND}; border-radius: 6px;")
                container_layout.addWidget(video_widget)

                if self.media_player is None:
                    self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
                self.media_player.setVideoOutput(video_widget)
                if url.startswith("http"):
                    media = QMediaContent(QUrl(url))
                else:
                    media = QMediaContent(QUrl.fromLocalFile(url))
                self.media_player.setMedia(media)

                if not self._trailer_connected:
                    self.media_player.mediaStatusChanged.connect(self._on_trailer_status_changed)
                    self._trailer_connected = True
                self.media_player.play()
                container.video_widget = video_widget
            else:
                
# Inside _load_gallery, where placeholder is created:
                placeholder = QLabel("🖼️")
                placeholder.setAlignment(Qt.AlignCenter)
                scaled_placeholder = int(24 * config.GLOBAL_FONT_SCALE)
                placeholder.setStyleSheet(f"background: transparent; color: {config.GALLERY_PLACEHOLDER_COLOR}; font-size: {scaled_placeholder}px; border: none;")
                container_layout.addWidget(placeholder)
                container.image_url = url
                container.image_index = image_index_map[url]

            container.mousePressEvent = lambda ev, r=row_index, idx=idx: self._open_viewer(r, idx)

            row = idx // cols
            col = idx % cols
            self.gallery_layout.addWidget(container, row, col)

            self._gallery_containers.append({
                "widget": container,
                "type": typ,
                "url": url,
                "gallery_index": idx,
                "image_index": container.image_index if typ == "image" else None,
                "cell_width": cell_width,
                "cell_height": cell_height,
            })

        for c in range(cols):
            self.gallery_layout.setColumnStretch(c, 1)

        if image_urls:
            def on_image_ready(url, pixmap, movie, index):
                for entry in self._gallery_containers:
                    if entry["type"] == "image" and entry["url"] == url:
                        container = entry["widget"]
                        while container.layout().count():
                            child = container.layout().takeAt(0)
                            if child.widget():
                                child.widget().deleteLater()
                        thumb_label = ClickableImageViewer()
                        thumb_label.setAlignment(Qt.AlignCenter)
                        thumb_label.setStyleSheet("background: transparent; border: none;")
                        thumb_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                        if pixmap and not pixmap.isNull():
                            thumb_label._original_gallery_pixmap = pixmap
                            self._gallery_pixmaps[url] = pixmap
                            scaled = pixmap.scaled(container.width(), container.height(),
                                                   Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            thumb_label.setPixmap(scaled)
                        elif movie:
                            thumb_label.setMovie(movie)
                            movie.start()
                        else:
                            thumb_label.setText("🖼️")
                            thumb_label.setStyleSheet(f"color: {config.GALLERY_PLACEHOLDER_COLOR}; font-size: 24px;")
                        container.layout().addWidget(thumb_label)
                        break

            self.image_display.fetch_and_display_images(row_index, image_urls, on_image_ready=on_image_ready)

        rows = (len(items) + cols - 1) // cols
        gallery_height = rows * (cell_height + spacing) - spacing
        self.gallery_widget.setFixedHeight(gallery_height)

    def _open_viewer(self, row_index: int, gallery_index: int):
        media_items = []
        for entry in self._gallery_containers:
            if entry["type"] in ("trailer", "video"):
                media_items.append({"type": "video", "url": entry["url"]})
            else:
                url = entry["url"]
                pixmap = self._gallery_pixmaps.get(url)
                media_items.append({"type": "image", "url": url, "pixmap": pixmap})

        if not media_items:
            return

        if gallery_index < 0 or gallery_index >= len(media_items):
            gallery_index = 0

        dialog = ScreenshotViewerDialog(self.main_window, media_items, gallery_index)
        dialog.exec_()

    def _on_trailer_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and self.media_player:
            self.media_player.setPosition(0)
            self.media_player.play()

    def refresh_gallery_layout(self):
        if not self._gallery_containers:
            return

        viewport_width = self.scroll.viewport().width()
        avail_width = viewport_width - 32
        if avail_width <= 0:
            avail_width = 400

        spacing = config.GALLERY_SPACING
        thumb_width = config.THUMBNAIL_SIZE
        if thumb_width < 80:
            thumb_width = 80
        col_width = thumb_width + spacing
        cols = avail_width // col_width
        if cols < 1:
            cols = 1
        if cols > 4:
            cols = 4

        cell_width = (avail_width - (cols - 1) * spacing) // cols
        cell_height = int(cell_width * 9 / 16)
        if cell_height < 60:
            cell_height = 60

        while self.gallery_layout.count():
            child = self.gallery_layout.takeAt(0)

        for idx, entry in enumerate(self._gallery_containers):
            container = entry["widget"]
            container.setFixedSize(cell_width, cell_height)
            entry["cell_width"] = cell_width
            entry["cell_height"] = cell_height
            row = idx // cols
            col = idx % cols
            self.gallery_layout.addWidget(container, row, col)

        for c in range(cols):
            self.gallery_layout.setColumnStretch(c, 1)

        for entry in self._gallery_containers:
            if entry["type"] != "image":
                continue
            container = entry["widget"]
            thumb_label = None
            for i in range(container.layout().count()):
                item = container.layout().itemAt(i)
                if item and isinstance(item.widget(), ClickableImageViewer):
                    thumb_label = item.widget()
                    break
            if thumb_label is None:
                continue
            original = getattr(thumb_label, "_original_gallery_pixmap", None)
            if original and not original.isNull():
                scaled = original.scaled(cell_width, cell_height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                thumb_label.setPixmap(scaled)

        rows = (len(self._gallery_containers) + cols - 1) // cols
        gallery_height = rows * (cell_height + spacing) - spacing
        self.gallery_widget.setFixedHeight(gallery_height)

        self.gallery_layout.invalidate()
        self.gallery_layout.activate()
        self.gallery_widget.updateGeometry()

    # ------------------------------------------------------------------
    # Links, Save Locations
    # ------------------------------------------------------------------
    def _build_links(self, game):
        while self.links_layout.count():
            child = self.links_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        link_map = {
            "Steam": "steam_link",
            "SteamDB": "steamdb_link",
            "PCGamingWiki": "pcgw_link",
            "IGDB": "igdb_link",
        }
        for label, key in link_map.items():
            url = game.get(key, "")
            if url:
                btn = QPushButton(label)
                btn.setFlat(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {config.HOVER_COLOR};
                        border: none;
                        border-radius: 4px;
                        padding: 4px 10px;
                        color: {config.PRIMARY_COLOR};
                    }}
                    QPushButton:hover {{
                        background: {config.BORDER_COLOR};
                    }}
                """)
                btn.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                self.links_layout.addWidget(btn)
        trailers = game.get("trailers") or game.get("igdb_trailers") or []
        if isinstance(trailers, str):
            trailers = [t.strip() for t in re.split(r"[,\|;\n]+", trailers) if t.strip()]
        for i, t_url in enumerate(trailers[:config.MAX_TRAILERS]):
            if t_url:
                btn = QPushButton(f"Trailer {i+1}")
                btn.setFlat(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {config.WARNING_COLOR};
                        border: none;
                        border-radius: 4px;
                        padding: 4px 10px;
                        color: {config.BUTTON_TEXT_COLOR};
                    }}
                    QPushButton:hover {{
                        background: {config.ACCENT_COLOR};
                    }}
                """)
                btn.clicked.connect(lambda checked, u=t_url: QDesktopServices.openUrl(QUrl(u)))
                self.links_layout.addWidget(btn)

    def _build_save_locations(self, game):
        while self.save_container_layout.count():
            child = self.save_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        save_locs = game.get("savegame_location") or game.get("savegame_locations") or []
        if isinstance(save_locs, str):
            save_locs = [s.strip() for s in save_locs.split("|") if s.strip()]
        if not save_locs:
            label = QLabel(config.LABEL_NO_SAVE_LOCATIONS)
            scaled = int(10 * config.GLOBAL_FONT_SCALE)
            label.setStyleSheet(f"color: {config.BORDER_COLOR}; font-size: {scaled}px;")
            self.save_container_layout.addWidget(label)
            return
        scaled_loc_font = int(10 * config.GLOBAL_FONT_SCALE)
        for loc in save_locs:
            label = QLabel(f"{config.ICON_SAVE} {loc}")
            label.setStyleSheet(f"color: {config.SECONDARY_COLOR}; font-size: {scaled_loc_font}px;")
            label.setOpenExternalLinks(False)
            label.mousePressEvent = lambda ev, l=loc: self._open_save_location(l)
            self.save_container_layout.addWidget(label)

    def _open_save_location(self, path):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except:
            from pathlib import Path
            p = Path(path)
            if p.parent.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))

    # ------------------------------------------------------------------
    # Resize handling
    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_game:
            self._build_metadata_grid(self.current_game)
        self._resize_timer.start(100)

    def _on_resize_finished(self):
        self.refresh_gallery_layout()
        if hasattr(self, "scroll_widget"):
            self.scroll_widget.updateGeometry()
        if hasattr(self, "scroll_layout"):
            self.scroll_layout.invalidate()
            self.scroll_layout.activate()

    def closeEvent(self, event):
        if self.media_player:
            self.media_player.stop()
        super().closeEvent(event)