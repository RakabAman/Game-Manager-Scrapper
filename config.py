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
    "GUI": {
        "ui_version": "1",   # "1-original", "2-claude", or "3-deep"
    },
    "General": {
        "cache_min_kb": "10",
        "cache_max_kb": "5120",
        "divider_percentage": "55",
        "default_database": "",
        "auto_save": "true",
        "auto_save_interval_seconds": "300",
        "auto_save_path": "",
        "auto_cache": "false",
        "auto_sanitize": "true",
        "show_console": "true",
        "show_thumbnails_in_details": "true",
        "auto_collapse_sidebars": "true",
        "cover_art_preference": "steam",   # "steam" or "igdb"
        "details_cover_multiplier": "1.5",
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
        "duplicate_color": "#ff4545",
        "played_color": "#20ff41",
        "unplayed_color": "#bef4ff",
        "favorite_color": "#f01eff",
        "table_background": "#ffffff",
        "table_alternate_background": "#f9f9f9",
        "table_text_color": "#000000",
        "details_title_font_size": "22",
        "details_desc_font_size": "14",
        "text_box_height": "30",
        "highlight_desaturate_percent": "20",  # last-resort fallback; each theme in theme.ini now
                                                # carries its own value (dark themes use 0 so row
                                                # highlights stay saturated/legible; see theme.ini)
        "details_rating_font_size": "12",
        "details_metadata_label_font_size": "10",
        "details_metadata_value_font_size": "10",
        "details_section_header_font_size": "11",
        "details_metadata_label_color": "#5f6b7a",
        "details_metadata_value_color": "#2c3e50",
        "details_description_color": "#333333",
        "details_rating_color": "#f39c12",
        "details_panel_background": "#ffffff",
        "details_panel_border_radius": "8",
        "active_theme": "1",
        "ui_text_color": "#2c3e50",
        "button_background": "#3498db",

        # -------- NEW KEYS (plain hex colours only) --------
        "stat_card_total_color": "#3498db",
        "stat_card_cached_color": "#f39c12",
        "stat_card_unscraped_color": "#e67e22",
        "stat_card_active_text_color": "#ffffff",
        "stat_card_inactive_label_color": "#5f6b7a",
        "cover_placeholder_background": "#f0f0f0",
        "gallery_placeholder_color": "#888888",
        "gallery_empty_text_color": "#999999",
        "viewer_counter_color": "#ffffff",
        "video_widget_background": "#000000",
        "image_viewer_background": "#000000",
        "button_text_color": "#ffffff",
        "toggle_button_color": "#5f6b7a",
        "splitter_handle_color": "#bdc3c7",

        # -------- ADDITIONAL NEW KEYS (for palette and interactivity) --------
        "button_hover_background": "#2980b9",
        "button_pressed_background": "#1a5276",
        "selection_text_color": "#000000",
        "header_text_color": "#ffffff",
        "label_text_color": "#2c3e50",
        "input_background": "#ffffff",

        # -------- FONT SCALING & TABLE FONT KEYS --------
        "table_data_font_size": "10",
        "global_font_scale": "1.0",
        "auto_contrast_table_text": "true",
    },
    "DetailsIcons": {
        "icon_release": "📅",
        "icon_genres": "🎭",
        "icon_modes": "🎮",
        "icon_themes": "🎯",
        "icon_developer": "🏢",
        "icon_publisher": "📢",
        "icon_perspective": "👁️",
        "icon_version": "🔧",
        "icon_steam": "🆔",
        "icon_igdb": "🔢",
        "icon_drive": "💾",
        "icon_scene": "🏷️",
        "icon_played": "▶",
        "icon_favourite": "♥",
        "icon_screenshots": "🖼️",
        "icon_trailer": "🎬",
        "icon_steamdb": "🔗",
        "icon_pcgwiki": "🔗",
        "icon_steam_link": "🔗",
        "icon_igdb_trailers": "🎥",
        "icon_notes": "🏷️",
        "icon_user_rating": "⭐",
        "icon_links": "🔗",
        "icon_save": "💾",
        "icon_original": "📝",
        "label_cover_placeholder": "🎮",
        "label_no_screenshots": "No screenshots available",
        "label_no_save_locations": "No save locations recorded",
        "label_no_description": "No description",
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
    "Thumbnails": {
        "thumbnail_size": "180",
        "cover_art_size": "80",
    },
    "Gallery": {
        "gallery_thumbnail_corner_radius": "6",
        "gallery_spacing": "8",
        "gallery_thumbnail_background": "#1e1e1e",
        "gallery_border_color": "#dddddd",
        "gallery_show_trailer": "true",
    },
    # Theme sections are created on the fly; we don't define defaults here
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
    
    # Merge with defaults (ensure all keys exist)
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
# Global font scale – must be read before any font size constants
# ----------------------------------------------------------------------
GLOBAL_FONT_SCALE = _CONFIG.getfloat("UI", "global_font_scale", fallback=1.0)
BASE_WIDGET_FONT_SIZE = int(11 * GLOBAL_FONT_SCALE)   # base font for widgets in stylesheet

# Font sizes (all are multiplied by GLOBAL_FONT_SCALE)
DETAILS_TITLE_FONT_SIZE = int(_CONFIG.getint("UI", "details_title_font_size") * GLOBAL_FONT_SCALE)
DETAILS_DESC_FONT_SIZE = int(_CONFIG.getint("UI", "details_desc_font_size") * GLOBAL_FONT_SCALE)
DETAILS_RATING_FONT_SIZE = int(_CONFIG.getint("UI", "details_rating_font_size") * GLOBAL_FONT_SCALE)
DETAILS_METADATA_LABEL_FONT_SIZE = int(_CONFIG.getint("UI", "details_metadata_label_font_size") * GLOBAL_FONT_SCALE)
DETAILS_METADATA_VALUE_FONT_SIZE = int(_CONFIG.getint("UI", "details_metadata_value_font_size") * GLOBAL_FONT_SCALE)
DETAILS_SECTION_HEADER_FONT_SIZE = int(_CONFIG.getint("UI", "details_section_header_font_size") * GLOBAL_FONT_SCALE)
TABLE_DATA_FONT_SIZE = int(_CONFIG.getint("UI", "table_data_font_size") * GLOBAL_FONT_SCALE)

# Auto‑contrast flag
AUTO_CONTRAST_TABLE_TEXT = _CONFIG.getboolean("UI", "auto_contrast_table_text", fallback=True)

# ----------------------------------------------------------------------
# Helper to get a color from the active theme section
# ----------------------------------------------------------------------
def _get_theme_color(key: str) -> str:
    """Return color from active theme section, fallback to UI section, then to DEFAULT_CONFIG."""
    active_theme = _CONFIG.getint("UI", "active_theme", fallback=1)
    theme_section = f"Theme{active_theme}"
    
    # Try theme section first
    if _CONFIG.has_option(theme_section, key):
        return _CONFIG.get(theme_section, key)
    # Then UI section
    if _CONFIG.has_option("UI", key):
        return _CONFIG.get("UI", key)
    # Finally fallback to DEFAULT_CONFIG (UI section)
    return DEFAULT_CONFIG["UI"].get(key, "#000000")


def _get_theme_int(key: str, fallback: int) -> int:
    """Return an integer setting from the active theme section (same lookup order
    as _get_theme_color): active Theme{N} section first, then the general UI
    section, then the supplied fallback. This lets each theme (dark or light)
    carry its own value -- e.g. row highlight desaturation, which needs to stay
    low/off for dark themes so highlighted rows don't wash out against light text."""
    active_theme = _CONFIG.getint("UI", "active_theme", fallback=1)
    theme_section = f"Theme{active_theme}"

    if _CONFIG.has_option(theme_section, key):
        try:
            return _CONFIG.getint(theme_section, key)
        except ValueError:
            pass
    if _CONFIG.has_option("UI", key):
        try:
            return _CONFIG.getint("UI", key)
        except ValueError:
            pass
    return fallback


# ----------------------------------------------------------------------
# Expose constants as module-level variables (now theme-aware)
# ----------------------------------------------------------------------

#GUI
UI_VERSION = _CONFIG.getint("GUI", "ui_version", fallback=1)

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
AUTO_COLLAPSE_SIDEBARS = _CONFIG.getboolean("General", "auto_collapse_sidebars", fallback=True)
COVER_ART_PREFERENCE = _CONFIG.get("General", "cover_art_preference", fallback="steam")
DETAILS_COVER_MULTIPLIER = _CONFIG.getfloat("UI", "details_cover_multiplier", fallback=1.5)

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

# UI colors – now theme-aware
PRIMARY_COLOR = _get_theme_color("primary_color")
SECONDARY_COLOR = _get_theme_color("secondary_color")
ACCENT_COLOR = _get_theme_color("accent_color")
SUCCESS_COLOR = _get_theme_color("success_color")
WARNING_COLOR = _get_theme_color("warning_color")
LIGHT_BG = _get_theme_color("light_bg")
DARK_BG = _get_theme_color("dark_bg")
BORDER_COLOR = _get_theme_color("border_color")
HOVER_COLOR = _get_theme_color("hover_color")
SELECTED_COLOR = _get_theme_color("selected_color")
DUPLICATE_COLOR = _get_theme_color("duplicate_color")
PLAYED_COLOR = _get_theme_color("played_color")
UNPLAYED_COLOR = _get_theme_color("unplayed_color")
FAVORITE_COLOR = _get_theme_color("favorite_color")
TABLE_BACKGROUND = _get_theme_color("table_background")
TABLE_ALTERNATE_BACKGROUND = _get_theme_color("table_alternate_background")
TABLE_TEXT_COLOR = _get_theme_color("table_text_color")
TEXT_BOX_HEIGHT = _CONFIG.getint("UI", "text_box_height")   # NOT scaled (pixel height)
HIGHLIGHT_DESATURATE_PERCENT = _get_theme_int("highlight_desaturate_percent", fallback=20)
UI_TEXT_COLOR = _get_theme_color("ui_text_color")
BUTTON_BACKGROUND = _get_theme_color("button_background")

# Details UI – font sizes are already scaled above, but colors are theme-aware
DETAILS_METADATA_LABEL_COLOR = _get_theme_color("details_metadata_label_color")
DETAILS_METADATA_VALUE_COLOR = _get_theme_color("details_metadata_value_color")
DETAILS_DESCRIPTION_COLOR = _get_theme_color("details_description_color")
DETAILS_RATING_COLOR = _get_theme_color("details_rating_color")
DETAILS_PANEL_BACKGROUND = _get_theme_color("details_panel_background")
DETAILS_PANEL_BORDER_RADIUS = _CONFIG.getint("UI", "details_panel_border_radius")

# -------- NEW THEME-AWARE COLOURS (stat cards, placeholders, etc.) --------
STAT_CARD_TOTAL_COLOR = _get_theme_color("stat_card_total_color")
STAT_CARD_CACHED_COLOR = _get_theme_color("stat_card_cached_color")
STAT_CARD_UNSCRAPED_COLOR = _get_theme_color("stat_card_unscraped_color")
STAT_CARD_ACTIVE_TEXT_COLOR = _get_theme_color("stat_card_active_text_color")
STAT_CARD_INACTIVE_LABEL_COLOR = _get_theme_color("stat_card_inactive_label_color")
COVER_PLACEHOLDER_BACKGROUND = _get_theme_color("cover_placeholder_background")
GALLERY_PLACEHOLDER_COLOR = _get_theme_color("gallery_placeholder_color")
GALLERY_EMPTY_TEXT_COLOR = _get_theme_color("gallery_empty_text_color")
VIEWER_COUNTER_COLOR = _get_theme_color("viewer_counter_color")
VIDEO_WIDGET_BACKGROUND = _get_theme_color("video_widget_background")
IMAGE_VIEWER_BACKGROUND = _get_theme_color("image_viewer_background")
BUTTON_TEXT_COLOR = _get_theme_color("button_text_color")
TOGGLE_BUTTON_COLOR = _get_theme_color("toggle_button_color")
SPLITTER_HANDLE_COLOR = _get_theme_color("splitter_handle_color")

# -------- ADDITIONAL NEW THEME-AWARE COLOURS (for interactivity) --------
BUTTON_HOVER_BACKGROUND = _get_theme_color("button_hover_background")
BUTTON_PRESSED_BACKGROUND = _get_theme_color("button_pressed_background")
SELECTION_TEXT_COLOR = _get_theme_color("selection_text_color")
HEADER_TEXT_COLOR = _get_theme_color("header_text_color")
LABEL_TEXT_COLOR = _get_theme_color("label_text_color")
INPUT_BACKGROUND = _get_theme_color("input_background")

# Details Icons
ICON_RELEASE = _CONFIG.get("DetailsIcons", "icon_release")
ICON_GENRES = _CONFIG.get("DetailsIcons", "icon_genres")
ICON_MODES = _CONFIG.get("DetailsIcons", "icon_modes")
ICON_THEMES = _CONFIG.get("DetailsIcons", "icon_themes")
ICON_DEVELOPER = _CONFIG.get("DetailsIcons", "icon_developer")
ICON_PUBLISHER = _CONFIG.get("DetailsIcons", "icon_publisher")
ICON_PERSPECTIVE = _CONFIG.get("DetailsIcons", "icon_perspective")
ICON_VERSION = _CONFIG.get("DetailsIcons", "icon_version")
ICON_STEAM = _CONFIG.get("DetailsIcons", "icon_steam")
ICON_IGDB = _CONFIG.get("DetailsIcons", "icon_igdb")
ICON_DRIVE = _CONFIG.get("DetailsIcons", "icon_drive")
ICON_SCENE = _CONFIG.get("DetailsIcons", "icon_scene")
ICON_SCREENSHOTS = _CONFIG.get("DetailsIcons", "icon_screenshots")
ICON_TRAILER = _CONFIG.get("DetailsIcons", "icon_trailer")
ICON_LINKS = _CONFIG.get("DetailsIcons", "icon_links")
ICON_SAVE = _CONFIG.get("DetailsIcons", "icon_save")
ICON_ORIGINAL = _CONFIG.get("DetailsIcons", "icon_original")
LABEL_COVER_PLACEHOLDER = _CONFIG.get("DetailsIcons", "label_cover_placeholder")
LABEL_NO_SCREENSHOTS = _CONFIG.get("DetailsIcons", "label_no_screenshots")
LABEL_NO_SAVE_LOCATIONS = _CONFIG.get("DetailsIcons", "label_no_save_locations")
LABEL_NO_DESCRIPTION = _CONFIG.get("DetailsIcons", "label_no_description")
ICON_PLAYED = _CONFIG.get("DetailsIcons", "icon_played")
ICON_FAVOURITE = _CONFIG.get("DetailsIcons", "icon_favourite")
ICON_USER_RATING = _CONFIG.get("DetailsIcons", "icon_user_rating")
ICON_NOTES = _CONFIG.get("DetailsIcons", "icon_notes")

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

# IGDB credentials
_IGDB_CLIENT_ID_FALLBACK = "3y74unpwlpblo3nwnx44a9fpm7aug7"
_IGDB_CLIENT_SECRET_FALLBACK = "t3wrmknntq1ix10wsz761o1uhxxmx0"
_IGDB_ACCESS_TOKEN_FALLBACK = "yqox9e79jt463xt44dyt85525gwkg2"

_igdb_client_id = _CONFIG.get("API", "igdb_client_id").strip()
_igdb_client_secret = _CONFIG.get("API", "igdb_client_secret").strip()
_igdb_access_token = _CONFIG.get("API", "igdb_access_token").strip()

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
# Thumbnails & Gallery
# ----------------------------------------------------------------------
THUMBNAIL_SIZE = _CONFIG.getint("Thumbnails", "thumbnail_size", fallback=180)
COVER_ART_SIZE = _CONFIG.getint("Thumbnails", "cover_art_size", fallback=80)
GALLERY_THUMBNAIL_CORNER_RADIUS = _CONFIG.getint("Gallery", "gallery_thumbnail_corner_radius")
GALLERY_SPACING = _CONFIG.getint("Gallery", "gallery_spacing")
GALLERY_THUMBNAIL_BACKGROUND = _get_theme_color("gallery_thumbnail_background")
GALLERY_BORDER_COLOR = _get_theme_color("gallery_border_color")
GALLERY_SHOW_TRAILER = _CONFIG.getboolean("Gallery", "gallery_show_trailer")

# ----------------------------------------------------------------------
# Application Stylesheet (built using loaded colors and scaled fonts)
# ----------------------------------------------------------------------
def _get_stylesheet():
    base_font = BASE_WIDGET_FONT_SIZE   # already scaled
    title_font = int(14 * GLOBAL_FONT_SCALE)
    subtitle_font = int(12 * GLOBAL_FONT_SCALE)
    return f"""
QMainWindow {{
    background-color: {LIGHT_BG};
}}

QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: {base_font}px;
}}

/* ========== LABELS ========== */
QLabel {{
    color: {LABEL_TEXT_COLOR};
    background-color: transparent;
}}

/* ========== CHECKBOX & RADIO BUTTON (transparent backgrounds) ========== */
QCheckBox, QRadioButton {{
    color: {LABEL_TEXT_COLOR};
    background-color: transparent;
    spacing: 6px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 3px;
    background-color: transparent;
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {SECONDARY_COLOR};
    border-color: {SECONDARY_COLOR};
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {SECONDARY_COLOR};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: #95a5a6;
    background-color: #ecf0f1;
}}

/* ========== INPUT WIDGETS (unified background & text) ========== */
QLineEdit, QTextEdit, QComboBox,
QSpinBox, QDoubleSpinBox,
QDateTimeEdit, QDateEdit, QTimeEdit {{
    color: {TABLE_TEXT_COLOR};
    background-color: {INPUT_BACKGROUND};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {SELECTED_COLOR};
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus,
QDateTimeEdit:focus, QDateEdit:focus, QTimeEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 3px 7px;
}}

QLineEdit[error="true"] {{
    border: 2px solid {ACCENT_COLOR};
}}

/* ========== TABLE STYLES ========== */
QTableView {{
    background-color: {TABLE_BACKGROUND};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    gridline-color: {BORDER_COLOR};
    selection-background-color: {SELECTED_COLOR};
    selection-color: {SELECTION_TEXT_COLOR};
    alternate-background-color: {TABLE_ALTERNATE_BACKGROUND};
}}

QTableView::item {{
    padding: 4px;
    border-bottom: 1px solid {BORDER_COLOR};
    color: {TABLE_TEXT_COLOR};
}}

QTableView::item:selected {{
    background-color: {SELECTED_COLOR};
    color: {SELECTION_TEXT_COLOR};
}}

QHeaderView::section {{
    background-color: {PRIMARY_COLOR};
    color: {HEADER_TEXT_COLOR};
    padding: 6px;
    border: 1px solid {DARK_BG};
    font-weight: bold;
    font-size: {base_font}px;
}}

/* ========== BUTTON STYLES ========== */
QPushButton {{
    background-color: {BUTTON_BACKGROUND};
    color: {BUTTON_TEXT_COLOR};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 24px;
}}

QPushButton:hover {{ background-color: {BUTTON_HOVER_BACKGROUND}; }}
QPushButton:pressed {{ background-color: {BUTTON_PRESSED_BACKGROUND}; }}
QPushButton:disabled {{
    background-color: #95a5a6;
    color: #7f8c8d;
}}

QPushButton[urgent="true"] {{ background-color: {ACCENT_COLOR}; }}
QPushButton[urgent="true"]:hover {{ background-color: #c0392b; }}
QPushButton[success="true"] {{ background-color: {SUCCESS_COLOR}; }}
QPushButton[success="true"]:hover {{ background-color: #229954; }}

/* ========== GROUP BOX ========== */
QGroupBox {{
    font-weight: bold;
    border: 2px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: {TABLE_BACKGROUND};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 8px 0 8px;
    color: {UI_TEXT_COLOR};
}}

/* ========== TABS ========== */
QTabWidget::pane {{
    border: none;
    margin: 0;
    padding: 0;
    background-color: {TABLE_BACKGROUND};
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
    background-color: {TABLE_BACKGROUND};
    border-bottom: 2px solid {SECONDARY_COLOR};
    font-weight: bold;
}}

QTabBar::tab:hover {{ background-color: {HOVER_COLOR}; }}

/* ========== SPLITTER ========== */
QSplitter::handle {{
    background-color: {SPLITTER_HANDLE_COLOR};
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

QScrollBar:horizontal {{
    border: none;
    background-color: #f0f0f0;
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: #c0c0c0;
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #a0a0a0;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
}}

QScrollArea > QWidget > QWidget {{
    margin: 0;
    padding: 0;
}}

/* ========== PROGRESS BAR ========== */
QProgressBar {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    text-align: center;
    background-color: {TABLE_BACKGROUND};
}}
QProgressBar::chunk {{
    background-color: {SUCCESS_COLOR};
    border-radius: 3px;
}}

/* ========== STATUS BAR ========== */
QStatusBar {{
    background-color: {PRIMARY_COLOR};
    color: {BUTTON_TEXT_COLOR};
    border-top: 1px solid {DARK_BG};
}}
QStatusBar QLabel {{
    color: {BUTTON_TEXT_COLOR};
    padding: 0 8px;
    border-right: 1px solid rgba(255, 255, 255, 0.2);
}}

/* ========== MENU ========== */
QMenuBar {{
    background-color: {PRIMARY_COLOR};
    color: {BUTTON_TEXT_COLOR};
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
    background-color: {TABLE_BACKGROUND};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    color: {UI_TEXT_COLOR};
}}
QMenu::item {{
    padding: 6px 24px 6px 20px;
    color: {UI_TEXT_COLOR};
}}
QMenu::item:selected {{
    background-color: {SELECTED_COLOR};
    color: {UI_TEXT_COLOR};
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
    font-size: {title_font}px;
    font-weight: bold;
    color: {PRIMARY_COLOR};
    padding: 4px 0;
}}
QLabel[subtitle="true"] {{
    font-size: {subtitle_font}px;
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
    background-color: {TABLE_BACKGROUND};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 8px;
}}
"""

APP_STYLESHEET = _get_stylesheet()

# config.py – add at the end, before reload_config()

def get_icon_path():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'icon.ico')

