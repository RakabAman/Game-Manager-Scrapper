# config.py
import os
import sys
import configparser
import json
from pathlib import Path

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
# Default configuration values
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "General": {
        "stall_timeout": "20",
        "chunk_size": "50",
        "cache_min_kb": "10",
        "cache_max_kb": "5120",
        "divider_percentage": "55",          # NEW: main list vs details split (0-100)
        "default_database": "",              # NEW: path to default database file (empty = none)
        "auto_save": "false",                # NEW: automatically save changes to database
        "auto_cache": "true",                # NEW: automatically cache images/videos
    },
    "Scraping": {
        "auto_accept_score": "92",
        "fetch_pcgw_save": "false",
    },
    "Download": {
        "max_images_to_download": "5",
        "max_images_to_display": "5",
        "max_microtrailers": "1",
        "max_trailers": "3",
        "debug_images": "false",
        "video_loop_enabled": "true",
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
    },
    "Cache": {
        "cache_dir_override": "",
    },
    "Sanitize": {
        "repack_list": "FitGirl Repack,DODI Repacks,GOG,CODEX,RELOADED,SKIDROW,CPY,PLAZA,Razor1911,FLT,SiMPLEX,PROPHET,HOODLUM,KaOs Krew,TinyRepacks,M4ckD0ge,qoob,JIT,GoldBerg,EMPRESS,INSANE,DOGE,ANOMALY",
        "edition_tokens": "deluxe,edition,ultimate,bundle,pack,premium,remastered,remake,complete,goty,director's cut,anniversary,super digital,evolved,classified archives,bonus ost,bonus",
        "emulator_tokens": "rpcs3,ryujinx,yuzu,cemu,dolphin,pcsx2,switch,ps3,wiiu,ps4,emulator,emu",
        "mode_keywords": '{"Multiplayer":["multiplayer","multi-player","mp","online"],"CO-OP":["coop","co-op","co op","cooperative"],"Singleplayer":["singleplayer","single-player","sp"]}',
    }
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
STALL_TIMEOUT = _CONFIG.getint("General", "stall_timeout")
CHUNK_SIZE = _CONFIG.getint("General", "chunk_size")
CACHE_MIN_KB = _CONFIG.getint("General", "cache_min_kb")
CACHE_MAX_KB = _CONFIG.getint("General", "cache_max_kb")
DIVIDER_PERCENTAGE = _CONFIG.getint("General", "divider_percentage")
DEFAULT_DATABASE = _CONFIG.get("General", "default_database").strip()
AUTO_SAVE = _CONFIG.getboolean("General", "auto_save")
AUTO_CACHE = _CONFIG.getboolean("General", "auto_cache")

# Scraping
AUTO_ACCEPT_SCORE = _CONFIG.getint("Scraping", "auto_accept_score")
FETCH_PCGW_SAVE = _CONFIG.getboolean("Scraping", "fetch_pcgw_save")

# Download
MAX_IMAGES_TO_DOWNLOAD = _CONFIG.getint("Download", "max_images_to_download")
MAX_IMAGES_TO_DISPLAY = _CONFIG.getint("Download", "max_images_to_display")
MAX_MICROTRAILERS = _CONFIG.getint("Download", "max_microtrailers")
MAX_TRAILERS = _CONFIG.getint("Download", "max_trailers")
DEBUG_IMAGES = _CONFIG.getboolean("Download", "debug_images")
VIDEO_LOOP_ENABLED = _CONFIG.getboolean("Download", "video_loop_enabled")

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

