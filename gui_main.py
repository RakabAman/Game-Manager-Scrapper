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

# Import helper modules
import config
from workers import ImageFetchWorker, ScrapeBatchWorker
from dialogs import MultiEditDialog, EditDialog
from widgets import AspectRatioWidget, ClickableImageViewer, ClickableVideoWidget, HighlightDelegate
from cache_utils import _to_relative, _game_cache_dir_for_game, _save_bytes_to_game_cache, scan_cache_directory_for_game
from download_helper import DownloadManager
from scrape_helper import ScrapeCoordinator
from metadata_helper import merge_and_apply_metadata
from sanitize_helper import sanitize_selected_rows
from image_display import ImageDisplayManager
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

        # Step 2: Create helpers that don't need UI widgets (only model/games)
        self.download_mgr = DownloadManager(self)
        self.scrape_coord = ScrapeCoordinator(self)

        # Step 3: Create UI panels that don't depend on image/trailer helpers
        self._setup_top_panel()
        self._setup_buttons()
        self._setup_details_panel()

        # Step 4: Create image viewer widgets (but not the helper yet)
        self._setup_image_viewer()   # creates self.viewer, self.prev_btn, etc.

        # Step 5: Now create image display helper (needs self.viewer)
        self.image_display = ImageDisplayManager(self)

        # Step 6: Connect image navigation buttons to the helper
        self.prev_btn.clicked.connect(self.image_display.prev_image)
        self.next_btn.clicked.connect(self.image_display.next_image)
        self.open_image_btn.clicked.connect(self.image_display.open_current_image_url)

        # Step 7: Create trailer player widgets and helper
        self._setup_trailer_player()   # creates self.video_widget, etc.
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
        
    
    # ----------------------------------------------------------------------
    # UI Setup Methods
    # ----------------------------------------------------------------------
    def _setup_data_model(self):
        self.model = QStandardItemModel(0, 32)
        self.model.setHorizontalHeaderLabels([
                    "Title", "Ver🔧", "Drive💾", "Steam🆔", "▶", "♥",
                    "Genres🎭", "Modes🎮", "Release📅", "Themes🎯", "Dev🏢",
                    "Pub📢", "Scene/Repack🏷️", "Perspective👁️", "Original Title📝",
                    "IGDB🆔", "Screenshots🖼️", "Trailer🎬 (micro)", "SteamDB🔗",
                    "PCGamingWiki🔗", "Steam🔗", "Description", "IGDB Trailers🎥",
                    "Cover URL", "Extra microtrailers🎬", "Original Title Base",
                    "Original Notes🏷️", "Image Cache Paths", "Savegame Locations",
                    "Microtrailers Cache Paths", "User Rating⭐", "IGDB CoverArt"
                ])

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


    def _setup_top_panel(self):
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(15)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_label = QLabel("🔍")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.on_search_changed)
        self.search.setMinimumWidth(200)
        self.search.setFixedHeight(config.TEXT_BOX_HEIGHT)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search)
        search_layout.addStretch()

        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(10)

        genre_container = QWidget()
        genre_layout = QHBoxLayout(genre_container)
        genre_layout.setContentsMargins(0, 0, 0, 0)
        genre_label = QLabel("Genre:")
        genre_label.setStyleSheet("font-weight: 600; min-width: 40px;")
        self.genre_filter = QLineEdit()
        self.genre_filter.setPlaceholderText("Genre...")
        self.genre_filter.textChanged.connect(self.apply_filters)
        self.genre_filter.setFixedHeight(config.TEXT_BOX_HEIGHT)
        self.genre_filter.setMinimumWidth(90)
        genre_layout.addWidget(genre_label)
        genre_layout.addWidget(self.genre_filter)

        drive_container = QWidget()
        drive_layout = QHBoxLayout(drive_container)
        drive_layout.setContentsMargins(0, 0, 0, 0)
        drive_label = QLabel("Drive:")
        drive_label.setStyleSheet("font-weight: 600; min-width: 40px;")
        self.game_drive_filter = QLineEdit()
        self.game_drive_filter.setPlaceholderText("Drive...")
        self.game_drive_filter.textChanged.connect(self.apply_filters)
        self.game_drive_filter.setFixedHeight(config.TEXT_BOX_HEIGHT)
        self.game_drive_filter.setMinimumWidth(90)
        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.game_drive_filter)

        filter_layout.addWidget(genre_container)
        filter_layout.addWidget(drive_container)
        filter_layout.addStretch()

        left_layout.addWidget(search_widget)
        left_layout.addWidget(filter_widget)

        self.search.setToolTip("Search all columns (case‑insensitive)")
        self.genre_filter.setToolTip("Filter rows by genre (partial match)")
        self.game_drive_filter.setToolTip("Filter rows by game drive path")

        stats_container = QWidget()
        stats_container.setMaximumHeight(70)
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)

        # In gui_main.py, inside _setup_top_panel, replace the stats_config and card creation loop

        # First, store the card widgets themselves
        self.stats_cards = {}       # value labels
        self.stats_card_widgets = {} # QWidget cards

        stats_config = [
            {"id": "total", "title": "Total", "color_source": None},          # neutral
            {"id": "played", "title": "Played", "color_source": "played"},
            {"id": "favourites", "title": "Fav", "color_source": "favourite"},
            {"id": "remaining", "title": "Remaining", "color_source": "unplayed"},
            {"id": "cached", "title": "Cached", "color_source": None},
            {"id": "duplicates", "title": "Duplicates", "color_source": "duplicate"},
            {"id": "unscraped", "title": "Unscraped", "color_source": None},
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
            card.setMinimumWidth(75)
            card.setMaximumWidth(85)
            # We'll set the stylesheet later after we know the color
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 3, 5, 3)
            card_layout.setSpacing(1)
            title_label = QLabel(stat["title"])
            title_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #7f8c8d;")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setToolTip(card_tooltips.get(stat["id"], ""))
            value_label = QLabel("0")
            value_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #2c3e50;")
            value_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            stats_layout.addWidget(card)
            self.stats_cards[stat["id"]] = value_label
            self.stats_card_widgets[stat["id"]] = card
            card.mousePressEvent = lambda event, cid=stat["id"]: self._on_stat_card_clicked(cid)

        # Now set the initial border colors
        self._refresh_stat_card_colors()
            
      

        top_layout.addWidget(left_container, 1)
        top_layout.addWidget(stats_container)
        self.top_container = top_container

    def _on_stat_card_clicked(self, card_id: str):
        self.search.clear()
        self.genre_filter.clear()
        self.game_drive_filter.clear()
        self.proxy.setFilterFixedString("")
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


    # Add this method to the GameManager class (e.g., after _apply_ui_colors)

    def _refresh_stat_card_colors(self):
        """Update stat card left border and background tint using current config colors."""
        
        # Map stat id to the config color constant or custom color
        color_map = {
            "played": config.PLAYED_COLOR,
            "favourites": config.FAVORITE_COLOR,
            "remaining": config.UNPLAYED_COLOR,
            "duplicates": config.DUPLICATE_COLOR,
            "total": "#3498db",          # blue
            "cached": "#f39c12",         # orange
            "unscraped": "#e67e22",      # darker orange
        }

        for stat_id, card in self.stats_card_widgets.items():
            # Use mapped color, fallback to blue if missing
            color = color_map.get(stat_id, "#3498db")
            
            # Convert hex to RGB for rgba background (optional, keep white background)
            # We're keeping white background with colored left border as before.
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: white;
                    border-radius: 3px;
                    border-left: 4px solid {color};
                    padding: 1px;
                }}
            """)

    def _setup_buttons(self):
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)

        self.open_db_btn = QPushButton("📂 Open DB")
        self.open_db_btn.clicked.connect(self._load_database_combined_dialog)
        self.save_db_btn = QPushButton("💾 Save DB")
        self.save_db_btn.clicked.connect(self._save_database_combined_dialog)
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #bdc3c7;")
        self.import_btn = QPushButton("📥 Add Titles")
        self.import_btn.clicked.connect(self._show_import_dialog)
        self.export_btn = QPushButton("📤 Export")
        self.export_btn.clicked.connect(self.export_to_pdf_dialog)
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #bdc3c7;")
        self.scrape_btn = QPushButton("🗲 Scrape Metadata")
        self.scrape_btn.clicked.connect(lambda: self.scrape_all(92))
        self.scrape_btn.setProperty("success", True)
        self.download_all_btn = QPushButton("⬇ Download Resources")
        self.download_all_btn.clicked.connect(self.download_all_screenshots)
        self.cancel_scrape_btn = QPushButton("✕ Cancel")
        self.cancel_scrape_btn.setVisible(False)
        self.cancel_scrape_btn.setProperty("urgent", True)

        button_layout.addWidget(self.open_db_btn)
        button_layout.addWidget(self.save_db_btn)
        button_layout.addWidget(sep1)
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(sep2)
        button_layout.addWidget(self.scrape_btn)
        button_layout.addWidget(self.download_all_btn)
        button_layout.addWidget(self.cancel_scrape_btn)
        button_layout.addStretch()
        self.open_db_btn.setToolTip("Open an existing database (JSON or SQLite)")
        self.save_db_btn.setToolTip("Save current database to file (JSON or SQLite)")
        self.import_btn.setToolTip("Import games from CSV, Excel, TXT, or paste titles")
        self.export_btn.setToolTip("Export visible games to PDF or HTML")
        self.scrape_btn.setToolTip("Scrape metadata (IGDB + Steam) for games missing IDs")
        self.download_all_btn.setToolTip("Download screenshots and microtrailers for all games")
        self.cancel_scrape_btn.setToolTip("Cancel the current scrape or download operation")        
        
        self.button_container = button_container

    def _setup_details_panel(self):
        details_container = QWidget()
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(5)

        links_group = QGroupBox("External Links")
        links_group.setMaximumHeight(80)
        links_layout = QVBoxLayout(links_group)
        self.links_label = QLabel("")
        self.links_label.setTextFormat(Qt.RichText)
        self.links_label.setOpenExternalLinks(True)
        self.links_label.setWordWrap(True)
        links_layout.addWidget(self.links_label)

        game_info_group = QGroupBox("Game Information")
        
        game_info_layout = QVBoxLayout(game_info_group)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(config.TEXT_BOX_HEIGHT)
        self.details.setStyleSheet("QTextEdit { margin: 0; padding: 0; }")
        game_info_layout.addWidget(self.details)

        details_layout.addWidget(links_group)
        details_layout.addWidget(game_info_group, 1)
        self.details_container = details_container

    def _setup_image_viewer(self):
        self.image_box = QGroupBox("Screenshots")
        image_layout = QVBoxLayout(self.image_box)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self.viewer = ClickableImageViewer(self)
        viewer_container = QWidget()
        viewer_container_layout = QVBoxLayout(viewer_container)
        viewer_container_layout.setContentsMargins(0, 0, 0, 0)
        self._viewer_container = AspectRatioWidget(self.viewer, parent=viewer_container)
        self._viewer_container.setMinimumSize(100, 56)
        self._viewer_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        viewer_container_layout.addWidget(self._viewer_container)

        self.nav_container = QWidget(viewer_container)
        self.nav_container.setStyleSheet("background: transparent;")
        self.nav_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.prev_btn = QPushButton("◀", self.nav_container)
        self.prev_btn.setFixedSize(40, 40)
        self.prev_btn.setEnabled(False)
        btn_style = """
        QPushButton {
            background-color: rgba(0,0,0,180);
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 16px;
        }
        QPushButton:hover { background-color: rgba(0,0,0,220); }
        QPushButton:disabled { background-color: rgba(0,0,0,80); color: #ccc; }
        """
        self.prev_btn.setStyleSheet(btn_style)
        self.open_image_btn = QPushButton("🌐", self.nav_container)
        self.open_image_btn.setFixedSize(40, 40)
        self.open_image_btn.setEnabled(False)
        self.open_image_btn.setStyleSheet(btn_style)
        self.next_btn = QPushButton("▶", self.nav_container)
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet(btn_style)
        self.image_counter = QLabel("No images", self.nav_container)
        self.image_counter.setAlignment(Qt.AlignCenter)
        self.image_counter.setStyleSheet("background-color: rgba(0,0,0,160); color: white; padding: 4px 8px; border-radius: 3px;")

        image_layout.addWidget(viewer_container, 1)
        self._viewer_container_widget = viewer_container
        viewer_container.resizeEvent = self._on_viewer_container_resize
        QTimer.singleShot(100, lambda: self.nav_container.raise_())

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
            self.open_image_btn.move(center_x, button_y)
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
        self.trailer_container = QGroupBox("Trailer Player")
        trailer_layout = QVBoxLayout(self.trailer_container)
        trailer_layout.setContentsMargins(2, 5, 2, 2)
        media_container = QWidget()
        media_layout = QVBoxLayout(media_container)
        media_layout.setAlignment(Qt.AlignCenter)

        self.video_widget = ClickableVideoWidget()
        self.video_widget.setMinimumSize(100, 56)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.hide()

        self.trailer_gif_label = ClickableImageViewer()
        self.trailer_gif_label.setMinimumSize(100, 56)
        self.trailer_gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.trailer_gif_label.hide()

        media_layout.addWidget(self.video_widget)
        media_layout.addWidget(self.trailer_gif_label)
        trailer_layout.addWidget(media_container, 1)

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setMuted(True)

    def _setup_main_layout(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5,5,5,5)
        main_layout.addWidget(self.top_container)

        splitter = QSplitter(Qt.Horizontal)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)
        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setWidget(self.table)
        table_scroll.setFrameShape(QFrame.NoFrame)
        left_layout.addWidget(table_scroll, 1)
        left_layout.addWidget(self.button_container)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_tabs = QTabWidget()
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setWidget(self.details_container)
        right_tabs.addTab(details_scroll, "📋 Details")
        media_tab = QWidget()
        media_layout = QVBoxLayout(media_tab)
        self.media_splitter = QSplitter(Qt.Vertical)
        self.media_splitter.addWidget(self.image_box)
        self.media_splitter.addWidget(self.trailer_container)
        self.media_splitter.setSizes([500,500])
        media_layout.addWidget(self.media_splitter)
        right_tabs.addTab(media_tab, "🎬 Media")
        right_layout.addWidget(right_tabs)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        divider = config.DIVIDER_PERCENTAGE / 100.0
        splitter.setSizes([int(self.width() * divider), int(self.width() * (1 - divider))])
        main_layout.addWidget(splitter, 1)

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
            # --- update this row's title cell ---
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
            # ------------------------------------
            selected_rows = self._selected_source_rows()
            if row in selected_rows:
                self.show_details_for_source_row(row)
            return

        if col == self.COL_FAV:
            game["fav"] = (item.checkState() == Qt.Checked)
            self._mark_dirty()
            # --- update this row's title cell ---
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
            # ------------------------------------
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
                            title_text = f"{title_text} ✅"   # tick after title
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

                    # ... rest of the existing elif branches unchanged ...

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
        self.apply_filters()
        self.table.viewport().update()
        self.update_counters()
        
    
    def recompute_duplicates(self):
        title_counts = {}
        steam_counts = {}
        igdb_counts = {}
        for game in self.games:
            # Sanitized title duplicates
            title = (game.get("title") or "").strip()
            if title:
                norm = title.lower()
                title_counts[norm] = title_counts.get(norm, 0) + 1
            # Steam ID duplicates
            sid = str(game.get("app_id") or "").strip()
            if sid:
                steam_counts[sid.lower()] = steam_counts.get(sid.lower(), 0) + 1
            # IGDB ID duplicates
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

    def _apply_config_settings(self):
        if config.AUTO_SAVE:
            self._auto_save_timer.setInterval(config.AUTO_SAVE_INTERVAL * 1000)
        else:
            self._auto_save_timer.stop()
        # Update splitter
        divider = config.DIVIDER_PERCENTAGE / 100.0
        self.media_splitter.setSizes([int(self.width() * divider), int(self.width() * (1 - divider))])
        # Reapply UI colours (palette)
        self._apply_ui_colors()
        # Reapply the full stylesheet (it uses the updated colour variables)
        self.setStyleSheet(config.APP_STYLESHEET)

        # Force the table delegate to reload colors from current config
        self.table.setItemDelegate(HighlightDelegate(self))

        self.setStyleSheet(config.APP_STYLESHEET)
        self.table.setItemDelegate(HighlightDelegate(self))
        self.table.viewport().update()
        self.table.update()

        # Refresh stat card colors (may have changed in settings)
        self._refresh_stat_card_colors()

        self.status.setText("Settings applied.")

        # Also force the viewport to repaint immediately
        self.table.viewport().update()
        self.table.update()

        self.status.setText("Settings applied.")

        # Refresh current details panel to apply new font sizes
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            src = self.proxy.mapToSource(selected_rows[0])
            if src.isValid():
                self.show_details_for_source_row(src.row())
                
    def _apply_ui_colors(self):
        """Reapply the application palette using current config colors."""
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(config.LIGHT_BG))
        palette.setColor(QPalette.WindowText, QColor(config.PRIMARY_COLOR))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f5f7fa"))
        palette.setColor(QPalette.Text, QColor("#2c3e50"))
        palette.setColor(QPalette.Button, QColor(config.SECONDARY_COLOR))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(config.SELECTED_COLOR))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)
    
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

    def _get_thumbnail_data_uri(self, game: dict) -> str:
        """Return a data URI for any suitable image in the game cache, or empty string."""
        try:
            if not config.SHOW_THUMBNAILS_IN_DETAILS:
                return ""

            cache_dir = _game_cache_dir_for_game(game)
            if not cache_dir or not cache_dir.exists():
                return ""

            # 1. Prefer cover art by URL hash
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

            # 2. Fallback: first valid image file >20KB
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
            # Log silently (or print for debugging)
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

        # Title with configurable font size
        title_font = config.DETAILS_TITLE_FONT_SIZE
        title_text = escape_html(game.get("title", "Untitled"))
        #check_html = ''
        #if game.get("played", False):
        #    check_html = f'<span style="color:#27ae60; font-size:{title_font}px; margin-right:8px;">✓</span>'
        
        #star_html = f'<span style="color:#e74c3c; font-size:{title_font}px; margin-left:8px;">♥</span>' if game.get("fav", False) else ''
        

        # Rating stars
        rating_html = ""
        user_rating = game.get("user_rating", "")
        if user_rating:
            try:
                stars = min(5, float(user_rating)/20)
                full = int(stars)
                half = 1 if stars - full >= 0.5 else 0
                empty = 5 - full - half
                stars_str = "★"*full + "½"*half + "☆"*empty
                rating_html = f'<div style="margin-top:4px;"><span style="color:#f39c12; font-size:16px;">{stars_str}</span> <span style="color:#555;">({user_rating}/100)</span></div>'
            except:
                rating_html = f'<div><b>User Rating:</b> {user_rating}/100</div>'

        # Description – font size inherited from outer div
        desc = game.get("description", "").strip()
        desc_html = f'<div style="margin:8px 0; max-height:150px; overflow-y:auto;">{escape_html(desc) or "<i>No description</i>"}</div>'

        # Field groups (IGDB ID moved after Steam ID)
        basic_fields = [
            ("📅 Release date", game.get("release_date", "")),
            ("🎭 Genres", game.get("genres", "")),
            ("🎮 Game modes", game.get("game_modes", "")),
            ("🎯 Themes", game.get("themes", "")),
        ]
        technical_fields = [
            ("🔧 Version", game.get("patch_version", "") or game.get("original_title_version", "")),
            ("💾 Game Drive", game.get("game_drive", "")),
            ("🆔 Steam ID", game.get("app_id", "")),
            ("🔢 IGDB ID", game.get("igdb_id", "")),
            ("🎨 Scene/Repack", game.get("scene_repack", "")),
            ("👁 Perspective", game.get("player_perspective", "")),
            ("🏢 Developer", game.get("developer", "")),
            ("📢 Publisher", game.get("publisher", "")),
            ("📝 Original title", game.get("original_title", "")),
        ]
        # Save locations
        save_locs = game.get("savegame_location") or game.get("savegame_locations") or []
        if isinstance(save_locs, str):
            save_locs = [s.strip() for s in save_locs.split("|") if s.strip()]

        def build_table(fields, title):
            if not any(val for _, val in fields):
                return ""
            rows = []
            for label, val in fields:
                if not val:
                    continue
                cell = f'<span>{escape_html(str(val))}</span>'
                rows.append(f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 8px; width:130px; font-weight:600; color:#2c3e50;">{label}</td><td style="padding:6px 8px;">{cell}</td></tr>')
            if not rows:
                return ""
            return f'<h4 style="margin:12px 0 6px 0; color:#2980b9;">{title}</h4><table style="width:100%; border-collapse:collapse;">{"".join(rows)}</table>'

        # Use description font size for entire container (except title)
        desc_font = config.DETAILS_DESC_FONT_SIZE
         # === CLEAN VERTICAL LAYOUT: Thumbnail above title ===
        thumbnail_uri = self._get_thumbnail_data_uri(game)
        
        # Build title with symbols and rating
        # === ZERO GAP – AGGRESSIVE ===
        thumbnail_uri = self._get_thumbnail_data_uri(game)
        
        # Build title (same as before)
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
                if rating_num == int(rating_num):
                    rating_display = f"{int(rating_num)}"
                else:
                    rating_display = f"{rating_num:.1f}"
                rating_inline = f' <span style="color:#f39c12;">{stars_str}</span> <span style="color:#555;">({rating_display})</span>'
            except:
                rating_inline = " <span style='color:#f39c12;'>☆</span> <span style='color:#555;'>(No rating)</span>"
        
        full_title = f"{title_text}{symbols_html}{rating_inline}"
        
        thumb_html = ''
        if thumbnail_uri:
            thumb_html = f'<img src="{thumbnail_uri}" style="width:48px; height:48px; border-radius:6px; object-fit:cover; margin:0; padding:0; border:0; display:block;">'
        
        desc = game.get("description", "").strip()
        desc_html = f'<div style="margin:0 0 6px 0; max-height:150px; overflow-y:auto;">{escape_html(desc) or "<i>No description</i>"}</div>'
        
        combined = f'''
        <div style="margin:0; padding:0; font-family: 'Segoe UI', Arial, sans-serif; font-size:{desc_font}px; line-height:1.3;">
            <div style="margin:0; padding:0; background:white; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1); padding:12px;">
                <div style="display:flex; flex-direction:column; align-items:center; gap:5; margin:0; padding:10; 
                            border-bottom:2px solid #3498db; padding-bottom:4px; margin-bottom:6px;">
                    {thumb_html}
                    <div style="margin:10; padding:5; font-size:{title_font}px; font-weight:bold; color:#2c3e50; text-align:center; line-height:1.2;">
                        {full_title}
                    </div>
                </div>
                {desc_html}
                {build_table(basic_fields, "📌 Basic Info")}
                {build_table(technical_fields, "⚙️ Technical Details")}
        '''


        if save_locs:
            locs_html = '<h4 style="margin:12px 0 6px 0; color:#2980b9;">💾 Savegame Locations</h4><div style="background:#f8f9fa; border-radius:6px; padding:8px;">'
            for loc in save_locs:
                try:
                    href = QUrl.fromLocalFile(str(loc)).toString() if not loc.startswith(("http://","https://")) else loc
                    locs_html += f'<div style="margin:4px 0;">📁 <a href="{href}" style="color:#3498db; text-decoration:none;">{escape_html(str(loc))}</a></div>'
                except:
                    locs_html += f'<div>📁 {escape_html(str(loc))}</div>'
            locs_html += '</div>'
            combined += locs_html

        combined += '''
            </div>
        </div>
        '''
        self.details.clear()
        
        self.details.setHtml(combined)

        # External links – simple underlined links (no highlights/buttons)
        links = []
        for link_name, link_key in [("Steam","steam_link"), ("SteamDB","steamdb_link"), ("PCGamingWiki","pcgw_link"), ("IGDB","igdb_link")]:
            url = game.get(link_key)
            if url:
                full_url = url if url.startswith("http") else "https:" + url
                links.append(f'<a href="{full_url}" style="color:#2980b9; text-decoration:underline; margin-right:12px;">{link_name}</a>')
        trailers = game.get("trailers") or game.get("igdb_trailers") or ""
        if trailers:
            if isinstance(trailers, str):
                trailer_list = [p.strip() for p in re.split(r"[,\|;\n]+", trailers) if p.strip()]
            else:
                trailer_list = trailers[:config.MAX_TRAILERS]
            for i, t in enumerate(trailer_list[:config.MAX_TRAILERS]):
                full_t = t if t.startswith("http") else "https:" + t
                links.append(f'<a href="{full_t}" style="color:#e67e22; text-decoration:underline; margin-right:12px;">Trailer {i+1}</a>')
        elif game.get("trailer_webm"):
            links.append(f'<a href="{game["trailer_webm"]}" style="color:#e67e22; text-decoration:underline; margin-right:12px;">Trailer</a>')
        self.links_label.setText('<div style="padding:4px 0;">' + " ".join(links) + '</div>' if links else "<i>No external links</i>")

        # Image display (unchanged)
        image_urls = []
        if game.get("cover_url"):
            image_urls.append(game["cover_url"])
        screens = game.get("screenshots") or []
        image_urls.extend(screens[:config.MAX_IMAGES_TO_DISPLAY])
        self.image_display.fetch_and_display_images(source_row, image_urls)

        # Trailer player (unchanged)
        trailer_url = game.get("trailer_webm") or ""
        if not trailer_url:
            micros = game.get("microtrailers") or []
            if micros and isinstance(micros, list) and len(micros):
                trailer_url = micros[0]
        if trailer_url:
            self.trailer_container.show()
            self.trailer_player.play_trailer_media(trailer_url)
        else:
            self.trailer_container.hide()
            
    # ----------------------------------------------------------------------
    # Search and filter
    # ----------------------------------------------------------------------
    def on_search_changed(self, text):
        self.proxy.setFilterFixedString(text or "")
        self.apply_filters()

    def apply_filters(self):
        genre_filter = (self.genre_filter.text() or "").lower().strip()
        drive_filter = (self.game_drive_filter.text() or "").lower().strip()
        if not genre_filter and not drive_filter:
            for r in range(self.proxy.rowCount()):
                self.table.setRowHidden(r, False)
            return
        for r in range(self.proxy.rowCount()):
            idx = self.proxy.index(r, 0)
            src = self.proxy.mapToSource(idx)
            show = True
            if src.isValid():
                row = src.row()
                genre = (self.model.data(self.model.index(row, self.COL_GENRES)) or "").lower()
                drive = (self.model.data(self.model.index(row, self.COL_GAMEDRIVE)) or "").lower()
                if genre_filter and genre_filter not in genre:
                    show = False
                if drive_filter and drive_filter not in drive:
                    show = False
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
            
            # 1. Manual title (always becomes the final game title)
            manual_title = result_data.get('title')
            if manual_title:
                game['title'] = manual_title
            
            # 2. Store candidate original names (if any)
            if 'igdb_title' in result_data:
                game['igdb_title'] = result_data['igdb_title']
            if 'steam_title' in result_data:
                game['steam_title'] = result_data['steam_title']
            
            # 3. IDs for scraping
            selected_igdb_id = result_data.get('igdb_id')
            selected_app_id = result_data.get('app_id')
            overwrite = result_data.get('overwrite', False)
            
            # 4. Fetch metadata (use manual title for searches if IDs missing)
            meta = scraping.scrape_igdb_then_steam(
                igdb_id=selected_igdb_id,
                title=manual_title or game.get('title', ''),
                auto_accept_score=92,
                steam_app_id=selected_app_id
            )
            
            # 5. Merge metadata but preserve the manual title
            if meta and "__candidates__" not in meta:
                merge_and_apply_metadata(
                    self.games, self.model, row, meta, self,
                    preserve_title=True   # <-- prevents title overwrite
                )
                # Double‑check that manual title is still there (safety)
                if game.get('title') != manual_title:
                    game['title'] = manual_title
                    # Update the model's title column
                    self.model.blockSignals(True)
                    title_item = self.model.item(row, self.COL_TITLE)
                    if title_item:
                        # Re‑apply played/favourite symbols
                        title_text = manual_title
                        if game.get('played'):
                            title_text += " ✅"
                        if game.get('fav'):
                            title_text += " ♥"
                        title_item.setText(title_text)
                    self.model.blockSignals(False)
            else:
                # No metadata – still need to refresh model to show manual title
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
            # --- update this row's title cell ---
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
            # ------------------------------------
        self.update_table_highlights()
        # Force immediate repaint of the table view
        self.table.viewport().repaint()
        self._mark_dirty()
        self.status.setText(f"Toggled favourite for {len(rows)} rows.")
        # Refresh details panel for the first selected row (to show star)
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
            # --- update this row's title cell ---
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
            # ------------------------------------
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

        # 1) Full games from CSV/Excel (if any)
        full_games = dlg.get_imported_games_from_file()
        if full_games:
            before = len(self.games)
            self.games.extend(full_games)
            after = len(self.games)
            self.refresh_model()
            self._mark_dirty()
            self.status.setText(f"Imported {len(full_games)} full games from file; total: {before} → {after}")
            # If there were also manual titles, process them separately below
            # But note: the dialog currently clears the text edit after loading a file,
            # so manual titles would be overwritten. That's acceptable.

        # 2) Manual titles from text edit (if any and not already processed via file)
        titles = dlg.get_imported_titles()
        if titles and not full_games:   # Only if no file was loaded, or you want to combine?
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

        # Get games in current display order (respects sorting/filtering)
        ordered_games = self._get_current_display_order()
        if not ordered_games:
            QMessageBox.information(self, "Export", "No games to export.")
            return

        # Get dynamic column definitions from settings
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
        """Return games in the order they appear in the table (after sorting/filtering)."""
        ordered_games = []
        for proxy_row in range(self.proxy.rowCount()):
            # Skip rows that are hidden by genre/drive filters
            if self.table.isRowHidden(proxy_row):
                continue
            src_index = self.proxy.mapToSource(self.proxy.index(proxy_row, 0))
            if src_index.isValid():
                row = src_index.row()
                if 0 <= row < len(self.games):
                    ordered_games.append(self.games[row])
        return ordered_games

    # Add this method to the GameManager class (e.g., after _get_current_display_order)

    def _get_export_columns(self):
        """Return a list of columns selected by the user, in canonical order, using saved headers/widths."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(config.CONFIG_FILE, encoding='utf-8')

        # Canonical order of columns (do not change)
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

        # Get selected keys from config
        if cfg.has_section("ExportColumns"):
            selected_str = cfg.get("ExportColumns", "selected", fallback="")
            selected_keys = [k.strip() for k in selected_str.split(",") if k.strip()]
        else:
            selected_keys = canonical_keys  # fallback to all

        columns = []
        for key in canonical_keys:
            if key in selected_keys:
                header = cfg.get("ExportColumns", f"header_{key}", fallback=default_headers.get(key, key.replace("_", " ").title()))
                width = cfg.getint("ExportColumns", f"width_{key}", fallback=default_widths.get(key, 5))
                columns.append({"key": key, "header": header, "width": width})

        # If no columns selected (or empty), fall back to all
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
            # reload_config() is already called inside the dialog
            # Now apply the new settings to this instance
            self._apply_config_settings()

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
    app = QApplication(sys.argv)
    app.setApplicationName("Game Manager")
    app.setOrganizationName("GameScraper")
    app.setStyle('Fusion')

    # Set application icon (taskbar)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_path, 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(config.LIGHT_BG))
    palette.setColor(QPalette.WindowText, QColor(config.PRIMARY_COLOR))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f5f7fa"))
    palette.setColor(QPalette.Text, QColor("#2c3e50"))
    palette.setColor(QPalette.Button, QColor(config.SECONDARY_COLOR))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.Highlight, QColor(config.SELECTED_COLOR))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    window = GameManager()
    window.show()
    sys.exit(app.exec_())