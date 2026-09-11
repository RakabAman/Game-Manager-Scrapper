# settings_dialog.py
import os
import configparser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QLineEdit,
    QSpinBox, QTextEdit, QScrollArea, QDoubleSpinBox, QCheckBox, QPushButton, QHBoxLayout,
    QMessageBox, QColorDialog, QLabel, QFileDialog, QGroupBox, QRadioButton,
    QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import config
from config import CONFIG_FILE, reload_config, BASE_DIR

# ----------------------------------------------------------------------
# All theme‑able colour keys (including button_background)
# ----------------------------------------------------------------------
COLOR_KEYS = [
    # Existing UI colours
    "primary_color", "secondary_color", "accent_color", "success_color",
    "warning_color", "light_bg", "dark_bg", "border_color", "hover_color",
    "selected_color", "duplicate_color", "played_color", "unplayed_color",
    "favorite_color",

    # Buttons & UI
    "button_background",          # <-- NEW
    "button_text_color", "button_hover_background", "button_pressed_background",
    "toggle_button_color", "splitter_handle_color",
    "selection_text_color", "header_text_color", "label_text_color",
    "input_background", "ui_text_color",

    # Details & gallery
    "details_metadata_label_color", "details_metadata_value_color",
    "details_description_color", "details_rating_color",
    "details_panel_background", "gallery_thumbnail_background",
    "gallery_border_color",

    # Table
    "table_background", "table_text_color", "table_alternate_background",

    # Stat cards
    "stat_card_total_color", "stat_card_cached_color", "stat_card_unscraped_color",
    "stat_card_active_text_color", "stat_card_inactive_label_color",

    # Cover & gallery placeholders
    "cover_placeholder_background", "gallery_placeholder_color",
    "gallery_empty_text_color", "viewer_counter_color",
    "video_widget_background", "image_viewer_background",
]

# ----------------------------------------------------------------------
# Descriptive labels and tooltips (unchanged)
# ----------------------------------------------------------------------
COLOR_LABELS = {
    "primary_color": "Primary Text & Headers",
    "secondary_color": "Buttons & Active Accents",
    "accent_color": "Important Highlights",
    "success_color": "Success Indicators",
    "warning_color": "Warnings & Attention",
    "light_bg": "Light Background Areas",
    "dark_bg": "Dark Background Areas",
    "border_color": "Borders & Separators",
    "hover_color": "Hover Background",
    "selected_color": "Selected Rows",
    "duplicate_color": "Duplicate Row Highlight",
    "played_color": "Played Row Highlight",
    "unplayed_color": "Unplayed Row Highlight",
    "favorite_color": "Favourite Row Highlight",

    "button_background": "Default Button Background",
    "button_text_color": "Standard Button Text",
    "button_hover_background": "Button Hover Background",
    "button_pressed_background": "Button Pressed Background",
    "toggle_button_color": "Toggle Button (e.g., Search & filters)",
    "splitter_handle_color": "Splitter Handles",
    "selection_text_color": "Selected Table Cell Text",
    "header_text_color": "Table Column Headers Text",
    "label_text_color": "General Labels (e.g., forms)",
    "input_background": "LineEdit / TextEdit Background",
    "ui_text_color": "UI Text (labels, menus, checkboxes)",

    "details_metadata_label_color": "Metadata Labels (e.g., 'Genres')",
    "details_metadata_value_color": "Metadata Values (e.g., 'Action')",
    "details_description_color": "Game Description Text",
    "details_rating_color": "Rating Stars & Score",
    "details_panel_background": "Details Panel Background",
    "gallery_thumbnail_background": "Gallery Thumbnail Background",
    "gallery_border_color": "Gallery Thumbnail Borders",

    "table_background": "Table Background (empty area & normal rows)",
    "table_text_color": "Table Default Text",
    "table_alternate_background": "Table Alternate Row Background",

    "stat_card_total_color": "Stat Card 'Total'",
    "stat_card_cached_color": "Stat Card 'Cached'",
    "stat_card_unscraped_color": "Stat Card 'Unscraped'",
    "stat_card_active_text_color": "Stat Card Active Text",
    "stat_card_inactive_label_color": "Stat Card Inactive Label",

    "cover_placeholder_background": "Cover Art Placeholder Background",
    "gallery_placeholder_color": "Gallery Missing Image Icon",
    "gallery_empty_text_color": "Gallery 'No Media' Text",
    "viewer_counter_color": "Image Viewer Counter Text",
    "video_widget_background": "Video Player Background",
    "image_viewer_background": "Image Viewer Background",
}

COLOR_TOOLTIPS = {
    "primary_color": "Main headings, menu bar text, and prominent labels.",
    "secondary_color": "Standard buttons, active elements, and primary accents.",
    "accent_color": "Important highlights such as the 'Clear all' filter button.",
    "success_color": "Success indicators (e.g., played status, progress bar chunks).",
    "warning_color": "Warnings and attention‑grabbing elements.",
    "light_bg": "Background for header, sidebar, and general light areas.",
    "dark_bg": "Alternate dark backgrounds (e.g., menu bar border).",
    "border_color": "Borders, separators, and frames.",
    "hover_color": "Background when hovering over interactive elements.",
    "selected_color": "Highlight colour for selected table rows.",
    "duplicate_color": "Background for cells containing duplicate titles/IDs.",
    "played_color": "Row background for games marked as played.",
    "unplayed_color": "Row background for games not yet played.",
    "favorite_color": "Row background for favourite games.",

    "button_background": "Default background of standard push buttons (Open DB, Save DB, etc.).",
    "button_text_color": "Text colour on standard push buttons.",
    "button_hover_background": "Background colour of buttons when the mouse hovers over them.",
    "button_pressed_background": "Background colour of buttons when pressed down.",
    "toggle_button_color": "Colour of toggle buttons (e.g., search/filter expand arrow).",
    "splitter_handle_color": "Colour of the splitter handles (adjustable dividers).",
    "selection_text_color": "Text colour of selected table rows.",
    "header_text_color": "Text colour of column headers in the table.",
    "label_text_color": "Default text colour for labels (e.g., in settings forms).",
    "input_background": "Background colour for line edits, text edits, and combo boxes.",
    "ui_text_color": "General text colour for labels, checkboxes, radio buttons, menus, and other UI elements (not the table).",

    "details_metadata_label_color": "Colour of field labels like 'Genres:' and 'Developer:'.",
    "details_metadata_value_color": "Colour of the actual metadata values (e.g., 'Action').",
    "details_description_color": "Colour of the game description text.",
    "details_rating_color": "Colour of rating stars and the score number.",
    "details_panel_background": "Background colour of the entire details panel.",
    "gallery_thumbnail_background": "Background of each thumbnail container.",
    "gallery_border_color": "Border colour of gallery thumbnails.",

    "table_background": "Main background of the table (empty area and normal rows).",
    "table_text_color": "Default text colour for all table cells.",
    "table_alternate_background": "Alternate row background (used when alternating rows are enabled).",

    "stat_card_total_color": "Colour of the 'Total' stat chip when active.",
    "stat_card_cached_color": "Colour of the 'Cached' stat chip when active.",
    "stat_card_unscraped_color": "Colour of the 'Unscraped' stat chip when active.",
    "stat_card_active_text_color": "Text colour for stat chips when active (usually white).",
    "stat_card_inactive_label_color": "Text colour for stat chip labels when inactive.",

    "cover_placeholder_background": "Background of the cover art placeholder (when no image loaded).",
    "gallery_placeholder_color": "Colour of the placeholder icon shown when an image fails to load.",
    "gallery_empty_text_color": "Colour of the 'No media available' text.",
    "viewer_counter_color": "Colour of the image counter (e.g., '1/5') in the full‑screen viewer.",
    "video_widget_background": "Background colour for the video player widget.",
    "image_viewer_background": "Background colour for the full‑screen image viewer.",
}

# ----------------------------------------------------------------------
# Group definitions for the UI Colors tab
# ----------------------------------------------------------------------
COLOR_GROUPS = {
    "General UI": [
        "primary_color", "secondary_color", "accent_color", "success_color",
        "warning_color", "light_bg", "dark_bg", "border_color", "hover_color"
    ],
    "Buttons & UI": [
        "button_background", "button_text_color", "button_hover_background",
        "button_pressed_background", "toggle_button_color", "splitter_handle_color",
        "header_text_color", "label_text_color", "input_background", "ui_text_color",
        "selection_text_color"
    ],
    "Table": [
        "table_background", "table_text_color", "table_alternate_background",
        "selected_color", "duplicate_color", "played_color", "unplayed_color",
        "favorite_color"
    ],
    "Details Panel": [
        "details_metadata_label_color", "details_metadata_value_color",
        "details_description_color", "details_rating_color",
        "details_panel_background"
    ],
    "Stat Cards": [
        "stat_card_total_color", "stat_card_cached_color",
        "stat_card_unscraped_color", "stat_card_active_text_color",
        "stat_card_inactive_label_color"
    ],
    "Gallery & Viewer": [
        "cover_placeholder_background", "gallery_thumbnail_background",
        "gallery_border_color", "gallery_placeholder_color",
        "gallery_empty_text_color", "viewer_counter_color",
        "video_widget_background", "image_viewer_background"
    ],
}

