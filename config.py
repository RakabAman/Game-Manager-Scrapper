# config.py
import os
import sys
import configparser
import json
from pathlib import Path

import colorsys

def desaturate_color(hex_color: str, percent: float = 20) -> str:
    """
    Desaturate a hex color by a given percentage (0-100).
    Returns a new hex string.
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return hex_color
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    s = max(0.0, min(1.0, s * (1 - percent/100.0)))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    r, g, b = int(r*255), int(g*255), int(b*255)
    return f"#{r:02x}{g:02x}{b:02x}"
    
_PRINTED = False

# ----------------------------------------------------------------------
# Base directory detection
# ----------------------------------------------------------------------
def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent

BASE_DIR = get_base_dir()
CONFIG_FILE = BASE_DIR / "config.ini"

# ----------------------------------------------------------------------
# Default configuration values – synchronised with user's config.ini
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "General": {
        "cache_min_kb": "10",
        "cache_max_kb": "5120",
        "divider_percentage": "55",
        "default_database": "",
        "auto_save": "true",
        "auto_save_interval_seconds": "300",
        "auto_save_path": "",
        "auto_cache": "false",                 # changed to match config.ini
        "auto_sanitize": "true",
        "show_console": "true",                # changed to match config.ini
        "show_thumbnails_in_details": "false", # changed to match config.ini
    },
    "Scraping": {
        "auto_accept_score": "92",
        "fetch_pcgw_save": "false",
        "chunk_size": "50",
        "stall_timeout": "20",
        "max_concurrent_scrapes": "1",
    },
    "Download": {
        "max_images_to_download": "5",
        "max_images_to_display": "5",
        "max_microtrailers": "1",
        "max_trailers": "3",
        "debug_images": "false",
        "video_loop_enabled": "true",
        "max_concurrent_downloads": "1",
    },
    "UI": {
        "primary_color": "#2c3e50",
        "secondary_color": "#3498db",
        "accent_color": "#e74c3c",
        "success_color": "#27ae60",
        "warning_color": "#f39c12",
        "light_bg": "#f5f7fa",
        "dark_bg": "#34495e",
        "border_color": "#bdc3c7",
        "hover_color": "#ecf0f1",
        "selected_color": "#d6eaf8",
        "duplicate_color": "#ff4545",        # updated
        "played_color": "#20ff41",           # updated
        "unplayed_color": "#bef4ff",         # updated
        "favorite_color": "#f01eff",         # updated
        "details_title_font_size": "22",
        "details_desc_font_size": "14",
        "text_box_height": "30",
        "highlight_desaturate_percent": "90", # updated
    },
    "Cache": {
        "cache_dir_override": "",
    },
    "Sanitize": {
        "repack_list": "FitGirl Repack,DODI Repacks,GOG,CODEX,RELOADED,SKIDROW,CPY,PLAZA,Razor1911,FLT,SiMPLEX,PROPHET,HOODLUM,KaOs Krew,TinyRepacks,M4ckD0ge,qoob,JIT,GoldBerg,EMPRESS,INSANE,DOGE,ANOMALY",
        "edition_tokens": "deluxe,edition,ultimate,bundle,pack,premium,remastered,remake,complete,goty,director's cut,anniversary,super digital,evolved,classified archives,bonus ost,bonus",
        "emulator_tokens": "rpcs3,ryujinx,yuzu,cemu,dolphin,pcsx2,switch,ps3,wiiu,ps4,emulator,emu",
        "mode_keywords": '{"Multiplayer":["multiplayer","multi-player","mp","online"],"CO-OP":["coop","co-op","co op","cooperative"],"Singleplayer":["singleplayer","single-player","sp"]}',
    },
    "Export": {
        "description_lines": "4",
        "export_thumbnails": "false",
        "export_thumbnail_width": "32",
        "export_thumbnail_height": "32",
        "col_title": "15",
        "col_steam": "5",
        "col_igdb": "5",
        "col_genre": "8",
        "col_theme": "6",
        "col_desc": "25",
        "col_mode": "5",
        "col_drive": "5",
        "col_original": "18",
        "col_resources": "8",
        "pdf_page_size": "A3 Landscape",
    },
    "ExportColumns": {
        "selected": "title,app_id,igdb_id,patch_version,release_date,description,game_modes,genres,themes,user_rating,player_perspective,developer,publisher,game_drive,scene_repack,original_title,resources,links,savegame_location",
        "width_title": "10",
        "width_app_id": "5",
        "width_igdb_id": "5",
        "width_patch_version": "4",
        "width_release_date": "4",
        "width_description": "25",
        "width_game_modes": "6",
        "width_genres": "8",
        "width_themes": "5",
        "width_user_rating": "3",
        "width_player_perspective": "5",
        "width_developer": "5",
        "width_publisher": "5",
        "width_game_drive": "5",
        "width_scene_repack": "5",
        "width_original_title": "10",
        "width_resources": "10",
        "width_links": "5",
        "width_savegame_location": "5",
        "header_title": "Title",
        "header_app_id": "Steam ID",
        "header_igdb_id": "IGDB ID",
        "header_patch_version": "Ver",
        "header_release_date": "Rel Date",
        "header_description": "Description",
        "header_game_modes": "Modes",
        "header_genres": "Genres",
        "header_themes": "Themes",
        "header_user_rating": "Rating",
        "header_player_perspective": "Perspective",
        "header_developer": "Developer",
        "header_publisher": "Publisher",
        "header_game_drive": "Drive",
        "header_scene_repack": "Scene/Repack",
        "header_original_title": "Original Title",
        "header_resources": "Resources",
        "header_links": "External Links",
        "header_savegame_location": "Savegame Locations",
        "links_steam": "true",
        "links_igdb": "true",
        "links_pcgw": "true",
        "links_steamdb": "true",
    },
    "Table": {
        "column_order": "0,1,2,3,15,4,5,6,7,8,9,10,11,12,13,14,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30",
        "column_widths": "200,66,87,61,57,35,32,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,100,80",
    },
    "DriveScanner": {
        "drive_tokens": "Game,Game_Drive,game drive,drive",
        "drive_number_pattern": "(\\d+)$",
    },
    "AssetExport": {
        "artbox_name": "artbox.jpg",
        "trailer_name": "trailer",
    },
    "API": {
        "steam_search_api": "https://store.steampowered.com/api/storesearch/?term={q}&cc=US&l=en",
        "steam_store_app_url": "https://store.steampowered.com/app/{appid}",
        "steamdb_app_url": "https://steamdb.info/app/{appid}",
        "pcgw_search_template": "https://www.pcgamingwiki.com/w/index.php?search={q}",
        "igdb_url_template": "https://www.igdb.com/games/{slug}?utm_source=SteamDB",
        "http_timeout": "8.0",
        "http_retries": "2",
        "sleep_between_requests": "0.15",
        "igdb_image_base_url": "https://images.igdb.com/igdb/image/upload",
        "igdb_screenshot_size": "t_720p",
        "igdb_cover_size": "t_cover_big",
        "igdb_client_id": "",
        "igdb_client_secret": "",
        "igdb_access_token": "",
    },
}

# ----------------------------------------------------------------------
# Ensure config file exists, load it
# ----------------------------------------------------------------------
def _create_default_config():
    config = configparser.ConfigParser()
    for section, options in DEFAULT_CONFIG.items():
        config[section] = options
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)
    if not _PRINTED:
        print(f"[CONFIG] Created default config file: {CONFIG_FILE}")

def _load_config():
    config = configparser.ConfigParser()
    if not CONFIG_FILE.exists():
        _create_default_config()
    config.read(CONFIG_FILE, encoding='utf-8')
    
    # Merge with defaults
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, default_value in options.items():
            if not config.has_option(section, key):
                config.set(section, key, default_value)
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)
    
    return config

_CONFIG = _load_config()

# ----------------------------------------------------------------------
# Expose constants as module-level variables
# ----------------------------------------------------------------------

# General
CACHE_MIN_KB = _CONFIG.getint("General", "cache_min_kb")
CACHE_MAX_KB = _CONFIG.getint("General", "cache_max_kb")
DIVIDER_PERCENTAGE = _CONFIG.getint("General", "divider_percentage")
DEFAULT_DATABASE = _CONFIG.get("General", "default_database").strip()
AUTO_SAVE = _CONFIG.getboolean("General", "auto_save")
AUTO_SAVE_INTERVAL = _CONFIG.getint("General", "auto_save_interval_seconds")
AUTO_SAVE_PATH = _CONFIG.get("General", "auto_save_path").strip()
AUTO_CACHE = _CONFIG.getboolean("General", "auto_cache")
AUTO_SANITIZE = _CONFIG.getboolean("General", "auto_sanitize")
SHOW_CONSOLE = _CONFIG.getboolean("General", "show_console", fallback=False)
SHOW_THUMBNAILS_IN_DETAILS = _CONFIG.getboolean("General", "show_thumbnails_in_details", fallback=True)

# Scraping
AUTO_ACCEPT_SCORE = _CONFIG.getint("Scraping", "auto_accept_score")
FETCH_PCGW_SAVE = _CONFIG.getboolean("Scraping", "fetch_pcgw_save")
CHUNK_SIZE = _CONFIG.getint("Scraping", "chunk_size")
STALL_TIMEOUT = _CONFIG.getint("Scraping", "stall_timeout")
MAX_CONCURRENT_SCRAPES = _CONFIG.getint("Scraping", "max_concurrent_scrapes")

# Download
MAX_IMAGES_TO_DOWNLOAD = _CONFIG.getint("Download", "max_images_to_download")
MAX_IMAGES_TO_DISPLAY = _CONFIG.getint("Download", "max_images_to_display")
MAX_MICROTRAILERS = _CONFIG.getint("Download", "max_microtrailers")
MAX_TRAILERS = _CONFIG.getint("Download", "max_trailers")
DEBUG_IMAGES = _CONFIG.getboolean("Download", "debug_images")
VIDEO_LOOP_ENABLED = _CONFIG.getboolean("Download", "video_loop_enabled")
MAX_CONCURRENT_DOWNLOADS = _CONFIG.getint("Download", "max_concurrent_downloads")

# UI colors
PRIMARY_COLOR = _CONFIG.get("UI", "primary_color")
SECONDARY_COLOR = _CONFIG.get("UI", "secondary_color")
ACCENT_COLOR = _CONFIG.get("UI", "accent_color")
SUCCESS_COLOR = _CONFIG.get("UI", "success_color")
WARNING_COLOR = _CONFIG.get("UI", "warning_color")
LIGHT_BG = _CONFIG.get("UI", "light_bg")
DARK_BG = _CONFIG.get("UI", "dark_bg")
BORDER_COLOR = _CONFIG.get("UI", "border_color")
HOVER_COLOR = _CONFIG.get("UI", "hover_color")
SELECTED_COLOR = _CONFIG.get("UI", "selected_color")
DUPLICATE_COLOR = _CONFIG.get("UI", "duplicate_color")
PLAYED_COLOR = _CONFIG.get("UI", "played_color")
UNPLAYED_COLOR = _CONFIG.get("UI", "unplayed_color")
FAVORITE_COLOR = _CONFIG.get("UI", "favorite_color")
DETAILS_TITLE_FONT_SIZE = _CONFIG.getint("UI", "details_title_font_size")
DETAILS_DESC_FONT_SIZE = _CONFIG.getint("UI", "details_desc_font_size")
TEXT_BOX_HEIGHT = _CONFIG.getint("UI", "text_box_height")
HIGHLIGHT_DESATURATE_PERCENT = _CONFIG.getint("UI", "highlight_desaturate_percent", fallback=20)

# Sanitize lists
REPACK_LIST = [x.strip() for x in _CONFIG.get("Sanitize", "repack_list").split(",") if x.strip()]
EDITION_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "edition_tokens").split(",") if x.strip()]
EMULATOR_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "emulator_tokens").split(",") if x.strip()]
MODE_KEYWORDS = json.loads(_CONFIG.get("Sanitize", "mode_keywords"))

# Export
EXPORT_DESC_LINES = _CONFIG.getint("Export", "description_lines")
EXPORT_THUMBNAILS = _CONFIG.getboolean("Export", "export_thumbnails", fallback=False)
EXPORT_THUMBNAIL_WIDTH = _CONFIG.getint("Export", "export_thumbnail_width", fallback=32)
EXPORT_THUMBNAIL_HEIGHT = _CONFIG.getint("Export", "export_thumbnail_height", fallback=32)
EXPORT_COL_TITLE = _CONFIG.getint("Export", "col_title")
EXPORT_COL_STEAM = _CONFIG.getint("Export", "col_steam")
EXPORT_COL_IGDB = _CONFIG.getint("Export", "col_igdb")
EXPORT_COL_GENRE = _CONFIG.getint("Export", "col_genre")
EXPORT_COL_THEME = _CONFIG.getint("Export", "col_theme")
EXPORT_COL_DESC = _CONFIG.getint("Export", "col_desc")
EXPORT_COL_MODE = _CONFIG.getint("Export", "col_mode")
EXPORT_COL_DRIVE = _CONFIG.getint("Export", "col_drive")
EXPORT_COL_ORIGINAL = _CONFIG.getint("Export", "col_original")
EXPORT_COL_RESOURCES = _CONFIG.getint("Export", "col_resources")
EXPORT_PDF_PAGE_SIZE = _CONFIG.get("Export", "pdf_page_size")

# DriveScanner
DRIVE_TOKENS = [x.strip() for x in _CONFIG.get("DriveScanner", "drive_tokens").split(",") if x.strip()]
DRIVE_NUMBER_PATTERN = _CONFIG.get("DriveScanner", "drive_number_pattern")

# AssetExport
ARTBOX_NAME = _CONFIG.get("AssetExport", "artbox_name")
TRAILER_NAME = _CONFIG.get("AssetExport", "trailer_name")

# API
STEAM_SEARCH_API = _CONFIG.get("API", "steam_search_api")
STEAM_STORE_APP_URL = _CONFIG.get("API", "steam_store_app_url")
STEAMDB_APP_URL = _CONFIG.get("API", "steamdb_app_url")
PCGW_SEARCH_TEMPLATE = _CONFIG.get("API", "pcgw_search_template")
IGDB_URL_TEMPLATE = _CONFIG.get("API", "igdb_url_template")
HTTP_TIMEOUT = _CONFIG.getfloat("API", "http_timeout")
HTTP_RETRIES = _CONFIG.getint("API", "http_retries")
SLEEP_BETWEEN_REQUESTS = _CONFIG.getfloat("API", "sleep_between_requests")
IGDB_IMAGE_BASE_URL = _CONFIG.get("API", "igdb_image_base_url")
IGDB_SCREENSHOT_SIZE = _CONFIG.get("API", "igdb_screenshot_size")
IGDB_COVER_SIZE = _CONFIG.get("API", "igdb_cover_size")

# IGDB credentials – environment variables override config; empty config values fall back to hardcoded defaults
_IGDB_CLIENT_ID_FALLBACK = "3y74unpwlpblo3nwnx44a9fpm7aug7"
_IGDB_CLIENT_SECRET_FALLBACK = "t3wrmknntq1ix10wsz761o1uhxxmx0"
_IGDB_ACCESS_TOKEN_FALLBACK = "yqox9e79jt463xt44dyt85525gwkg2"

# Read from config (may be empty)
_igdb_client_id = _CONFIG.get("API", "igdb_client_id").strip()
_igdb_client_secret = _CONFIG.get("API", "igdb_client_secret").strip()
_igdb_access_token = _CONFIG.get("API", "igdb_access_token").strip()

# Use environment variables first, then config, then fallback
IGDB_CLIENT_ID = os.environ.get("IGDB_CLIENT_ID", _igdb_client_id or _IGDB_CLIENT_ID_FALLBACK)
IGDB_CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET", _igdb_client_secret or _IGDB_CLIENT_SECRET_FALLBACK)
IGDB_ACCESS_TOKEN = os.environ.get("IGDB_ACCESS_TOKEN", _igdb_access_token or _IGDB_ACCESS_TOKEN_FALLBACK)

# Cache directory
CACHE_DIR_OVERRIDE = _CONFIG.get("Cache", "cache_dir_override").strip()
if CACHE_DIR_OVERRIDE:
    CACHE_DIR = Path(CACHE_DIR_OVERRIDE)
else:
    CACHE_DIR = BASE_DIR / "cache"
SCRIPT_DIR = CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Application Stylesheet (built using loaded colors)
# ----------------------------------------------------------------------
def _get_stylesheet():
    return f"""
