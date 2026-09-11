#!/usr/bin/env python3
# gui_main.py - Refactored main window using helper modules

import os
import sys
import re
import time
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt
from drive_scanner import _get_drive_selection
import base64
import requests   # <-- ADD THIS LINE
# Import helper modules
import config
from workers import ImageFetchWorker, ScrapeBatchWorker
from dialogs import MultiEditDialog, EditDialog
from widgets import AspectRatioWidget, ClickableImageViewer, ClickableVideoWidget, HighlightDelegate, CheckableComboBox
from cache_utils import (
    _to_relative,
    _game_cache_dir_for_game,
    _save_bytes_to_game_cache,
    scan_cache_directory_for_game,
    resolve_cover_art_cache_path   # <-- ADD THIS
)
from download_helper import DownloadManager
from scrape_helper import ScrapeCoordinator
from metadata_helper import merge_and_apply_metadata
from sanitize_helper import sanitize_selected_rows
from image_display import ImageDisplayManager, ScreenshotViewerDialog
from trailer_player import TrailerPlayerManager

# Existing modules
import scraping
import import_export
from import_export import (
    import_csv, import_excel, import_txt,
    save_to_json, load_from_json,
    save_to_sqlite, load_from_sqlite,
    merge_imported_rows,
    export_games_to_pdf, export_games_to_html
)
from match_dialog import MatchDialog
from utils_sanitize import sanitize_original_title

import configparser
from config import CONFIG_FILE