# Sanitize lists
REPACK_LIST = [x.strip() for x in _CONFIG.get("Sanitize", "repack_list").split(",") if x.strip()]
EDITION_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "edition_tokens").split(",") if x.strip()]
EMULATOR_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "emulator_tokens").split(",") if x.strip()]
MODE_KEYWORDS = json.loads(_CONFIG.get("Sanitize", "mode_keywords"))

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
APP_STYLESHEET = f"""
QMainWindow {{
    background-color: {LIGHT_BG};
}}

QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}}

/* Table Styles */
QTableView {{
    background-color: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    gridline-color: {BORDER_COLOR};
    selection-background-color: {SELECTED_COLOR};
    selection-color: black;
    alternate-background-color: #f9f9f9;
}}

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

/* Button Styles */
QPushButton {{
    background-color: {SECONDARY_COLOR};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #2980b9;
}}

QPushButton:pressed {{
    background-color: {PRIMARY_COLOR};
}}

QPushButton:disabled {{
    background-color: #95a5a6;
    color: #7f8c8d;
}}

/* Special Buttons */
QPushButton[urgent="true"] {{
    background-color: {ACCENT_COLOR};
}}

QPushButton[urgent="true"]:hover {{
    background-color: #c0392b;
}}

QPushButton[success="true"] {{
    background-color: {SUCCESS_COLOR};
}}

QPushButton[success="true"]:hover {{
    background-color: #229954;
}}

/* Line Edit Styles */
QLineEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px;
    background-color: white;
    selection-background-color: {SELECTED_COLOR};
}}

QLineEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 5px;
}}

QLineEdit[error="true"] {{
    border: 2px solid {ACCENT_COLOR};
}}

/* Text Edit Styles */
QTextEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}}

QTextEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 5px;
}}

/* Group Box Styles */
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

/* Tab Widget Styles */
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

QTabBar::tab:hover {{
    background-color: {HOVER_COLOR};
}}

/* Splitter Styles */
QSplitter::handle {{
    background-color: {BORDER_COLOR};
    width: 4px;
    height: 4px;
}}

QSplitter::handle:hover {{
    background-color: {SECONDARY_COLOR};
}}

/* Scroll Area */
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

QScrollBar::handle:vertical:hover {{
    background-color: #a0a0a0;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
}}

/* Progress Bar */
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

/* Status Bar */
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

/* Menu Bar */
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

/* Dialog Styles */
QDialog {{
    background-color: {LIGHT_BG};
}}

QDialogButtonBox {{
    background-color: transparent;
}}

/* Label Styles */
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

/* Frame Styles */
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


# ----------------------------------------------------------------------
# Utility function to reload config at runtime
# ----------------------------------------------------------------------
def reload_config():
    """Reload configuration from disk and update module variables."""
    global _CONFIG, STALL_TIMEOUT, CHUNK_SIZE, CACHE_MIN_KB, CACHE_MAX_KB
    global DIVIDER_PERCENTAGE, DEFAULT_DATABASE, AUTO_SAVE, AUTO_CACHE
    global AUTO_ACCEPT_SCORE, FETCH_PCGW_SAVE
    global MAX_IMAGES_TO_DOWNLOAD, MAX_IMAGES_TO_DISPLAY, MAX_MICROTRAILERS, MAX_TRAILERS
    global DEBUG_IMAGES, VIDEO_LOOP_ENABLED
    global PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR, SUCCESS_COLOR, WARNING_COLOR
    global LIGHT_BG, DARK_BG, BORDER_COLOR, HOVER_COLOR, SELECTED_COLOR
    global CACHE_DIR, SCRIPT_DIR, APP_STYLESHEET
    global REPACK_LIST, EDITION_TOKENS, EMULATOR_TOKENS, MODE_KEYWORDS

    _CONFIG = _load_config()
    
    STALL_TIMEOUT = _CONFIG.getint("General", "stall_timeout")
    CHUNK_SIZE = _CONFIG.getint("General", "chunk_size")
    CACHE_MIN_KB = _CONFIG.getint("General", "cache_min_kb")
    CACHE_MAX_KB = _CONFIG.getint("General", "cache_max_kb")
    DIVIDER_PERCENTAGE = _CONFIG.getint("General", "divider_percentage")
    DEFAULT_DATABASE = _CONFIG.get("General", "default_database").strip()
    AUTO_SAVE = _CONFIG.getboolean("General", "auto_save")
    AUTO_CACHE = _CONFIG.getboolean("General", "auto_cache")
    
    AUTO_ACCEPT_SCORE = _CONFIG.getint("Scraping", "auto_accept_score")
    FETCH_PCGW_SAVE = _CONFIG.getboolean("Scraping", "fetch_pcgw_save")
    
    MAX_IMAGES_TO_DOWNLOAD = _CONFIG.getint("Download", "max_images_to_download")
    MAX_IMAGES_TO_DISPLAY = _CONFIG.getint("Download", "max_images_to_display")
    MAX_MICROTRAILERS = _CONFIG.getint("Download", "max_microtrailers")
    MAX_TRAILERS = _CONFIG.getint("Download", "max_trailers")
    DEBUG_IMAGES = _CONFIG.getboolean("Download", "debug_images")
    VIDEO_LOOP_ENABLED = _CONFIG.getboolean("Download", "video_loop_enabled")
    
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
    
    REPACK_LIST = [x.strip() for x in _CONFIG.get("Sanitize", "repack_list").split(",") if x.strip()]
    EDITION_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "edition_tokens").split(",") if x.strip()]
    EMULATOR_TOKENS = [x.strip() for x in _CONFIG.get("Sanitize", "emulator_tokens").split(",") if x.strip()]
    MODE_KEYWORDS = json.loads(_CONFIG.get("Sanitize", "mode_keywords"))
    
    override = _CONFIG.get("Cache", "cache_dir_override").strip()
    if override:
        CACHE_DIR = Path(override)
    else:
        CACHE_DIR = BASE_DIR / "cache"
    SCRIPT_DIR = CACHE_DIR
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Rebuild stylesheet (the f-string will use the new color variables)
    # In practice, you would reassign the full string; here we just note it.
    # For brevity, I'll assume the full string is reassigned.
    # APP_STYLESHEET = f"""..."""
APP_STYLESHEET = f"""
QMainWindow {{
    background-color: {LIGHT_BG};
}}

QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}}

/* Table Styles */
QTableView {{
    background-color: white;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    gridline-color: {BORDER_COLOR};
    selection-background-color: {SELECTED_COLOR};
    selection-color: black;
    alternate-background-color: #f9f9f9;
}}

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

/* Button Styles */
QPushButton {{
    background-color: {SECONDARY_COLOR};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #2980b9;
}}

QPushButton:pressed {{
    background-color: {PRIMARY_COLOR};
}}

QPushButton:disabled {{
    background-color: #95a5a6;
    color: #7f8c8d;
}}

/* Special Buttons */
QPushButton[urgent="true"] {{
    background-color: {ACCENT_COLOR};
}}

QPushButton[urgent="true"]:hover {{
    background-color: #c0392b;
}}

QPushButton[success="true"] {{
    background-color: {SUCCESS_COLOR};
}}

QPushButton[success="true"]:hover {{
    background-color: #229954;
}}

/* Line Edit Styles */
QLineEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px;
    background-color: white;
    selection-background-color: {SELECTED_COLOR};
}}

QLineEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 5px;
}}

QLineEdit[error="true"] {{
    border: 2px solid {ACCENT_COLOR};
}}

/* Text Edit Styles */
QTextEdit {{
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 6px;
    background-color: white;
}}

QTextEdit:focus {{
    border: 2px solid {SECONDARY_COLOR};
    padding: 5px;
}}

/* Group Box Styles */
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

/* Tab Widget Styles */
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

QTabBar::tab:hover {{
    background-color: {HOVER_COLOR};
}}

/* Splitter Styles */
QSplitter::handle {{
    background-color: {BORDER_COLOR};
    width: 4px;
    height: 4px;
}}

QSplitter::handle:hover {{
    background-color: {SECONDARY_COLOR};
}}

/* Scroll Area */
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

QScrollBar::handle:vertical:hover {{
    background-color: #a0a0a0;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
}}

/* Progress Bar */
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

/* Status Bar */
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

/* Menu Bar */
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

/* Dialog Styles */
QDialog {{
    background-color: {LIGHT_BG};
}}

QDialogButtonBox {{
    background-color: transparent;
}}

/* Label Styles */
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

/* Frame Styles */
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

# ----------------------------------------------------------------------
# Print status
# ----------------------------------------------------------------------
print(f"[CONFIG] Loaded from: {CONFIG_FILE}")
print(f"[CONFIG] CACHE_DIR = {CACHE_DIR}")
print(f"[CONFIG] Loaded {len(REPACK_LIST)} repack names, {len(EDITION_TOKENS)} edition tokens, {len(EMULATOR_TOKENS)} emulator tokens")