QMainWindow {{
    background-color: {LIGHT_BG};
}}

QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}}

/* ========== TABLE STYLES ========== */
QTableView {{
    background-color: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    gridline-color: {BORDER_COLOR};
    selection-background-color: {SELECTED_COLOR};
    selection-color: black;
    alternate-background-color: #f9f9f9;
}}

/* Padding inside table cells (content spacing) */
QTableView::item {{
    padding: 4px;
    border-bottom: 1px solid #f0f0f0;
}}

QTableView::item:selected {{
    background-color: {SELECTED_COLOR};
    color: black;
}}

QHeaderView::section {{
    background-color: {PRIMARY_COLOR};
    color: white;
    padding: 6px;
    border: 1px solid {DARK_BG};
    font-weight: bold;
    font-size: 11px;
}}

/* ========== BUTTON STYLES ========== */
QPushButton {{
    background-color: {SECONDARY_COLOR};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 24px;
}}

QPushButton:hover {{ background-color: #2980b9; }}
QPushButton:pressed {{ background-color: {PRIMARY_COLOR}; }}
QPushButton:disabled {{
    background-color: #95a5a6;
    color: #7f8c8d;
}}

QPushButton[urgent="true"] {{ background-color: {ACCENT_COLOR}; }}
QPushButton[urgent="true"]:hover {{ background-color: #c0392b; }}
QPushButton[success="true"] {{ background-color: {SUCCESS_COLOR}; }}
QPushButton[success="true"]:hover {{ background-color: #229954; }}

/* ========== EDITABLE TEXT FIELDS ========== */
/* General padding for line edits (search box, filters, settings) */
QLineEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;          /* vertical 4px, horizontal 8px – comfortable for typing */
    background-color: white;
    selection-background-color: {SELECTED_COLOR};
}}

QLineEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 3px 7px;          /* compensate for the thicker border */
}}

QLineEdit[error="true"] {{
    border: 2px solid {ACCENT_COLOR};
}}

/* Text edits (description, multi‑line fields) */
QTextEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px;              /* uniform inner spacing */
    background-color: white;
}}

QTextEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 5px;
}}

/* ========== GROUP BOX ========== */
QGroupBox {{
    font-weight: bold;
    border: 2px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: white;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 8px 0 8px;
    color: {PRIMARY_COLOR};
}}

/* ========== TABS ========== */
QTabWidget::pane {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    background-color: white;
}}

QTabBar::tab {{
    background-color: #ecf0f1;
    border: 1px solid {BORDER_COLOR};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 12px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: white;
    border-bottom: 2px solid {SECONDARY_COLOR};
    font-weight: bold;
}}

QTabBar::tab:hover {{ background-color: {HOVER_COLOR}; }}

/* ========== SPLITTER ========== */
QSplitter::handle {{
    background-color: {BORDER_COLOR};
    width: 4px;
    height: 4px;
}}
QSplitter::handle:hover {{ background-color: {SECONDARY_COLOR}; }}

/* ========== SCROLL AREA & SCROLLBARS ========== */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    border: none;
    background-color: #f0f0f0;
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: #c0c0c0;
    border-radius: 6px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background-color: #a0a0a0; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
}}

/* ========== PROGRESS BAR ========== */
QProgressBar {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    text-align: center;
    background-color: white;
}}
QProgressBar::chunk {{
    background-color: {SUCCESS_COLOR};
    border-radius: 3px;
}}