def apply_application_icon(app):
    from PyQt5.QtGui import QIcon
    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Warning: icon not found at {icon_path}")

def refresh_all(root_widget):
    """
    Single entry point for propagating a config change to the live UI.

    Walks the QObject/QWidget tree rooted at `root_widget` (Qt parent/child
    ownership is used as the registry -- nothing needs to be manually
    registered) and calls `apply_theme()` on every widget that defines it.
    This is the ONE method name every config-aware custom widget should
    implement (HeaderWidget, SidebarWidget, ModernDetailsPanel,
    CheckableComboBox, ClickableImageViewer, AspectRatioWidget, the main
    window itself, and anything added later).

    Widgets that only own plain/anonymous Qt widgets with config-driven
    styling (e.g. dynamically created QLabel/QToolButton instances) are not
    reachable this way since they have no apply_theme() of their own -- the
    owning widget's own apply_theme() is still responsible for restyling
    those directly (e.g. via a tracked list of labels it created).

    Call this AFTER reload_config() and after the caller's own apply_theme()
    has already updated its own top-level stylesheet/palette, so that any
    top-level QSS rules are already in place before children are polished.
    """
    from PyQt5.QtWidgets import QWidget

    if root_widget is None:
        return

    # root_widget's own apply_theme() is the caller's responsibility to call
    # first (it may need to run before its children, e.g. to set a palette
    # that children inherit). We only walk *descendants* here.
    widgets = root_widget.findChildren(QWidget)

    for w in widgets:
        fn = getattr(w, "apply_theme", None)
        if callable(fn):
            try:
                fn()
            except Exception as e:
                print(f"[refresh_all] apply_theme() failed on {w!r}: {e}")

    # Force a full unpolish/polish/repaint sweep so QSS selectors that
    # depend on dynamic properties (e.g. [urgent="true"]) are re-evaluated
    # everywhere, not just on widgets that defined apply_theme().
    style = root_widget.style()
    style.unpolish(root_widget)
    style.polish(root_widget)
    root_widget.update()
    for w in widgets:
        w_style = w.style()
        w_style.unpolish(w)
        w_style.polish(w)
        w.update()