# All DetailsIcons keys (emoji / text) – unchanged
ICON_KEYS = [
    "icon_release", "icon_genres", "icon_modes", "icon_themes",
    "icon_developer", "icon_publisher", "icon_perspective",
    "icon_version", "icon_steam", "icon_igdb", "icon_drive",
    "icon_scene", "icon_screenshots", "icon_trailer", "icon_links",
    "icon_save", "icon_original",
    "icon_played", "icon_favourite", "icon_steamdb", "icon_pcgwiki",
    "icon_steam_link", "icon_igdb_trailers", "icon_notes", "icon_user_rating",
    "label_cover_placeholder", "label_no_screenshots",
    "label_no_save_locations", "label_no_description"
]

# ----------------------------------------------------------------------
# SettingsDialog class
# ----------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(950, 750)

        # Apply the global stylesheet and then add a local override to force spinbox arrows
        extra_style = """
        QDialog QSpinBox, QDialog QDoubleSpinBox {
            padding-right: 20px;
            min-height: 32px;
        }
        QDialog QSpinBox::up-button, QDialog QDoubleSpinBox::up-button {
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
            margin: 0px;
            padding: 0px;
            subcontrol-origin: padding;
            subcontrol-position: right top;
        }
        QDialog QSpinBox::down-button, QDialog QDoubleSpinBox::down-button {
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
            margin: 0px;
            padding: 0px;
            subcontrol-origin: padding;
            subcontrol-position: right bottom;
        }
        QDialog QSpinBox::up-arrow, QDialog QDoubleSpinBox::up-arrow,
        QDialog QSpinBox::down-arrow, QDialog QDoubleSpinBox::down-arrow {
            width: 8px;
            height: 8px;
            margin: 0px;
            padding: 0px;
        }
        """
        self.setStyleSheet(config.APP_STYLESHEET + extra_style)

        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE, encoding='utf-8')

        self._ensure_theme_sections()
        self.extra_style = extra_style

        # Load themes from external theme.ini (if exists)
        self.themes = self._load_themes_from_ini()
        self.selected_theme_name = None

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        self._create_general_tab()
        self._create_scraping_tab()
        self._create_download_tab()
        self._create_ui_colors_tab()
        self._create_sanitize_tab()
        self._create_export_tab()
        self._create_drive_scanner_tab()

        main_layout.addWidget(self.tab_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_btn = QPushButton("Apply")
        save_btn.clicked.connect(self._save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Ensure theme sections exist with default colours from config.DEFAULT_CONFIG["UI"]
    # ------------------------------------------------------------------
    def _ensure_theme_sections(self):
        """Ensure Theme1, Theme2, Theme3 sections exist with all colour keys.
        Missing keys are filled from config.DEFAULT_CONFIG['UI'].
        """
        default_colors = config.DEFAULT_CONFIG.get("UI", {})
        for idx in range(1, 4):  # Theme1, Theme2, Theme3
            section = f"Theme{idx}"
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key in COLOR_KEYS:
                if not self.config.has_option(section, key):
                    # use default from config.DEFAULT_CONFIG["UI"] if present, else "#000000"
                    default_val = default_colors.get(key, "#000000")
                    self.config.set(section, key, default_val)

        if not self.config.has_option("UI", "active_theme"):
            self.config.set("UI", "active_theme", "1")

    # ------------------------------------------------------------------
    # Load themes from theme.ini
    # ------------------------------------------------------------------
    def _load_themes_from_ini(self):
        """Parse theme.ini in the app directory and return dict of theme_name -> {color_key: hex}."""
        theme_file = BASE_DIR / "theme.ini"
        themes = {}
        if not theme_file.exists():
            return themes
        try:
            parser = configparser.ConfigParser()
            parser.read(theme_file, encoding='utf-8')
            for section in parser.sections():
                themes[section] = dict(parser.items(section))
        except Exception as e:
            print(f"Error loading theme.ini: {e}")
        return themes

    # ------------------------------------------------------------------
    # Helpers for file browsing
    # ------------------------------------------------------------------
    def _create_file_browse_row(self, line_edit, file_filter="JSON (*.json);;SQLite (*.sqlite *.db);;All files (*.*)", is_directory=False):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(line_edit)
        btn = QPushButton("Browse")
        if is_directory:
            btn.clicked.connect(lambda: self._browse_directory(line_edit))
        else:
            btn.clicked.connect(lambda: self._browse_file(line_edit, file_filter))
        layout.addWidget(btn)
        return w

    def _browse_file(self, line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", line_edit.text(), file_filter)
        if path:
            line_edit.setText(path)

    def _browse_directory(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit.text())
        if path:
            line_edit.setText(path)

    # ------------------------------------------------------------------
    # General tab (Active Theme dropdown removed)
    # ------------------------------------------------------------------
    def _create_general_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12,12,12,12)

        # ---- Top row: UI Version + Divider (no active theme) ----
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("UI Version:"))
        self.ui_version_combo = QComboBox()
        self.ui_version_combo.addItems(["UI #1", "UI #2", "UI #3"])
        current_version = self.config.getint("GUI", "ui_version", fallback=1)
        self.ui_version_combo.setCurrentIndex(current_version - 1)
        self.ui_version_combo.setToolTip("Select the GUI layout version. Restart the application for changes to take full effect.")
        top_layout.addWidget(self.ui_version_combo)

        top_layout.addSpacing(30)
        top_layout.addWidget(QLabel("Divider Percentage (%):"))
        self.divider_percentage = QSpinBox()
        self.divider_percentage.setRange(10,90)
        self.divider_percentage.setValue(self.config.getint("General","divider_percentage"))
        self.divider_percentage.setToolTip("Percentage of the main splitter allocated to the table (left) vs details panel (right).")
        top_layout.addWidget(self.divider_percentage)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)

        # ---- Details Panel ----
        details_group = QGroupBox("Details Panel")
        details_layout = QFormLayout(details_group)
        details_layout.setVerticalSpacing(6)

        self.show_thumbnails_in_details = QCheckBox()
        self.show_thumbnails_in_details.setChecked(self.config.getboolean("General", "show_thumbnails_in_details", fallback=True))
        self.show_thumbnails_in_details.setToolTip("Show/hide the entire gallery (screenshots & trailer) in the details panel.")
        details_layout.addRow("Show thumbnails:", self.show_thumbnails_in_details)

        self.details_title_font_size = QSpinBox()
        self.details_title_font_size.setRange(12,48)
        self.details_title_font_size.setValue(self.config.getint("UI","details_title_font_size", fallback=22))
        self.details_title_font_size.setToolTip("Font size (in points) for the game title in the details panel.")
        details_layout.addRow("Title font (pt):", self.details_title_font_size)

        self.details_desc_font_size = QSpinBox()
        self.details_desc_font_size.setRange(10,24)
        self.details_desc_font_size.setValue(self.config.getint("UI","details_desc_font_size", fallback=14))
        self.details_desc_font_size.setToolTip("Font size (in points) for the description text.")
        details_layout.addRow("Desc font (pt):", self.details_desc_font_size)

        self.details_rating_font_size = QSpinBox()
        self.details_rating_font_size.setRange(8,24)
        self.details_rating_font_size.setValue(self.config.getint("UI","details_rating_font_size", fallback=12))
        self.details_rating_font_size.setToolTip("Font size (in points) for the rating stars and score.")
        details_layout.addRow("Rating font (pt):", self.details_rating_font_size)

        self.details_metadata_label_font_size = QSpinBox()
        self.details_metadata_label_font_size.setRange(8,16)
        self.details_metadata_label_font_size.setValue(self.config.getint("UI","details_metadata_label_font_size", fallback=10))
        self.details_metadata_label_font_size.setToolTip("Font size (in points) for metadata field labels (e.g., 'Genres', 'Developer').")
        details_layout.addRow("Meta label font (pt):", self.details_metadata_label_font_size)

        self.details_metadata_value_font_size = QSpinBox()
        self.details_metadata_value_font_size.setRange(8,16)
        self.details_metadata_value_font_size.setValue(self.config.getint("UI","details_metadata_value_font_size", fallback=10))
        self.details_metadata_value_font_size.setToolTip("Font size (in points) for metadata values (e.g., 'Action', 'Single-player').")
        details_layout.addRow("Meta value font (pt):", self.details_metadata_value_font_size)

        self.details_section_header_font_size = QSpinBox()
        self.details_section_header_font_size.setRange(8,18)
        self.details_section_header_font_size.setValue(self.config.getint("UI","details_section_header_font_size", fallback=11))
        self.details_section_header_font_size.setToolTip("Font size (in points) for section headers (Gallery, Links, Save Locations).")
        details_layout.addRow("Section header font (pt):", self.details_section_header_font_size)

        self.details_panel_border_radius = QSpinBox()
        self.details_panel_border_radius.setRange(0,20)
        self.details_panel_border_radius.setValue(self.config.getint("UI","details_panel_border_radius", fallback=8))
        self.details_panel_border_radius.setToolTip("Corner radius (in pixels) of the details panel background.")
        details_layout.addRow("Panel border radius (px):", self.details_panel_border_radius)

        self.auto_collapse_sidebars = QCheckBox()
        self.auto_collapse_sidebars.setChecked(self.config.getboolean("General","auto_collapse_sidebars", fallback=True))
        self.auto_collapse_sidebars.setToolTip("Automatically collapse the sidebar and search/filter overlay when clicking outside them.")
        details_layout.addRow("Auto‑collapse sidebars:", self.auto_collapse_sidebars)

        grid.addWidget(details_group, 0, 0)

        # ---- Gallery ----
        gallery_group = QGroupBox("Gallery")
        gallery_layout = QFormLayout(gallery_group)
        self.thumbnail_size = QSpinBox()
        self.thumbnail_size.setRange(80,400)
        self.thumbnail_size.setValue(self.config.getint("Thumbnails","thumbnail_size", fallback=180))
        self.thumbnail_size.setToolTip("Desired width (in pixels) for each gallery thumbnail. Height is automatically set to 9/16 of this.")
        gallery_layout.addRow("Thumbnail width (px):", self.thumbnail_size)

        self.gallery_corner_radius = QSpinBox()
        self.gallery_corner_radius.setRange(0,20)
        self.gallery_corner_radius.setValue(self.config.getint("Gallery","gallery_thumbnail_corner_radius", fallback=6))
        self.gallery_corner_radius.setToolTip("Corner radius (in pixels) for each thumbnail container.")
        gallery_layout.addRow("Corner radius (px):", self.gallery_corner_radius)

        self.gallery_spacing = QSpinBox()
        self.gallery_spacing.setRange(0,30)
        self.gallery_spacing.setValue(self.config.getint("Gallery","gallery_spacing", fallback=8))
        self.gallery_spacing.setToolTip("Spacing (in pixels) between gallery items.")
        gallery_layout.addRow("Spacing (px):", self.gallery_spacing)

        self.gallery_show_trailer = QCheckBox()
        self.gallery_show_trailer.setChecked(self.config.getboolean("Gallery","gallery_show_trailer", fallback=True))
        self.gallery_show_trailer.setToolTip("If enabled, the trailer (if available) appears as the first gallery item.")
        gallery_layout.addRow("Show trailer first:", self.gallery_show_trailer)
        grid.addWidget(gallery_group, 0, 1)

        # ---- Auto Save ----
        auto_group = QGroupBox("Auto Save")
        auto_layout = QFormLayout(auto_group)
        self.auto_save = QCheckBox()
        self.auto_save.setChecked(self.config.getboolean("General","auto_save"))
        self.auto_save.setToolTip("Enable automatic saving of the database at regular intervals.")
        auto_layout.addRow("Enable Auto Save:", self.auto_save)

        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(5,600)
        self.auto_save_interval.setValue(self.config.getint("General","auto_save_interval_seconds"))
        self.auto_save_interval.setToolTip("Interval (in seconds) between auto‑saves.")
        auto_layout.addRow("Interval (seconds):", self.auto_save_interval)

        self.auto_save_path = QLineEdit()
        self.auto_save_path.setText(self.config.get("General","auto_save_path"))
        self.auto_save_path.setToolTip("Path where the database will be saved automatically. If empty, uses the default database path.")
        auto_layout.addRow("Save path:", self._create_file_browse_row(self.auto_save_path))
        grid.addWidget(auto_group, 1, 0)

        # ---- Other General ----
        other_group = QGroupBox("General Options")
        other_layout = QFormLayout(other_group)
        self.text_box_height = QSpinBox()
        self.text_box_height.setRange(20,100)
        self.text_box_height.setValue(self.config.getint("UI","text_box_height", fallback=30))
        self.text_box_height.setToolTip("Height (in pixels) of text boxes and combo boxes throughout the UI.")
        other_layout.addRow("Text Box Height (px):", self.text_box_height)

        self.default_database = QLineEdit()
        self.default_database.setText(self.config.get("General","default_database"))
        self.default_database.setToolTip("Path to the database to load automatically when the application starts. Leave blank for none.")
        other_layout.addRow("Default Database:", self._create_file_browse_row(self.default_database))

        self.auto_cache = QCheckBox()
        self.auto_cache.setChecked(self.config.getboolean("General","auto_cache"))
        self.auto_cache.setToolTip("Automatically cache images when they are viewed (download to local cache).")
        other_layout.addRow("Auto Cache:", self.auto_cache)

        self.auto_sanitize = QCheckBox()
        self.auto_sanitize.setChecked(self.config.getboolean("General","auto_sanitize"))
        self.auto_sanitize.setToolTip("Automatically sanitise imported titles (extract version, repack, etc.).")
        other_layout.addRow("Auto Sanitize:", self.auto_sanitize)

        self.show_console = QCheckBox()
        self.show_console.setChecked(self.config.getboolean("General","show_console", fallback=False))
        self.show_console.setToolTip("Show the console window when running the application (debugging).")
        other_layout.addRow("Show Console:", self.show_console)
        grid.addWidget(other_group, 1, 1)

        # ---- Cover Art Preference ----
        cover_group = QGroupBox("Cover Art Preference")
        cover_layout = QFormLayout(cover_group)
        self.cover_art_preference = QComboBox()
        self.cover_art_preference.addItems(["steam", "igdb"])
        current_pref = self.config.get("General", "cover_art_preference", fallback="steam")
        self.cover_art_preference.setCurrentText(current_pref)
        self.cover_art_preference.setToolTip("Preferred source for cover art: 'steam' or 'igdb'. Falls back to the other if not available.")
        cover_layout.addRow("Preferred source:", self.cover_art_preference)
        grid.addWidget(cover_group, 2, 0, 1, 1)

        # ---- Details Icons (spans both columns) ----
        icons_group = QGroupBox("Details Icons (emojis / symbols)")
        icons_layout = QGridLayout(icons_group)
        icons_layout.setHorizontalSpacing(20)
        self.icon_edits = {}
        row, col = 0, 0
        for key in ICON_KEYS:
            label = QLabel(key.replace("icon_","").replace("label_","").replace("_"," ").title())
            edit = QLineEdit()
            edit.setText(self.config.get("DetailsIcons", key, fallback=""))
            edit.setFixedWidth(80)
            edit.setToolTip(f"Enter the emoji or text to display for '{key}'.")
            icons_layout.addWidget(label, row, col*2, 1, 1)
            icons_layout.addWidget(edit, row, col*2+1, 1, 1)
            self.icon_edits[key] = edit
            col += 1
            if col >= 4:
                col = 0
                row += 1
        icons_layout.setRowStretch(row+1, 1)
        grid.addWidget(icons_group, 3, 0, 1, 2)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "General")

    # ------------------------------------------------------------------
    # Scraping tab
    # ------------------------------------------------------------------
    def _create_scraping_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(12,12,12,12)

        scraping_group = QGroupBox("Scraping Settings")
        scraping_layout = QFormLayout(scraping_group)
        scraping_layout.setVerticalSpacing(10)

        self.auto_accept_score = QSpinBox()
        self.auto_accept_score.setRange(0,100)
        self.auto_accept_score.setValue(self.config.getint("Scraping","auto_accept_score"))
        self.auto_accept_score.setToolTip("Confidence score threshold (0‑100) above which metadata is automatically applied without user confirmation.")
        scraping_layout.addRow("Auto Accept Score:", self.auto_accept_score)

        self.fetch_pcgw_save = QCheckBox()
        self.fetch_pcgw_save.setChecked(self.config.getboolean("Scraping","fetch_pcgw_save"))
        self.fetch_pcgw_save.setToolTip("Attempt to fetch savegame locations from PCGamingWiki during scraping.")
        scraping_layout.addRow("Fetch PCGW Save Locations:", self.fetch_pcgw_save)

        self.chunk_size = QSpinBox()
        self.chunk_size.setRange(1,500)
        self.chunk_size.setValue(self.config.getint("Scraping","chunk_size"))
        self.chunk_size.setToolTip("Number of games to process in each batch during bulk scraping.")
        scraping_layout.addRow("Chunk Size:", self.chunk_size)

        self.stall_timeout = QSpinBox()
        self.stall_timeout.setRange(5,300)
        self.stall_timeout.setValue(self.config.getint("Scraping","stall_timeout"))
        self.stall_timeout.setToolTip("Timeout (in seconds) for network operations during scraping.")
        scraping_layout.addRow("Stall Timeout (seconds):", self.stall_timeout)

        self.max_concurrent_scrapes = QSpinBox()
        self.max_concurrent_scrapes.setRange(1,10)
        self.max_concurrent_scrapes.setValue(self.config.getint("Scraping","max_concurrent_scrapes"))
        self.max_concurrent_scrapes.setToolTip("Maximum number of games to scrape simultaneously (higher = faster but more network load).")
        scraping_layout.addRow("Max Concurrent Scrapes:", self.max_concurrent_scrapes)

        main_layout.addWidget(scraping_group)

        # API group
        api_group = QGroupBox("API Settings")
        api_layout = QFormLayout(api_group)
        self.steam_search_api = QLineEdit()
        self.steam_search_api.setText(self.config.get("API","steam_search_api"))
        self.steam_search_api.setToolTip("Steam Store search API endpoint.")
        api_layout.addRow("Steam Search API:", self.steam_search_api)

        self.steam_store_app_url = QLineEdit()
        self.steam_store_app_url.setText(self.config.get("API","steam_store_app_url"))
        self.steam_store_app_url.setToolTip("Steam Store page URL template (use {appid}).")
        api_layout.addRow("Steam Store App URL:", self.steam_store_app_url)

        self.steamdb_app_url = QLineEdit()
        self.steamdb_app_url.setText(self.config.get("API","steamdb_app_url"))
        self.steamdb_app_url.setToolTip("SteamDB page URL template (use {appid}).")
        api_layout.addRow("SteamDB App URL:", self.steamdb_app_url)

        self.pcgw_search_template = QLineEdit()
        self.pcgw_search_template.setText(self.config.get("API","pcgw_search_template"))
        self.pcgw_search_template.setToolTip("PCGamingWiki search URL template (use {q}).")
        api_layout.addRow("PCGW Search Template:", self.pcgw_search_template)

        self.igdb_url_template = QLineEdit()
        self.igdb_url_template.setText(self.config.get("API","igdb_url_template"))
        self.igdb_url_template.setToolTip("IGDB game page URL template (use {slug}).")
        api_layout.addRow("IGDB URL Template:", self.igdb_url_template)

        self.http_timeout = QDoubleSpinBox()
        self.http_timeout.setRange(1,60)
        self.http_timeout.setSingleStep(0.5)
        self.http_timeout.setValue(self.config.getfloat("API","http_timeout"))
        self.http_timeout.setToolTip("HTTP request timeout in seconds.")
        api_layout.addRow("HTTP Timeout (seconds):", self.http_timeout)

        self.http_retries = QSpinBox()
        self.http_retries.setRange(0,10)
        self.http_retries.setValue(self.config.getint("API","http_retries"))
        self.http_retries.setToolTip("Number of retries for failed HTTP requests.")
        api_layout.addRow("HTTP Retries:", self.http_retries)

        self.sleep_between_requests = QDoubleSpinBox()
        self.sleep_between_requests.setRange(0,5)
        self.sleep_between_requests.setSingleStep(0.05)
        self.sleep_between_requests.setValue(self.config.getfloat("API","sleep_between_requests"))
        self.sleep_between_requests.setToolTip("Delay (in seconds) between consecutive API requests to avoid rate limiting.")
        api_layout.addRow("Sleep Between Requests:", self.sleep_between_requests)

        self.igdb_image_base_url = QLineEdit()
        self.igdb_image_base_url.setText(self.config.get("API","igdb_image_base_url"))
        self.igdb_image_base_url.setToolTip("Base URL for IGDB images.")
        api_layout.addRow("IGDB Image Base URL:", self.igdb_image_base_url)

        self.igdb_screenshot_size = QLineEdit()
        self.igdb_screenshot_size.setText(self.config.get("API","igdb_screenshot_size"))
        self.igdb_screenshot_size.setToolTip("Size qualifier for IGDB screenshots (e.g., t_720p).")
        api_layout.addRow("IGDB Screenshot Size:", self.igdb_screenshot_size)

        self.igdb_cover_size = QLineEdit()
        self.igdb_cover_size.setText(self.config.get("API","igdb_cover_size"))
        self.igdb_cover_size.setToolTip("Size qualifier for IGDB cover art (e.g., t_cover_big).")
        api_layout.addRow("IGDB Cover Size:", self.igdb_cover_size)

        self.igdb_client_id = QLineEdit()
        self.igdb_client_id.setText(self.config.get("API","igdb_client_id"))
        self.igdb_client_id.setToolTip("IGDB API Client ID.")
        api_layout.addRow("IGDB Client ID:", self.igdb_client_id)

        self.igdb_client_secret = QLineEdit()
        self.igdb_client_secret.setText(self.config.get("API","igdb_client_secret"))
        self.igdb_client_secret.setToolTip("IGDB API Client Secret.")
        api_layout.addRow("IGDB Client Secret:", self.igdb_client_secret)

        self.igdb_access_token = QLineEdit()
        self.igdb_access_token.setText(self.config.get("API","igdb_access_token"))
        self.igdb_access_token.setToolTip("IGDB API Access Token (optional, auto‑generated if empty).")
        api_layout.addRow("IGDB Access Token:", self.igdb_access_token)

        main_layout.addWidget(api_group)
        main_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Scraping")

    # ------------------------------------------------------------------
    # Download tab
    # ------------------------------------------------------------------
    def _create_download_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(12,12,12,12)

        download_group = QGroupBox("Download Settings")
        dl_layout = QFormLayout(download_group)
        self.max_images_to_download = QSpinBox()
        self.max_images_to_download.setRange(1,20)
        self.max_images_to_download.setValue(self.config.getint("Download","max_images_to_download"))
        self.max_images_to_download.setToolTip("Maximum number of screenshots to download per game.")
        dl_layout.addRow("Max Images to Download:", self.max_images_to_download)

        self.max_images_to_display = QSpinBox()
        self.max_images_to_display.setRange(1,20)
        self.max_images_to_display.setValue(self.config.getint("Download","max_images_to_display"))
        self.max_images_to_display.setToolTip("Maximum number of screenshots to display in the gallery.")
        dl_layout.addRow("Max Images to Display:", self.max_images_to_display)

        self.max_microtrailers = QSpinBox()
        self.max_microtrailers.setRange(0,5)
        self.max_microtrailers.setValue(self.config.getint("Download","max_microtrailers"))
        self.max_microtrailers.setToolTip("Maximum number of microtrailers (short videos) to download per game.")
        dl_layout.addRow("Max Microtrailers per Game:", self.max_microtrailers)

        self.max_trailers = QSpinBox()
        self.max_trailers.setRange(0,10)
        self.max_trailers.setValue(self.config.getint("Download","max_trailers"))
        self.max_trailers.setToolTip("Maximum number of full trailer links to display in the details panel.")
        dl_layout.addRow("Max Trailer Links:", self.max_trailers)

        self.debug_images = QCheckBox()
        self.debug_images.setChecked(self.config.getboolean("Download","debug_images"))
        self.debug_images.setToolTip("Enable debug logging for image downloads.")
        dl_layout.addRow("Debug Images:", self.debug_images)

        self.video_loop_enabled = QCheckBox()
        self.video_loop_enabled.setChecked(self.config.getboolean("Download","video_loop_enabled"))
        self.video_loop_enabled.setToolTip("Automatically loop video playback in the gallery.")
        dl_layout.addRow("Video Loop Enabled:", self.video_loop_enabled)

        self.max_concurrent_downloads = QSpinBox()
        self.max_concurrent_downloads.setRange(1,10)
        self.max_concurrent_downloads.setValue(self.config.getint("Download","max_concurrent_downloads"))
        self.max_concurrent_downloads.setToolTip("Maximum number of simultaneous downloads (higher = faster but more bandwidth).")
        dl_layout.addRow("Max Concurrent Downloads:", self.max_concurrent_downloads)
        main_layout.addWidget(download_group)

        cache_group = QGroupBox("Cache")
        cache_layout = QFormLayout(cache_group)
        self.cache_min_kb = QSpinBox()
        self.cache_min_kb.setRange(1,100)
        self.cache_min_kb.setValue(self.config.getint("General","cache_min_kb"))
        self.cache_min_kb.setToolTip("Minimum file size (in KB) to consider for caching (ignore very small files).")
        cache_layout.addRow("Cache Min KB:", self.cache_min_kb)

        self.cache_max_kb = QSpinBox()
        self.cache_max_kb.setRange(100,50000)
        self.cache_max_kb.setValue(self.config.getint("General","cache_max_kb"))
        self.cache_max_kb.setToolTip("Maximum file size (in KB) to cache (skip very large files).")
        cache_layout.addRow("Cache Max KB:", self.cache_max_kb)

        self.cache_dir_override = QLineEdit()
        self.cache_dir_override.setText(self.config.get("Cache","cache_dir_override"))
        self.cache_dir_override.setToolTip("Override the default cache directory (leave empty to use the default ./cache).")
        cache_layout.addRow("Cache Directory:", self._create_file_browse_row(self.cache_dir_override, is_directory=True))
        main_layout.addWidget(cache_group)
        main_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Download")

    # ------------------------------------------------------------------
    # UI Colors tab – two columns: active (editable) + external preview
    # ------------------------------------------------------------------
    def _create_ui_colors_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ----- Dropdown + buttons (unchanged) -----
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Theme from theme.ini:"))
        self.theme_combo = QComboBox()
        if self.themes:
            self.theme_combo.addItems(list(self.themes.keys()))
            self.theme_combo.setToolTip("Select a theme from the external theme.ini file.")
        else:
            self.theme_combo.addItem("No theme.ini found")
            self.theme_combo.setEnabled(False)
            self.theme_combo.setToolTip("Create a theme.ini file in the application directory with theme sections.")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected_dropdown)
        selector_layout.addWidget(self.theme_combo)

        self.apply_theme_btn = QPushButton("Apply Selected Theme")
        self.apply_theme_btn.setToolTip("Copy the selected theme's colours into the active theme pickers (you can then tweak them).")
        self.apply_theme_btn.clicked.connect(self._apply_selected_theme_to_pickers)
        selector_layout.addWidget(self.apply_theme_btn)

        self.reset_default_btn = QPushButton("Reset to Default")
        self.reset_default_btn.setToolTip("Reset the active theme's colour pickers to the application default values.")
        self.reset_default_btn.clicked.connect(self._reset_to_default)
        selector_layout.addWidget(self.reset_default_btn)

        selector_layout.addStretch()
        main_layout.addLayout(selector_layout)

        # ----- Two columns -----
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)

        # Left: Active theme with editable color pickers
        left_group = QGroupBox("Active Theme (editable)")
        left_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        left_container = QWidget()
        left_layout = QGridLayout(left_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(4)
        scroll_left = QScrollArea()
        scroll_left.setWidgetResizable(True)
        scroll_left.setWidget(left_container)
        left_group.setLayout(QVBoxLayout())
        left_group.layout().addWidget(scroll_left)

        # Right: Preview of selected theme from dropdown
        right_group = QGroupBox("Selected Theme Preview")
        right_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        right_container = QWidget()
        right_layout = QGridLayout(right_container)
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(4)
        scroll_right = QScrollArea()
        scroll_right.setWidgetResizable(True)
        scroll_right.setWidget(right_container)
        right_group.setLayout(QVBoxLayout())
        right_group.layout().addWidget(scroll_right)

        columns_layout.addWidget(left_group, 1)
        columns_layout.addWidget(right_group, 1)
        main_layout.addLayout(columns_layout, 1)

        # Store references
        self.active_pickers_container = left_container
        self.active_pickers_layout = left_layout
        self.preview_container = right_container
        self.preview_layout = right_layout

        # Build the active pickers (grouped)
        self.color_pickers = {}
        self._build_active_pickers()

        # Build initial preview
        self._refresh_preview()

        # ----- Desaturation (common) -----
        desat_layout = QHBoxLayout()
        desat_layout.addWidget(QLabel("Row Highlight Desaturation (%):"))
        self.highlight_desaturate_spin = QSpinBox()
        self.highlight_desaturate_spin.setRange(0,100)
        self.highlight_desaturate_spin.setSuffix("%")
        _active_for_desat = self.config.getint("UI", "active_theme", fallback=1)
        _desat_default = self.config.getint("UI", "highlight_desaturate_percent", fallback=20)
        self.highlight_desaturate_spin.setValue(
            self.config.getint(f"Theme{_active_for_desat}", "highlight_desaturate_percent", fallback=_desat_default)
        )
        self.highlight_desaturate_spin.setToolTip(
            "Desaturation percentage for row highlight colours (0 = full colour, 100 = grey).\n"
            "This is saved per theme, not globally: dark themes generally need a low value "
            "(their preset default is 0%) so highlighted rows stay readable, while light "
            "themes can usually take more desaturation for a softer look."
        )
        desat_layout.addWidget(self.highlight_desaturate_spin)
        desat_layout.addStretch()
        main_layout.addLayout(desat_layout)

        main_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "UI Colors")

    # ------------------------------------------------------------------
    # Build active pickers – now using COLOR_GROUPS
    # ------------------------------------------------------------------
    def _build_active_pickers(self):
        self._clear_layout(self.active_pickers_layout)
        self.color_pickers.clear()

        active = self.config.getint("UI", "active_theme", fallback=1)
        section = f"Theme{active}"

        row = 0
        col = 0
        max_cols = 4

        for group_name, keys in COLOR_GROUPS.items():
            # Group label
            label = QLabel(group_name)
            label.setStyleSheet("font-weight: bold; color: #555; margin-top: 8px;")
            self.active_pickers_layout.addWidget(label, row, 0, 1, max_cols * 2)
            row += 1

            col = 0
            for key in keys:
                current = self.config.get(section, key, fallback="#000000")
                btn = QPushButton()
                btn.setFixedSize(40, 25)
                btn.setStyleSheet(f"background-color: {current}; border: 1px solid gray;")
                btn.setProperty("color_key", key)
                btn.clicked.connect(lambda checked, b=btn: self._pick_color_for_active(b))

                label_text = COLOR_LABELS.get(key, key.replace("_", " ").title())
                tooltip = COLOR_TOOLTIPS.get(key, f"Colour for '{key}'")
                btn.setToolTip(tooltip)

                lbl = QLabel(label_text)
                lbl.setWordWrap(True)

                self.active_pickers_layout.addWidget(lbl, row, col * 2, 1, 1)
                self.active_pickers_layout.addWidget(btn, row, col * 2 + 1, 1, 1)
                self.color_pickers[key] = btn

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            # Add a small spacer after each group
            row += 1

        self.active_pickers_layout.setRowStretch(row, 1)

    # ------------------------------------------------------------------
    # Color picker dialog for active theme
    # ------------------------------------------------------------------
    def _pick_color_for_active(self, button):
        key = button.property("color_key")
        current = button.styleSheet().split("background-color:")[1].split(";")[0].strip()
        color = QColorDialog.getColor(QColor(current), self, f"Select {key}")
        if color.isValid():
            hex_color = color.name()
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid gray;")

    # ------------------------------------------------------------------
    # Reset to application default colours (from config.DEFAULT_CONFIG["UI"])
    # ------------------------------------------------------------------
    def _reset_to_default(self):
        default_colors = config.DEFAULT_CONFIG.get("UI", {})
        for key, btn in self.color_pickers.items():
            default_val = default_colors.get(key, "#000000")
            btn.setStyleSheet(f"background-color: {default_val}; border: 1px solid gray;")
        default_desat = default_colors.get("highlight_desaturate_percent", "20")
        try:
            self.highlight_desaturate_spin.setValue(int(float(default_desat)))
        except (ValueError, TypeError):
            pass
        QMessageBox.information(self, "Reset", "Active theme colours have been reset to the application defaults.")

    # ------------------------------------------------------------------
    # Build the preview of the selected external theme
    # ------------------------------------------------------------------
    def _build_preview(self, theme_name=None):
        self._clear_layout(self.preview_layout)
        if not self.themes or not theme_name or theme_name not in self.themes:
            placeholder = QLabel("No theme selected or theme.ini missing.")
            placeholder.setAlignment(Qt.AlignCenter)
            self.preview_layout.addWidget(placeholder, 0, 0)
            return

        theme_colors = self.themes[theme_name]
        row = 0
        col = 0
        max_cols = 4

        for group_name, keys in COLOR_GROUPS.items():
            # Group label
            lbl_group = QLabel(group_name)
            lbl_group.setStyleSheet("font-weight: bold; color: #555; margin-top: 6px;")
            self.preview_layout.addWidget(lbl_group, row, 0, 1, max_cols * 2)
            row += 1

            col = 0
            for key in keys:
                color = theme_colors.get(key, "#000000")
                label_text = COLOR_LABELS.get(key, key.replace("_", " ").title())

                swatch = QLabel()
                swatch.setFixedSize(24, 24)
                swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #888; border-radius: 3px;")
                swatch.setToolTip(f"{label_text}\n{color}")

                lbl = QLabel(label_text)
                lbl.setWordWrap(True)
                lbl.setToolTip(f"{label_text}\n{color}")

                self.preview_layout.addWidget(swatch, row, col * 2, 1, 1, Qt.AlignCenter)
                self.preview_layout.addWidget(lbl, row, col * 2 + 1, 1, 1, Qt.AlignLeft | Qt.AlignVCenter)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            row += 1   # spacer after each group

        # Row highlight desaturation is theme-specific too (see theme.ini) --
        # show it here so it's visible before "Apply Selected Theme" is clicked.
        if "highlight_desaturate_percent" in theme_colors:
            desat_lbl = QLabel(f"Row Highlight Desaturation: {theme_colors['highlight_desaturate_percent']}%")
            desat_lbl.setStyleSheet("font-weight: bold; color: #555; margin-top: 4px;")
            desat_lbl.setToolTip(
                "Dark themes ship with 0% (fully saturated) so highlighted rows stay legible "
                "against light table text; light themes can afford more desaturation."
            )
            self.preview_layout.addWidget(desat_lbl, row, 0, 1, max_cols * 2)
            row += 1

        self.preview_layout.setRowStretch(row, 1)

    def _refresh_preview(self):
        if self.themes and self.theme_combo.count() > 0:
            current = self.theme_combo.currentText()
            self._build_preview(current)
        else:
            self._build_preview(None)

    # ------------------------------------------------------------------
    # Apply selected theme to active pickers
    def _apply_selected_theme_to_pickers(self):
        if not self.themes or not self.theme_combo.currentText():
            QMessageBox.information(self, "No theme", "No external theme selected or theme.ini missing.")
            return
        theme_name = self.theme_combo.currentText()
        if theme_name not in self.themes:
            return
        colors = self.themes[theme_name]

        # 1. Update the active theme section in the in‑memory config
        active = self.config.getint("UI", "active_theme", fallback=1)
        section = f"Theme{active}"
        for key in COLOR_KEYS:
            if key in colors:
                self.config.set(section, key, colors[key])

        # 2. Update the color picker buttons to reflect the new colours
        for key, btn in self.color_pickers.items():
            if key in colors:
                btn.setStyleSheet(f"background-color: {colors[key]}; border: 1px solid gray;")
            # If the key is missing, leave it unchanged (or set a default)

        # 3. Row highlight desaturation is also theme-specific (see theme.ini) --
        #    dark themes ship with a low/0% default so highlighted rows stay
        #    saturated and legible; light themes can take more desaturation.
        if "highlight_desaturate_percent" in colors:
            try:
                desat_val = int(float(colors["highlight_desaturate_percent"]))
                self.config.set(section, "highlight_desaturate_percent", str(desat_val))
                self.highlight_desaturate_spin.setValue(desat_val)
            except (ValueError, TypeError):
                pass

        QMessageBox.information(self, "Theme applied",
            f"Colours from '{theme_name}' have been copied to the active theme pickers.\n"
            "You can now tweak them further and click Save to write them to disk.")

    # ------------------------------------------------------------------
    # Slot for dropdown selection
    # ------------------------------------------------------------------
    def _on_theme_selected_dropdown(self, index):
        if index < 0 or not self.themes:
            return
        self.selected_theme_name = self.theme_combo.currentText()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Clear a layout (helper)
    # ------------------------------------------------------------------
    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # ------------------------------------------------------------------
    # Sanitize tab
    # ------------------------------------------------------------------
    def _create_sanitize_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12,12,12,12)

        self.repack_list = QTextEdit()
        self.repack_list.setPlainText(self._comma_to_lines(self.config.get("Sanitize","repack_list")))
        self.repack_list.setFixedHeight(120)
        self.repack_list.setToolTip("List of repack names (one per line) to detect during title sanitising.")
        layout.addRow("Repack List (one per line):", self.repack_list)

        self.edition_tokens = QTextEdit()
        self.edition_tokens.setPlainText(self._comma_to_lines(self.config.get("Sanitize","edition_tokens")))
        self.edition_tokens.setFixedHeight(120)
        self.edition_tokens.setToolTip("Edition tokens (e.g., 'Deluxe', 'GOTY') to remove from titles (one per line).")
        layout.addRow("Edition Tokens (one per line):", self.edition_tokens)

        self.emulator_tokens = QTextEdit()
        self.emulator_tokens.setPlainText(self._comma_to_lines(self.config.get("Sanitize","emulator_tokens")))
        self.emulator_tokens.setFixedHeight(120)
        self.emulator_tokens.setToolTip("Emulator names/tokens to detect in folder names (one per line).")
        layout.addRow("Emulator Tokens (one per line):", self.emulator_tokens)

        self.mode_keywords = QTextEdit()
        self.mode_keywords.setPlainText(self.config.get("Sanitize","mode_keywords"))
        self.mode_keywords.setFixedHeight(80)
        self.mode_keywords.setToolTip("JSON mapping of mode names to keyword lists (e.g., {'Multiplayer': ['multiplayer','mp']}).")
        layout.addRow("Mode Keywords (JSON):", self.mode_keywords)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Sanitize")

    # ------------------------------------------------------------------
    # Export tab
    # ------------------------------------------------------------------
    def _create_export_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(12,12,12,12)

        # Asset Export
        asset_group = QGroupBox("Asset Export (to game folders)")
        asset_layout = QFormLayout(asset_group)
        self.artbox_name = QLineEdit()
        self.artbox_name.setText(self.config.get("AssetExport","artbox_name"))
        self.artbox_name.setToolTip("Filename for the cover art image when exporting to game folders.")
        asset_layout.addRow("Artbox Filename:", self.artbox_name)

        self.trailer_name = QLineEdit()
        self.trailer_name.setText(self.config.get("AssetExport","trailer_name"))
        self.trailer_name.setToolTip("Base filename for trailer videos (e.g., 'trailer' → trailer.mp4).")
        asset_layout.addRow("Trailer Base Filename:", self.trailer_name)
        main_layout.addWidget(asset_group)

        # Common export settings
        common_group = QGroupBox("General Export Settings (PDF/HTML)")
        common_layout = QFormLayout(common_group)
        self.desc_lines = QSpinBox()
        self.desc_lines.setRange(1,20)
        self.desc_lines.setValue(self.config.getint("Export","description_lines"))
        self.desc_lines.setToolTip("Number of description lines to include in PDF/HTML exports.")
        common_layout.addRow("Description Lines:", self.desc_lines)

        self.export_thumbnails_cb = QCheckBox("Include cover thumbnails in Title column (HTML)")
        self.export_thumbnails_cb.setChecked(self.config.getboolean("Export","export_thumbnails", fallback=False))
        self.export_thumbnails_cb.setToolTip("If checked, the HTML export will embed small cover thumbnails next to each game title.")
        common_layout.addRow(self.export_thumbnails_cb)

        size_layout = QHBoxLayout()
        self.thumbnail_width_spin = QSpinBox()
        self.thumbnail_width_spin.setRange(16,256)
        self.thumbnail_width_spin.setValue(self.config.getint("Export","export_thumbnail_width", fallback=32))
        self.thumbnail_width_spin.setSuffix(" px")
        self.thumbnail_width_spin.setToolTip("Width of cover thumbnails in HTML export.")
        self.thumbnail_height_spin = QSpinBox()
        self.thumbnail_height_spin.setRange(16,256)
        self.thumbnail_height_spin.setValue(self.config.getint("Export","export_thumbnail_height", fallback=32))
        self.thumbnail_height_spin.setSuffix(" px")
        self.thumbnail_height_spin.setToolTip("Height of cover thumbnails in HTML export.")
        size_layout.addWidget(QLabel("Width:")); size_layout.addWidget(self.thumbnail_width_spin)
        size_layout.addWidget(QLabel("Height:")); size_layout.addWidget(self.thumbnail_height_spin)
        size_layout.addStretch()
        common_layout.addRow("Thumbnail size (for HTML export):", size_layout)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A3 Landscape", "A4 Landscape", "Letter Landscape"])
        self.page_size_combo.setCurrentText(self.config.get("Export","pdf_page_size", fallback="A3 Landscape"))
        self.page_size_combo.setToolTip("Page size and orientation for PDF export.")
        common_layout.addRow("PDF Page Size:", self.page_size_combo)
        main_layout.addWidget(common_group)

        # Columns selection
        columns_group = QGroupBox("Export Columns")
        columns_layout = QVBoxLayout(columns_group)
        self.available_columns = [
            ("title","Title"), ("app_id","Steam ID"), ("igdb_id","IGDB ID"),
            ("release_date","Release Date"), ("description","Description"),
            ("game_modes","Modes"), ("genres","Genre"), ("themes","Themes"),
            ("player_perspective","Perspective"), ("developer","Developer"),
            ("publisher","Publisher"), ("game_drive","Drive"),
            ("scene_repack","Repack"), ("original_title","Orgtitle"),
            ("resources","Resources"), ("links","External Links"),
            ("savegame_location","Save Location")
        ]
        saved_selected = self.config.get("ExportColumns","selected", fallback="title,app_id,igdb_id,genres,themes,description,game_modes,game_drive,original_title,trailer_webm,screenshots,steam_link")
        selected_keys = set(saved_selected.split(","))

        self.export_col_checkboxes = {}
        self.export_col_widths = {}
        self.export_col_headers = {}

        scroll_widget = QWidget()
        scroll_widget.setAttribute(Qt.WA_TranslucentBackground, True)
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(6)
        for key, default_header in self.available_columns:
            row = QHBoxLayout()
            cb = QCheckBox(default_header)
            cb.setChecked(key in selected_keys)
            cb.setMinimumWidth(150)
            cb.setToolTip(f"Include '{default_header}' column in export.")
            width_spin = QSpinBox()
            width_spin.setRange(1,50)
            width_spin.setValue(self.config.getint("ExportColumns", f"width_{key}", fallback=8 if key=="description" else 5))
            width_spin.setSuffix("%")
            width_spin.setToolTip("Relative width percentage for this column.")
            header_edit = QLineEdit()
            header_edit.setText(self.config.get("ExportColumns", f"header_{key}", fallback=default_header))
            header_edit.setPlaceholderText(default_header)
            header_edit.setToolTip("Custom header text for the column.")
            row.addWidget(cb,2)
            row.addWidget(QLabel("Width:"),1)
            row.addWidget(width_spin,1)
            row.addWidget(QLabel("Header:"),1)
            row.addWidget(header_edit,3)
            scroll_layout.addLayout(row)
            self.export_col_checkboxes[key] = cb
            self.export_col_widths[key] = width_spin
            self.export_col_headers[key] = header_edit

        # Link types
        link_box = QGroupBox("Link types to include (when 'Links' column selected)")
        link_inner = QHBoxLayout(link_box)
        self.links_steam = QCheckBox("Steam")
        self.links_steam.setChecked(self.config.getboolean("ExportColumns","links_steam", fallback=True))
        self.links_steam.setToolTip("Include Steam store link.")
        self.links_igdb = QCheckBox("IGDB")
        self.links_igdb.setChecked(self.config.getboolean("ExportColumns","links_igdb", fallback=True))
        self.links_igdb.setToolTip("Include IGDB game link.")
        self.links_pcgw = QCheckBox("PCGW")
        self.links_pcgw.setChecked(self.config.getboolean("ExportColumns","links_pcgw", fallback=True))
        self.links_pcgw.setToolTip("Include PCGamingWiki link.")
        self.links_steamdb = QCheckBox("SteamDB")
        self.links_steamdb.setChecked(self.config.getboolean("ExportColumns","links_steamdb", fallback=True))
        self.links_steamdb.setToolTip("Include SteamDB link.")
        link_inner.addWidget(self.links_steam)
        link_inner.addWidget(self.links_igdb)
        link_inner.addWidget(self.links_pcgw)
        link_inner.addWidget(self.links_steamdb)
        link_inner.addStretch()
        scroll_layout.addWidget(link_box)
        scroll_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)
        columns_layout.addWidget(scroll_area)

        note_label = QLabel("Widths are percentages; sum should be ~100%. Steam/IGDB/Resources are hyperlinked.")
        note_label.setWordWrap(True)
        note_label.setStyleSheet(f"color: {config.BORDER_COLOR}; font-size: 10px; margin-top: 4px;")
        columns_layout.addWidget(note_label)

        main_layout.addWidget(columns_group)
        main_layout.addStretch()

        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setWidget(tab)
        self.tab_widget.addTab(outer_scroll, "Export")

    # ------------------------------------------------------------------
    # DriveScanner tab
    # ------------------------------------------------------------------
    def _create_drive_scanner_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setVerticalSpacing(10)
        layout.setContentsMargins(12,12,12,12)
        self.drive_tokens = QLineEdit()
        self.drive_tokens.setText(self.config.get("DriveScanner","drive_tokens"))
        self.drive_tokens.setToolTip("Comma‑separated list of folder names to scan for games (e.g., 'Game,Game_Drive').")
        layout.addRow("Drive Tokens (comma separated):", self.drive_tokens)

        self.drive_number_pattern = QLineEdit()
        self.drive_number_pattern.setText(self.config.get("DriveScanner","drive_number_pattern"))
        self.drive_number_pattern.setToolTip("Regular expression to extract drive numbers from folder names (e.g., '(\\d+)$' for trailing digits).")
        layout.addRow("Drive Number Pattern (regex):", self.drive_number_pattern)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Drive Scanner")

    # ------------------------------------------------------------------
    # Save settings – active theme taken from config
    # ------------------------------------------------------------------
    def _save_settings(self):
        try:
            # ------------------------------------------------------------
            # DETECT CHANGES THAT REQUIRE A RESTART
            # ------------------------------------------------------------
            old_colors = {}
            active = self.config.getint("UI", "active_theme", fallback=1)
            section = f"Theme{active}"
            for key in self.color_pickers:
                if self.config.has_option(section, key):
                    old_colors[key] = self.config.get(section, key)

            old_ui_version = self.config.getint("GUI", "ui_version", fallback=1)
            new_ui_version = self.ui_version_combo.currentIndex() + 1

            requires_restart = False
            if old_ui_version != new_ui_version:
                requires_restart = True

            for key, btn in self.color_pickers.items():
                new_color = btn.styleSheet().split("background-color:")[1].split(";")[0].strip()
                if old_colors.get(key) != new_color:
                    requires_restart = True
                    break

            # ---- General ----
            self.config.set("General", "cache_min_kb", str(self.cache_min_kb.value()))
            self.config.set("General", "cache_max_kb", str(self.cache_max_kb.value()))
            self.config.set("General", "divider_percentage", str(self.divider_percentage.value()))
            self.config.set("General", "default_database", self.default_database.text())
            self.config.set("General", "auto_save", str(self.auto_save.isChecked()))
            self.config.set("General", "auto_save_interval_seconds", str(self.auto_save_interval.value()))
            self.config.set("General", "auto_save_path", self.auto_save_path.text())
            self.config.set("General", "auto_cache", str(self.auto_cache.isChecked()))
            self.config.set("General", "auto_sanitize", str(self.auto_sanitize.isChecked()))
            self.config.set("General", "show_console", str(self.show_console.isChecked()))
            self.config.set("General", "show_thumbnails_in_details", str(self.show_thumbnails_in_details.isChecked()))
            self.config.set("General", "auto_collapse_sidebars", str(self.auto_collapse_sidebars.isChecked()))
            self.config.set("General", "cover_art_preference", self.cover_art_preference.currentText())

            # ---- Details UI font sizes & border radius ----
            self.config.set("UI", "details_title_font_size", str(self.details_title_font_size.value()))
            self.config.set("UI", "details_desc_font_size", str(self.details_desc_font_size.value()))
            self.config.set("UI", "details_rating_font_size", str(self.details_rating_font_size.value()))
            self.config.set("UI", "details_metadata_label_font_size", str(self.details_metadata_label_font_size.value()))
            self.config.set("UI", "details_metadata_value_font_size", str(self.details_metadata_value_font_size.value()))
            self.config.set("UI", "details_section_header_font_size", str(self.details_section_header_font_size.value()))
            self.config.set("UI", "details_panel_border_radius", str(self.details_panel_border_radius.value()))
            self.config.set("UI", "text_box_height", str(self.text_box_height.value()))
            # NOTE: row highlight desaturation is saved per-theme below (with the
            # rest of the active theme's colours), not globally in [UI] anymore --
            # each theme carries its own value in theme.ini.

            # ---- Thumbnails & Gallery ----
            self.config.set("Thumbnails", "thumbnail_size", str(self.thumbnail_size.value()))
            self.config.set("Gallery", "gallery_thumbnail_corner_radius", str(self.gallery_corner_radius.value()))
            self.config.set("Gallery", "gallery_spacing", str(self.gallery_spacing.value()))
            self.config.set("Gallery", "gallery_show_trailer", str(self.gallery_show_trailer.isChecked()))

            # ---- Details Icons ----
            if not self.config.has_section("DetailsIcons"):
                self.config.add_section("DetailsIcons")
            for key, edit in self.icon_edits.items():
                self.config.set("DetailsIcons", key, edit.text())

            # ---- Scraping ----
            self.config.set("Scraping", "auto_accept_score", str(self.auto_accept_score.value()))
            self.config.set("Scraping", "fetch_pcgw_save", str(self.fetch_pcgw_save.isChecked()))
            self.config.set("Scraping", "chunk_size", str(self.chunk_size.value()))
            self.config.set("Scraping", "stall_timeout", str(self.stall_timeout.value()))
            self.config.set("Scraping", "max_concurrent_scrapes", str(self.max_concurrent_scrapes.value()))

            # ---- Download ----
            self.config.set("Download", "max_images_to_download", str(self.max_images_to_download.value()))
            self.config.set("Download", "max_images_to_display", str(self.max_images_to_display.value()))
            self.config.set("Download", "max_microtrailers", str(self.max_microtrailers.value()))
            self.config.set("Download", "max_trailers", str(self.max_trailers.value()))
            self.config.set("Download", "debug_images", str(self.debug_images.isChecked()))
            self.config.set("Download", "video_loop_enabled", str(self.video_loop_enabled.isChecked()))
            self.config.set("Download", "max_concurrent_downloads", str(self.max_concurrent_downloads.value()))

            # ---- Cache ----
            self.config.set("Cache", "cache_dir_override", self.cache_dir_override.text())

            # ---- Sanitize ----
            self.config.set("Sanitize", "repack_list", self._textedit_to_comma_string(self.repack_list))
            self.config.set("Sanitize", "edition_tokens", self._textedit_to_comma_string(self.edition_tokens))
            self.config.set("Sanitize", "emulator_tokens", self._textedit_to_comma_string(self.emulator_tokens))
            self.config.set("Sanitize", "mode_keywords", self._textedit_to_comma_string(self.mode_keywords))

            # ---- Export ----
            self.config.set("Export", "description_lines", str(self.desc_lines.value()))
            self.config.set("Export", "export_thumbnails", str(self.export_thumbnails_cb.isChecked()))
            self.config.set("Export", "export_thumbnail_width", str(self.thumbnail_width_spin.value()))
            self.config.set("Export", "export_thumbnail_height", str(self.thumbnail_height_spin.value()))
            self.config.set("Export", "pdf_page_size", self.page_size_combo.currentText())

            if not self.config.has_section("ExportColumns"):
                self.config.add_section("ExportColumns")
            selected = [key for key, cb in self.export_col_checkboxes.items() if cb.isChecked()]
            self.config.set("ExportColumns", "selected", ",".join(selected))
            for key, spin in self.export_col_widths.items():
                self.config.set("ExportColumns", f"width_{key}", str(spin.value()))
            for key, edit in self.export_col_headers.items():
                self.config.set("ExportColumns", f"header_{key}", edit.text())
            self.config.set("ExportColumns", "links_steam", str(self.links_steam.isChecked()))
            self.config.set("ExportColumns", "links_igdb", str(self.links_igdb.isChecked()))
            self.config.set("ExportColumns", "links_pcgw", str(self.links_pcgw.isChecked()))
            self.config.set("ExportColumns", "links_steamdb", str(self.links_steamdb.isChecked()))

            # ---- API ----
            self.config.set("API", "steam_search_api", self.steam_search_api.text())
            self.config.set("API", "steam_store_app_url", self.steam_store_app_url.text())
            self.config.set("API", "steamdb_app_url", self.steamdb_app_url.text())
            self.config.set("API", "pcgw_search_template", self.pcgw_search_template.text())
            self.config.set("API", "igdb_url_template", self.igdb_url_template.text())
            self.config.set("API", "http_timeout", str(self.http_timeout.value()))
            self.config.set("API", "http_retries", str(self.http_retries.value()))
            self.config.set("API", "sleep_between_requests", str(self.sleep_between_requests.value()))
            self.config.set("API", "igdb_image_base_url", self.igdb_image_base_url.text())
            self.config.set("API", "igdb_screenshot_size", self.igdb_screenshot_size.text())
            self.config.set("API", "igdb_cover_size", self.igdb_cover_size.text())
            self.config.set("API", "igdb_client_id", self.igdb_client_id.text())
            self.config.set("API", "igdb_client_secret", self.igdb_client_secret.text())
            self.config.set("API", "igdb_access_token", self.igdb_access_token.text())

            # ---- DriveScanner ----
            self.config.set("DriveScanner", "drive_tokens", self.drive_tokens.text())
            self.config.set("DriveScanner", "drive_number_pattern", self.drive_number_pattern.text())

            # ---- AssetExport ----
            self.config.set("AssetExport", "artbox_name", self.artbox_name.text())
            self.config.set("AssetExport", "trailer_name", self.trailer_name.text())

            # ---- Save active theme colors from pickers ----
            active = self.config.getint("UI", "active_theme", fallback=1)
            section = f"Theme{active}"
            for key, btn in self.color_pickers.items():
                color = btn.styleSheet().split("background-color:")[1].split(";")[0].strip()
                self.config.set(section, key, color)

            # ---- Save row highlight desaturation for the active theme ----
            # Stored per-theme (not in [UI]) so dark and light themes can each
            # keep their own value -- e.g. a dark theme desaturated the same
            # amount as a light theme would wash its highlighted rows out
            # against light table text.
            self.config.set(section, "highlight_desaturate_percent", str(self.highlight_desaturate_spin.value()))

            # ---- UI Version ----
            if not self.config.has_section("GUI"):
                self.config.add_section("GUI")
            self.config.set("GUI", "ui_version", str(self.ui_version_combo.currentIndex() + 1))

            # ---- Write config file ----
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                self.config.write(f)

            # ---- Reload config and apply to main window ----
            reload_config()
            if self.parent() and hasattr(self.parent(), 'apply_theme'):
                self.parent().apply_theme()
                self.parent().repaint()
                if hasattr(self.parent(), 'table'):
                    self.parent().table.viewport().repaint()
                if hasattr(self.parent(), 'details_panel'):
                    self.parent().details_panel.repaint()

            self.apply_theme()

            # ---- Refresh the active pickers to reflect saved values (optional) ----
            self._build_active_pickers()

            # ------------------------------------------------------------
            # RESTART WARNING (if needed)
            # ------------------------------------------------------------
            if requires_restart:
                QMessageBox.information(
                    self,
                    "Restart Required",
                    "Theme or UI version changes require a restart of the application to take full effect.\n\n"
                    "Please close and reopen the app."
                )

            QMessageBox.information(self, "Settings", "Settings saved and applied.")
            #self.accept()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{str(e)}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _textedit_to_comma_string(self, text_edit):
        lines = [line.strip() for line in text_edit.toPlainText().splitlines() if line.strip()]
        return ", ".join(lines)

    def _comma_to_lines(self, text):
        return "\n".join([x.strip() for x in text.split(',') if x.strip()])
        
    def apply_theme(self):
        """Reapply the current config colours to the dialog's palette and
        stylesheet, and propagate to all child widgets.

        Same protocol as every other config-aware widget in the app: this
        is what config.refresh_all() would call if this dialog were ever
        walked as a child, and it's what settings_dialog calls on itself
        directly since it's its own top-level window.
        """
        # Reapply the global stylesheet
        self.setStyleSheet(config.APP_STYLESHEET + self.extra_style)
        self.style().unpolish(self)
        self.style().polish(self)

        # Update the palette with current config colours
        palette = self.palette()
        from PyQt5.QtGui import QColor, QPalette
        palette.setColor(QPalette.Window, QColor(config.LIGHT_BG))
        palette.setColor(QPalette.WindowText, QColor(config.PRIMARY_COLOR))
        palette.setColor(QPalette.Base, QColor(config.INPUT_BACKGROUND))
        palette.setColor(QPalette.AlternateBase, QColor(config.TABLE_ALTERNATE_BACKGROUND))
        palette.setColor(QPalette.Text, QColor(config.LABEL_TEXT_COLOR))
        palette.setColor(QPalette.Button, QColor(config.SECONDARY_COLOR))
        palette.setColor(QPalette.ButtonText, QColor(config.BUTTON_TEXT_COLOR))
        palette.setColor(QPalette.Highlight, QColor(config.SELECTED_COLOR))
        palette.setColor(QPalette.HighlightedText, QColor(config.SELECTION_TEXT_COLOR))
        self.setPalette(palette)

        # Propagate the palette to all child widgets, and let any
        # apply_theme()-aware custom widgets (e.g. CheckableComboBox
        # pickers) restyle themselves too.
        for child in self.findChildren(QWidget):
            child.setPalette(palette)
        config.refresh_all(self)
        self.repaint()

    # Back-compat alias for any external callers using the old name
    _refresh_dialog_style = apply_theme