/* ========== STATUS BAR ========== */
QStatusBar {{
    background-color: {PRIMARY_COLOR};
    color: white;
    border-top: 1px solid {DARK_BG};
}}
QStatusBar QLabel {{
    color: white;
    padding: 0 8px;
    border-right: 1px solid rgba(255, 255, 255, 0.2);
}}

/* ========== MENU ========== */
QMenuBar {{
    background-color: {PRIMARY_COLOR};
    color: white;
    border-bottom: 1px solid {DARK_BG};
}}
QMenuBar::item {{
    background-color: transparent;
    padding: 4px 10px;
}}
QMenuBar::item:selected {{
    background-color: {SECONDARY_COLOR};
    border-radius: 2px;
}}
QMenu {{
    background-color: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    color: {PRIMARY_COLOR};
}}
QMenu::item {{
    padding: 6px 24px 6px 20px;
    color: {PRIMARY_COLOR};
}}
QMenu::item:selected {{
    background-color: {SELECTED_COLOR};
    color: {PRIMARY_COLOR};
}}
QMenu::separator {{
    height: 1px;
    background-color: {BORDER_COLOR};
    margin: 4px 0;
}}

/* ========== DIALOGS ========== */
QDialog {{
    background-color: {LIGHT_BG};
}}
QDialogButtonBox {{
    background-color: transparent;
}}

