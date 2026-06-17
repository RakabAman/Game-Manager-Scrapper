# settings_dialog.py
import os
import configparser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QLineEdit,
    QSpinBox, QTextEdit, QScrollArea, QDoubleSpinBox, QCheckBox, QPushButton, QHBoxLayout, QMessageBox, QColorDialog,
    QLabel, QFileDialog, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from config import CONFIG_FILE, reload_config, APP_STYLESHEET, BASE_DIR, SHOW_THUMBNAILS_IN_DETAILS


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 700)
        self.setStyleSheet(APP_STYLESHEET)

        # Load current config
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE, encoding='utf-8')

        # Main layout
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        # Create tabs
        self._create_general_tab()
        self._create_scraping_tab()
        self._create_download_tab()
        self._create_ui_tab()
        self._create_sanitize_tab()
        self._create_export_tab()
        self._create_drive_scanner_tab()

        main_layout.addWidget(self.tab_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

    # ----------------------------------------------------------------------
    # Helper to create a line edit with browse button
    # ----------------------------------------------------------------------
    def _create_file_browse_row(self, label, line_edit, file_filter="JSON (*.json);;SQLite (*.sqlite *.db);;All files (*.*)", is_directory=False):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)
        btn = QPushButton("Browse")
        if is_directory:
            btn.clicked.connect(lambda: self._browse_directory(line_edit))
        else:
            btn.clicked.connect(lambda: self._browse_file(line_edit, file_filter))
        layout.addWidget(btn)
        return widget

    def _browse_file(self, line_edit, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", line_edit.text(), file_filter)
        if path:
            line_edit.setText(path)

    def _browse_directory(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit.text())
        if dir_path:
            line_edit.setText(dir_path)

    # ----------------------------------------------------------------------
    # General Tab
    # ----------------------------------------------------------------------
    def _create_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setVerticalSpacing(10)      # space between rows
        layout.setHorizontalSpacing(20)    # space between label and field
        layout.setContentsMargins(12, 12, 12, 12)
        
        self.divider_percentage = QSpinBox()
        self.divider_percentage.setRange(10, 90)
        self.divider_percentage.setValue(self.config.getint("General", "divider_percentage"))
        layout.addRow("Divider Percentage (%):", self.divider_percentage)

        # Font sizes for details panel
        self.details_title_font_size = QSpinBox()
        self.details_title_font_size.setRange(12, 48)
        self.details_title_font_size.setValue(self.config.getint("UI", "details_title_font_size", fallback=22))
        layout.addRow("Details Title Font Size (px):", self.details_title_font_size)

        self.details_desc_font_size = QSpinBox()
        self.details_desc_font_size.setRange(10, 24)
        self.details_desc_font_size.setValue(self.config.getint("UI", "details_desc_font_size", fallback=14))
        layout.addRow("Details Description Font Size (px):", self.details_desc_font_size)

        # Text box height for all line edits / text edits
        self.text_box_height = QSpinBox()
        self.text_box_height.setRange(20, 100)
        self.text_box_height.setValue(self.config.getint("UI", "text_box_height", fallback=30))
        layout.addRow("Text Box Height (px):", self.text_box_height)

        self.default_database = QLineEdit()
        self.default_database.setText(self.config.get("General", "default_database"))
        default_db_widget = self._create_file_browse_row("Default Database:", self.default_database)
        layout.addRow("Default Database Path:", default_db_widget)

        self.auto_save = QCheckBox()
        self.auto_save.setChecked(self.config.getboolean("General", "auto_save"))
        layout.addRow("Auto Save:", self.auto_save)

        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(5, 600)
        self.auto_save_interval.setValue(self.config.getint("General", "auto_save_interval_seconds"))
        layout.addRow("Auto Save Interval (seconds):", self.auto_save_interval)

        self.auto_save_path = QLineEdit()
        self.auto_save_path.setText(self.config.get("General", "auto_save_path"))
        auto_save_widget = self._create_file_browse_row("Auto Save Path:", self.auto_save_path)
        layout.addRow("Auto Save Path (empty = default):", auto_save_widget)

        self.auto_cache = QCheckBox()
        self.auto_cache.setChecked(self.config.getboolean("General", "auto_cache"))
        layout.addRow("Auto Cache:", self.auto_cache)

        self.auto_sanitize = QCheckBox()
        self.auto_sanitize.setChecked(self.config.getboolean("General", "auto_sanitize"))
        layout.addRow("Auto Sanitize on Import:", self.auto_sanitize)
        
        self.show_thumbnails_cb = QCheckBox()
        self.show_thumbnails_cb.setChecked(SHOW_THUMBNAILS_IN_DETAILS)
        layout.addRow("Show cover thumbnails in details panel:", self.show_thumbnails_cb)

        self.show_console = QCheckBox()
        self.show_console.setChecked(self.config.getboolean("General", "show_console", fallback=False))
        layout.addRow("Show Console Window:", self.show_console)

        
        # Wrap tab in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "General")
    # ----------------------------------------------------------------------
    # Scraping Tab (now includes API settings)
    # ----------------------------------------------------------------------
    def _create_scraping_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)                 # space between groups
        main_layout.setContentsMargins(12, 12, 12, 12)   # outer padding
        
        # --- Scraping group ---
        scraping_group = QGroupBox("Scraping Settings")
        scraping_layout = QFormLayout(scraping_group)
        scraping_layout.setVerticalSpacing(10)
        scraping_layout.setHorizontalSpacing(20)
        
        self.auto_accept_score = QSpinBox()
        self.auto_accept_score.setRange(0, 100)
        self.auto_accept_score.setValue(self.config.getint("Scraping", "auto_accept_score"))
        scraping_layout.addRow("Auto Accept Score:", self.auto_accept_score)

        self.fetch_pcgw_save = QCheckBox()
        self.fetch_pcgw_save.setChecked(self.config.getboolean("Scraping", "fetch_pcgw_save"))
        scraping_layout.addRow("Fetch PCGW Save Locations:", self.fetch_pcgw_save)

        self.chunk_size = QSpinBox()
        self.chunk_size.setRange(1, 500)
        self.chunk_size.setValue(self.config.getint("Scraping", "chunk_size"))
        scraping_layout.addRow("Chunk Size (games per batch):", self.chunk_size)

        self.stall_timeout = QSpinBox()
        self.stall_timeout.setRange(5, 300)
        self.stall_timeout.setValue(self.config.getint("Scraping", "stall_timeout"))
        scraping_layout.addRow("Stall Timeout (seconds):", self.stall_timeout)

        self.max_concurrent_scrapes = QSpinBox()
        self.max_concurrent_scrapes.setRange(1, 10)
        self.max_concurrent_scrapes.setValue(self.config.getint("Scraping", "max_concurrent_scrapes"))
        scraping_layout.addRow("Max Concurrent Scrapes:", self.max_concurrent_scrapes)

        main_layout.addWidget(scraping_group)

        # --- API group ---
        api_group = QGroupBox("API Settings")
        api_layout = QFormLayout(api_group)
        api_layout.setVerticalSpacing(10)
        api_layout.setHorizontalSpacing(20)
        
        self.steam_search_api = QLineEdit()
        self.steam_search_api.setText(self.config.get("API", "steam_search_api"))
        api_layout.addRow("Steam Search API:", self.steam_search_api)

        self.steam_store_app_url = QLineEdit()
        self.steam_store_app_url.setText(self.config.get("API", "steam_store_app_url"))
        api_layout.addRow("Steam Store App URL:", self.steam_store_app_url)

        self.steamdb_app_url = QLineEdit()
        self.steamdb_app_url.setText(self.config.get("API", "steamdb_app_url"))
        api_layout.addRow("SteamDB App URL:", self.steamdb_app_url)

        self.pcgw_search_template = QLineEdit()
        self.pcgw_search_template.setText(self.config.get("API", "pcgw_search_template"))
        api_layout.addRow("PCGW Search Template:", self.pcgw_search_template)

        self.igdb_url_template = QLineEdit()
        self.igdb_url_template.setText(self.config.get("API", "igdb_url_template"))
        api_layout.addRow("IGDB URL Template:", self.igdb_url_template)

        self.http_timeout = QDoubleSpinBox()
        self.http_timeout.setRange(1.0, 60.0)
        self.http_timeout.setSingleStep(0.5)
        self.http_timeout.setValue(self.config.getfloat("API", "http_timeout"))
        api_layout.addRow("HTTP Timeout (seconds):", self.http_timeout)

        self.http_retries = QSpinBox()
        self.http_retries.setRange(0, 10)
        self.http_retries.setValue(self.config.getint("API", "http_retries"))
        api_layout.addRow("HTTP Retries:", self.http_retries)

        self.sleep_between_requests = QDoubleSpinBox()
        self.sleep_between_requests.setRange(0.0, 5.0)
        self.sleep_between_requests.setSingleStep(0.05)
        self.sleep_between_requests.setValue(self.config.getfloat("API", "sleep_between_requests"))
        api_layout.addRow("Sleep Between Requests (seconds):", self.sleep_between_requests)

        self.igdb_image_base_url = QLineEdit()
        self.igdb_image_base_url.setText(self.config.get("API", "igdb_image_base_url"))
        api_layout.addRow("IGDB Image Base URL:", self.igdb_image_base_url)

        self.igdb_screenshot_size = QLineEdit()
        self.igdb_screenshot_size.setText(self.config.get("API", "igdb_screenshot_size"))
        api_layout.addRow("IGDB Screenshot Size:", self.igdb_screenshot_size)

        self.igdb_cover_size = QLineEdit()
        self.igdb_cover_size.setText(self.config.get("API", "igdb_cover_size"))
        api_layout.addRow("IGDB Cover Size:", self.igdb_cover_size)

        self.igdb_client_id = QLineEdit()
        self.igdb_client_id.setText(self.config.get("API", "igdb_client_id"))
        api_layout.addRow("IGDB Client ID:", self.igdb_client_id)

        self.igdb_client_secret = QLineEdit()
        self.igdb_client_secret.setText(self.config.get("API", "igdb_client_secret"))
        api_layout.addRow("IGDB Client Secret:", self.igdb_client_secret)

        self.igdb_access_token = QLineEdit()
        self.igdb_access_token.setText(self.config.get("API", "igdb_access_token"))
        api_layout.addRow("IGDB Access Token:", self.igdb_access_token)

        main_layout.addWidget(api_group)
        main_layout.addStretch()
    
        
        # Wrap tab in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Scraping")
    # ----------------------------------------------------------------------
    # Download Tab (now includes Cache group)
    # ----------------------------------------------------------------------
    def _create_download_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)


        # --- Download group ---
        download_group = QGroupBox("Download Settings")
        download_layout = QFormLayout(download_group)
        download_layout.setVerticalSpacing(10)
        download_layout.setHorizontalSpacing(20)
        
        self.max_images_to_download = QSpinBox()
        self.max_images_to_download.setRange(1, 20)
        self.max_images_to_download.setValue(self.config.getint("Download", "max_images_to_download"))
        download_layout.addRow("Max Images to Download:", self.max_images_to_download)

        self.max_images_to_display = QSpinBox()
        self.max_images_to_display.setRange(1, 20)
        self.max_images_to_display.setValue(self.config.getint("Download", "max_images_to_display"))
        download_layout.addRow("Max Images to Display:", self.max_images_to_display)

        self.max_microtrailers = QSpinBox()
        self.max_microtrailers.setRange(0, 5)
        self.max_microtrailers.setValue(self.config.getint("Download", "max_microtrailers"))
        download_layout.addRow("Max Microtrailers per Game:", self.max_microtrailers)

        self.max_trailers = QSpinBox()
        self.max_trailers.setRange(0, 10)
        self.max_trailers.setValue(self.config.getint("Download", "max_trailers"))
        download_layout.addRow("Max Trailer Links:", self.max_trailers)

        self.debug_images = QCheckBox()
        self.debug_images.setChecked(self.config.getboolean("Download", "debug_images"))
        download_layout.addRow("Debug Images:", self.debug_images)

        self.video_loop_enabled = QCheckBox()
        self.video_loop_enabled.setChecked(self.config.getboolean("Download", "video_loop_enabled"))
        download_layout.addRow("Video Loop Enabled:", self.video_loop_enabled)

        self.max_concurrent_downloads = QSpinBox()
        self.max_concurrent_downloads.setRange(1, 10)
        self.max_concurrent_downloads.setValue(self.config.getint("Download", "max_concurrent_downloads"))
        download_layout.addRow("Max Concurrent Downloads:", self.max_concurrent_downloads)

        main_layout.addWidget(download_group)

        # --- Cache group ---
        cache_group = QGroupBox("Cache")
        cache_layout = QFormLayout(cache_group)
        cache_layout.setVerticalSpacing(10)
        cache_layout.setHorizontalSpacing(20)

        self.cache_min_kb = QSpinBox()
        self.cache_min_kb.setRange(1, 100)
        self.cache_min_kb.setValue(self.config.getint("General", "cache_min_kb"))
        cache_layout.addRow("Cache Min KB:", self.cache_min_kb)

        self.cache_max_kb = QSpinBox()
        self.cache_max_kb.setRange(100, 50000)
        self.cache_max_kb.setValue(self.config.getint("General", "cache_max_kb"))
        cache_layout.addRow("Cache Max KB:", self.cache_max_kb)

        self.cache_dir_override = QLineEdit()
        self.cache_dir_override.setText(self.config.get("Cache", "cache_dir_override"))
        cache_dir_widget = self._create_file_browse_row("Cache Directory:", self.cache_dir_override, is_directory=True)
        cache_layout.addRow("Cache Directory Override (empty = default):", cache_dir_widget)

        main_layout.addWidget(cache_group)
        main_layout.addStretch()

        
        # Wrap tab in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Download")
    # ----------------------------------------------------------------------
    # UI Colors Tab
    # ----------------------------------------------------------------------
    def _create_ui_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(15)

        def color_picker(section, key):
            current = self.config.get(section, key)
            picker = QPushButton()
            picker.setFixedSize(50, 25)
            picker.setStyleSheet(f"background-color: {current}; border: 1px solid gray;")
            picker.clicked.connect(lambda: self._pick_color(picker, section, key))
            return picker

        self.color_widgets = {}
        color_keys = [
            ("primary_color", "Primary"), ("secondary_color", "Secondary"),
            ("accent_color", "Accent"), ("success_color", "Success"),
            ("warning_color", "Warning"), ("light_bg", "Light Background"),
            ("dark_bg", "Dark Background"), ("border_color", "Border"),
            ("hover_color", "Hover"), ("selected_color", "Selected"),
            ("duplicate_color", "Duplicate"), ("played_color", "Played"),
            ("unplayed_color", "Unplayed"), ("favorite_color", "Favorite")
        ]
        for key, label in color_keys:
            picker = color_picker("UI", key)
            layout.addRow(f"{label} Color:", picker)
            self.color_widgets[key] = picker

                # Desaturation percentage for table row highlights
        self.highlight_desaturate_spin = QSpinBox()
        self.highlight_desaturate_spin.setRange(0, 100)
        self.highlight_desaturate_spin.setSuffix("%")
        # Read current value from config (default 20)
        current_desat = self.config.getint("UI", "highlight_desaturate_percent", fallback=20)
        self.highlight_desaturate_spin.setValue(current_desat)
        layout.addRow("Row Highlight Desaturation (%):", self.highlight_desaturate_spin)
        
        # Wrap tab in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "UI Colors")
        
    def _pick_color(self, button, section, key):
        current = self.config.get(section, key)
        color = QColorDialog.getColor(QColor(current), self, f"Select {key}")
        if color.isValid():
            hex_color = color.name()
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid gray;")
            if not hasattr(self, '_pending_ui_colors'):
                self._pending_ui_colors = {}
            self._pending_ui_colors[key] = hex_color

    # ----------------------------------------------------------------------
    # Sanitize Tab
    # ----------------------------------------------------------------------
    def _create_sanitize_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.repack_list = QTextEdit()
        self.repack_list.setPlainText(self._comma_to_lines(self.config.get("Sanitize", "repack_list")))
        self.repack_list.setFixedHeight(120)
        layout.addRow("Repack List (one per line):", self.repack_list)

        self.edition_tokens = QTextEdit()
        self.edition_tokens.setPlainText(self._comma_to_lines(self.config.get("Sanitize", "edition_tokens")))
        self.edition_tokens.setFixedHeight(120)
        layout.addRow("Edition Tokens (one per line):", self.edition_tokens)

        self.emulator_tokens = QTextEdit()
        self.emulator_tokens.setPlainText(self._comma_to_lines(self.config.get("Sanitize", "emulator_tokens")))
        self.emulator_tokens.setFixedHeight(120)
        layout.addRow("Emulator Tokens (one per line):", self.emulator_tokens)

        self.mode_keywords = QTextEdit()
        self.mode_keywords.setPlainText(self.config.get("Sanitize", "mode_keywords"))  # JSON stays as is
        self.mode_keywords.setFixedHeight(80)
        layout.addRow("Mode Keywords (JSON):", self.mode_keywords)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Sanitize")
    # ----------------------------------------------------------------------
    # Export Tab (now includes Asset Export group)
    # ----------------------------------------------------------------------
    def _create_export_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- Asset Export group (top) ---
        asset_group = QGroupBox("Asset Export (to game folders)")
        asset_layout = QFormLayout(asset_group)
        asset_layout.setVerticalSpacing(10)
        asset_layout.setHorizontalSpacing(20)
        self.artbox_name = QLineEdit()
        self.artbox_name.setText(self.config.get("AssetExport", "artbox_name"))
        asset_layout.addRow("Artbox Filename:", self.artbox_name)
        self.trailer_name = QLineEdit()
        self.trailer_name.setText(self.config.get("AssetExport", "trailer_name"))
        asset_layout.addRow("Trailer Base Filename (without extension):", self.trailer_name)
        main_layout.addWidget(asset_group)

        # --- General Export Settings (PDF/HTML) ---
        common_group = QGroupBox("General Export Settings (PDF/HTML)")
        common_layout = QFormLayout(common_group)
        common_layout.setVerticalSpacing(10)
        common_layout.setHorizontalSpacing(20)
        self.desc_lines = QSpinBox()
        self.desc_lines.setRange(1, 20)
        self.desc_lines.setValue(self.config.getint("Export", "description_lines"))
        common_layout.addRow("Description Lines:", self.desc_lines)
        self.export_thumbnails_cb = QCheckBox("Include cover thumbnails in Title column (HTML export only)")
        self.export_thumbnails_cb.setChecked(self.config.getboolean("Export", "export_thumbnails", fallback=False))
        common_layout.addRow(self.export_thumbnails_cb)

        # Thumbnail dimensions row
        size_layout = QHBoxLayout()
        self.thumbnail_width_spin = QSpinBox()
        self.thumbnail_width_spin.setRange(16, 256)
        self.thumbnail_width_spin.setValue(self.config.getint("Export", "export_thumbnail_width", fallback=32))
        self.thumbnail_width_spin.setSuffix(" px")
        self.thumbnail_height_spin = QSpinBox()
        self.thumbnail_height_spin.setRange(16, 256)
        self.thumbnail_height_spin.setValue(self.config.getint("Export", "export_thumbnail_height", fallback=32))
        self.thumbnail_height_spin.setSuffix(" px")
        size_layout.addWidget(QLabel("Width:"))
        size_layout.addWidget(self.thumbnail_width_spin)
        size_layout.addWidget(QLabel("Height:"))
        size_layout.addWidget(self.thumbnail_height_spin)
        size_layout.addStretch()
        common_layout.addRow("Thumbnail size:", size_layout)
        
        main_layout.addWidget(common_group)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A3 Landscape", "A4 Landscape", "Letter Landscape"])
        # Load saved value
        saved_size = self.config.get("Export", "pdf_page_size", fallback="A3 Landscape")
        self.page_size_combo.setCurrentText(saved_size)
        common_layout.addRow("PDF Page Size:", self.page_size_combo)

        # --- Dynamic column selection group ---
        columns_group = QGroupBox("Export Columns (select which columns to include)")
        columns_layout = QVBoxLayout(columns_group)

        # List of all possible export fields (key, default header)
        self.available_columns = [
            ("title", "Title"),
            ("app_id", "Steam ID"),
            ("igdb_id", "IGDB ID"),
            ("release_date", "Release Date"),
            ("description", "Description"),
            ("game_modes", "Modes"),
            ("genres", "Genre"),
            ("themes", "Themes"),
            ("player_perspective", "Perspective"),
            ("developer", "Developer"),
            ("publisher", "Publisher"),
            ("game_drive", "Drive"),
            ("scene_repack", "Repack"),
            ("original_title", "Orgtitle"),
            ("resources", "Resources (SS/TT links)"),
            ("links", "External Links"),
            ("savegame_location", "Save Location"),
        ]

        # Load saved settings or use defaults
        saved_selected = self.config.get("ExportColumns", "selected", fallback="title,app_id,igdb_id,genres,themes,description,game_modes,game_drive,original_title,trailer_webm,screenshots,steam_link")
        selected_keys = set(saved_selected.split(","))

        self.export_col_checkboxes = {}
        self.export_col_widths = {}
        self.export_col_headers = {}

        # Scrollable area for columns
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        for key, default_header in self.available_columns:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            cb = QCheckBox(default_header)
            cb.setChecked(key in selected_keys)
            cb.setMinimumWidth(150)

            width_spin = QSpinBox()
            width_spin.setRange(1, 50)
            saved_width = self.config.getint("ExportColumns", f"width_{key}", fallback=8 if key == "description" else 5)
            width_spin.setValue(saved_width)
            width_spin.setSuffix("%")

            header_edit = QLineEdit()
            saved_header = self.config.get("ExportColumns", f"header_{key}", fallback=default_header)
            header_edit.setText(saved_header)
            header_edit.setPlaceholderText(default_header)

            row_layout.addWidget(cb, 2)
            row_layout.addWidget(QLabel("Width:"), 1)
            row_layout.addWidget(width_spin, 1)
            row_layout.addWidget(QLabel("Header:"), 1)
            row_layout.addWidget(header_edit, 3)

            scroll_layout.addWidget(row_widget)

            self.export_col_checkboxes[key] = cb
            self.export_col_widths[key] = width_spin
            self.export_col_headers[key] = header_edit

        # Add link type checkboxes as a special row inside the scrollable area
        link_box = QGroupBox("Link types to include (when 'Links' column is selected)")
        link_inner = QHBoxLayout(link_box)
        self.links_steam = QCheckBox("Steam")
        self.links_igdb = QCheckBox("IGDB")
        self.links_pcgw = QCheckBox("PCGW")
        self.links_steamdb = QCheckBox("SteamDB")
        # Load saved values
        self.links_steam.setChecked(self.config.getboolean("ExportColumns", "links_steam", fallback=True))
        self.links_igdb.setChecked(self.config.getboolean("ExportColumns", "links_igdb", fallback=True))
        self.links_pcgw.setChecked(self.config.getboolean("ExportColumns", "links_pcgw", fallback=True))
        self.links_steamdb.setChecked(self.config.getboolean("ExportColumns", "links_steamdb", fallback=True))
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

        # After columns_layout.addWidget(scroll_area) and before note_label:



        note_label = QLabel(
            "Note: Widths are percentages of the total table width. "
            "The sum of widths for selected columns should ideally be 100%.\n"
            "Steam ID, IGDB ID, and Resources columns are automatically hyperlinked."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: gray; font-size: 10px; margin-top: 6px;")
        columns_layout.addWidget(note_label)

        main_layout.addWidget(columns_group)
        main_layout.addStretch()

        outer_scroll = QScrollArea()
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setWidget(tab)
        self.tab_widget.addTab(outer_scroll, "Export") 
        
    
    # ----------------------------------------------------------------------
    # DriveScanner Tab
    # ----------------------------------------------------------------------
    def _create_drive_scanner_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setVerticalSpacing(10)      # space between rows
        layout.setHorizontalSpacing(20)    # space between label and field
        layout.setContentsMargins(12, 12, 12, 12)

        self.drive_tokens = QLineEdit()
        self.drive_tokens.setText(self.config.get("DriveScanner", "drive_tokens"))
        layout.addRow("Drive Tokens (comma separated):", self.drive_tokens)

        self.drive_number_pattern = QLineEdit()
        self.drive_number_pattern.setText(self.config.get("DriveScanner", "drive_number_pattern"))
        layout.addRow("Drive Number Pattern (regex):", self.drive_number_pattern)

        
        # Wrap tab in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "Drive Scanner")
    # ----------------------------------------------------------------------
    # Save Settings
    # ----------------------------------------------------------------------
    def _save_settings(self):
        try:
            # General
            self.config.set("General", "cache_min_kb", str(self.cache_min_kb.value()))
            self.config.set("General", "cache_max_kb", str(self.cache_max_kb.value()))
            self.config.set("General", "divider_percentage", str(self.divider_percentage.value()))
            self.config.set("General", "default_database", self.default_database.text())
            self.config.set("General", "auto_save", str(self.auto_save.isChecked()))
            self.config.set("General", "auto_save_interval_seconds", str(self.auto_save_interval.value()))
            self.config.set("General", "auto_save_path", self.auto_save_path.text())
            self.config.set("General", "auto_cache", str(self.auto_cache.isChecked()))
            self.config.set("General", "auto_sanitize", str(self.auto_sanitize.isChecked()))
            # ... existing General settings ...
            self.config.set("General", "show_console", str(self.show_console.isChecked()))
            self.config.set("General", "show_thumbnails_in_details", str(self.show_thumbnails_cb.isChecked()))

            # Font sizes for details panel
            # Inside _save_settings, after the font size lines:
            self.config.set("UI", "details_title_font_size", str(self.details_title_font_size.value()))
            self.config.set("UI", "details_desc_font_size", str(self.details_desc_font_size.value()))
            self.config.set("UI", "text_box_height", str(self.text_box_height.value()))   # <-- add this

            # Scraping
            self.config.set("Scraping", "auto_accept_score", str(self.auto_accept_score.value()))
            self.config.set("Scraping", "fetch_pcgw_save", str(self.fetch_pcgw_save.isChecked()))
            self.config.set("Scraping", "chunk_size", str(self.chunk_size.value()))
            self.config.set("Scraping", "stall_timeout", str(self.stall_timeout.value()))
            self.config.set("Scraping", "max_concurrent_scrapes", str(self.max_concurrent_scrapes.value()))

            # Download
            self.config.set("Download", "max_images_to_download", str(self.max_images_to_download.value()))
            self.config.set("Download", "max_images_to_display", str(self.max_images_to_display.value()))
            self.config.set("Download", "max_microtrailers", str(self.max_microtrailers.value()))
            self.config.set("Download", "max_trailers", str(self.max_trailers.value()))
            self.config.set("Download", "debug_images", str(self.debug_images.isChecked()))
            self.config.set("Download", "video_loop_enabled", str(self.video_loop_enabled.isChecked()))
            self.config.set("Download", "max_concurrent_downloads", str(self.max_concurrent_downloads.value()))

            # UI Colors
            for key, widget in self.color_widgets.items():
                style = widget.styleSheet()
                if "background-color:" in style:
                    color = style.split("background-color:")[1].split(";")[0].strip()
                    self.config.set("UI", key, color)
            # UI Colors (existing loop) ...
            # After the loop, save desaturation percentage
            self.config.set("UI", "highlight_desaturate_percent", str(self.highlight_desaturate_spin.value()))

            # Cache
            self.config.set("Cache", "cache_dir_override", self.cache_dir_override.text())

            # Sanitize
            # Sanitize tab – convert newlines to commas
            self.config.set("Sanitize", "repack_list", self._textedit_to_comma_string(self.repack_list))
            self.config.set("Sanitize", "edition_tokens", self._textedit_to_comma_string(self.edition_tokens))
            self.config.set("Sanitize", "emulator_tokens", self._textedit_to_comma_string(self.emulator_tokens))
            self.config.set("Sanitize", "mode_keywords", self._textedit_to_comma_string(self.mode_keywords))

            # Export
            # Export – common settings
            self.config.set("Export", "description_lines", str(self.desc_lines.value()))
            self.config.set("Export", "export_thumbnails", str(self.export_thumbnails_cb.isChecked()))
            self.config.set("Export", "export_thumbnail_width", str(self.thumbnail_width_spin.value()))
            self.config.set("Export", "export_thumbnail_height", str(self.thumbnail_height_spin.value()))
            

            # Export Columns – save selection, widths, headers
            if not self.config.has_section("ExportColumns"):
                self.config.add_section("ExportColumns")

            selected = [key for key, cb in self.export_col_checkboxes.items() if cb.isChecked()]
            self.config.set("ExportColumns", "selected", ",".join(selected))

            for key, spin in self.export_col_widths.items():
                self.config.set("ExportColumns", f"width_{key}", str(spin.value()))

            for key, edit in self.export_col_headers.items():
                self.config.set("ExportColumns", f"header_{key}", edit.text())
                
            # Inside _save_settings, after saving column selections:
            self.config.set("ExportColumns", "links_steam", str(self.links_steam.isChecked()))
            self.config.set("ExportColumns", "links_igdb", str(self.links_igdb.isChecked()))
            self.config.set("ExportColumns", "links_pcgw", str(self.links_pcgw.isChecked()))
            self.config.set("ExportColumns", "links_steamdb", str(self.links_steamdb.isChecked()))

            self.config.set("Export", "pdf_page_size", self.page_size_combo.currentText())


            # API
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

            # DriveScanner
            self.config.set("DriveScanner", "drive_tokens", self.drive_tokens.text())
            self.config.set("DriveScanner", "drive_number_pattern", self.drive_number_pattern.text())

            # AssetExport
            self.config.set("AssetExport", "artbox_name", self.artbox_name.text())
            self.config.set("AssetExport", "trailer_name", self.trailer_name.text())

            # Write to file
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                self.config.write(f)

            # Reload config in the running application
            reload_config()

            # Notify the main window to apply changes (if parent is GameManager)
            if self.parent() and hasattr(self.parent(), '_apply_config_settings'):
                self.parent()._apply_config_settings()

            QMessageBox.information(self, "Settings", "Settings saved and applied.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{str(e)}")
            
    def _textedit_to_comma_string(self, text_edit: QTextEdit) -> str:
        """Convert multi‑line text to a single line with commas."""
        text = text_edit.toPlainText().strip()
        # Replace newlines, carriage returns, and multiple spaces with a single comma
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return ", ".join(lines)
        
            
    def _comma_to_lines(self, text: str) -> str:
        """Convert comma-separated string to newline-separated for multi-line editing."""
        items = [item.strip() for item in text.split(',') if item.strip()]
        return "\n".join(items)