class ClickableRow(QWidget):
    """A QWidget-based clickable row with a real `clicked` signal — same
    .clicked.connect(...) API as QAbstractButton, so existing code (e.g.
    cancel_scrape_btn.clicked.connect(...) elsewhere in this file) keeps
    working unchanged. Used for sidebar nav buttons instead of QToolButton
    because QToolButton renders icon+text as one combined string when both
    are passed via setText(): the `text-align` QSS property isn't honored
    for QToolButton (only QPushButton/QLineEdit per Qt's stylesheet docs),
    so it always centers; and `color` applies to the whole string, so an
    emoji icon and its label can't be colored independently. Building the
    row from two explicitly-positioned QLabels avoids both problems."""
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Plain QWidgets don't paint background-color/border-radius from a
        # stylesheet unless this attribute is set — without it, Qt silently
        # skips the styled background entirely, which is why neither the
        # base nor hover background ever appeared for these rows.
        self.setAttribute(Qt.WA_StyledBackground, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class GameManager(QMainWindow):
    # Column constants
    COL_TITLE = 0
    COL_VERSION = 1
    COL_GAMEDRIVE = 2
    COL_STEAMID = 3
    COL_PLAYED = 4
    COL_FAV = 5
    COL_GENRES = 6
    COL_GAME_MODES = 7
    COL_RELEASE = 8
    COL_THEMES = 9
    COL_DEV = 10
    COL_PUB = 11
    COL_SCENE = 12
    COL_PERSPECTIVE = 13
    COL_ORIGINAL = 14
    COL_IGDB_ID = 15
    COL_SHORTCUTS = 16
    COL_TRAILER = 17
    COL_STEAMDB = 18
    COL_PCWIKI = 19
    COL_STEAM_LINK = 20
    COL_DESCRIPTION = 21
    COL_IGDB_TRAILERS = 22
    COL_COVER_URL = 23
    COL_MICROTRAILERS = 24
    COL_IMAGE_CACHE_PATHS = 27
    COL_MICROTRAILER_CACHE_PATH = 29
    COL_USER_RATING = 30
    COL_SAVE_LOCATION = 28
    COL_IGDB_COVER_ART = 31

    COLUMN_KEYS = {
        0: "title",
        1: "patch_version",
        2: "game_drive",
        3: "app_id",
        4: "played",
        5: "fav",
        6: "genres",
        7: "game_modes",
        8: "release_date",
        9: "themes",
        10: "developer",
        11: "publisher",
        12: "scene_repack",
        13: "player_perspective",
        14: "original_title",
        15: "igdb_id",
        16: "screenshots",
        17: "trailer_webm",
        18: "steamdb_link",
        19: "pcgw_link",
        20: "steam_link",
        21: "description",
        22: "trailers",
        23: "cover_url",
        24: "microtrailers_extra",   # <-- changed from "microtrailers"
        25: "original_title_base",
        26: "original_notes",
        27: "image_cache_paths",
        28: "savegame_location",
        29: "microtrailer_cache_path",
        30: "user_rating",
        31: "igdb_cover_art",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Manager (Refactored) By Rakab Aman")
        self.resize(1300, 900)
        self.setStyleSheet(config.APP_STYLESHEET)

        # Application state
        self.games: List[Dict] = []
        self._threads: List[QThread] = []
        self._suppress_model_change = False
        self._dup_title_set = set()
        self._dup_steamid_set = set()
        self._cancel_current_scrape = False
        self._cancel_batch = False

        # Auto‑save
        self._dirty = False
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._perform_auto_save)
        self._current_save_path = None

        # Ensure DB directory exists
        self._db_dir = config.BASE_DIR / "DB"
        self._db_dir.mkdir(exist_ok=True)

        # Step 1: Create data model and table (needed by helpers)
        self._setup_data_model()
        self._setup_table_view()
        self._apply_table_font()


        # Step 2: Create helpers that don't need UI widgets (only model/games)
        self.download_mgr = DownloadManager(self)
        self.scrape_coord = ScrapeCoordinator(self)

        self._expander_title_labels = []   # for collapsible section headers
        self._expander_chevron_labels = [] # for the chevron icon
        self._filter_caption_labels = []   # for filter captions (Genre, Drive, etc.)

        # Step 3: Create UI panels that don't depend on image/trailer helpers_fetch_steam_header_pixmap
        self._setup_sidebar()
        self._setup_details_panel()

        # Step 4: Create image viewer widgets (but not the helper yet)
        self._setup_image_viewer()   # creates self.viewer, self.prev_btn, etc.

        # Step 5: Now create image display helper (needs self.viewer)
        self.image_display = ImageDisplayManager(self)
        self.cover_fetcher = ImageDisplayManager(self)  

        # Step 6: Connect nav buttons to the unified media-slide handlers —
        # trailer (if present) is slide 0, images follow after it, so one
        # set of prev/next buttons walks through both instead of each
        # having its own separate controls. ImageDisplayManager itself is
        # untouched; these wrappers just call into it for the image slides.
        self.prev_btn.clicked.connect(self._media_prev)
        self.next_btn.clicked.connect(self._media_next)
        self.open_image_btn.clicked.connect(self._media_open_current)

        # Step 7: Create trailer player widgets and helper
        self._setup_trailer_player()   # creates self.trailer_container
        self.trailer_player = TrailerPlayerManager(self)

        # Step 8: Final layout and status bar
        self._setup_main_layout()
        self._setup_status_bar()
        self.build_menus()


        self._manual_match_queue = []
        self._manual_match_in_progress = False

        # Load default database if configured and exists (after all UI is built)
        if config.DEFAULT_DATABASE and os.path.exists(os.path.join(config.BASE_DIR, config.DEFAULT_DATABASE) if not os.path.isabs(config.DEFAULT_DATABASE) else config.DEFAULT_DATABASE):
            self._load_database_from_path(config.DEFAULT_DATABASE)
        elif config.AUTO_SAVE and config.AUTO_SAVE_PATH and os.path.exists(os.path.join(config.BASE_DIR, config.AUTO_SAVE_PATH) if not os.path.isabs(config.AUTO_SAVE_PATH) else config.AUTO_SAVE_PATH):
            self._load_database_from_path(config.AUTO_SAVE_PATH)

        QCoreApplication.instance().aboutToQuit.connect(self._shutdown_workers)
        self.center_window()
        self.table.setItemDelegate(HighlightDelegate(self))
        self.cancel_scrape_btn.clicked.connect(self.force_cancel_operation)

    
        
    def set_cancel_button_visible(self, visible: bool):
        """Show/hide the cancel button (used by DownloadManager)."""
        if hasattr(self, 'cancel_scrape_btn'):
            self.cancel_scrape_btn.setVisible(visible)
                
    def _apply_table_font(self):
        font = self.table.font()
        font.setPointSize(config.TABLE_DATA_FONT_SIZE)
        self.table.setFont(font)
        # Optionally also set the header font (same size or different)
        header_font = self.table.horizontalHeader().font()
        header_font.setPointSize(config.TABLE_DATA_FONT_SIZE)
        self.table.horizontalHeader().setFont(header_font)     
        
    # ----------------------------------------------------------------------
    # UI Setup Methods
    # ----------------------------------------------------------------------
    def _setup_data_model(self):
        self.model = QStandardItemModel(0, 32)
        # Use config icons for header labels
        self.model.setHorizontalHeaderLabels([
            "Title",
            f"Ver{config.ICON_VERSION}",
            f"Drive{config.ICON_DRIVE}",
            f"Steam{config.ICON_STEAM}",
            config.ICON_PLAYED,
            config.ICON_FAVOURITE,
            f"Genres{config.ICON_GENRES}",
            f"Modes{config.ICON_MODES}",
            f"Release{config.ICON_RELEASE}",
            f"Themes{config.ICON_THEMES}",
            f"Dev{config.ICON_DEVELOPER}",
            f"Pub{config.ICON_PUBLISHER}",
            f"Scene/Repack{config.ICON_SCENE}",
            f"Perspective{config.ICON_PERSPECTIVE}",
            f"Original Title{config.ICON_ORIGINAL}",
            f"IGDB{config.ICON_IGDB}",
            f"Screenshots{config.ICON_SCREENSHOTS}",
            f"Trailer{config.ICON_TRAILER} (micro)",
            "SteamDB🔗",          # no config icon for "links" – optional: we could use config.ICON_LINKS
            "PCGamingWiki🔗",
            "Steam🔗",
            "Description",
            "IGDB Trailers🎥",
            "Cover URL",
            "Extra microtrailers🎬",
            "Original Title Base",
            "Original Notes🏷️",   # no config icon for notes; keep as is
            "Image Cache Paths",
            "Savegame Locations",
            "Microtrailers Cache Paths",
            f"User Rating{config.ICON_USER_RATING}",
            "IGDB CoverArt"
        ])
        # ... rest of method unchanged

        # ========== ENHANCED COLUMN TOOLTIPS ==========
        headers = self.model.horizontalHeaderItem

        headers(self.COL_TITLE).setToolTip(
            "Game title – cleaned after scraping or sanitising.\n"
            "Source: IGDB / Steam, or manual entry."
        )

        headers(self.COL_VERSION).setToolTip(
            "Patch or version number – extracted from the original title.\n"
            "Example pattern: v1.5.3, Update 2, Build 12345."
        )

        headers(self.COL_GAMEDRIVE).setToolTip(
            "Drive or folder path where the game is installed.\n"
            "Useful for organising games by location (e.g., D:/Games)."
        )

        headers(self.COL_STEAMID).setToolTip(
            "Steam App ID – numeric identifier for the game on Steam.\n"
            "Used to fetch metadata and generate store links."
        )

        headers(self.COL_PLAYED).setToolTip(
            "Played status – click to toggle.\n"
            "Marking a game as played turns its table row green."
        )

        headers(self.COL_FAV).setToolTip(
            "Favourite status – click to toggle.\n"
            "Favourites appear with a pink row background and a star in the details panel."
        )

        headers(self.COL_GENRES).setToolTip(
            "Game genres – categories describing the core gameplay.\n"
            "Examples: Action, Adventure, RPG, Strategy.\n"
            "Scraped from IGDB/Steam."
        )

        headers(self.COL_GAME_MODES).setToolTip(
            "Game modes – how the game can be played.\n"
            "Examples: Single‑player, Multiplayer, Co‑op, Massively Multiplayer.\n"
            "Scraped from IGDB/Steam."
        )

        headers(self.COL_RELEASE).setToolTip(
            "Release date – when the game was first published.\n"
            "Format: YYYY-MM-DD (ISO 8601)."
        )

        headers(self.COL_THEMES).setToolTip(
            "Themes – the setting, mood, or subject matter.\n"
            "Examples: Fantasy, Sci‑fi, Horror, Historical.\n"
            "Scraped from IGDB."
        )

        headers(self.COL_DEV).setToolTip(
            "Developer – the studio or individual that created the game.\n"
            "Scraped from IGDB/Steam."
        )

        headers(self.COL_PUB).setToolTip(
            "Publisher – the company that distributed the game.\n"
            "Scraped from IGDB/Steam."
        )

        headers(self.COL_SCENE).setToolTip(
            "Scene or repack name – extracted from the original title.\n"
            "Examples: FitGirl Repack, CODEX, GOG."
        )

        headers(self.COL_PERSPECTIVE).setToolTip(
            "Player perspective – the point of view from which the game world is presented.\n"
            "Also indicates camera position (first‑person, third‑person, top‑down, etc.).\n"
            "Scraped from IGDB."
        )

        headers(self.COL_ORIGINAL).setToolTip(
            "Original title – exactly as imported (folder name, file, or input).\n"
            "Never overwritten by sanitising – preserves the raw source."
        )

        headers(self.COL_IGDB_ID).setToolTip(
            "IGDB game ID – numeric identifier for the game on IGDB.\n"
            "Used to fetch rich metadata, cover art, screenshots, and trailers."
        )

        headers(self.COL_SHORTCUTS).setToolTip(
            "Screenshot URLs – direct links to in‑game images.\n"
            "Scraped from IGDB/Steam. Up to 5 are shown in the Media tab."
        )

        headers(self.COL_TRAILER).setToolTip(
            "Microtrailer URL – direct link to a short video (webm/mp4/gif).\n"
            "Automatically played when you select the game.\n"
            "Scraped from IGDB/Steam if available."
        )

        headers(self.COL_STEAMDB).setToolTip(
            "SteamDB page link – generated from the Steam ID.\n"
            "Click to view detailed game stats, price history, and ownership data."
        )

        headers(self.COL_PCWIKI).setToolTip(
            "PCGamingWiki page link – generated from the game title.\n"
            "Click for fixes, save game locations, and performance tweaks."
        )

        headers(self.COL_STEAM_LINK).setToolTip(
            "Steam store page link – generated from the Steam ID.\n"
            "Click to open the game’s official Steam store page."
        )

        headers(self.COL_DESCRIPTION).setToolTip(
            "Game description – a summary outlining key features, gameplay mechanics, and unique aspects.\n"
            "Serves as a crucial tool to attract and inform players.\n"
            "Combined from IGDB and Steam data."
        )

        headers(self.COL_IGDB_TRAILERS).setToolTip(
            "Additional trailer URLs – direct links to video trailers.\n"
            "Scraped from IGDB. Shown as external links in the details panel."
        )

        headers(self.COL_COVER_URL).setToolTip(
            "Cover art URL – the main promotional image of the game.\n"
            "Scraped from IGDB/Steam. Displayed as the first image in the Media tab."
        )

        headers(self.COL_MICROTRAILERS).setToolTip(
            "Extra microtrailer URLs – manually entered, one per line in the edit dialog.\n"
            "Used as fallback if the main microtrailer URL is missing."
        )

        headers(self.COL_USER_RATING).setToolTip(
            "User rating – average score from players (0–100).\n"
            "Scraped from IGDB/Steam. Displayed as star ratings in the details panel."
        )

        self.model.itemChanged.connect(self.on_model_item_changed)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)

    def _setup_table_view(self):
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.selectionModel().selectionChanged.connect(
            lambda s, d: self._handle_selection_changed(s, d)
        )
        self.table.setColumnWidth(self.COL_TITLE, 200)
        self.table.setColumnWidth(self.COL_USER_RATING, 80)
        self.table.setColumnWidth(self.COL_VERSION, 80)
        self.table.setColumnWidth(self.COL_PLAYED, 60)

        # Restore saved column order and widths
        self._restore_column_state()

        # Connect signals to save when user changes
        header = self.table.horizontalHeader()
        header.sectionMoved.connect(self._save_column_state)
        header.sectionResized.connect(self._save_column_state)

    def _save_column_state(self):
        header = self.table.horizontalHeader()
        visual_order = [header.logicalIndex(i) for i in range(header.count())]
        order_str = ','.join(str(idx) for idx in visual_order)
        widths = [header.sectionSize(logical) for logical in visual_order]
        widths_str = ','.join(str(w) for w in widths)
        # Save hidden columns
        hidden = [col for col in range(self.model.columnCount()) if self.table.isColumnHidden(col)]
        hidden_str = ','.join(str(col) for col in hidden)

        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='utf-8')
        if not config.has_section('Table'):
            config.add_section('Table')
        config.set('Table', 'column_order', order_str)
        config.set('Table', 'column_widths', widths_str)
        config.set('Table', 'hidden_columns', hidden_str)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)

    def _restore_column_state(self):
        """Restore column order, widths, and hidden state from config."""
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='utf-8')
        if not config.has_section('Table'):
            return
        order_str = config.get('Table', 'column_order', fallback='')
        widths_str = config.get('Table', 'column_widths', fallback='')
        hidden_str = config.get('Table', 'hidden_columns', fallback='')

        if not order_str or not widths_str:
            return
        try:
            order = [int(x) for x in order_str.split(',') if x.strip()]
            widths = [int(x) for x in widths_str.split(',') if x.strip()]
            hidden = [int(x) for x in hidden_str.split(',') if x.strip()] if hidden_str else []

            header = self.table.horizontalHeader()

            # Apply order first
            for visual_index, logical in enumerate(order):
                current_visual = header.visualIndex(logical)
                if current_visual != visual_index:
                    header.moveSection(current_visual, visual_index)

            # Apply widths
            for visual_index, logical in enumerate(order):
                if visual_index < len(widths):
                    header.resizeSection(logical, widths[visual_index])

            # Apply hidden columns (restore saved visibility)
            for col in range(self.model.columnCount()):
                self.table.setColumnHidden(col, col in hidden)

        except Exception as e:
            print(f"Error restoring column state: {e}")

    # ----------------------------------------------------------------------
    # Redesign helpers — reused across the sidebar, top bar, and stat cards
    # to give panels real depth (drop shadows) and tinted card backgrounds
    # derived from config.py colors.
    # ----------------------------------------------------------------------
    def _add_shadow(self, widget, blur=16, x_offset=0, y_offset=2, alpha=45):
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(x_offset, y_offset)
        effect.setColor(QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        hex_color = (hex_color or "#3498db").lstrip('#')
        if len(hex_color) != 6:
            return f"rgba(52,152,219,{alpha})"
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    @staticmethod
    def _darken_color(hex_color: str, factor: int = 116) -> str:
        """Return a slightly darker shade of hex_color, used for the hover
        state of solid-colored (urgent/success) sidebar buttons where the
        base state already uses the full accent color — factor > 100
        darkens, matching QColor.darker()'s convention."""
        color = QColor(hex_color or "#3498db")
        return color.darker(factor).name()

    def _set_search_toggle_indicator(self):
        """Tint the search/filter toggle button to show whether any filter
        (search text or any of the 7 CheckableComboBox filters) is
        currently active — generalized over self._filter_defs so adding a
        filter later doesn't require touching this method."""
        any_active = bool(self.search.text().strip()) or any(
            getattr(self, attr)._current_terms() for attr, label, icon, game_key, col_name in self._filter_defs
        )
        color = config.ACCENT_COLOR if any_active else config.SECONDARY_COLOR
        scaled_filter_toggle = int(13 * config.GLOBAL_FONT_SCALE)

        self.search_toggle_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background-color: {self._hex_to_rgba(color, 0.12)};
                color: {color};
                font-size: {scaled_filter_toggle}px;
                text-align: left;
                padding: 10px 14px;
                border-radius: 6px;
            }}
            QToolButton:hover {{ background-color: {self._hex_to_rgba(color, 0.22)}; }}
        """)

    def _on_stat_card_clicked(self, card_id: str):
        self.search.clear()
        for attr, label, icon, game_key, col_name in self._filter_defs:
            getattr(self, attr).clear_all()
        self.proxy.setFilterFixedString("")
        self._active_stat_id = card_id
        self._refresh_stat_card_colors()
        self._set_search_toggle_indicator()
        self.clear_filters_btn.setVisible(card_id != "total")
        if card_id == "total":
            for row in range(self.proxy.rowCount()):
                self.table.setRowHidden(row, False)
            self.status.setText("Showing all games")
            return
        for proxy_row in range(self.proxy.rowCount()):
            idx = self.proxy.index(proxy_row, 0)
            src = self.proxy.mapToSource(idx)
            show = False
            if src.isValid():
                row = src.row()
                game = self.games[row]
                if card_id == "played":
                    show = game.get("played", False)
                elif card_id == "remaining":
                    show = not game.get("played", False)
                elif card_id == "cached":
                    paths = game.get("image_cache_paths") or []
                    show = any(p and (config.SCRIPT_DIR / p).exists() for p in paths)
                elif card_id == "duplicates":
                    title = (game.get("title") or "").strip().lower()
                    show = title and title in self._dup_title_set
                elif card_id == "unscraped":
                    show = not (game.get("app_id") or "").strip() and not (game.get("igdb_id") or "").strip()
                elif card_id == "favourites":
                    show = game.get("fav", False)
            self.table.setRowHidden(proxy_row, not show)
        self.status.setText(f"Showing: {card_id.capitalize()} games")

    def _refresh_stat_card_colors(self):
        """Update stat chip colors using current config colors. Flat pills only —
        no border + border-radius combination (that combo, with a border on only
        one side, is what rendered as a curled bracket shape instead of a clean
        accent), and no drop shadow on chips this small."""

        # Map stat id to the config color constant or custom color
        color_map = {
            "played": config.PLAYED_COLOR,
            "favourites": config.FAVORITE_COLOR,
            "remaining": config.UNPLAYED_COLOR,
            "duplicates": config.DUPLICATE_COLOR,
            "total": config.STAT_CARD_TOTAL_COLOR,
            "cached": config.STAT_CARD_CACHED_COLOR,
            "unscraped": config.STAT_CARD_UNSCRAPED_COLOR,
        }

        active_id = getattr(self, "_active_stat_id", "total")

        for stat_id, card in self.stats_card_widgets.items():
            color = color_map.get(stat_id, config.STAT_CARD_TOTAL_COLOR)
            is_active = (stat_id == active_id)
            bg = color if is_active else self._hex_to_rgba(color, 0.12)
            value_color = config.STAT_CARD_ACTIVE_TEXT_COLOR if is_active else color
            label_color = config.STAT_CARD_INACTIVE_LABEL_COLOR if not is_active else self._hex_to_rgba(color, 0.85)

            # Compute hover background – brighten the normal bg
            if bg.startswith('#'):
                hover_bg = self._brighten_color(bg, 130)
            else:
                # If bg is rgba (e.g., inactive with transparency), brighten the solid color
                hover_bg = self._brighten_color(color, 130) if color.startswith('#') else color

            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg};
                    border-radius: 8px;
                    border: none;
                }}
                QWidget:hover {{
                    background-color: {hover_bg};
                }}
            """)
            card.setGraphicsEffect(None)
            value_label = card.findChild(QLabel, "chip_value")
            label_label = card.findChild(QLabel, "chip_label")
            scaled_value = int(13 * config.GLOBAL_FONT_SCALE)
            scaled_label = int(11 * config.GLOBAL_FONT_SCALE)
            if value_label:
                value_label.setStyleSheet(f"font-size: {scaled_value}px; font-weight: 700; color: {value_color}; background: transparent; border: none;")
            if label_label:
                label_label.setStyleSheet(f"font-size: {scaled_label}px; font-weight: 500; color: {label_color}; background: transparent; border: none;")
                
    def _setup_sidebar(self):
        """Unified left sidebar: stat badges, quick search, filters, and nav
        buttons. Same attribute names as before (self.open_db_btn,
        self.scrape_btn, self.search, self.genre_filter, self.stats_cards,
        etc.) so every other place in this file that references them keeps
        working unchanged — only where/how they're built changed."""
        SIDEBAR_COLLAPSED_W = 56
        SIDEBAR_EXPANDED_W = 200

        sidebar_outer = QWidget()
        sidebar_outer.setObjectName("sidebar")
        sidebar_outer.setStyleSheet(f"""
            QWidget#sidebar {{
                background-color: {config.LIGHT_BG};
                border-right: 1px solid {config.BORDER_COLOR};
            }}
        """)
        sidebar_outer.setMinimumWidth(SIDEBAR_COLLAPSED_W)
        sidebar_outer.setMaximumWidth(SIDEBAR_COLLAPSED_W)
        outer_layout = QVBoxLayout(sidebar_outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scrollable body — with stat badges + search + filters + nav
        # buttons all stacked in one sidebar now, this can get taller than
        # the window on smaller screens, so it needs to scroll rather than
        # overflow or get clipped.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        outer_layout.addWidget(scroll)

        sidebar = QWidget()
        sidebar.setStyleSheet("background: transparent;")
        scroll.setWidget(sidebar)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 8, 6, 8)
        sidebar_layout.setSpacing(4)

        toggle_btn = QToolButton()
        toggle_btn.setText("☰")
        toggle_btn.setToolTip("Expand / collapse sidebar")
        toggle_btn.setCursor(Qt.PointingHandCursor)
        scaled_toggle = int(16 * config.GLOBAL_FONT_SCALE)
        toggle_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background-color: {config.BUTTON_BACKGROUND};
                font-size: {scaled_toggle}px;
                padding: 8px;
                border-radius: 6px;
                color: {config.PRIMARY_COLOR};
            }}
            QToolButton:hover {{ background-color: {config.HOVER_COLOR}; }}
        """)
        sidebar_layout.addWidget(toggle_btn)
        sidebar_layout.addSpacing(6)

        def add_separator():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"background-color: {config.BORDER_COLOR}; max-height: 1px; border: none;")
            sidebar_layout.addSpacing(4)
            sidebar_layout.addWidget(line)
            sidebar_layout.addSpacing(4)

        # ------------------------------------------------------------
        # Stat badges — same card widgets serve both states: collapsed
        # shows just the colored number (title_label hidden, value
        # centered); expanded shows value + label side by side. No
        # separate widgets needed since the sidebar's own width animation
        # already reflows these (they're not fixed-width).
        # ------------------------------------------------------------
        self.stats_cards = {}
        self.stats_card_widgets = {}
        stats_config = [
            {"id": "total", "title": "Total"},
            {"id": "played", "title": "Played"},
            {"id": "favourites", "title": "Fav"},
            {"id": "remaining", "title": "Remaining"},
            {"id": "cached", "title": "Cached"},
            {"id": "duplicates", "title": "Duplicates"},
            {"id": "unscraped", "title": "Unscraped"},
        ]
        card_tooltips = {
            "total": "Total number of games in the database",
            "played": "Games marked as played",
            "favourites": "Games marked as favourite (♥)",
            "remaining": "Games not yet played",
            "cached": "Games that have at least one cached screenshot",
            "duplicates": "Games with duplicate titles (case‑insensitive)",
            "unscraped": "Games missing both Steam ID and IGDB ID",
        }
        for stat in stats_config:
            card = QWidget()
            card.setFixedHeight(26)
            card.setCursor(Qt.PointingHandCursor)
            card.setToolTip(card_tooltips.get(stat["id"], ""))
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 0, 8, 0)
            card_layout.setSpacing(6)
            value_label = QLabel("0")
            value_label.setObjectName("chip_value")
            title_label = QLabel(stat["title"].lower())
            title_label.setObjectName("chip_label")
            title_label.setVisible(False)   # shown only when sidebar is expanded
            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label, 1)
            sidebar_layout.addWidget(card)
            card._title_label = title_label
            card._value_label = value_label
            self.stats_cards[stat["id"]] = value_label
            self.stats_card_widgets[stat["id"]] = card
            card.mousePressEvent = lambda event, cid=stat["id"]: self._on_stat_card_clicked(cid)

        self._active_stat_id = "total"
        self._refresh_stat_card_colors()
        add_separator()

        # ------------------------------------------------------------
        # Quick search — icon-only button when collapsed (clicking it
        # expands the sidebar and focuses the box); real inline field
        # when expanded.
        # ------------------------------------------------------------
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.on_search_changed)
        self.search.setFixedHeight(config.TEXT_BOX_HEIGHT)
        self.search.setToolTip("Search all columns (case‑insensitive)")
        self.search.setVisible(False)

        self.search_icon_btn = QToolButton()
        self.search_icon_btn.setText("🔍")
        self.search_icon_btn.setToolTip("Search games")
        self.search_icon_btn.setCursor(Qt.PointingHandCursor)
        scaled_search_icon = int(14 * config.GLOBAL_FONT_SCALE)

        self.search_icon_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background-color: {config.BUTTON_BACKGROUND};
                font-size: {scaled_search_icon}px;
                padding: 8px;
                border-radius: 6px;
                color: {config.PRIMARY_COLOR};
            }}
            QToolButton:hover {{ background-color: {config.HOVER_COLOR}; }}
        """)

        def on_search_icon_clicked():
            if not self._sidebar_expanded:
                toggle_sidebar()
            self.search.setFocus()

        self.search_icon_btn.clicked.connect(on_search_icon_clicked)
        sidebar_layout.addWidget(self.search_icon_btn)
        sidebar_layout.addWidget(self.search)

        # ------------------------------------------------------------
        # Filter definitions — same 7 filters as before, same
        # CheckableComboBox, same apply_filters()/_refresh_filter_options()
        # matching logic downstream. Stacked single-column here (label
        # above combo) since the sidebar is too narrow for the old grid.
        # ------------------------------------------------------------
        self._filter_defs = [
            ("genre_filter", "Genre", "🎭", "genres", "COL_GENRES"),
            ("game_drive_filter", "Drive", "💾", "game_drive", "COL_GAMEDRIVE"),
            ("developer_filter", "Developer", "🏢", "developer", "COL_DEV"),
            ("publisher_filter", "Publisher", "📢", "publisher", "COL_PUB"),
            ("themes_filter", "Themes", "🎯", "themes", "COL_THEMES"),
            ("modes_filter", "Modes", "🎮", "game_modes", "COL_GAME_MODES"),
            ("perspective_filter", "Perspective", "👁", "player_perspective", "COL_PERSPECTIVE"),
        ]
        caption_color = self._hex_to_rgba(config.PRIMARY_COLOR, 0.65)
        scaled_caption = int(11 * config.GLOBAL_FONT_SCALE)

        filter_section = QWidget()
        filter_section.setMaximumHeight(0)
        filter_section_layout = QVBoxLayout(filter_section)
        filter_section_layout.setContentsMargins(0, 4, 0, 4)
        filter_section_layout.setSpacing(8)

        for attr, label, icon, game_key, col_name in self._filter_defs:
            combo = CheckableComboBox(placeholder=f"{icon} {label}...")
            combo.editTextChanged.connect(self.apply_filters)
            combo.selectionChanged.connect(self.apply_filters)
            combo.setFixedHeight(config.TEXT_BOX_HEIGHT)
            combo.setToolTip(f"Click the dropdown to check one or more {label.lower()} values from your\n"
                              f"collection, or type directly to filter by any text (partial match).\n"
                              f"Multiple selections match games with ANY of the checked {label.lower()} values.")
            setattr(self, attr, combo)
            caption = QLabel(f"{label}:")
            caption.setStyleSheet(f"font-size: {scaled_caption}px; font-weight: 600; color: {caption_color};")
            self._filter_caption_labels.append(caption)
            filter_section_layout.addWidget(caption)
            filter_section_layout.addWidget(combo)

        self.clear_filters_btn = QToolButton()
        self.clear_filters_btn.setText("✕ Clear all filters")
        self.clear_filters_btn.setCursor(Qt.PointingHandCursor)
        self.clear_filters_btn.setVisible(False)
        scaled_clear = int(11 * config.GLOBAL_FONT_SCALE)

        self.clear_filters_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background-color: {self._hex_to_rgba(config.ACCENT_COLOR, 0.12)};
                color: {config.ACCENT_COLOR};
                font-size: {scaled_clear}px;
                font-weight: 600;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QToolButton:hover {{ background-color: {self._hex_to_rgba(config.ACCENT_COLOR, 0.20)}; }}
        """)
        self.clear_filters_btn.clicked.connect(lambda: self._on_stat_card_clicked("total"))
        filter_section_layout.addWidget(self.clear_filters_btn)

        # Filter section's own toggle — only usable/visible once the
        # sidebar itself is expanded (no room for it collapsed). Repurposes
        # the same attribute name other code already tints via
        # _set_search_toggle_indicator() when a filter/search is active.
        self.search_toggle_btn = QToolButton()
        self.search_toggle_btn.setText("🎛  Filters  ▾")
        self.search_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.search_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.search_toggle_btn.setVisible(False)
        self.search_toggle_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_toggle_btn.setMinimumHeight(38)
        scaled_filter_toggle = int(13 * config.GLOBAL_FONT_SCALE)

        self.search_toggle_btn.setStyleSheet(f"""
            QToolButton {{
                border: none;
                background-color: {config.BUTTON_BACKGROUND};
                color: {config.PRIMARY_COLOR};
                font-size: {scaled_filter_toggle}px;
                text-align: left;
                padding: 10px 14px;
                border-radius: 6px;
            }}
            QToolButton:hover {{ background-color: {config.HOVER_COLOR}; }}
        """)
        self._filters_expanded = False

        def toggle_filter_section():
            self._filters_expanded = not self._filters_expanded
            target = filter_section.sizeHint().height() if self._filters_expanded else 0
            anim = QPropertyAnimation(filter_section, b"maximumHeight", filter_section)
            anim.setDuration(160)
            anim.setStartValue(filter_section.maximumHeight())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            filter_section._toggle_anim = anim
            self.search_toggle_btn.setText(f"🎛  Filters  {'▴' if self._filters_expanded else '▾'}")

        self.search_toggle_btn.clicked.connect(toggle_filter_section)
        sidebar_layout.addWidget(self.search_toggle_btn)
        sidebar_layout.addWidget(filter_section)

        def update_filter_indicator(*_args):
            self._set_search_toggle_indicator()

        self.search.textChanged.connect(update_filter_indicator)
        for attr, label, icon, game_key, col_name in self._filter_defs:
            getattr(self, attr).selectionChanged.connect(update_filter_indicator)
        self._update_filter_indicator = update_filter_indicator
        self._set_search_toggle_indicator()

        add_separator()

        self._sidebar_nav_buttons = []

        def add_nav_button(icon, label, tooltip, handler=None, urgent=False, success=False, visible=True):
            btn = ClickableRow()
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setVisible(visible)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(38)

            row_layout = QHBoxLayout(btn)
            row_layout.setContentsMargins(14, 8, 14, 8)
            row_layout.setSpacing(10)

            icon_label = QLabel(icon)
            icon_label.setFixedWidth(18)
            icon_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            scaled_icon = int(14 * config.GLOBAL_FONT_SCALE)
            icon_label.setStyleSheet(f"background: transparent; border: none; font-size: {scaled_icon}px;")
            icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            if urgent or success:
                role_color = config.ACCENT_COLOR if urgent else config.SUCCESS_COLOR
                base_color = role_color
                text_color = config.BUTTON_TEXT_COLOR
                hover_color = self._darken_color(role_color)
            else:
                base_color = config.BUTTON_BACKGROUND
                text_color = config.BUTTON_TEXT_COLOR
                hover_color = config.HOVER_COLOR

            text_label = QLabel(label)
            scaled_text = int(13 * config.GLOBAL_FONT_SCALE)
            text_label.setStyleSheet(f"background: transparent; border: none; font-size: {scaled_text}px; color: {text_color};")
            text_label.setVisible(False)
            text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            row_layout.setAlignment(Qt.AlignLeft)
            row_layout.addWidget(icon_label)
            row_layout.addWidget(text_label)
            row_layout.addStretch(1)

            # Store base and hover styles (for later updates)
            btn._base_style = f"QWidget {{ background-color: {base_color}; border-radius: 6px; }}"
            btn._hover_style = f"QWidget {{ background-color: {hover_color}; border-radius: 6px; }}"
            btn.setStyleSheet(btn._base_style)

            # Manual hover handlers
            def _on_enter(event, b=btn):
                b.setStyleSheet(b._hover_style)
                QWidget.enterEvent(b, event)
            def _on_leave(event, b=btn):
                b.setStyleSheet(b._base_style)
                QWidget.leaveEvent(b, event)
            btn.enterEvent = _on_enter
            btn.leaveEvent = _on_leave

            if handler:
                btn.clicked.connect(handler)
            sidebar_layout.addWidget(btn)
            self._sidebar_nav_buttons.append((btn, icon, label, icon_label, text_label))
            return btn

        self.open_db_btn = add_nav_button("📂", "Open DB", "Open an existing database (JSON or SQLite)",
                                           self._load_database_combined_dialog)
        self.save_db_btn = add_nav_button("💾", "Save DB", "Save current database to file (JSON or SQLite)",
                                           self._save_database_combined_dialog)
        add_separator()
        self.import_btn = add_nav_button("📥", "Add Titles", "Import games from CSV, Excel, TXT, or paste titles",
                                          self._show_import_dialog)
        self.export_btn = add_nav_button("📤", "Export", "Export visible games to PDF or HTML",
                                          self.export_to_pdf_dialog)
        add_separator()
        self.scrape_btn = add_nav_button("🗲", "Scrape Metadata", "Scrape metadata (IGDB + Steam) for games missing IDs",
                                          lambda: self.scrape_all(92), success=True)
        self.scrape_btn.setProperty("success", True)
        self.download_all_btn = add_nav_button("⬇", "Download Resources", "Download screenshots and microtrailers for all games",
                                                self.download_all_screenshots)
        self.cancel_scrape_btn = add_nav_button("✕", "Cancel", "Cancel the current scrape or download operation",
                                                 handler=None, urgent=True, visible=False)
        self.cancel_scrape_btn.setProperty("urgent", True)

        sidebar_layout.addStretch()

        # ------------------------------------------------------------
        # Sidebar expand/collapse
        # ------------------------------------------------------------
        self._sidebar_expanded = False

        def toggle_sidebar():
            self._sidebar_expanded = not self._sidebar_expanded
            target_w = SIDEBAR_EXPANDED_W if self._sidebar_expanded else SIDEBAR_COLLAPSED_W
            for prop in (b"minimumWidth", b"maximumWidth"):
                anim = QPropertyAnimation(sidebar_outer, prop, sidebar_outer)
                anim.setDuration(160)
                anim.setStartValue(sidebar_outer.width())
                anim.setEndValue(target_w)
                anim.setEasingCurve(QEasingCurve.OutCubic)
                anim.start(QPropertyAnimation.DeleteWhenStopped)
                setattr(sidebar_outer, f"_anim_{prop.decode()}", anim)

            for btn, icon, label, icon_label, text_label in self._sidebar_nav_buttons:
                text_label.setVisible(self._sidebar_expanded)

            for stat_id, card in self.stats_card_widgets.items():
                card._title_label.setVisible(self._sidebar_expanded)
                card_layout = card.layout()
                card_layout.setAlignment(Qt.AlignLeft if self._sidebar_expanded else Qt.AlignCenter)
            self._refresh_stat_card_colors()

            self.search_icon_btn.setVisible(not self._sidebar_expanded)
            self.search.setVisible(self._sidebar_expanded)

            self.search_toggle_btn.setVisible(self._sidebar_expanded)
            if not self._sidebar_expanded and self._filters_expanded:
                self._filters_expanded = False
                filter_section.setMaximumHeight(0)
                self.search_toggle_btn.setText("🎛  Filters  ▾")

        toggle_btn.clicked.connect(toggle_sidebar)

        self.sidebar = sidebar_outer
        
    def _make_expander(self, parent_layout, icon, title, start_expanded=True):
        """Reusable collapsible section — a plain header row (label left,
        chevron right) with a thin divider beneath, not its own boxed card,
        so multiple sections read as one continuous surface when placed
        inside a shared parent card."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        header = QWidget()
        header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 8, 0, 8)
        header_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px; font-weight: 700; color: {config.UI_TEXT_COLOR}; background: transparent; border: none;")
        self._expander_title_labels.append(title_label)   # <-- ADD
        chevron_label = QLabel("⌄")
        chevron_label.setStyleSheet(f"font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px; color: {self._hex_to_rgba(config.PRIMARY_COLOR, 0.5)}; background: transparent; border: none;")
        self._expander_chevron_labels.append(chevron_label)  # <-- ADD
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(chevron_label)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 10)
        content_layout.setSpacing(6)

        state = {"expanded": start_expanded}

        def set_chevron():
            chevron_label.setText("⌄" if state["expanded"] else "›")
        set_chevron()
        content.setMaximumHeight(16777215 if start_expanded else 0)
        content.setVisible(start_expanded)

        def toggle(*_args):
            state["expanded"] = not state["expanded"]
            if state["expanded"]:
                # Show BEFORE animating open, so it has real geometry for
                # sizeHint() to measure.
                content.setVisible(True)
            target = content.sizeHint().height() if state["expanded"] else 0
            anim = QPropertyAnimation(content, b"maximumHeight", content)
            anim.setDuration(160)
            anim.setStartValue(content.maximumHeight())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            if not state["expanded"]:
                # Fully remove from layout once collapsed — maximumHeight
                # alone doesn't stop a child with a real minimumSize (e.g.
                # the Media section's image/video widgets) from still
                # claiming space and leaving a visible gap.
                anim.finished.connect(lambda: content.setVisible(False))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            content._toggle_anim = anim
            set_chevron()

        header.mousePressEvent = toggle
        section_layout.addWidget(header)
        section_layout.addWidget(content)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {config.BORDER_COLOR}; max-height: 1px; border: none;")
        section_layout.addWidget(divider)

        # Exposed as attributes (not extra return values) so every existing
        # `content, _ = self._make_expander(...)` call site keeps working
        # unchanged; only code that specifically needs to trigger a toggle
        # externally (e.g. jumping to the Media section) needs these.
        section._toggle = toggle
        section._state = state
        section._header = header

        parent_layout.addWidget(section)
        return content_layout, section

    def _add_detail_field_row(self, content_layout, game_key, icon, label_text):
        """Create one label:value row, once, reused across selections via
        setText()/setVisible() — avoids rebuilding widgets on every table
        click, which a fixed field set doesn't need. Two columns only
        (label left, value right-aligned) — no icon column."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)
        name_label = QLabel(f"{icon} {label_text}")
        name_label.setStyleSheet(f"color: {config.DETAILS_METADATA_LABEL_COLOR}; font-size: {config.DETAILS_METADATA_LABEL_FONT_SIZE}px; background: transparent; border: none;")
        value_label = QLabel("")
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setStyleSheet(f"color: {config.DETAILS_METADATA_VALUE_COLOR}; font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px; font-weight: 600; background: transparent; border: none;")
        row_layout.addWidget(name_label)
        row_layout.addWidget(value_label, 1)
        content_layout.addWidget(row)
        self._detail_field_rows[game_key] = (row, value_label)

    def _setup_details_panel(self):
        details_container = QWidget()
        outer_layout = QVBoxLayout(details_container)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)

        # ---------- ONE unified card holds everything: hero, resource
        # strip, description, links, and every expander section — reads
        # as a single continuous surface rather than nested boxes. ----------
        card = QWidget()
        card.setObjectName("details_card")
        card.setStyleSheet(f"""
            QWidget#details_card {{
                background-color: {config.DETAILS_PANEL_BACKGROUND};
                border: 1px solid {config.BORDER_COLOR};
                border-radius: {config.DETAILS_PANEL_BORDER_RADIUS}px;
            }}
        """)
        self.details_card = card   # <-- ADD THIS
        details_layout = QVBoxLayout(card)
        details_layout.setContentsMargins(16, 16, 16, 8)
        details_layout.setSpacing(4)
        outer_layout.addWidget(card)

        # ---------- Cover art: fixed 16:9 container, centered, image
        # cropped to completely fill it. This is a real QLabel with a
        # pre-cropped QPixmap rather than an HTML <img> inside the title
        # richtext — QTextDocument's rich-text engine doesn't reliably
        # honor CSS width/height/object-fit on <img>, which was letting
        # the raw cover art render at its native size and balloon the
        # table row, shoving the title text on top of the artwork. ----------
        self.details_cover = QLabel()
        self.details_cover.setObjectName("details_cover")
        BASE_COVER_WIDTH = 230
        cover_w = int(BASE_COVER_WIDTH * config.DETAILS_COVER_MULTIPLIER)
        cover_h = int(cover_w * 215 / 460)   # original aspect ratio
        self.details_cover.setFixedSize(cover_w, cover_h)
        self.details_cover.setAlignment(Qt.AlignCenter)
        self.details_cover.setScaledContents(False)
        self.details_cover.setStyleSheet(
            f"background-color: {config.IMAGE_VIEWER_BACKGROUND}; border-radius: 8px; color: {config.DETAILS_METADATA_LABEL_COLOR};"
        )
        cover_row = QHBoxLayout()
        cover_row.setContentsMargins(0, 0, 0, 8)
        cover_row.addStretch()
        cover_row.addWidget(self.details_cover)
        cover_row.addStretch()
        details_layout.addLayout(cover_row)

        # ---------- Hero: title + compact genre subtitle, now entirely
        # separate from the cover art above so the two can never overlap
        # regardless of image size (no long description here — kept short,
        # matching the reference; full description moves below the
        # resource strip instead). ----------
        self.details_hero = QLabel("")
        self.details_hero.setTextFormat(Qt.RichText)
        self.details_hero.setWordWrap(True)
        details_layout.addWidget(self.details_hero)

        # Steam ID / IGDB ID — pinned permanently in the title area (not
        # inside a collapsible section) since these are looked up often
        # enough that hiding them behind a toggle would be annoying.
        self.details_ids_label = QLabel("")
        self.details_ids_label.setTextFormat(Qt.RichText)
        self.details_ids_label.setStyleSheet("margin-top: 2px;")
        details_layout.addWidget(self.details_ids_label)

        # Resource strip — clickable screenshot/trailer thumbnails so
        # resources are visible right away. Clicking one jumps to (and
        # expands, if needed) the Media section below.
        self.resource_strip = QWidget()
        self.resource_strip_layout = QHBoxLayout(self.resource_strip)
        self.resource_strip_layout.setContentsMargins(0, 8, 0, 4)
        self.resource_strip_layout.setSpacing(6)
        details_layout.addWidget(self.resource_strip)

        self.details_description = QLabel("")
        self.details_description.setWordWrap(True)
        self.details_description.setStyleSheet(
            f"color: {config.DETAILS_DESCRIPTION_COLOR}; font-size: {config.DETAILS_DESC_FONT_SIZE}px; "
            f"background: transparent; border: none; margin-top: 4px;"
        )
        details_layout.addWidget(self.details_description)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {config.BORDER_COLOR}; max-height: 1px; border: none; margin-top: 6px;")
        details_layout.addWidget(divider)

        # ---------- Collapsible field sections. Order: Basic info ->
        # Technical details -> Media -> External links -> Save locations.
        # Basic info starts open, everything else starts collapsed. ----------
        self._detail_field_rows = {}

        basic_content, _ = self._make_expander(details_layout, "📌", "Basic info", start_expanded=True)
        self._add_detail_field_row(basic_content, "release_date", config.ICON_RELEASE, "Release date")
        self._add_detail_field_row(basic_content, "genres", config.ICON_GENRES, "Genres")
        self._add_detail_field_row(basic_content, "game_modes", config.ICON_MODES, "Game modes")
        self._add_detail_field_row(basic_content, "themes", config.ICON_THEMES, "Themes")

        tech_content, _ = self._make_expander(details_layout, "⚙️", "Technical details", start_expanded=False)
        self._add_detail_field_row(tech_content, "_version", config.ICON_VERSION, "Version")
        self._add_detail_field_row(tech_content, "game_drive", config.ICON_DRIVE, "Game Drive")
        self._add_detail_field_row(tech_content, "scene_repack", config.ICON_SCENE, "Scene/Repack")
        self._add_detail_field_row(tech_content, "player_perspective", config.ICON_PERSPECTIVE, "Perspective")
        self._add_detail_field_row(tech_content, "developer", config.ICON_DEVELOPER, "Developer")
        self._add_detail_field_row(tech_content, "publisher", config.ICON_PUBLISHER, "Publisher")
        self._add_detail_field_row(tech_content, "original_title", config.ICON_ORIGINAL, "Original title")

        # Media — image viewer + trailer player get inserted into this
        # content_layout later, in _setup_main_layout, once those widgets
        # exist (_setup_image_viewer/_setup_trailer_player run after this
        # method during __init__). Kept on self so that step can reach it,
        # and so the resource strip's jump-to-media click can expand +
        # scroll to this section (via media_section._toggle/_state).
        self.media_content_layout, self.media_section = self._make_expander(
            details_layout, "🎬", "Media", start_expanded=False
        )
        _media_original_toggle = self.media_section._toggle
        def _media_toggle_and_maybe_play(*_args):
            _media_original_toggle(*_args)
            # Wait for the expand animation (160ms) to finish before
            # starting playback — starting it the instant the animation
            # begins means the video widget may still have near-zero
            # geometry, which can be enough to prevent a real frame from
            # ever rendering even once state becomes Playing.
            QTimer.singleShot(200, self._start_trailer_if_visible)
        self.media_section._header.mousePressEvent = _media_toggle_and_maybe_play
        self.media_section._toggle = _media_toggle_and_maybe_play

        self.links_label = QLabel("")
        self.links_label.setTextFormat(Qt.RichText)
        self.links_label.setOpenExternalLinks(True)
        self.links_label.setWordWrap(True)
        links_content, _ = self._make_expander(details_layout, "🔗", "External links", start_expanded=False)
        links_content.addWidget(self.links_label)

        self.save_locs_content, self.save_locs_section = self._make_expander(
            details_layout, "💾", "Savegame locations", start_expanded=False
        )

        details_layout.addStretch()
        self.details_container = details_container

    def _setup_image_viewer(self):
        self.image_box = QWidget()
        self.image_box.setObjectName("image_box")
        # No title, no flat, no group‑box stylesheet
        self.image_box.setContentsMargins(0, 0, 0, 0)
        image_layout = QVBoxLayout(self.image_box)
        image_layout.setContentsMargins(0, 0, 0, 0)        # zero margins
        image_layout.setSpacing(0)                         # zero spacing
        image_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.viewer = ClickableImageViewer(self)
        self.viewer.setStyleSheet(f"background-color: {config.IMAGE_VIEWER_BACKGROUND}; border-radius: 4px; padding: 0px; margin: 0px;")
        viewer_container = QWidget()
        viewer_container.setContentsMargins(0, 0, 0, 0)
        viewer_container_layout = QVBoxLayout(viewer_container)
        viewer_container_layout.setContentsMargins(0, 0, 0, 0)
        self._viewer_container = AspectRatioWidget(self.viewer, parent=viewer_container)
        # (removed _child_layout lines as they are not needed)
        self._viewer_container.setMinimumSize(100, 70)
        self._viewer_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        viewer_container_layout.addWidget(self._viewer_container)

        self.nav_container = QWidget(viewer_container)
        self.nav_container.setStyleSheet("background: transparent;")
        self.nav_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.prev_btn = QPushButton("◀", self.nav_container)
        self.prev_btn.setFixedSize(40, 40)
        self.prev_btn.setEnabled(False)
        btn_style = f"""
        QPushButton {{
            background-color: rgba(0,0,0,180);
            color: {config.BUTTON_TEXT_COLOR};
            border: none;
            border-radius: 20px;
            font-size: 16px;
        }}
        QPushButton:hover {{ background-color: rgba(0,0,0,220); }}
        QPushButton:disabled {{ background-color: rgba(0,0,0,80); color: {config.BUTTON_TEXT_COLOR}; }}
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.open_image_btn = QPushButton("🌐", self.nav_container)
        self.open_image_btn.setFixedSize(40, 40)
        self.open_image_btn.setEnabled(False)
        self.open_image_btn.setStyleSheet(btn_style)
        self.expand_btn = QPushButton("⛶", self.nav_container)
        self.expand_btn.setFixedSize(40, 40)
        self.expand_btn.setEnabled(False)
        self.expand_btn.setToolTip("Open fullscreen viewer")
        self.expand_btn.setStyleSheet(btn_style)
        self.expand_btn.clicked.connect(self._open_media_viewer)
        self.next_btn = QPushButton("▶", self.nav_container)
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet(btn_style)
        self.image_counter = QLabel("No images", self.nav_container)
        self.image_counter.setAlignment(Qt.AlignCenter)
        self.image_counter.setStyleSheet(f"background-color: rgba(0,0,0,160); color: {config.VIEWER_COUNTER_COLOR}; padding: 4px 8px; border-radius: 3px;")

        image_layout.addWidget(viewer_container, 1)
        self._viewer_container_widget = viewer_container
        viewer_container.resizeEvent = self._on_viewer_container_resize
        QTimer.singleShot(100, lambda: self.nav_container.raise_())

        # Clicking directly on the image also opens the same fullscreen
        # screenshot/trailer viewer used by the details panel (gui_main_3).
        self.viewer.mousePressEvent = lambda ev: self._open_media_viewer()

    def _on_viewer_container_resize(self, event):
        QWidget.resizeEvent(self._viewer_container_widget, event)
        QTimer.singleShot(50, self._position_navigation_buttons)

    def _position_navigation_buttons(self):
        try:
            if not hasattr(self, 'prev_btn'):
                return
            viewer_rect = self._viewer_container_widget.rect()
            if viewer_rect.isEmpty():
                return
            self.nav_container.setGeometry(viewer_rect)
            button_y = max(10, viewer_rect.height() - 60)
            self.prev_btn.move(20, button_y)
            center_x = (viewer_rect.width() - 40) // 2
            self.open_image_btn.move(center_x - 50, button_y)
            self.expand_btn.move(center_x + 50, button_y)
            self.next_btn.move(viewer_rect.width() - 60, button_y)
            counter_width = self.image_counter.sizeHint().width()
            self.image_counter.move((viewer_rect.width() - counter_width) // 2, 10)
            self.nav_container.raise_()
        except Exception as e:
            print(f"Button positioning error: {e}")

    def _force_button_refresh(self):
        self._position_navigation_buttons()
        if hasattr(self, 'nav_container'):
            self.nav_container.update()
            self.nav_container.repaint()

    def _setup_trailer_player(self):
        """Create an empty container for the trailer player.
           The actual video widgets are managed by TrailerPlayerManager."""
        self.trailer_container = QWidget()
        self.trailer_container.setObjectName("trailer_container")
        self.trailer_container.setContentsMargins(0, 0, 0, 0)
        # No layout or widgets added here – the manager will populate it.
        # Best-effort: clicking on the trailer area (when the click isn't
        # consumed by whatever TrailerPlayerManager places inside it) opens
        # the same fullscreen viewer used elsewhere.
        self.trailer_container.mousePressEvent = lambda ev: self._open_media_viewer()

    def _start_trailer_if_visible(self):
        if not getattr(self, "_media_has_trailer", False):
            return
        if getattr(self, "_media_slide", -1) != 0:
            return
        if not self.media_section._state["expanded"]:
            return

        trailer_url = getattr(self, "_media_trailer_url", "")
        game = getattr(self, "_media_current_game", None)
        if trailer_url:
            self.trailer_player.play_trailer_media(trailer_url, game)

    def _media_total_slides(self):
        n_images = len(self.image_display._image_items) if hasattr(self, "image_display") else 0
        return n_images + (1 if getattr(self, "_media_has_trailer", False) else 0)

    def _media_show_slide(self, slide_idx):
        total = self._media_total_slides()
        if total == 0:
            self.media_stack.setCurrentIndex(0)
            self.image_counter.setText("No media")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.open_image_btn.setEnabled(False)
            self._media_slide = 0
            return

        slide_idx = slide_idx % total
        self._media_slide = slide_idx
        has_trailer = getattr(self, "_media_has_trailer", False)

        if has_trailer and slide_idx == 0:
            self.media_stack.setCurrentIndex(1)   # trailer page
            self.image_counter.setText(f"Trailer  ·  1/{total}")
            trailer_url = getattr(self, "_media_trailer_url", "")
            self.open_image_btn.setToolTip(f"Open trailer in browser: {trailer_url}" if trailer_url else "")
            self.open_image_btn.setEnabled(bool(trailer_url))
            self._start_trailer_if_visible()
        else:
            img_idx = slide_idx - (1 if has_trailer else 0)
            self.media_stack.setCurrentIndex(0)   # image page
            self.image_display.display_image(img_idx)
            self.image_counter.setText(f"{slide_idx + 1}/{total}")
            items = self.image_display._image_items
            cur_item = items[img_idx] if 0 <= img_idx < len(items) else None
            url = cur_item.get("url") if cur_item else ""
            self.open_image_btn.setToolTip(f"Open in browser: {url}" if url else "")
            self.open_image_btn.setEnabled(bool(url))

        self.prev_btn.setEnabled(total > 1)
        self.next_btn.setEnabled(total > 1)
        QTimer.singleShot(50, self._position_navigation_buttons)

    def _media_next(self):
        self._media_show_slide(getattr(self, "_media_slide", 0) + 1)

    def _media_prev(self):
        self._media_show_slide(getattr(self, "_media_slide", 0) - 1)

    def _media_open_current(self):
        if getattr(self, "_media_has_trailer", False) and getattr(self, "_media_slide", 0) == 0:
            trailer_url = getattr(self, "_media_trailer_url", "")
            if trailer_url:
                QDesktopServices.openUrl(QUrl(trailer_url))
                self.status.setText("Opened trailer URL in browser")
        else:
            self.image_display.open_current_image_url()

    def _open_media_viewer(self):
        """Open the same fullscreen media viewer (ScreenshotViewerDialog)
        used by the details panel, pre-loaded with the current game's
        trailer and screenshots, starting at the slide currently shown."""
        if self._media_total_slides() == 0:
            return

        media_items = []
        has_trailer = getattr(self, "_media_has_trailer", False)
        if has_trailer:
            media_items.append({
                "type": "video",
                "url": getattr(self, "_media_trailer_url", ""),
            })

        for item in getattr(self.image_display, "_image_items", []):
            media_items.append({
                "type": "image",
                "url": item.get("url"),
                "pixmap": item.get("pixmap"),
            })

        if not media_items:
            return

        start_index = getattr(self, "_media_slide", 0)
        start_index = max(0, min(start_index, len(media_items) - 1))

        dialog = ScreenshotViewerDialog(self, media_items, start_index)
        dialog.exec_()

    def _setup_main_layout(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Outer layout: sidebar (full height, owns search/filters/stats) +
        # a content column that's now JUST the table/details splitter —
        # no top bar competing for vertical space.
        outer_layout = QHBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(self.sidebar)

        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)   # already zero

        splitter = QSplitter(Qt.Horizontal)

        # --- NEW: Remove splitter margins and set thin handle ---
        splitter.setContentsMargins(0, 0, 0, 0)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {config.SPLITTER_HANDLE_COLOR};
                width: 2px;
            }}
            QSplitter {{
                border: none;
            }}
        """)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)   # already zero
        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setWidget(self.table)
        table_scroll.setFrameShape(QFrame.NoFrame)
        left_layout.addWidget(table_scroll, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)   # already zero

        # Media (image viewer + trailer) lives inside the details panel as
        # its own collapsible section. Both share ONE viewing frame via a
        # QStackedWidget (image = page 0, trailer = page 1, only one
        # visible at a time, both occupying the exact same rect) instead of
        # being stacked vertically as two separate boxes. The nav overlay
        # (prev/next/open/counter, built in _setup_image_viewer) is
        # reparented onto the stack itself so it floats over whichever
        # page is current, giving one seamless viewer with one set of
        # controls instead of two independent widgets sandwiched together.
        self.media_stack = QStackedWidget()
        self.media_stack.setStyleSheet(f"background-color: {config.IMAGE_VIEWER_BACKGROUND}; border-radius: 6px;")
        self.media_stack.addWidget(self.image_box)      # page 0: images
        self.media_stack.addWidget(self.trailer_container)  # page 1: trailer
        self.media_stack.setMinimumHeight(280)

        self.nav_container.setParent(self.media_stack)
        self.nav_container.raise_()
        self._viewer_container_widget = self.media_stack
        self.media_stack.resizeEvent = self._on_viewer_container_resize

        self.media_content_layout.addWidget(self.media_stack)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setWidget(self.details_container)
        details_scroll.setFrameShape(QFrame.NoFrame)
        right_layout.addWidget(details_scroll)
        self.details_scroll = details_scroll

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        divider = config.DIVIDER_PERCENTAGE / 100.0
        splitter.setSizes([int(self.width() * divider), int(self.width() * (1 - divider))])
        main_layout.addWidget(splitter, 1)
        self.main_splitter = splitter

        outer_layout.addWidget(content_widget, 1)

    def _setup_status_bar(self):
        self.status = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.total_label = QLabel("Total: 0")
        self.played_label = QLabel("Played: 0")
        self.remaining_label = QLabel("Remaining: 0")
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addWidget(self.progress_bar)
        self.statusBar().addPermanentWidget(self.total_label)
        self.statusBar().addPermanentWidget(self.played_label)
        self.statusBar().addPermanentWidget(self.remaining_label)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._viewer_container._update_child_geometry()
        QTimer.singleShot(50, self._position_navigation_buttons)

    def clear_filters(self):
        """Clear search and every filter dropdown."""
        self.search.clear()
        self.proxy.setFilterFixedString("")
        for attr, label, icon, game_key, col_name in self._filter_defs:
            getattr(self, attr).clear_all()

    # ----------------------------------------------------------------------
    # Model and data methods
    # ----------------------------------------------------------------------
    def on_model_item_changed(self, item: QStandardItem):
        if self._suppress_model_change:
            return
        row = item.row()
        col = item.column()
        if row < 0 or row >= len(self.games):
            return
        game = self.games[row]

        if col == self.COL_PLAYED:
            game["played"] = (item.checkState() == Qt.Checked)
            self._mark_dirty()
            self.model.blockSignals(True)
            title_item = self.model.item(row, self.COL_TITLE)
            if title_item:
                base = self.games[row].get("title", "")
                sym = []
                if self.games[row].get("played"):
                    sym.append("✅")
                if self.games[row].get("fav"):
                    sym.append("♥")
                new_text = base + (" " + " ".join(sym) if sym else "")
                title_item.setText(new_text)
            self.model.blockSignals(False)
            selected_rows = self._selected_source_rows()
            if row in selected_rows:
                self.show_details_for_source_row(row)
            return

        if col == self.COL_FAV:
            game["fav"] = (item.checkState() == Qt.Checked)
            self._mark_dirty()
            self.model.blockSignals(True)
            title_item = self.model.item(row, self.COL_TITLE)
            if title_item:
                base = self.games[row].get("title", "")
                sym = []
                if self.games[row].get("played"):
                    sym.append("✅")
                if self.games[row].get("fav"):
                    sym.append("♥")
                new_text = base + (" " + " ".join(sym) if sym else "")
                title_item.setText(new_text)
            self.model.blockSignals(False)
            selected_rows = self._selected_source_rows()
            if row in selected_rows:
                self.show_details_for_source_row(row)
            return

        text = item.text().strip()
        if not text:
            return
        mapping = {
            self.COL_TITLE: "title",
            self.COL_VERSION: "patch_version",
            self.COL_GAMEDRIVE: "game_drive",
            self.COL_STEAMID: "app_id",
            self.COL_GENRES: "genres",
            self.COL_GAME_MODES: "game_modes",
            self.COL_RELEASE: "release_date",
            self.COL_THEMES: "themes",
            self.COL_DEV: "developer",
            self.COL_PUB: "publisher",
            self.COL_SCENE: "scene_repack",
            self.COL_PERSPECTIVE: "player_perspective",
            self.COL_ORIGINAL: "original_title",
            self.COL_IGDB_ID: "igdb_id",
            self.COL_SHORTCUTS: "screenshots",
            self.COL_TRAILER: "microtrailers",      # this is index 17, used for trailer_webm
            self.COL_STEAMDB: "steamdb_link",
            self.COL_PCWIKI: "pcgw_link",
            self.COL_STEAM_LINK: "steam_link",
            self.COL_COVER_URL: "cover_url",
            self.COL_DESCRIPTION: "description",
            self.COL_IGDB_TRAILERS: "trailers",
            self.COL_MICROTRAILERS: "microtrailers_extra",   # index 24 → microtrailers_extra
            self.COL_USER_RATING: "user_rating",
            self.COL_IGDB_COVER_ART: "igdb_cover_art"
        }
        key = mapping.get(col)
        if key:
            game[key] = text
            self._mark_dirty()

    def refresh_model(self):
        self._suppress_model_change = True
        try:
            self.model.blockSignals(True)
            self.model.setRowCount(0)
            self.recompute_duplicates()
            for game_idx, game in enumerate(self.games):
                row_items = []
                for col in range(len(self.COLUMN_KEYS)):
                    key = self.COLUMN_KEYS[col]
                    if col == 0:  # Title column
                        title_text = game.get("title", "")
                        if game.get("played"):
                            title_text = f"{title_text} ✅"
                        if game.get("fav"):
                            title_text = f"{title_text} ♥"
                        value = title_text
                    elif key == "patch_version":
                        value = game.get("patch_version", "") or game.get("original_title_version", "")
                    elif key == "screenshots":
                        val = game.get("screenshots", [])
                        if isinstance(val, str):
                            val = [val] if val else []
                        value = ", ".join(str(x) for x in val if x)
                    elif key == "trailers":
                        val = game.get("trailers", [])
                        if isinstance(val, str):
                            val = [val] if val else []
                        value = ", ".join(str(x) for x in val if x)
                    elif key == "microtrailers_extra":
                        val = game.get("microtrailers_extra", [])
                        if isinstance(val, str):
                            val = [val] if val else []
                        value = ", ".join(str(x) for x in val if x)
                    elif key == "played":
                        value = ""
                    elif key == "fav":
                        value = ""
                    else:
                        value = game.get(key, "")
                    row_items.append(QStandardItem(str(value)))
                row_items[0].setData(game, Qt.UserRole)
                row_items[self.COL_PLAYED].setCheckable(True)
                row_items[self.COL_PLAYED].setCheckState(Qt.Checked if game.get("played", False) else Qt.Unchecked)
                row_items[self.COL_FAV].setCheckable(True)
                row_items[self.COL_FAV].setCheckState(Qt.Checked if game.get("fav", False) else Qt.Unchecked)
                for col_idx, it in enumerate(row_items):
                    it.setEditable(col_idx != self.COL_PLAYED and col_idx != self.COL_FAV and col_idx != self.COL_TITLE)
                self.model.appendRow(row_items)
            self.model.blockSignals(False)
        finally:
            self._suppress_model_change = False
        self.proxy.invalidate()
        self._refresh_filter_options()
        self.apply_filters()
        self.table.viewport().update()
        self.update_counters()

    def recompute_duplicates(self):
        title_counts = {}
        steam_counts = {}
        igdb_counts = {}
        for game in self.games:
            title = (game.get("title") or "").strip()
            if title:
                norm = title.lower()
                title_counts[norm] = title_counts.get(norm, 0) + 1
            sid = str(game.get("app_id") or "").strip()
            if sid:
                steam_counts[sid.lower()] = steam_counts.get(sid.lower(), 0) + 1
            iid = str(game.get("igdb_id") or "").strip()
            if iid:
                igdb_counts[iid.lower()] = igdb_counts.get(iid.lower(), 0) + 1

        self._dup_title_set = {k for k, v in title_counts.items() if v > 1}
        self._dup_steamid_set = {k for k, v in steam_counts.items() if v > 1}
        self._dup_igdbid_set = {k for k, v in igdb_counts.items() if v > 1}

    def update_counters(self):
        total = len(self.games)
        played = sum(1 for g in self.games if g.get("played", False))
        remaining = total - played
        cached = 0
        for g in self.games:
            paths = g.get("image_cache_paths") or []
            for p in paths:
                if p and (config.SCRIPT_DIR / p).exists():
                    cached += 1
                    break
        title_counts = {}
        for g in self.games:
            t = (g.get("title") or "").strip().lower()
            if t:
                title_counts[t] = title_counts.get(t, 0) + 1
        duplicate_games = sum(c for c in title_counts.values() if c > 1)
        unscraped = sum(1 for g in self.games if not (g.get("app_id") or "").strip() and not (g.get("igdb_id") or "").strip())
        self.stats_cards["total"].setText(str(total))
        self.stats_cards["played"].setText(str(played))
        self.stats_cards["remaining"].setText(str(remaining))
        self.stats_cards["cached"].setText(str(cached))
        self.stats_cards["duplicates"].setText(str(duplicate_games))
        self.stats_cards["unscraped"].setText(str(unscraped))
        favourites = sum(1 for g in self.games if g.get("fav", False))
        self.stats_cards["favourites"].setText(str(favourites))
        self.total_label.setText(f"Total: {total}")
        self.played_label.setText(f"Played: {played}")
        self.remaining_label.setText(f"Remaining: {remaining}")

    def apply_theme(self):
        """Single entry point: re-apply every config-driven setting to this
        window (including the bespoke inline-widget styling this variant
        builds by hand), then hand off to config.refresh_all() to propagate
        the same change to every custom child widget automatically.
        """
        if config.AUTO_SAVE:
            self._auto_save_timer.setInterval(config.AUTO_SAVE_INTERVAL * 1000)
        else:
            self._auto_save_timer.stop()
        divider = config.DIVIDER_PERCENTAGE / 100.0
        self.main_splitter.setSizes([int(self.width() * divider), int(self.width() * (1 - divider))])
        self._apply_ui_colors()
        self._restyle_local_widgets()   # this window's own hand-built widgets
        self.table.setItemDelegate(HighlightDelegate(self))
        self.table.viewport().update()
        self.table.update()
        self._refresh_stat_card_colors()
        self._apply_table_font()

        # Propagate to every child widget that defines apply_theme()
        # (sidebar/header/details-panel-equivalents this variant doesn't
        # use, but also CheckableComboBox filters, image viewers, etc.)
        # This also does the unpolish/polish/repaint sweep across the whole
        # tree, replacing the manual loop that used to live here.
        config.refresh_all(self)

        self.status.setText("Settings applied.")
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            src = self.proxy.mapToSource(selected_rows[0])
            if src.isValid():
                self.show_details_for_source_row(src.row())

    # Back-compat alias for any external callers using the old name
    _apply_config_settings = apply_theme


    def _apply_ui_colors(self):
        """Reapply the application palette using current config colors."""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(config.LIGHT_BG))
        palette.setColor(QPalette.WindowText, QColor(config.PRIMARY_COLOR))
        palette.setColor(QPalette.Base, QColor(config.INPUT_BACKGROUND))
        palette.setColor(QPalette.AlternateBase, QColor(config.TABLE_ALTERNATE_BACKGROUND))
        palette.setColor(QPalette.Text, QColor(config.TABLE_TEXT_COLOR))
        palette.setColor(QPalette.Button, QColor(config.SECONDARY_COLOR))
        palette.setColor(QPalette.ButtonText, QColor(config.BUTTON_TEXT_COLOR))
        palette.setColor(QPalette.Highlight, QColor(config.SELECTED_COLOR))
        palette.setColor(QPalette.HighlightedText, QColor(config.SELECTION_TEXT_COLOR))
        self.setPalette(palette)

    def _restyle_local_widgets(self):
        """Reapply styling for this window's hand-built (non-custom-class)
        widgets: plain QLabel/QToolButton instances created inline here have
        no apply_theme() of their own, so config.refresh_all() can't reach
        them -- they're tracked in the lists below and restyled directly.
        Anything built as a reusable custom widget class (CheckableComboBox,
        ClickableImageViewer, ...) does NOT need to be touched here; it's
        handled automatically by config.refresh_all() at the end of
        apply_theme().
        """
        
        # 1. Main window background (the area behind the splitter)
        if hasattr(self, 'centralWidget'):
            self.centralWidget().setStyleSheet(f"background-color: {config.LIGHT_BG};")

        # 2. Sidebar container
        if hasattr(self, 'sidebar'):
            self.sidebar.setStyleSheet(f"""
                QWidget#sidebar {{
                    background-color: {config.LIGHT_BG};
                    border-right: 1px solid {config.BORDER_COLOR};
                }}
            """)

        # 3. Details container background (the "white border" area)
        if hasattr(self, 'details_container'):
            self.details_container.setStyleSheet(f"background-color: {config.LIGHT_BG};")

        # 4. Details card (border and background)
        if hasattr(self, 'details_card'):
            self.details_card.setStyleSheet(f"""
                QWidget#details_card {{
                    background-color: {config.DETAILS_PANEL_BACKGROUND};
                    border: 1px solid {config.BORDER_COLOR};
                    border-radius: {config.DETAILS_PANEL_BORDER_RADIUS}px;
                }}
            """)
            self.details_card.style().unpolish(self.details_card)
            self.details_card.style().polish(self.details_card)
            self.details_card.update()

        # 5. Filter caption labels (Genre, Drive, etc.)
        caption_color = self._hex_to_rgba(config.PRIMARY_COLOR, 0.65)
        for label in self._filter_caption_labels:
            label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {caption_color};")

        # 6. Expander title labels
        for title_label in self._expander_title_labels:
            title_label.setStyleSheet(
                f"font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px; "
                f"font-weight: 700; color: {config.UI_TEXT_COLOR}; "
                "background: transparent; border: none;"
            )

        # 7. Expander chevron labels
        for chevron_label in self._expander_chevron_labels:
            chevron_label.setStyleSheet(
                f"font-size: {config.DETAILS_SECTION_HEADER_FONT_SIZE}px; "
                f"color: {self._hex_to_rgba(config.PRIMARY_COLOR, 0.5)}; "
                "background: transparent; border: none;"
            )

        # 8. Expander section headers – hover background
        for title_label in self._expander_title_labels:
            header = title_label.parentWidget()
            if header and isinstance(header, QWidget):
                hover_color = self._hex_to_rgba(config.UI_TEXT_COLOR, 0.08)
                header.setStyleSheet(f"""
                    QWidget:hover {{
                        background-color: {hover_color};
                        border-radius: 4px;
                    }}
                """)

        # 9. Details field rows
        for key, (row, value_label) in self._detail_field_rows.items():
            name_label = row.findChild(QLabel)
            if name_label:
                name_label.setStyleSheet(
                    f"color: {config.DETAILS_METADATA_LABEL_COLOR}; "
                    f"font-size: {config.DETAILS_METADATA_LABEL_FONT_SIZE}px; "
                    "background: transparent; border: none;"
                )
            if value_label:
                value_label.setStyleSheet(
                    f"color: {config.DETAILS_METADATA_VALUE_COLOR}; "
                    f"font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px; "
                    "font-weight: 600; background: transparent; border: none;"
                )

        # 10. Sidebar navigation buttons
        for btn, icon, label, icon_label, text_label in self._sidebar_nav_buttons:
            if btn.property("success") or btn.property("urgent"):
                role_color = config.ACCENT_COLOR if btn.property("urgent") else config.SUCCESS_COLOR
                base_color = role_color
                hover_color = self._darken_color(role_color)
            else:
                base_color = config.BUTTON_BACKGROUND
                hover_color = config.HOVER_COLOR

            btn._base_style = f"QWidget {{ background-color: {base_color}; border-radius: 6px; }}"
            btn._hover_style = f"QWidget {{ background-color: {hover_color}; border-radius: 6px; }}"
            btn.setStyleSheet(btn._base_style)

        # ========== NEW: Sidebar toggle, filters toggle, clear filters ==========
        # 11. Sidebar toggle button (☰)
        if hasattr(self, 'toggle_btn'):
            scaled_toggle = int(16 * config.GLOBAL_FONT_SCALE)
            self.toggle_btn.setStyleSheet(f"""
                QToolButton {{
                    border: none;
                    background-color: {config.BUTTON_BACKGROUND};
                    font-size: {scaled_toggle}px;
                    padding: 8px;
                    border-radius: 6px;
                    color: {config.PRIMARY_COLOR};
                }}
                QToolButton:hover {{ background-color: {config.HOVER_COLOR}; }}
            """)

        # 12. Filters toggle button (🎛 Filters ▾)
        if hasattr(self, 'search_toggle_btn'):
            scaled_filter_toggle = int(13 * config.GLOBAL_FONT_SCALE)
            self.search_toggle_btn.setStyleSheet(f"""
                QToolButton {{
                    border: none;
                    background-color: {config.BUTTON_BACKGROUND};
                    color: {config.PRIMARY_COLOR};
                    font-size: {scaled_filter_toggle}px;
                    text-align: left;
                    padding: 10px 14px;
                    border-radius: 6px;
                }}
                QToolButton:hover {{ background-color: {config.HOVER_COLOR}; }}
            """)
            self._set_search_toggle_indicator()

        # 13. Clear all filters button
        if hasattr(self, 'clear_filters_btn'):
            scaled_clear = int(11 * config.GLOBAL_FONT_SCALE)
            self.clear_filters_btn.setStyleSheet(f"""
                QToolButton {{
                    border: none;
                    background-color: {self._hex_to_rgba(config.ACCENT_COLOR, 0.12)};
                    color: {config.ACCENT_COLOR};
                    font-size: {scaled_clear}px;
                    font-weight: 600;
                    padding: 6px 10px;
                    border-radius: 6px;
                }}
                QToolButton:hover {{ background-color: {self._hex_to_rgba(config.ACCENT_COLOR, 0.20)}; }}
            """)
        # =====================================================================

        # Reapply the main stylesheet. (Stat-card colors, the unpolish/polish
        # sweep, and every apply_theme()-aware child widget are now handled
        # once, centrally, by config.refresh_all() at the end of
        # apply_theme() -- no need to duplicate that here.)
        self.setStyleSheet(config.APP_STYLESHEET)
    
    def _brighten_color(self, hex_color: str, factor: int = 130) -> str:
        """
        Return a lighter version of the hex color.
        factor: 100 = original, >100 = lighter, <100 = darker.
        """
        if not hex_color or not hex_color.startswith('#'):
            return hex_color
        try:
            color = QColor(hex_color)
            lighter = color.lighter(factor)
            return lighter.name()
        except Exception:
            return hex_color    
    # ----------------------------------------------------------------------
    # Delegated operations
    # ----------------------------------------------------------------------
    def download_all_screenshots(self):
        self._cancel_current_scrape = False
        self.download_mgr.download_all_screenshots()

    def scrape_all(self, auto_accept_score=92):
        self._cancel_current_scrape = False
        self.scrape_coord.scrape_all(auto_accept_score)

    def sanitize_selected_rows(self):
        rows = self._selected_source_rows()
        if not rows:
            self.status.setText("No rows selected.")
            return
        updated = sanitize_selected_rows(self.games, self.model, rows)
        if updated:
            self.refresh_model()
            self._mark_dirty()
            self.status.setText(f"Sanitized {updated} rows")
            QMessageBox.information(self, "Sanitize Complete", f"Sanitized {updated} rows.")
        else:
            self.status.setText("No changes made")

    def _sanitize_single_row(self, row: int):
        if row is not None and 0 <= row < len(self.games):
            sanitize_selected_rows(self.games, self.model, [row])
            self._mark_dirty()

    def recache_selected_rows(self):
        rows = self._selected_source_rows()
        if not rows:
            self.status.setText("No rows selected.")
            return
        reply = QMessageBox.question(self, "Recache Selected Rows",
            f"Clear cached assets for {len(rows)} rows? They will redownload on view.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        cleared = 0
        for row in rows:
            if row < len(self.games):
                game = self.games[row]
                if "image_cache_paths" in game:
                    del game["image_cache_paths"]
                if "microtrailer_cache_path" in game:
                    del game["microtrailer_cache_path"]
                if "igdb_cover_art_cache_path" in game:
                    del game["igdb_cover_art_cache_path"]
                self.model.setItem(row, self.COL_IMAGE_CACHE_PATHS, QStandardItem(""))
                self.model.setItem(row, self.COL_MICROTRAILER_CACHE_PATH, QStandardItem(""))
                cleared += 1
        self.refresh_model()
        self._mark_dirty()
        self.status.setText(f"Cache cleared for {cleared} rows")


    def _load_cover_for_game(self, game):
        """Fetch Steam cover art asynchronously using ImageDisplayManager."""
        app_id = game.get("app_id", "")
        if not app_id or not str(app_id).strip():
            # No Steam ID – hide cover
            self.details_cover.clear()
            self.details_cover.setVisible(False)
            return

        steam_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg"
        print(f"[CoverArt] Fetching Steam cover: {steam_url}")

        # 1. Check cache directly (cover_type='steam')
        cache_path = resolve_cover_art_cache_path(game, cover_type='steam')
        if cache_path and cache_path.exists() and cache_path.stat().st_size > 0:
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                print("[CoverArt] Loaded from cache.")
                self._set_cover_pixmap(pixmap)
                return
            else:
                print("[CoverArt] Cache file exists but QPixmap load failed.")

        # 2. Not cached – download asynchronously
        print("[CoverArt] Not cached, downloading asynchronously...")
        def on_cover_ready(url, pixmap, movie, index):
            if pixmap and not pixmap.isNull():
                print(f"[CoverArt] Downloaded cover: {url}")
                self._set_cover_pixmap(pixmap)
            else:
                print("[CoverArt] Download failed.")
                self.details_cover.clear()
                self.details_cover.setVisible(False)

        # Ensure we have a cover_fetcher
        if not hasattr(self, 'cover_fetcher'):
            self.cover_fetcher = ImageDisplayManager(self)

        # Use a temporary viewer (the fetcher expects one)
        temp_viewer = ClickableImageViewer()
        temp_viewer.hide()
        self.cover_fetcher.viewer = temp_viewer

        # Start the download with cover_type='steam' and respect AUTO_CACHE
        self.cover_fetcher.fetch_and_display_images(
            row_index=0,               # dummy
            urls=[steam_url],
            on_image_ready=on_cover_ready,
            cover_type='steam',        # save as steam_coverart.*
            save_to_cache=config.AUTO_CACHE
        )

    def _set_cover_pixmap(self, pixmap):
        if pixmap.isNull():
            self.details_cover.clear()
            self.details_cover.setVisible(False)
            return
        target = self.details_cover.size()
        if target.width() > 0 and target.height() > 0:
            # Use KeepAspectRatioByExpanding to fill the container
            scaled = pixmap.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.details_cover.setPixmap(scaled)
        else:
            self.details_cover.setPixmap(pixmap)
        self.details_cover.setVisible(True)
 
    def _get_thumbnail_data_uri(self, game: dict) -> str:
        """Return a data URI for any suitable image in the game cache, or empty string."""
        try:
            if not config.SHOW_THUMBNAILS_IN_DETAILS:
                return ""

            cache_dir = _game_cache_dir_for_game(game)
            if not cache_dir or not cache_dir.exists():
                return ""

            cover_url = game.get("cover_url", "") or game.get("igdb_cover_art", "")
            if cover_url:
                norm_url = cover_url.split('?')[0]
                if norm_url.startswith('http://'):
                    norm_url = 'https://' + norm_url[7:]
                url_hash = hashlib.sha256(norm_url.encode("utf-8")).hexdigest()
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    candidate = cache_dir / f"{url_hash}{ext}"
                    if candidate.exists() and candidate.stat().st_size > 0:
                        with open(candidate, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode('utf-8')
                        mime = "image/jpeg" if ext in ('.jpg','.jpeg') else "image/png"
                        return f"data:{mime};base64,{img_data}"

            images = [f for f in cache_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in ('.jpg','.jpeg','.png')
                      and f.stat().st_size > 20*1024]
            if images:
                best = max(images, key=lambda f: f.stat().st_size)
                with open(best, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                ext = best.suffix.lower()
                mime = "image/jpeg" if ext in ('.jpg','.jpeg') else "image/png"
                return f"data:{mime};base64,{img_data}"
        except Exception as e:
            print(f"Thumbnail error: {e}")
        return ""

    # ----------------------------------------------------------------------
    # Selection and details
    # ----------------------------------------------------------------------
    def _selected_source_rows(self) -> List[int]:
        selected = self.table.selectionModel().selectedRows()
        rows = set()
        for idx in selected:
            src = self.proxy.mapToSource(idx)
            if src.isValid():
                rows.add(src.row())
        return sorted(rows)

    def _handle_selection_changed(self, selected, deselected):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            src = self.proxy.mapToSource(rows[0])
            if src.isValid():
                self.show_details_for_source_row(src.row())

    def show_details_for_source_row(self, source_row: int):
        if source_row < 0 or source_row >= len(self.games):
            return
        game = self.games[source_row]

        def escape_html(t):
            return (t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>"))

        title_font = config.DETAILS_TITLE_FONT_SIZE

# In show_details_for_source_row, after the escape_html function definition

        # ---- Cover art (Steam-only) ----
        self._load_cover_for_game(game)
            
        title_text = escape_html(game.get("title", "Untitled"))
        symbols = []
        if game.get("played", False):
            symbols.append("✅")
        if game.get("fav", False):
            symbols.append("♥")
        symbols_html = " " + " ".join(symbols) if symbols else ""

        rating_inline = ""
        user_rating = game.get("user_rating", "")
        if user_rating:
            try:
                rating_num = float(user_rating)
                rating_clamped = max(0, min(100, rating_num))
                stars = rating_clamped / 20.0
                full = int(stars)
                half = 1 if (stars - full) >= 0.5 else 0
                empty = 5 - full - half
                stars_str = "★" * full + "½" * half + "☆" * empty
                rating_display = f"{int(rating_num)}" if rating_num == int(rating_num) else f"{rating_num:.1f}"
                # In show_details_for_source_row, around the rating display:
                rating_inline = f' <span style="font-size:{config.DETAILS_RATING_FONT_SIZE}px; color:{config.DETAILS_RATING_COLOR};">{stars_str}</span><span style="color:{config.DETAILS_METADATA_LABEL_COLOR};">({rating_display})</span>'
            except Exception:
                rating_inline = " <span style='color:{config.DETAILS_RATING_COLOR};'>☆</span> <span style='color:{config.DETAILS_METADATA_LABEL_COLOR};'>(No rating)</span>"

        full_title = f"{title_text}{symbols_html}{rating_inline}"

        genres_val = (game.get("genres") or "").strip()
        subtitle_terms = [t.strip() for t in genres_val.split(",") if t.strip()][:3]
        subtitle_html = ""
        if subtitle_terms:
            subtitle_html = (f'<div style="font-size:{config.DETAILS_METADATA_LABEL_FONT_SIZE}px; color:{self._hex_to_rgba(config.PRIMARY_COLOR, 0.55)}; '
                              f'margin-top:2px;">{escape_html(" · ".join(subtitle_terms))}</div>')

        self.details_hero.setText(
            f'<div style="font-family:\'Segoe UI\', Arial, sans-serif;">'
            f'<div style="font-size:{title_font}px; font-weight:bold; color:{config.PRIMARY_COLOR};">{full_title}</div>'
            f'{subtitle_html}'
            f'</div>'
        )

        desc = game.get("description", "").strip()
        self.details_description.setText(escape_html(desc) if desc else "<i>No description</i>")

        # --- Resource strip: cached screenshot thumbnails + a trailer icon,
        # each jumping to the Media tab on click instead of hiding
        # resources behind a tab switch. ---
        while self.resource_strip_layout.count():
            item = self.resource_strip_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        def jump_to_media(*_args):
            if not self.media_section._state["expanded"]:
                self.media_section._toggle()
            QTimer.singleShot(180, lambda: self.details_scroll.ensureWidgetVisible(self.media_section, 0, 40))

        def jump_to_trailer(*_args):
            jump_to_media()
            if getattr(self, "_media_has_trailer", False):
                self._media_show_slide(0)

        try:
            cache_dir = _game_cache_dir_for_game(game)
            thumb_files = []
            if cache_dir and cache_dir.exists():
                thumb_files = sorted(
                    [f for f in cache_dir.iterdir()
                     if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')
                     and f.stat().st_size > 5 * 1024],
                    key=lambda f: f.stat().st_size, reverse=True
                )[:4]
        except Exception:
            thumb_files = []

        for f in thumb_files:
            thumb_btn = QLabel()
            thumb_btn.setFixedSize(44, 32)
            thumb_btn.setCursor(Qt.PointingHandCursor)
            thumb_btn.setScaledContents(True)
            thumb_btn.setStyleSheet(f"border-radius: 6px; border: 1px solid {config.BORDER_COLOR};")
            pix = QPixmap(str(f))
            if not pix.isNull():
                thumb_btn.setPixmap(pix)
            thumb_btn.mousePressEvent = jump_to_media
            self.resource_strip_layout.addWidget(thumb_btn)

        trailer_url = game.get("trailer_webm") or ""
        if not trailer_url:
            micros = game.get("microtrailers") or []
            if micros and isinstance(micros, list) and len(micros):
                trailer_url = micros[0]
        if trailer_url:
            trailer_btn = QToolButton()
            trailer_btn.setText("▶")
            trailer_btn.setToolTip("Play trailer")
            trailer_btn.setFixedSize(44, 32)
            trailer_btn.setCursor(Qt.PointingHandCursor)
            scaled_trailer_btn = int(13 * config.GLOBAL_FONT_SCALE)

            trailer_btn.setStyleSheet(f"""
                QToolButton {{
                    border: 1px solid {config.BORDER_COLOR};
                    border-radius: 6px;
                    background-color: {self._hex_to_rgba(config.SECONDARY_COLOR, 0.10)};
                    color: {config.SECONDARY_COLOR};
                    font-size: {scaled_trailer_btn}px;
                }}
                QToolButton:hover {{ background-color: {self._hex_to_rgba(config.SECONDARY_COLOR, 0.20)}; }}
            """)
            trailer_btn.clicked.connect(jump_to_trailer)
            self.resource_strip_layout.addWidget(trailer_btn)

        self.resource_strip_layout.addStretch()
        self.resource_strip.setVisible(bool(thumb_files) or bool(trailer_url))

        # --- Steam ID / IGDB ID: pinned permanently in the hero area,
        # always visible regardless of which section is expanded. ---
        id_badges = []
        if game.get("app_id"):
            id_badges.append(f'<span style="background:{self._hex_to_rgba(config.SECONDARY_COLOR, 0.12)}; color:{config.SECONDARY_COLOR}; '
                              f'padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600;">Steam {escape_html(str(game["app_id"]))}</span>')
        if game.get("igdb_id"):
            scaled_badge = int(11 * config.GLOBAL_FONT_SCALE)

            id_badges.append(f'<span style="background:{self._hex_to_rgba(config.SUCCESS_COLOR, 0.12)}; color:{config.SUCCESS_COLOR}; '
                              f'padding:2px 8px; border-radius:10px; font-size:{scaled_badge}px; font-weight:600; margin-left:6px;">IGDB {escape_html(str(game["igdb_id"]))}</span>')
        self.details_ids_label.setText("".join(id_badges))
        self.details_ids_label.setVisible(bool(id_badges))

        # --- Basic Info / Technical Details field rows: fixed widgets,
        # just update text + visibility per selection. ---
        field_values = {
            "release_date": game.get("release_date", ""),
            "genres": game.get("genres", ""),
            "game_modes": game.get("game_modes", ""),
            "themes": game.get("themes", ""),
            "_version": game.get("patch_version", "") or game.get("original_title_version", ""),
            "game_drive": game.get("game_drive", ""),
            "scene_repack": game.get("scene_repack", ""),
            "player_perspective": game.get("player_perspective", ""),
            "developer": game.get("developer", ""),
            "publisher": game.get("publisher", ""),
            "original_title": game.get("original_title", ""),
        }
        for key, (row, value_label) in self._detail_field_rows.items():
            val = field_values.get(key, "")
            row.setVisible(bool(val))
            if val:
                value_label.setText(escape_html(str(val)))

        # --- Savegame locations (variable-length, rebuilt each time) ---
        save_locs = game.get("savegame_location") or game.get("savegame_locations") or []
        if isinstance(save_locs, str):
            save_locs = [s.strip() for s in save_locs.split("|") if s.strip()]

        while self.save_locs_content.count():
            item = self.save_locs_content.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.save_locs_section.setVisible(bool(save_locs))
        for loc in save_locs:
            try:
                href = QUrl.fromLocalFile(str(loc)).toString() if not str(loc).startswith(("http://", "https://")) else loc
            except Exception:
                href = ""
            loc_label = QLabel(f'📁 <a href="{href}" style="color:{config.SECONDARY_COLOR}; text-decoration:none;">{escape_html(str(loc))}</a>'
                                if href else f'📁 {escape_html(str(loc))}')
            loc_label.setTextFormat(Qt.RichText)
            loc_label.setOpenExternalLinks(True)
            loc_label.setWordWrap(True)
            loc_label.setStyleSheet(f"font-size: {config.DETAILS_METADATA_VALUE_FONT_SIZE}px; color: {config.PRIMARY_COLOR}; padding: 2px 0;")
            self.save_locs_content.addWidget(loc_label)

        # --- External links (unchanged logic) ---
        links = []
        for link_name, link_key in [("Steam","steam_link"), ("SteamDB","steamdb_link"), ("PCGamingWiki","pcgw_link"), ("IGDB","igdb_link")]:
            url = game.get(link_key)
            if url:
                full_url = url if url.startswith("http") else "https:" + url
                links.append(f'<a href="{full_url}" style="color:{config.SECONDARY_COLOR}; text-decoration:underline; margin-right:12px;">{link_name}</a>')
        trailers = game.get("trailers") or game.get("igdb_trailers") or ""
        if trailers:
            if isinstance(trailers, str):
                trailer_list = [p.strip() for p in re.split(r"[,\|;\n]+", trailers) if p.strip()]
            else:
                trailer_list = trailers[:config.MAX_TRAILERS]
            for i, t in enumerate(trailer_list[:config.MAX_TRAILERS]):
                full_t = t if t.startswith("http") else "https:" + t
                links.append(f'<a href="{full_t}" style="color:{config.WARNING_COLOR}; text-decoration:underline; margin-right:12px;">Trailer {i+1}</a>')
        elif game.get("trailer_webm"):
            links.append(f'<a href="{game["trailer_webm"]}" style="color:{config.WARNING_COLOR}; text-decoration:underline; margin-right:12px;">Trailer</a>')
        self.links_label.setText('<div style="padding:4px 0;">' + " ".join(links) + '</div>' if links else "<i>No external links</i>")

        # Image display (unchanged — ImageDisplayManager itself untouched)
        image_urls = []
        if game.get("cover_url"):
            image_urls.append(game["cover_url"])
        screens = game.get("screenshots") or []
        image_urls.extend(screens[:config.MAX_IMAGES_TO_DISPLAY])
        self.image_display.fetch_and_display_images(source_row, image_urls)

        # Trailer player — TrailerPlayerManager itself untouched, but
        # playback is deferred to when the Media section is actually
        # visible (see _media_show_slide / the Media toggle wrapper below).
        # Starting playback while the section is hidden meant the video
        # surface never got a real paint/show event to render onto, so it
        # stayed a black frame even after the user expanded the section.
        self._media_has_trailer = bool(trailer_url)
        self._media_trailer_url = trailer_url
        self._media_current_game = game

        # Unified nav: land on the trailer if there is one, otherwise the
        # first image — one prev/next pair walks through both from here.
        self._media_show_slide(0)

    # ----------------------------------------------------------------------
    # Search and filter
    # ----------------------------------------------------------------------
    def on_search_changed(self, text):
        self.proxy.setFilterFixedString(text or "")
        self.apply_filters()

    def _collect_unique_filter_values(self, game_key: str) -> list:
        values = set()
        for g in self.games:
            raw = g.get(game_key, "")
            parts = raw if isinstance(raw, list) else str(raw).split(",")
            for p in parts:
                p = (p or "").strip()
                if p:
                    values.add(p)
        return sorted(values, key=str.lower)

    def _refresh_filter_options(self):
        for attr, label, icon, game_key, col_name in self._filter_defs:
            getattr(self, attr).set_options(self._collect_unique_filter_values(game_key))

    def apply_filters(self):
        active_terms = []   # list of (column_index, [terms])
        for attr, label, icon, game_key, col_name in self._filter_defs:
            combo = getattr(self, attr)
            terms = [t.strip().lower() for t in (combo.currentText() or "").split(",") if t.strip()]
            if terms:
                active_terms.append((getattr(self, col_name), terms))

        if not active_terms:
            for r in range(self.proxy.rowCount()):
                self.table.setRowHidden(r, False)
            return
        for r in range(self.proxy.rowCount()):
            idx = self.proxy.index(r, 0)
            src = self.proxy.mapToSource(idx)
            show = True
            if src.isValid():
                row = src.row()
                for col, terms in active_terms:
                    val = (self.model.data(self.model.index(row, col)) or "").lower()
                    if not any(t in val for t in terms):
                        show = False
                        break
            else:
                show = False
            self.table.setRowHidden(r, not show)

    # ----------------------------------------------------------------------
    # Context menu and batch operations
    # ----------------------------------------------------------------------
    def open_context_menu(self, pos):
        menu = QMenu(self)
        rows = self._selected_source_rows()
        if rows:
            fav_action = QAction("⭐ Add to Favourite", self)
            fav_action.triggered.connect(self.toggle_favourite_selected)
            menu.addAction(fav_action)
            played_action = QAction("✓ Toggle Played Status", self)
            played_action.triggered.connect(self.toggle_played_selected)
            menu.addAction(played_action)
            menu.addSeparator()
            scrape_action = QAction("🔄 Scrape selected game(s)...", self)
            scrape_action.triggered.connect(self.scrape_selected_games)
            menu.addAction(scrape_action)
            recache_action = QAction("💾 Recache selected row(s)...", self)
            recache_action.triggered.connect(self.recache_selected_rows)
            menu.addAction(recache_action)
            sanitize_action = QAction("🧹 Sanitize selected row(s)...", self)
            sanitize_action.triggered.connect(self.sanitize_selected_rows)
            menu.addAction(sanitize_action)
            edit_action = QAction("✏️ Edit selected game...", self)
            edit_action.triggered.connect(self.edit_selected_game)
            menu.addAction(edit_action)
            multi_edit_action = QAction("📝 Multi-edit selected...", self)
            multi_edit_action.triggered.connect(self.multi_edit_selected)
            menu.addAction(multi_edit_action)
            menu.addSeparator()
            drive_action = QAction("💽 Set Game Drive for selected...", self)
            drive_action.triggered.connect(self.set_game_drive_selected)
            menu.addAction(drive_action)
            save_action = QAction("🗑️ Clear Save Location for selected", self)
            save_action.triggered.connect(self.clear_save_location_selected)
            menu.addAction(save_action)
            menu.addSeparator()
            delete_action = QAction("❌ Delete selected", self)
            delete_action.triggered.connect(self.delete_selected)
            menu.addAction(delete_action)
        else:
            menu.addAction("No selection", lambda: None)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def scrape_selected_games(self):
        rows = self._selected_source_rows()
        for row in rows:
            self.run_match_dialog_for_row(row)
        self.refresh_model()

    def run_match_dialog_for_row(self, row: int):
        if row < 0 or row >= len(self.games):
            return
        game = self.games[row]
        original_item = {
            "title": game.get("title", ""),
            "original_title": game.get("original_title", ""),
            "description": game.get("description", "")
        }
        try:
            candidates = scraping.find_candidates_for_title_igdb(
                original_item["title"] or original_item["original_title"],
                max_candidates=12
            )
        except Exception:
            candidates = []
        dlg = MatchDialog(original_item, candidates, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            result_data = dlg.result_dict or {}

            manual_title = result_data.get('title')
            if manual_title:
                game['title'] = manual_title

            if 'igdb_title' in result_data:
                game['igdb_title'] = result_data['igdb_title']
            if 'steam_title' in result_data:
                game['steam_title'] = result_data['steam_title']

            selected_igdb_id = result_data.get('igdb_id')
            selected_app_id = result_data.get('app_id')
            overwrite = result_data.get('overwrite', False)

            meta = scraping.scrape_igdb_then_steam(
                igdb_id=selected_igdb_id,
                title=manual_title or game.get('title', ''),
                auto_accept_score=92,
                steam_app_id=selected_app_id
            )

            if meta and "__candidates__" not in meta:
                merge_and_apply_metadata(
                    self.games, self.model, row, meta, self,
                    preserve_title=True
                )
                if game.get('title') != manual_title:
                    game['title'] = manual_title
                    self.model.blockSignals(True)
                    title_item = self.model.item(row, self.COL_TITLE)
                    if title_item:
                        title_text = manual_title
                        if game.get('played'):
                            title_text += " ✅"
                        if game.get('fav'):
                            title_text += " ♥"
                        title_item.setText(title_text)
                    self.model.blockSignals(False)
            else:
                self.refresh_model()

            self._mark_dirty()
            self.show_details_for_source_row(row)

    def edit_selected_game(self):
        rows = self._selected_source_rows()
        if not rows:
            QMessageBox.information(self, "Edit", "Select a game first.")
            return
        dlg = EditDialog(self.games[rows[0]], self)
        if dlg.exec_() == QDialog.Accepted:
            self.games[rows[0]].update(dlg.result())
            self.refresh_model()
            self._mark_dirty()
            self.status.setText("Game updated.")

    def multi_edit_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        dlg = MultiEditDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        changes = dlg.result()
        applied = 0
        for row in rows:
            game = self.games[row]
            changed = False
            for k, v in changes.items():
                if v is None:
                    continue
                if k == "played":
                    if game.get("played") != v:
                        game["played"] = v
                        changed = True
                else:
                    if game.get(k, "") != v:
                        game[k] = v
                        changed = True
            if changed:
                applied += 1
        if applied:
            self.refresh_model()
            self._mark_dirty()
            self.status.setText(f"Multi-edited {applied} rows.")

    def mark_played_selected(self, played: bool):
        rows = self._selected_source_rows()
        for row in rows:
            self.games[row]["played"] = played
            self.model.setData(self.model.index(row, self.COL_PLAYED), Qt.Checked if played else Qt.Unchecked, Qt.CheckStateRole)
        self.update_table_highlights()
        self.update_counters()
        self._mark_dirty()
        self.status.setText(f"Marked {len(rows)} rows as {'Played' if played else 'Unplayed'}.")

    def set_game_drive_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        drive = _get_drive_selection(self)
        if drive:
            for row in rows:
                self.games[row]["game_drive"] = drive
                index = self.model.index(row, self.COL_GAMEDRIVE)
                self.model.setData(index, drive)
            self._mark_dirty()
            self.status.setText(f"Set drive to '{drive}' for {len(rows)} rows.")

    def clear_save_location_selected(self):
        rows = self._selected_source_rows()
        for row in rows:
            self.games[row]["savegame_location"] = ""
            index = self.model.index(row, self.COL_SAVE_LOCATION)
            self.model.setData(index, "")
        self._mark_dirty()
        self.status.setText(f"Cleared save location for {len(rows)} rows.")

    def delete_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        if QMessageBox.question(self, "Delete", f"Delete {len(rows)} rows? Cannot undo.", QMessageBox.Yes|QMessageBox.No) != QMessageBox.Yes:
            return
        for row in sorted(rows, reverse=True):
            del self.games[row]
        self.refresh_model()
        self._mark_dirty()
        self.status.setText(f"Deleted {len(rows)} rows.")

    def update_table_highlights(self):
        self.recompute_duplicates()
        self.table.viewport().update()

    def toggle_favourite_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        for row in rows:
            game = self.games[row]
            current = game.get("fav", False)
            game["fav"] = not current
            check_state = Qt.Checked if not current else Qt.Unchecked
            self.model.setData(self.model.index(row, self.COL_FAV), check_state, Qt.CheckStateRole)
            self.model.blockSignals(True)
            title_item = self.model.item(row, self.COL_TITLE)
            if title_item:
                base = self.games[row].get("title", "")
                sym = []
                if self.games[row].get("played"):
                    sym.append("✅")
                if self.games[row].get("fav"):
                    sym.append("♥")
                new_text = base + (" " + " ".join(sym) if sym else "")
                title_item.setText(new_text)
            self.model.blockSignals(False)
        self.update_table_highlights()
        self.table.viewport().repaint()
        self._mark_dirty()
        self.status.setText(f"Toggled favourite for {len(rows)} rows.")
        if rows:
            self.show_details_for_source_row(rows[0])

    def toggle_played_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        for row in rows:
            game = self.games[row]
            current = game.get("played", False)
            game["played"] = not current
            check_state = Qt.Checked if not current else Qt.Unchecked
            self.model.setData(self.model.index(row, self.COL_PLAYED), check_state, Qt.CheckStateRole)
            self.model.blockSignals(True)
            title_item = self.model.item(row, self.COL_TITLE)
            if title_item:
                base = self.games[row].get("title", "")
                sym = []
                if self.games[row].get("played"):
                    sym.append("✅")
                if self.games[row].get("fav"):
                    sym.append("♥")
                new_text = base + (" " + " ".join(sym) if sym else "")
                title_item.setText(new_text)
            self.model.blockSignals(False)
        self.update_table_highlights()
        self.update_counters()
        self._mark_dirty()
        self.status.setText(f"Toggled played status for {len(rows)} rows.")
        if rows:
            self.show_details_for_source_row(rows[0])

    # ----------------------------------------------------------------------
    # Import/Export
    # ----------------------------------------------------------------------
    def _save_database_combined_dialog(self):
        start_dir = str(self._db_dir)
        path, filt = QFileDialog.getSaveFileName(self, "Save Database", os.path.join(start_dir, "games.json"),
                                                "JSON (*.json);;SQLite (*.sqlite *.db)")
        if not path:
            return
        if "." not in os.path.basename(path):
            if "JSON" in filt:
                path += ".json"
            else:
                path += ".sqlite"
        ext = os.path.splitext(path)[1].lower()
        try:
            if os.path.exists(path):
                self._backup_file(path)
            if ext == ".json":
                err = save_to_json(path, self.games)
            else:
                err = save_to_sqlite(path, self.games)
            if err:
                QMessageBox.critical(self, "Error", f"Save failed: {err}")
            else:
                self._current_save_path = path
                self._dirty = False
                self._auto_save_timer.stop()
                self.status.setText(f"Saved {len(self.games)} games to {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _load_database_combined_dialog(self):
        start_dir = str(self._db_dir)
        path, _ = QFileDialog.getOpenFileName(self, "Load Database", start_dir,
                                              "JSON (*.json);;SQLite (*.sqlite *.db)")
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            loaded, err = load_from_json(path)
        else:
            loaded, err = load_from_sqlite(path)
        if err:
            QMessageBox.critical(self, "Load failed", err)
            return
        if isinstance(loaded, list):
            self.games = loaded
            self.download_mgr = DownloadManager(self)
            self.scrape_coord = ScrapeCoordinator(self)
            self.clear_filters()
            self.refresh_model()
            self._current_save_path = path
            self._dirty = False
            self._auto_save_timer.stop()
            self.status.setText(f"Loaded {len(self.games)} games from {os.path.basename(path)}")
        else:
            QMessageBox.critical(self, "Invalid data", "Loaded data is not a list.")

    def _show_import_dialog(self):
        from import_dialog import ImportDialog
        dlg = ImportDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        full_games = dlg.get_imported_games_from_file()
        if full_games:
            before = len(self.games)
            self.games.extend(full_games)
            after = len(self.games)
            self.refresh_model()
            self._mark_dirty()
            self.status.setText(f"Imported {len(full_games)} full games from file; total: {before} → {after}")

        titles = dlg.get_imported_titles()
        if titles and not full_games:
            auto_sanitize = dlg.auto_sanitize_enabled()
            imported_games = []
            for raw_title in titles:
                game = {"original_title": raw_title}
                if auto_sanitize:
                    san = sanitize_original_title(raw_title)
                    game["original_title_base"] = san.get("base_title", "")
                    game["original_title_version"] = san.get("version", "")
                    game["scene_repack"] = san.get("repack", "")
                    game["original_notes"] = san.get("notes", "")
                    game["game_modes"] = ", ".join(san.get("modes", []))
                    game["title"] = san.get("base_title") or raw_title
                else:
                    game["title"] = raw_title
                    game["original_title"] = raw_title
                imported_games.append(game)

            before = len(self.games)
            self.games.extend(imported_games)
            after = len(self.games)
            self.refresh_model()
            self._mark_dirty()
            self.status.setText(f"Imported {len(imported_games)} titles; total: {before} → {after}")

    def export_to_pdf_dialog(self):
        from datetime import datetime
        start_dir = str(self._db_dir)
        default_name = f"games_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Export", os.path.join(start_dir, default_name),
                                              "PDF (*.pdf);;HTML (*.html)")
        if not path:
            return

        ordered_games = self._get_current_display_order()
        if not ordered_games:
            QMessageBox.information(self, "Export", "No games to export.")
            return

        columns = self._get_export_columns()
        description_lines = config.EXPORT_DESC_LINES

        if path.lower().endswith(".html"):
            err = export_games_to_html(path, ordered_games, title="Game Manager Export",
                                       open_after=True, description_lines=description_lines,
                                       columns=columns)
            if err:
                QMessageBox.critical(self, "Export error", err)
            else:
                QMessageBox.information(self, "Export", f"Exported HTML to {path}")
        else:
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            err = export_games_to_pdf(path, ordered_games, title="Game Manager Export",
                                      description_lines=description_lines, columns=columns)
            if err:
                QMessageBox.critical(self, "Export error", err)
            else:
                QMessageBox.information(self, "Export", f"Exported PDF to {path}")

    def _get_current_display_order(self) -> List[Dict]:
        ordered_games = []
        for proxy_row in range(self.proxy.rowCount()):
            if self.table.isRowHidden(proxy_row):
                continue
            src_index = self.proxy.mapToSource(self.proxy.index(proxy_row, 0))
            if src_index.isValid():
                row = src_index.row()
                if 0 <= row < len(self.games):
                    ordered_games.append(self.games[row])
        return ordered_games

    def _get_export_columns(self):
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(config.CONFIG_FILE, encoding='utf-8')

        canonical_keys = [
            "title", "app_id", "igdb_id", "patch_version", "release_date",
            "description", "game_modes", "genres", "themes", "user_rating",
            "player_perspective", "developer", "publisher", "game_drive",
            "scene_repack", "original_title", "resources", "links", "savegame_location"
        ]

        default_headers = {
            "title": "Title", "app_id": "Steam ID", "igdb_id": "IGDB ID",
            "patch_version": "Ver", "release_date": "Rel Date",
            "description": "Description", "game_modes": "Modes",
            "genres": "Genres", "themes": "Themes", "user_rating": "Rating",
            "player_perspective": "Perspective", "developer": "Developer",
            "publisher": "Publisher", "game_drive": "Drive",
            "scene_repack": "Scene/Repack", "original_title": "Original Title",
            "resources": "Resources", "links": "External Links",
            "savegame_location": "Savegame Locations"
        }
        default_widths = {
            "title": 10, "app_id": 5, "igdb_id": 5, "patch_version": 4,
            "release_date": 4, "description": 25, "game_modes": 6,
            "genres": 8, "themes": 5, "user_rating": 3, "player_perspective": 5,
            "developer": 5, "publisher": 5, "game_drive": 5, "scene_repack": 5,
            "original_title": 10, "resources": 10, "links": 5, "savegame_location": 5
        }

        if cfg.has_section("ExportColumns"):
            selected_str = cfg.get("ExportColumns", "selected", fallback="")
            selected_keys = [k.strip() for k in selected_str.split(",") if k.strip()]
        else:
            selected_keys = canonical_keys

        columns = []
        for key in canonical_keys:
            if key in selected_keys:
                header = cfg.get("ExportColumns", f"header_{key}", fallback=default_headers.get(key, key.replace("_", " ").title()))
                width = cfg.getint("ExportColumns", f"width_{key}", fallback=default_widths.get(key, 5))
                columns.append({"key": key, "header": header, "width": width})

        if not columns:
            columns = [{"key": k, "header": default_headers[k], "width": default_widths[k]} for k in canonical_keys]
        return columns

    def scan_drive_for_games(self):
        from drive_scanner import scan_drive
        scan_drive(self)

    def export_assets_to_folders(self):
        from drive_scanner import copy_assets_to_drive
        copy_assets_to_drive(self)

    # ----------------------------------------------------------------------
    # Menus
    # ----------------------------------------------------------------------
    def build_menus(self):
        menubar = self.menuBar()
        menubar.clear()

        file_menu = menubar.addMenu("📁 File")
        add_game_action = QAction("➕ Add New Game", self)
        add_game_action.setShortcut("Ctrl+N")
        add_game_action.triggered.connect(self._show_import_dialog)
        file_menu.addAction(add_game_action)
        file_menu.addSeparator()
        open_db_action = QAction("📂 Open Database", self)
        open_db_action.setShortcut("Ctrl+O")
        open_db_action.triggered.connect(self._load_database_combined_dialog)
        file_menu.addAction(open_db_action)
        save_db_action = QAction("💾 Save Database", self)
        save_db_action.setShortcut("Ctrl+S")
        save_db_action.triggered.connect(self._save_database_combined_dialog)
        file_menu.addAction(save_db_action)
        file_menu.addSeparator()
        export_action = QAction("📄 Export to PDF/HTML...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_to_pdf_dialog)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        exit_action = QAction("🚪 Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("✏️ Edit")
        sanitize_action = QAction("🧹 Sanitize Selected Rows", self)
        sanitize_action.setShortcut("Ctrl+Shift+S")
        sanitize_action.triggered.connect(self.sanitize_selected_rows)
        edit_menu.addAction(sanitize_action)
        recache_action = QAction("💾 Recache Selected Rows", self)
        recache_action.setShortcut("F7")
        recache_action.triggered.connect(self.recache_selected_rows)
        edit_menu.addAction(recache_action)
        scrape_action = QAction("🔄 Scrape Selected Game(s)", self)
        scrape_action.triggered.connect(self.scrape_selected_games)
        edit_menu.addAction(scrape_action)
        edit_game = QAction("✏️ Edit Selected Game", self)
        edit_game.setShortcut("Ctrl+Shift+E")
        edit_game.triggered.connect(self.edit_selected_game)
        edit_menu.addAction(edit_game)
        edit_menu.addSeparator()
        multi_edit = QAction("📝 Multi-Edit Selected", self)
        multi_edit.setShortcut("Ctrl+Shift+M")
        multi_edit.triggered.connect(self.multi_edit_selected)
        edit_menu.addAction(multi_edit)
        edit_menu.addSeparator()
        toggle_played = QAction("✓ Toggle Played Status", self)
        toggle_played.setShortcut("Ctrl+P")
        toggle_played.triggered.connect(self.toggle_played_selected)
        edit_menu.addAction(toggle_played)
        toggle_fav = QAction("⭐ Toggle Favourite", self)
        toggle_fav.setShortcut("Ctrl+F")
        toggle_fav.triggered.connect(self.toggle_favourite_selected)
        edit_menu.addAction(toggle_fav)
        edit_menu.addSeparator()
        set_drive = QAction("💽 Set Game Drive for Selected", self)
        set_drive.triggered.connect(self.set_game_drive_selected)
        edit_menu.addAction(set_drive)
        clear_save = QAction("🗑️ Clear Save Location for Selected", self)
        clear_save.triggered.connect(self.clear_save_location_selected)
        edit_menu.addAction(clear_save)
        edit_menu.addSeparator()
        delete_action = QAction("🗑 Delete Selected", self)
        delete_action.setShortcut("Del")
        delete_action.triggered.connect(self.delete_selected)
        edit_menu.addAction(delete_action)

        tools_menu = menubar.addMenu("🛠 Tools")

        scan_drive_action = QAction("🗂️ Scan Drive for New Games", self)
        scan_drive_action.triggered.connect(self.scan_drive_for_games)
        tools_menu.addAction(scan_drive_action)
        export_assets_action = QAction("📁 Export Assets to Game Folders", self)
        export_assets_action.triggered.connect(self.export_assets_to_folders)
        tools_menu.addAction(export_assets_action)

        tools_menu.addSeparator()
        scrape_action = QAction("🔄 Scrape Metadata", self)
        scrape_action.setShortcut("F5")
        scrape_action.triggered.connect(lambda: self.scrape_all(92))
        tools_menu.addAction(scrape_action)
        download_action = QAction("⬇ Download Resources", self)
        download_action.setShortcut("F6")
        download_action.triggered.connect(self.download_all_screenshots)
        tools_menu.addAction(download_action)

        tools_menu.addSeparator()
        sanitize_tool = QAction("🧹 Sanitize Titles", self)
        sanitize_tool.triggered.connect(self.sanitize_selected_rows)
        tools_menu.addAction(sanitize_tool)
        tools_menu.addSeparator()
        clean_cache_action = QAction("🧹 Clear Redundant Cache", self)
        clean_cache_action.triggered.connect(self.clear_redundant_cache)
        tools_menu.addAction(clean_cache_action)
        test_scrape = QAction("🔍 Test Scrape Selected", self)
        test_scrape.triggered.connect(self.test_scrape_single)
        tools_menu.addAction(test_scrape)
        tools_menu.addSeparator()
        settings_action = QAction("⚙️ Settings", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        view_menu = menubar.addMenu("👁 View")
        refresh_action = QAction("⟳ Refresh View", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_model)
        view_menu.addAction(refresh_action)
        view_menu.addSeparator()
        show_columns = view_menu.addMenu("📋 Show Columns")
        for col in range(self.model.columnCount()):
            name = self.model.headerData(col, Qt.Horizontal)
            if name:
                action = QAction(name, self)
                action.setCheckable(True)
                action.setChecked(not self.table.isColumnHidden(col))
                action.toggled.connect(lambda checked, c=col: self.table.setColumnHidden(c, not checked))
                show_columns.addAction(action)
        view_menu.addSeparator()
        show_all = QAction("👁 Show All Columns", self)
        show_all.triggered.connect(lambda: self._set_all_columns_visible(True))
        view_menu.addAction(show_all)
        hide_all = QAction("🙈 Hide All Columns (Except Title)", self)
        hide_all.triggered.connect(lambda: self._set_all_columns_visible(False))
        view_menu.addAction(hide_all)

        help_menu = menubar.addMenu("❓ Help")
        about_action = QAction("ℹ️ About Game Manager", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
        docs_action = QAction("📚 Documentation", self)
        docs_action.triggered.connect(self._open_documentation)
        help_menu.addAction(docs_action)

    def _set_all_columns_visible(self, visible):
        for col in range(self.model.columnCount()):
            if col != self.COL_TITLE:
                self.table.setColumnHidden(col, not visible)

    def _show_about_dialog(self):
        from about_dialog import show_about_dialog
        show_about_dialog(self)

    def _open_documentation(self):
        QDesktopServices.openUrl(QUrl("https://github.com/RakabAman/GameScrapper-Manager"))

    def test_scrape_single(self):
        rows = self._selected_source_rows()
        if not rows:
            QMessageBox.information(self, "Test", "Select a game first")
            return
        row = rows[0]
        game = self.games[row]
        title = game.get("title") or game.get("original_title") or ""
        try:
            meta = scraping.scrape_igdb_then_steam(None, title, auto_accept_score=92, fetch_pcgw_save=False) or {}
            if meta:
                merge_and_apply_metadata(self.games, self.model, row, meta, self)
                self._mark_dirty()
                self.status.setText(f"Test scrape applied to '{title}'")
            else:
                self.status.setText("No metadata found")
        except Exception as e:
            self.status.setText(f"Error: {e}")

    def _open_settings(self):
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec_():
            self
            
    # ----------------------------------------------------------------------
    # Cleanup, cancel and auto‑save
    # ----------------------------------------------------------------------
    
    def clear_redundant_cache(self):
        """Delete cache folders for games no longer in the list, and any empty folders."""
        from cache_utils import _game_cache_dir_for_game
        import config
        import shutil

        # Build set of expected cache folder names for current games
        expected_folders = set()
        for game in self.games:
            cache_dir = _game_cache_dir_for_game(game)
            expected_folders.add(cache_dir.name)  # e.g., "game_12345"

        deleted_folders = []
        total_size = 0

        # Scan cache directory for subfolders
        for item in config.CACHE_DIR.iterdir():
            if not item.is_dir():
                continue
            if item.name not in expected_folders:
                # Folder belongs to a game no longer in the list – delete it
                try:
                    # Calculate folder size
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    total_size += size
                    shutil.rmtree(item)
                    deleted_folders.append(item.name)
                    print(f"[CACHE CLEAN] Deleted folder: {item.name} ({size/1024/1024:.2f} MB)")
                except Exception as e:
                    print(f"Error deleting {item.name}: {e}")

        # Remove any empty folders inside expected game folders
        for game in self.games:
            cache_dir = _game_cache_dir_for_game(game)
            if cache_dir.exists() and not any(cache_dir.iterdir()):
                cache_dir.rmdir()
                print(f"[CACHE CLEAN] Removed empty folder: {cache_dir.name}")

        # Also clean empty root‑level folders (if any)
        for item in config.CACHE_DIR.iterdir():
            if item.is_dir() and not any(item.iterdir()):
                item.rmdir()
                print(f"[CACHE CLEAN] Removed empty root folder: {item.name}")

        size_mb = total_size / (1024 * 1024)
        QMessageBox.information(
            self,
            "Cache Cleaned",
            f"Deleted {len(deleted_folders)} orphaned game folders\nFreed space: {size_mb:.2f} MB"
        )
        self.status.setText(f"Cleaned {len(deleted_folders)} redundant cache folders ({size_mb:.2f} MB)")

        
    def force_cancel_operation(self):
        if self._cancel_current_scrape:
            return
        self._cancel_current_scrape = True
        self._cancel_batch = True
        if hasattr(self, 'scrape_coord'):
            self.scrape_coord.cancel()
        if hasattr(self, 'download_mgr'):
            self.download_mgr.cancel()
        self.scrape_btn.setEnabled(True)
        self.cancel_scrape_btn.setVisible(False)
        self.status.setText("Operation cancelled.")
        self.refresh_model()

    def _shutdown_workers(self):
        self._cancel_current_scrape = True
        self._cancel_batch = True
        QCoreApplication.processEvents()
        time.sleep(0.1)

    def closeEvent(self, event):
        if self._dirty and config.AUTO_SAVE:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._perform_auto_save()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            else:  # Cancel
                event.ignore()
                return
        self._shutdown_workers()
        event.accept()

    def _mark_dirty(self):
        if not config.AUTO_SAVE:
            return
        self._dirty = True
        self._auto_save_timer.start(config.AUTO_SAVE_INTERVAL * 1000)

    def _perform_auto_save(self):
        if not config.AUTO_SAVE or not self._dirty:
            return
        # ... rest unchanged
        save_path = self._current_save_path
        if not save_path:
            if config.DEFAULT_DATABASE:
                save_path = config.DEFAULT_DATABASE
            else:
                save_path = str(self._db_dir / "games.json")
        if not save_path:
            return
        try:
            # Create backup before overwriting
            if os.path.exists(save_path):
                self._backup_file(save_path)
            ext = os.path.splitext(save_path)[1].lower()
            if ext == ".json":
                err = save_to_json(save_path, self.games)
            elif ext in (".db", ".sqlite"):
                err = save_to_sqlite(save_path, self.games)
            else:
                err = save_to_json(save_path + ".json", self.games)
                save_path = save_path + ".json"
            if err:
                print(f"Auto‑save error: {err}")
            else:
                self._dirty = False
                self._current_save_path = save_path
                self.status.setText(f"Auto‑saved to {os.path.basename(save_path)}")
        except Exception as e:
            print(f"Auto‑save exception: {e}")

    def _load_database_from_path(self, path: str) -> bool:
        """Load database from given path (absolute or relative to BASE_DIR)."""
        if not os.path.isabs(path):
            path = os.path.join(config.BASE_DIR, path)
        if not os.path.exists(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            loaded, err = load_from_json(path)
        else:
            loaded, err = load_from_sqlite(path)
        if err:
            print(f"Error loading default database: {err}")
            return False
        if isinstance(loaded, list):
            self.games = loaded
            self.download_mgr = DownloadManager(self)
            self.scrape_coord = ScrapeCoordinator(self)
            self.clear_filters()                     # <-- ADD THIS
            self.refresh_model()
            self._current_save_path = path
            self._dirty = False
            self._auto_save_timer.stop()
            self.status.setText(f"Loaded {len(self.games)} games from {os.path.basename(path)}")
            return True
        return False

    def mark_dirty(self):
        """Public method for helpers to mark unsaved changes."""
        self._mark_dirty()

    def _backup_file(self, file_path: str) -> None:
        """Create a backup of the file if it exists."""
        if not os.path.exists(file_path):
            return
        backup_path = file_path + ".backup"
        try:
            import shutil
            shutil.copy2(file_path, backup_path)
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Failed to create backup: {e}")

if __name__ == "__main__":
    # ----- REQUIRED for QtWebEngine (trailer player) -----
    from PyQt5.QtCore import QCoreApplication, Qt
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    # ------------------------------------------------------

    # DPI scaling (works well with modern Windows/macOS)
    #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Game Manager")
    app.setOrganizationName("GameScraper")
    app.setStyle('Fusion')



    # After:
    base_font_size = 9   # or read from config? We'll use a fixed base.
    scaled_size = int(base_font_size * config.GLOBAL_FONT_SCALE)
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(scaled_size)
    app.setFont(font)

    # Apply icon and palette from config
    config.apply_application_icon(app)
    config.apply_application_palette(app)

    window = GameManager()
    window.show()
    sys.exit(app.exec_())