/* ========== LABELS WITH SPECIAL ROLES ========== */
QLabel[title="true"] {{
    font-size: 14px;
    font-weight: bold;
    color: {PRIMARY_COLOR};
    padding: 4px 0;
}}
QLabel[subtitle="true"] {{
    font-size: 12px;
    font-weight: 600;
    color: {DARK_BG};
    padding: 2px 0;
}}

/* ========== FRAMES ========== */
QFrame[separator="true"] {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 1px;
}}
QFrame[panel="true"] {{
    background-color: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 8px;
}}
"""

APP_STYLESHEET = _get_stylesheet()

# ----------------------------------------------------------------------
# Utility function to reload config at runtime
# ----------------------------------------------------------------------
def reload_config():
    """Reload configuration from disk and update module variables."""
    global _CONFIG, STALL_TIMEOUT, CHUNK_SIZE, CACHE_MIN_KB, CACHE_MAX_KB
    global DIVIDER_PERCENTAGE, DEFAULT_DATABASE, AUTO_SAVE, AUTO_SAVE_INTERVAL, AUTO_SAVE_PATH
    global AUTO_CACHE, AUTO_SANITIZE, SHOW_CONSOLE, SHOW_THUMBNAILS_IN_DETAILS
    global AUTO_ACCEPT_SCORE, FETCH_PCGW_SAVE, MAX_CONCURRENT_SCRAPES
    global MAX_IMAGES_TO_DOWNLOAD, MAX_IMAGES_TO_DISPLAY, MAX_MICROTRAILERS, MAX_TRAILERS
    global DEBUG_IMAGES, VIDEO_LOOP_ENABLED, MAX_CONCURRENT_DOWNLOADS
    global PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR, SUCCESS_COLOR, WARNING_COLOR
    global LIGHT_BG, DARK_BG, BORDER_COLOR, HOVER_COLOR, SELECTED_COLOR
    global DUPLICATE_COLOR, PLAYED_COLOR, UNPLAYED_COLOR, FAVORITE_COLOR
    global REPACK_LIST, EDITION_TOKENS, EMULATOR_TOKENS, MODE_KEYWORDS
    global EXPORT_DESC_LINES, EXPORT_COL_TITLE, EXPORT_COL_STEAM, EXPORT_COL_IGDB
    global EXPORT_THUMBNAILS, EXPORT_THUMBNAIL_WIDTH, EXPORT_THUMBNAIL_HEIGHT
    global EXPORT_COL_GENRE, EXPORT_COL_THEME, EXPORT_COL_DESC, EXPORT_COL_MODE
    global EXPORT_COL_DRIVE, EXPORT_COL_ORIGINAL, EXPORT_COL_RESOURCES, EXPORT_PDF_PAGE_SIZE
    global DRIVE_TOKENS, DRIVE_NUMBER_PATTERN, ARTBOX_NAME, TRAILER_NAME
    global STEAM_SEARCH_API, STEAM_STORE_APP_URL, STEAMDB_APP_URL, PCGW_SEARCH_TEMPLATE
    global IGDB_URL_TEMPLATE, HTTP_TIMEOUT, HTTP_RETRIES, SLEEP_BETWEEN_REQUESTS
    global IGDB_IMAGE_BASE_URL, IGDB_SCREENSHOT_SIZE, IGDB_COVER_SIZE
    global IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, IGDB_ACCESS_TOKEN
    global CACHE_DIR, SCRIPT_DIR, APP_STYLESHEET
    global DETAILS_TITLE_FONT_SIZE, DETAILS_DESC_FONT_SIZE, TEXT_BOX_HEIGHT
    global HIGHLIGHT_DESATURATE_PERCENT
    
    _CONFIG = _load_config()
    
    # General
    CACHE_MIN_KB = _CONFIG.getint("General", "cache_min_kb")
    CACHE_MAX_KB = _CONFIG.getint("General", "cache_max_kb")
    DIVIDER_PERCENTAGE = _CONFIG.getint("General", "divider_percentage")
    DEFAULT_DATABASE = _CONFIG.get("General", "default_database").strip()
    AUTO_SAVE = _CONFIG.getboolean("General", "auto_save")
    AUTO_SAVE_INTERVAL = _CONFIG.getint("General", "auto_save_interval_seconds")
    AUTO_SAVE_PATH = _CONFIG.get("General", "auto_save_path").strip()
    AUTO_CACHE = _CONFIG.getboolean("General", "auto_cache")
    AUTO_SANITIZE = _CONFIG.getboolean("General", "auto_sanitize")
    SHOW_CONSOLE = _CONFIG.getboolean("General", "show_console", fallback=False)
    SHOW_THUMBNAILS_IN_DETAILS = _CONFIG.getboolean("General", "show_thumbnails_in_details", fallback=True)
    
    # Scraping
    AUTO_ACCEPT_SCORE = _CONFIG.getint("Scraping", "auto_accept_score")
    FETCH_PCGW_SAVE = _CONFIG.getboolean("Scraping", "fetch_pcgw_save")
    CHUNK_SIZE = _CONFIG.getint("Scraping", "chunk_size")
    STALL_TIMEOUT = _CONFIG.getint("Scraping", "stall_timeout")
    MAX_CONCURRENT_SCRAPES = _CONFIG.getint("Scraping", "max_concurrent_scrapes")

    # Download
    MAX_IMAGES_TO_DOWNLOAD = _CONFIG.getint("Download", "max_images_to_download")
    MAX_IMAGES_TO_DISPLAY = _CONFIG.getint("Download", "max_images_to_display")
    MAX_MICROTRAILERS = _CONFIG.getint("Download", "max_microtrailers")
    MAX_TRAILERS = _CONFIG.getint("Download", "max_trailers")
    DEBUG_IMAGES = _CONFIG.getboolean("Download", "debug_images")
    VIDEO_LOOP_ENABLED = _CONFIG.getboolean("Download", "video_loop_enabled")
    MAX_CONCURRENT_DOWNLOADS = _CONFIG.getint("Download", "max_concurrent_downloads")

    # UI
    PRIMARY_COLOR = _CONFIG.get("UI", "primary_color")
    SECONDARY_COLOR = _CONFIG.get("UI", "secondary_color")
    ACCENT_COLOR = _CONFIG.get("UI", "accent_color")
    SUCCESS_COLOR = _CONFIG.get("UI", "success_color")
    WARNING_COLOR = _CONFIG.get("UI", "warning_color")
    LIGHT_BG = _CONFIG.get("UI", "light_bg")
    DARK_BG = _CONFIG.get("UI", "dark_bg")
    BORDER_COLOR = _CONFIG.get("UI", "border_color")
    HOVER_COLOR = _CONFIG.get("UI", "hover_color")
    SELECTED_COLOR = _CONFIG.get("UI", "selected_color")
    DUPLICATE_COLOR = _CONFIG.get("UI", "duplicate_color")
    PLAYED_COLOR = _CONFIG.get("UI", "played_color")
    UNPLAYED_COLOR = _CONFIG.get("UI", "unplayed_color")
    FAVORITE_COLOR = _CONFIG.get("UI", "favorite_color")
    DETAILS_TITLE_FONT_SIZE = _CONFIG.getint("UI", "details_title_font_size")
    DETAILS_DESC_FONT_SIZE = _CONFIG.getint("UI", "details_desc_font_size")
    TEXT_BOX_HEIGHT = _CONFIG.getint("UI", "text_box_height")
    HIGHLIGHT_DESATURATE_PERCENT = _CONFIG.getint("UI", "highlight_desaturate_percent", fallback=20)

    # Sanitize
    REPACK_LIST = [x.strip() for x in _CONFIG.get("Sanitize", "repack_list").split(",") if x.strip()]
    EDITION_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "edition_tokens").split(",") if x.strip()]
    EMULATOR_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "emulator_tokens").split(",") if x.strip()]
    MODE_KEYWORDS = json.loads(_CONFIG.get("Sanitize", "mode_keywords"))

    # Export
    EXPORT_DESC_LINES = _CONFIG.getint("Export", "description_lines")
    EXPORT_THUMBNAILS = _CONFIG.getboolean("Export", "export_thumbnails", fallback=False)
    EXPORT_THUMBNAIL_WIDTH = _CONFIG.getint("Export", "export_thumbnail_width", fallback=32)
    EXPORT_THUMBNAIL_HEIGHT = _CONFIG.getint("Export", "export_thumbnail_height", fallback=32)
    EXPORT_COL_TITLE = _CONFIG.getint("Export", "col_title")
    EXPORT_COL_STEAM = _CONFIG.getint("Export", "col_steam")
    EXPORT_COL_IGDB = _CONFIG.getint("Export", "col_igdb")
    EXPORT_COL_GENRE = _CONFIG.getint("Export", "col_genre")
    EXPORT_COL_THEME = _CONFIG.getint("Export", "col_theme")
    EXPORT_COL_DESC = _CONFIG.getint("Export", "col_desc")
    EXPORT_COL_MODE = _CONFIG.getint("Export", "col_mode")
    EXPORT_COL_DRIVE = _CONFIG.getint("Export", "col_drive")
    EXPORT_COL_ORIGINAL = _CONFIG.getint("Export", "col_original")
    EXPORT_COL_RESOURCES = _CONFIG.getint("Export", "col_resources")
    EXPORT_PDF_PAGE_SIZE = _CONFIG.get("Export", "pdf_page_size")

    # DriveScanner
    DRIVE_TOKENS = [x.strip() for x in _CONFIG.get("DriveScanner", "drive_tokens").split(",") if x.strip()]
    DRIVE_NUMBER_PATTERN = _CONFIG.get("DriveScanner", "drive_number_pattern")

    # AssetExport
    ARTBOX_NAME = _CONFIG.get("AssetExport", "artbox_name")
    TRAILER_NAME = _CONFIG.get("AssetExport", "trailer_name")

    # API
    STEAM_SEARCH_API = _CONFIG.get("API", "steam_search_api")
    STEAM_STORE_APP_URL = _CONFIG.get("API", "steam_store_app_url")
    STEAMDB_APP_URL = _CONFIG.get("API", "steamdb_app_url")
    PCGW_SEARCH_TEMPLATE = _CONFIG.get("API", "pcgw_search_template")
    IGDB_URL_TEMPLATE = _CONFIG.get("API", "igdb_url_template")
    HTTP_TIMEOUT = _CONFIG.getfloat("API", "http_timeout")
    HTTP_RETRIES = _CONFIG.getint("API", "http_retries")
    SLEEP_BETWEEN_REQUESTS = _CONFIG.getfloat("API", "sleep_between_requests")
    IGDB_IMAGE_BASE_URL = _CONFIG.get("API", "igdb_image_base_url")
    IGDB_SCREENSHOT_SIZE = _CONFIG.get("API", "igdb_screenshot_size")
    IGDB_COVER_SIZE = _CONFIG.get("API", "igdb_cover_size")

    # IGDB credentials – environment variables override config; empty config values fall back to hardcoded defaults
    _igdb_client_id = _CONFIG.get("API", "igdb_client_id").strip()
    _igdb_client_secret = _CONFIG.get("API", "igdb_client_secret").strip()
    _igdb_access_token = _CONFIG.get("API", "igdb_access_token").strip()
    IGDB_CLIENT_ID = os.environ.get("IGDB_CLIENT_ID", _igdb_client_id or _IGDB_CLIENT_ID_FALLBACK)
    IGDB_CLIENT_SECRET = os.environ.get("IGDB_CLIENT_SECRET", _igdb_client_secret or _IGDB_CLIENT_SECRET_FALLBACK)
    IGDB_ACCESS_TOKEN = os.environ.get("IGDB_ACCESS_TOKEN", _igdb_access_token or _IGDB_ACCESS_TOKEN_FALLBACK)

    # Cache directory
    override = _CONFIG.get("Cache", "cache_dir_override").strip()
    if override:
        CACHE_DIR = Path(override)
    else:
        CACHE_DIR = BASE_DIR / "cache"
    SCRIPT_DIR = CACHE_DIR
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Rebuild stylesheet
    APP_STYLESHEET = _get_stylesheet()