def apply_application_palette(app):
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtCore import Qt
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor(LIGHT_BG))
    palette.setColor(QPalette.WindowText, QColor(PRIMARY_COLOR))
    palette.setColor(QPalette.Base, QColor(TABLE_BACKGROUND))
    palette.setColor(QPalette.AlternateBase, QColor(TABLE_ALTERNATE_BACKGROUND))
    palette.setColor(QPalette.Text, QColor(TABLE_TEXT_COLOR))
    palette.setColor(QPalette.Button, QColor(SECONDARY_COLOR))
    palette.setColor(QPalette.ButtonText, QColor(BUTTON_TEXT_COLOR))
    palette.setColor(QPalette.Highlight, QColor(SELECTED_COLOR))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

# ----------------------------------------------------------------------
# Utility function to reload config at runtime
# ----------------------------------------------------------------------
def reload_config():
    """Reload configuration from disk and update module variables."""
    global _CONFIG, UI_VERSION, STALL_TIMEOUT, CHUNK_SIZE, CACHE_MIN_KB, CACHE_MAX_KB
    global DIVIDER_PERCENTAGE, DEFAULT_DATABASE, AUTO_SAVE, AUTO_SAVE_INTERVAL, AUTO_SAVE_PATH
    global AUTO_CACHE, AUTO_SANITIZE, SHOW_CONSOLE, SHOW_THUMBNAILS_IN_DETAILS
    global AUTO_ACCEPT_SCORE, FETCH_PCGW_SAVE, MAX_CONCURRENT_SCRAPES
    global MAX_IMAGES_TO_DOWNLOAD, MAX_IMAGES_TO_DISPLAY, MAX_MICROTRAILERS, MAX_TRAILERS
    global DEBUG_IMAGES, VIDEO_LOOP_ENABLED, MAX_CONCURRENT_DOWNLOADS
    global PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR, SUCCESS_COLOR, WARNING_COLOR
    global LIGHT_BG, DARK_BG, BORDER_COLOR, HOVER_COLOR, SELECTED_COLOR
    global DUPLICATE_COLOR, PLAYED_COLOR, UNPLAYED_COLOR, FAVORITE_COLOR
    global TABLE_BACKGROUND, TABLE_ALTERNATE_BACKGROUND, TABLE_TEXT_COLOR
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
    global HIGHLIGHT_DESATURATE_PERCENT, DETAILS_COVER_MULTIPLIER
    global DETAILS_RATING_FONT_SIZE, DETAILS_METADATA_LABEL_FONT_SIZE, DETAILS_METADATA_VALUE_FONT_SIZE
    global DETAILS_SECTION_HEADER_FONT_SIZE, DETAILS_METADATA_LABEL_COLOR, DETAILS_METADATA_VALUE_COLOR
    global DETAILS_DESCRIPTION_COLOR, DETAILS_RATING_COLOR, DETAILS_PANEL_BACKGROUND, DETAILS_PANEL_BORDER_RADIUS
    global THUMBNAIL_SIZE, COVER_ART_SIZE, GALLERY_THUMBNAIL_CORNER_RADIUS, GALLERY_SPACING
    global GALLERY_THUMBNAIL_BACKGROUND, GALLERY_BORDER_COLOR, GALLERY_SHOW_TRAILER
    global ICON_RELEASE, ICON_GENRES, ICON_MODES, ICON_THEMES, ICON_DEVELOPER, ICON_PUBLISHER
    global ICON_PERSPECTIVE, ICON_VERSION, ICON_STEAM, ICON_IGDB, ICON_DRIVE, ICON_SCENE
    global ICON_SCREENSHOTS, ICON_TRAILER, ICON_LINKS, ICON_SAVE, ICON_ORIGINAL
    global LABEL_COVER_PLACEHOLDER, LABEL_NO_SCREENSHOTS, LABEL_NO_SAVE_LOCATIONS, LABEL_NO_DESCRIPTION
    global ICON_PLAYED, ICON_FAVOURITE, ICON_USER_RATING, ICON_NOTES
    global STAT_CARD_TOTAL_COLOR, STAT_CARD_CACHED_COLOR, STAT_CARD_UNSCRAPED_COLOR
    global STAT_CARD_ACTIVE_TEXT_COLOR, STAT_CARD_INACTIVE_LABEL_COLOR
    global COVER_PLACEHOLDER_BACKGROUND, GALLERY_PLACEHOLDER_COLOR, GALLERY_EMPTY_TEXT_COLOR
    global VIEWER_COUNTER_COLOR, VIDEO_WIDGET_BACKGROUND, IMAGE_VIEWER_BACKGROUND
    global BUTTON_TEXT_COLOR, TOGGLE_BUTTON_COLOR, SPLITTER_HANDLE_COLOR, UI_TEXT_COLOR
    global BUTTON_HOVER_BACKGROUND, BUTTON_PRESSED_BACKGROUND, BUTTON_BACKGROUND
    global SELECTION_TEXT_COLOR, HEADER_TEXT_COLOR, LABEL_TEXT_COLOR, INPUT_BACKGROUND

    # NEW globals for font scaling and table
    global GLOBAL_FONT_SCALE, BASE_WIDGET_FONT_SIZE, TABLE_DATA_FONT_SIZE, AUTO_CONTRAST_TABLE_TEXT

    _CONFIG = _load_config()

    #GUI
    UI_VERSION = _CONFIG.getint("GUI", "ui_version", fallback=1)    
    
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
    AUTO_COLLAPSE_SIDEBARS = _CONFIG.getboolean("General", "auto_collapse_sidebars", fallback=True)
    COVER_ART_PREFERENCE = _CONFIG.get("General", "cover_art_preference", fallback="steam")
 
    DETAILS_COVER_MULTIPLIER = _CONFIG.getfloat("UI", "details_cover_multiplier", fallback=1.5)    

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

    # UI – theme-aware colors
    PRIMARY_COLOR = _get_theme_color("primary_color")
    SECONDARY_COLOR = _get_theme_color("secondary_color")
    ACCENT_COLOR = _get_theme_color("accent_color")
    SUCCESS_COLOR = _get_theme_color("success_color")
    WARNING_COLOR = _get_theme_color("warning_color")
    LIGHT_BG = _get_theme_color("light_bg")
    DARK_BG = _get_theme_color("dark_bg")
    BORDER_COLOR = _get_theme_color("border_color")
    HOVER_COLOR = _get_theme_color("hover_color")
    SELECTED_COLOR = _get_theme_color("selected_color")
    DUPLICATE_COLOR = _get_theme_color("duplicate_color")
    PLAYED_COLOR = _get_theme_color("played_color")
    UNPLAYED_COLOR = _get_theme_color("unplayed_color")
    FAVORITE_COLOR = _get_theme_color("favorite_color")
    UI_TEXT_COLOR = _get_theme_color("ui_text_color")
    BUTTON_BACKGROUND = _get_theme_color("button_background")

    # Table colors
    TABLE_BACKGROUND = _get_theme_color("table_background")
    TABLE_ALTERNATE_BACKGROUND = _get_theme_color("table_alternate_background")
    TABLE_TEXT_COLOR = _get_theme_color("table_text_color")
    TEXT_BOX_HEIGHT = _CONFIG.getint("UI", "text_box_height")   # not scaled
    HIGHLIGHT_DESATURATE_PERCENT = _get_theme_int("highlight_desaturate_percent", fallback=20)

    # Details UI – font sizes are scaled below
    DETAILS_METADATA_LABEL_COLOR = _get_theme_color("details_metadata_label_color")
    DETAILS_METADATA_VALUE_COLOR = _get_theme_color("details_metadata_value_color")
    DETAILS_DESCRIPTION_COLOR = _get_theme_color("details_description_color")
    DETAILS_RATING_COLOR = _get_theme_color("details_rating_color")
    DETAILS_PANEL_BACKGROUND = _get_theme_color("details_panel_background")
    DETAILS_PANEL_BORDER_RADIUS = _CONFIG.getint("UI", "details_panel_border_radius")

    # New colours (stat cards, etc.)
    STAT_CARD_TOTAL_COLOR = _get_theme_color("stat_card_total_color")
    STAT_CARD_CACHED_COLOR = _get_theme_color("stat_card_cached_color")
    STAT_CARD_UNSCRAPED_COLOR = _get_theme_color("stat_card_unscraped_color")
    STAT_CARD_ACTIVE_TEXT_COLOR = _get_theme_color("stat_card_active_text_color")
    STAT_CARD_INACTIVE_LABEL_COLOR = _get_theme_color("stat_card_inactive_label_color")
    COVER_PLACEHOLDER_BACKGROUND = _get_theme_color("cover_placeholder_background")
    GALLERY_PLACEHOLDER_COLOR = _get_theme_color("gallery_placeholder_color")
    GALLERY_EMPTY_TEXT_COLOR = _get_theme_color("gallery_empty_text_color")
    VIEWER_COUNTER_COLOR = _get_theme_color("viewer_counter_color")
    VIDEO_WIDGET_BACKGROUND = _get_theme_color("video_widget_background")
    IMAGE_VIEWER_BACKGROUND = _get_theme_color("image_viewer_background")
    BUTTON_TEXT_COLOR = _get_theme_color("button_text_color")
    TOGGLE_BUTTON_COLOR = _get_theme_color("toggle_button_color")
    SPLITTER_HANDLE_COLOR = _get_theme_color("splitter_handle_color")

    # Additional new colours (palette interactivity)
    BUTTON_HOVER_BACKGROUND = _get_theme_color("button_hover_background")
    BUTTON_PRESSED_BACKGROUND = _get_theme_color("button_pressed_background")
    SELECTION_TEXT_COLOR = _get_theme_color("selection_text_color")
    HEADER_TEXT_COLOR = _get_theme_color("header_text_color")
    LABEL_TEXT_COLOR = _get_theme_color("label_text_color")
    INPUT_BACKGROUND = _get_theme_color("input_background")

    # ------- FONT SCALING (recompute all sizes) -------
    GLOBAL_FONT_SCALE = _CONFIG.getfloat("UI", "global_font_scale", fallback=1.0)
    BASE_WIDGET_FONT_SIZE = int(11 * GLOBAL_FONT_SCALE)

    DETAILS_TITLE_FONT_SIZE = int(_CONFIG.getint("UI", "details_title_font_size") * GLOBAL_FONT_SCALE)
    DETAILS_DESC_FONT_SIZE = int(_CONFIG.getint("UI", "details_desc_font_size") * GLOBAL_FONT_SCALE)
    DETAILS_RATING_FONT_SIZE = int(_CONFIG.getint("UI", "details_rating_font_size") * GLOBAL_FONT_SCALE)
    DETAILS_METADATA_LABEL_FONT_SIZE = int(_CONFIG.getint("UI", "details_metadata_label_font_size") * GLOBAL_FONT_SCALE)
    DETAILS_METADATA_VALUE_FONT_SIZE = int(_CONFIG.getint("UI", "details_metadata_value_font_size") * GLOBAL_FONT_SCALE)
    DETAILS_SECTION_HEADER_FONT_SIZE = int(_CONFIG.getint("UI", "details_section_header_font_size") * GLOBAL_FONT_SCALE)
    TABLE_DATA_FONT_SIZE = int(_CONFIG.getint("UI", "table_data_font_size") * GLOBAL_FONT_SCALE)

    AUTO_CONTRAST_TABLE_TEXT = _CONFIG.getboolean("UI", "auto_contrast_table_text", fallback=True)

    # Details Icons
    ICON_RELEASE = _CONFIG.get("DetailsIcons", "icon_release")
    ICON_GENRES = _CONFIG.get("DetailsIcons", "icon_genres")
    ICON_MODES = _CONFIG.get("DetailsIcons", "icon_modes")
    ICON_THEMES = _CONFIG.get("DetailsIcons", "icon_themes")
    ICON_DEVELOPER = _CONFIG.get("DetailsIcons", "icon_developer")
    ICON_PUBLISHER = _CONFIG.get("DetailsIcons", "icon_publisher")
    ICON_PERSPECTIVE = _CONFIG.get("DetailsIcons", "icon_perspective")
    ICON_VERSION = _CONFIG.get("DetailsIcons", "icon_version")
    ICON_STEAM = _CONFIG.get("DetailsIcons", "icon_steam")
    ICON_IGDB = _CONFIG.get("DetailsIcons", "icon_igdb")
    ICON_DRIVE = _CONFIG.get("DetailsIcons", "icon_drive")
    ICON_SCENE = _CONFIG.get("DetailsIcons", "icon_scene")
    ICON_SCREENSHOTS = _CONFIG.get("DetailsIcons", "icon_screenshots")
    ICON_TRAILER = _CONFIG.get("DetailsIcons", "icon_trailer")
    ICON_LINKS = _CONFIG.get("DetailsIcons", "icon_links")
    ICON_SAVE = _CONFIG.get("DetailsIcons", "icon_save")
    ICON_ORIGINAL = _CONFIG.get("DetailsIcons", "icon_original")
    LABEL_COVER_PLACEHOLDER = _CONFIG.get("DetailsIcons", "label_cover_placeholder")
    LABEL_NO_SCREENSHOTS = _CONFIG.get("DetailsIcons", "label_no_screenshots")
    LABEL_NO_SAVE_LOCATIONS = _CONFIG.get("DetailsIcons", "label_no_save_locations")
    LABEL_NO_DESCRIPTION = _CONFIG.get("DetailsIcons", "label_no_description")
    ICON_PLAYED = _CONFIG.get("DetailsIcons", "icon_played")
    ICON_FAVOURITE = _CONFIG.get("DetailsIcons", "icon_favourite")
    ICON_USER_RATING = _CONFIG.get("DetailsIcons", "icon_user_rating")
    ICON_NOTES = _CONFIG.get("DetailsIcons", "icon_notes")

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

    # Thumbnails & Gallery
    THUMBNAIL_SIZE = _CONFIG.getint("Thumbnails", "thumbnail_size", fallback=180)
    COVER_ART_SIZE = _CONFIG.getint("Thumbnails", "cover_art_size", fallback=80)
    GALLERY_THUMBNAIL_CORNER_RADIUS = _CONFIG.getint("Gallery", "gallery_thumbnail_corner_radius")
    GALLERY_SPACING = _CONFIG.getint("Gallery", "gallery_spacing")
    GALLERY_THUMBNAIL_BACKGROUND = _get_theme_color("gallery_thumbnail_background")
    GALLERY_BORDER_COLOR = _get_theme_color("gallery_border_color")
    GALLERY_SHOW_TRAILER = _CONFIG.getboolean("Gallery", "gallery_show_trailer")

    # Rebuild stylesheet
    APP_STYLESHEET = _get_stylesheet()