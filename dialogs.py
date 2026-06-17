# dialogs.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QWidget, QFormLayout,
    QLineEdit, QTextEdit as QTE, QDialogButtonBox, QHBoxLayout, QPushButton,
    QTabWidget, QCheckBox, QFrame
)
from PyQt5.QtCore import Qt
from config import APP_STYLESHEET

class MultiEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-edit Selected Games")
        self.setMinimumWidth(500)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header_label = QLabel("Edit Multiple Games")
        header_label.setProperty("title", True)
        main_layout.addWidget(header_label)

        instruction_label = QLabel("Leave fields empty to skip updating them. Changes apply to all selected games.")
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        main_layout.addWidget(instruction_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        self.game_drive = QLineEdit()
        self.game_drive.setPlaceholderText("e.g., D:/Games")
        self.scene_repack = QLineEdit()
        self.scene_repack.setPlaceholderText("e.g., FitGirl Repack")
        self.game_modes = QLineEdit()
        self.game_modes.setPlaceholderText("e.g., Single-player, Multiplayer")
        self.patch_version = QLineEdit()
        self.patch_version.setPlaceholderText("e.g., v1.5.3")
        self.played = QLineEdit()
        self.played.setPlaceholderText("Yes/No or True/False")
        self.save_location = QTE()
        self.save_location.setFixedHeight(100)

        form_layout.addRow(self._create_form_label("Game Drive:"), self.game_drive)
        form_layout.addRow(self._create_form_label("Scene/Repack:"), self.scene_repack)
        form_layout.addRow(self._create_form_label("Game Modes:"), self.game_modes)
        form_layout.addRow(self._create_form_label("Patch Version:"), self.patch_version)
        form_layout.addRow(self._create_form_label("Played Status:"), self.played)
        form_layout.addRow(self._create_form_label("Save Location:"), self.save_location)

        scroll_area.setWidget(form_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply Changes")
        apply_btn.setProperty("success", True)
        apply_btn.clicked.connect(self.accept)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(apply_btn)
        main_layout.addLayout(button_layout)

    def _create_form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setMinimumWidth(120)
        label.setStyleSheet("font-weight: 600; color: #2c3e50;")
        return label

    def result(self) -> dict:
        played_text = self.played.text().strip().lower()
        played_val = None
        if played_text in ("yes", "y", "true", "1"):
            played_val = True
        elif played_text in ("no", "n", "false", "0"):
            played_val = False
        return {
            "game_drive": self.game_drive.text().strip() or None,
            "scene_repack": self.scene_repack.text().strip() or None,
            "game_modes": self.game_modes.text().strip() or None,
            "patch_version": self.patch_version.text().strip() or None,
            "played": played_val,
            "save_location": self.save_location.toPlainText().strip() or None
        }


class EditDialog(QDialog):
    def __init__(self, game: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Game: {game.get('title', 'Untitled')}")
        self.setMinimumSize(850, 950)
        self.setStyleSheet(APP_STYLESHEET)
        self.game = dict(game)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        header_label = QLabel(f"Editing: {self.game.get('title', 'Untitled Game')}")
        header_label.setProperty("title", True)
        main_layout.addWidget(header_label)

        tab_widget = QTabWidget()

        # ========== GENERAL TAB (improved grid layout) ==========
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(20, 20, 20, 20)
        general_layout.setSpacing(15)

        # Grid layout for paired fields
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(20)

        # Row 0: Title (full width)
        grid.addWidget(self._create_form_label("Title:"), 0, 0)
        self.title = self._create_line_edit("title", "Game Title")
        self.title.setMinimumWidth(300)
        grid.addWidget(self.title, 0, 1, 1, 3)

        # Row 1: Steam ID + IGDB ID
        grid.addWidget(self._create_form_label("Steam ID:"), 1, 0)
        self.appid = self._create_line_edit("app_id", "Steam App ID")
        self.appid.setMinimumWidth(200)
        grid.addWidget(self.appid, 1, 1)
        grid.addWidget(self._create_form_label("IGDB ID:"), 1, 2)
        self.igdb_id = self._create_line_edit("igdb_id", "IGDB ID")
        self.igdb_id.setMinimumWidth(200)
        grid.addWidget(self.igdb_id, 1, 3)

        # Row 2: Release Date + User Rating
        grid.addWidget(self._create_form_label("Release Date:"), 2, 0)
        self.release = self._create_line_edit("release_date", "YYYY-MM-DD")
        grid.addWidget(self.release, 2, 1)
        grid.addWidget(self._create_form_label("User Rating:"), 2, 2)
        self.user_rating = self._create_line_edit("user_rating", "0-100")
        grid.addWidget(self.user_rating, 2, 3)

        # Row 3: Developer + Publisher
        grid.addWidget(self._create_form_label("Developer:"), 3, 0)
        self.dev = self._create_line_edit("developer", "Developer")
        grid.addWidget(self.dev, 3, 1)
        grid.addWidget(self._create_form_label("Publisher:"), 3, 2)
        self.pub = self._create_line_edit("publisher", "Publisher")
        grid.addWidget(self.pub, 3, 3)

        # Row 4: Genres + Game Modes
        grid.addWidget(self._create_form_label("Genres:"), 4, 0)
        self.genres = self._create_line_edit("genres", "Action, Adventure, RPG")
        grid.addWidget(self.genres, 4, 1)
        grid.addWidget(self._create_form_label("Game Modes:"), 4, 2)
        self.game_modes = self._create_line_edit("game_modes", "Single-player, Multiplayer")
        grid.addWidget(self.game_modes, 4, 3)

        # Row 5: Original Title + Patch Version
        grid.addWidget(self._create_form_label("Original Title:"), 5, 0)
        self.original_title = self._create_line_edit("original_title", "Original Title")
        grid.addWidget(self.original_title, 5, 1)
        grid.addWidget(self._create_form_label("Patch Version:"), 5, 2)
        self.patch_version = self._create_line_edit("patch_version", "v1.5.3")
        grid.addWidget(self.patch_version, 5, 3)

        # Row 6: Game Drive + Scene/Repack
        grid.addWidget(self._create_form_label("Game Drive:"), 6, 0)
        self.game_drive = self._create_line_edit("game_drive", "e.g., D:/Games")
        grid.addWidget(self.game_drive, 6, 1)
        grid.addWidget(self._create_form_label("Scene/Repack:"), 6, 2)
        self.scene_repack = self._create_line_edit("scene_repack", "e.g., FitGirl Repack")
        grid.addWidget(self.scene_repack, 6, 3)

        # Row 7: Themes + Perspective
        grid.addWidget(self._create_form_label("Themes:"), 7, 0)
        self.themes = self._create_line_edit("themes", "Fantasy, Sci-fi")
        grid.addWidget(self.themes, 7, 1)
        grid.addWidget(self._create_form_label("Perspective:"), 7, 2)
        self.perspective = self._create_line_edit("player_perspective", "First-person, Third-person")
        grid.addWidget(self.perspective, 7, 3)

        general_layout.addLayout(grid)

        # Description (multi-line)
        desc_label = self._create_form_label("Description:")
        desc_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        general_layout.addWidget(desc_label)
        self.desc = QTE()
        self.desc.setPlainText(self.game.get("description", ""))
        self.desc.setMinimumHeight(120)
        general_layout.addWidget(self.desc)

        # Save Location (multi-line)
        save_label = self._create_form_label("Save Location:")
        save_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        general_layout.addWidget(save_label)
        self.save_loc = QTE(self.game.get("save_location", ""))
        self.save_loc.setFixedHeight(80)
        general_layout.addWidget(self.save_loc)

        # Checkboxes row (Played + Favourite)
        checkboxes_widget = QWidget()
        checkboxes_layout = QHBoxLayout(checkboxes_widget)
        checkboxes_layout.setContentsMargins(0, 10, 0, 0)
        self.played_checkbox = QCheckBox("Mark as played")
        self.played_checkbox.setChecked(self.game.get("played", False))
        self.fav_checkbox = QCheckBox("Mark as favourite")
        self.fav_checkbox.setChecked(self.game.get("fav", False))
        checkboxes_layout.addWidget(self.played_checkbox)
        checkboxes_layout.addWidget(self.fav_checkbox)
        checkboxes_layout.addStretch()
        general_layout.addWidget(checkboxes_widget)

        general_layout.addStretch()
        tab_widget.addTab(general_tab, "General")

        # ========== MEDIA TAB (single URLs + list fields) ==========
        media_tab = QWidget()
        media_layout = QVBoxLayout(media_tab)
        media_layout.setContentsMargins(20, 20, 20, 20)
        media_layout.setSpacing(15)

        # Single URL fields
        single_form = QFormLayout()
        single_form.setSpacing(12)
        self.cover = self._create_line_edit("cover_url", "https://...")
        self.igdb_cover = self._create_line_edit("igdb_cover_art", "IGDB cover URL")
        self.trailer = self._create_line_edit("trailer_webm", "https://...")
        single_form.addRow(self._create_form_label("Cover URL (Steam):"), self.cover)
        single_form.addRow(self._create_form_label("IGDB Cover Art URL:"), self.igdb_cover)
        single_form.addRow(self._create_form_label("Trailer URL (webm):"), self.trailer)
        media_layout.addLayout(single_form)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #bdc3c7; max-height: 1px;")
        media_layout.addWidget(sep)

        # List fields (one per line)
        screenshots_label = QLabel("Screenshots URLs (one per line):")
        screenshots_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        media_layout.addWidget(screenshots_label)
        self.screenshots = self._create_text_edit("screenshots")
        self.screenshots.setFixedHeight(120)
        media_layout.addWidget(self.screenshots)

        micro_label = QLabel("Extra Microtrailers URLs (one per line):")
        micro_label.setStyleSheet("font-weight: 600;")
        media_layout.addWidget(micro_label)
        self.microtrailers_extra = self._create_text_edit("microtrailers_extra")
        self.microtrailers_extra.setFixedHeight(100)
        media_layout.addWidget(self.microtrailers_extra)

        trailers_label = QLabel("IGDB Trailers URLs (one per line):")
        trailers_label.setStyleSheet("font-weight: 600;")
        media_layout.addWidget(trailers_label)
        self.trailers = self._create_text_edit("trailers")
        self.trailers.setFixedHeight(100)
        media_layout.addWidget(self.trailers)

        media_layout.addStretch()
        tab_widget.addTab(media_tab, "Media")

        # ========== LINKS TAB ==========
        links_tab = QWidget()
        links_layout = QFormLayout(links_tab)
        links_layout.setContentsMargins(20, 20, 20, 20)
        links_layout.setSpacing(12)
        self.steam = self._create_line_edit("steam_link", "https://store.steampowered.com/app/...")
        self.steamdb = self._create_line_edit("steamdb_link", "https://steamdb.info/app/...")
        self.pcgw = self._create_line_edit("pcgw_link", "https://www.pcgamingwiki.com/wiki/...")
        self.igdb_link = self._create_line_edit("igdb_link", "https://www.igdb.com/games/...")
        links_layout.addRow(self._create_form_label("Steam Link:"), self.steam)
        links_layout.addRow(self._create_form_label("SteamDB Link:"), self.steamdb)
        links_layout.addRow(self._create_form_label("PCGamingWiki:"), self.pcgw)
        links_layout.addRow(self._create_form_label("IGDB Link:"), self.igdb_link)
        tab_widget.addTab(links_tab, "Links")

        # ========== CACHE TAB (read-only) ==========
        cache_tab = QWidget()
        cache_layout = QVBoxLayout(cache_tab)
        cache_layout.setContentsMargins(20, 20, 20, 20)
        cache_layout.setSpacing(15)

        cache_info = QLabel("Cached assets (read-only – edit by recaching)")
        cache_info.setStyleSheet("font-weight: bold; color: #3498db;")
        cache_layout.addWidget(cache_info)

        screenshots_cache_label = QLabel("Screenshots cache paths (one per line):")
        screenshots_cache_label.setStyleSheet("font-weight: 600;")
        cache_layout.addWidget(screenshots_cache_label)
        self.screenshots_cache = QTE()
        self.screenshots_cache.setReadOnly(True)
        self.screenshots_cache.setFixedHeight(120)
        paths = self.game.get("image_cache_paths", [])
        if isinstance(paths, list):
            self.screenshots_cache.setPlainText("\n".join(str(p) for p in paths if p))
        else:
            self.screenshots_cache.setPlainText(str(paths) if paths else "")
        cache_layout.addWidget(self.screenshots_cache)

        micro_cache_label = QLabel("Microtrailer cache path:")
        micro_cache_label.setStyleSheet("font-weight: 600;")
        cache_layout.addWidget(micro_cache_label)
        self.micro_cache = QTE()
        self.micro_cache.setReadOnly(True)
        self.micro_cache.setFixedHeight(60)
        micro_path = self.game.get("microtrailer_cache_path", "")
        self.micro_cache.setPlainText(str(micro_path) if micro_path else "")
        cache_layout.addWidget(self.micro_cache)

        igdb_cover_cache_label = QLabel("IGDB Cover cache path:")
        igdb_cover_cache_label.setStyleSheet("font-weight: 600;")
        cache_layout.addWidget(igdb_cover_cache_label)
        self.igdb_cover_cache = QTE()
        self.igdb_cover_cache.setReadOnly(True)
        self.igdb_cover_cache.setFixedHeight(60)
        igdb_cover_path = self.game.get("igdb_cover_art_cache_path", "")
        self.igdb_cover_cache.setPlainText(str(igdb_cover_path) if igdb_cover_path else "")
        cache_layout.addWidget(self.igdb_cover_cache)

        cache_layout.addStretch()
        tab_widget.addTab(cache_tab, "Cache")

        main_layout.addWidget(tab_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _create_line_edit(self, key: str, placeholder: str = "") -> QLineEdit:
        value = self.game.get(key, "")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        edit = QLineEdit(str(value))
        edit.setPlaceholderText(placeholder)
        edit.setMinimumWidth(200)  # ensure enough width
        return edit

    def _create_text_edit(self, key: str) -> QTE:
        """Create a QTextEdit populated with a list (one item per line)."""
        value = self.game.get(key, [])
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        elif not isinstance(value, list):
            value = []
        text = "\n".join(str(v) for v in value if v)
        edit = QTE()
        edit.setPlainText(text)
        return edit

    def _create_form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setMinimumWidth(100)
        label.setStyleSheet("font-weight: 600; color: #2c3e50;")
        return label

    def result(self) -> dict:
        def to_list(text_edit: QTE) -> list:
            text = text_edit.toPlainText().strip()
            if not text:
                return []
            return [line.strip() for line in text.splitlines() if line.strip()]

        return {
            "title": self.title.text().strip(),
            "app_id": self.appid.text().strip(),
            "igdb_id": self.igdb_id.text().strip(),
            "user_rating": self.user_rating.text().strip(),
            "release_date": self.release.text().strip(),
            "developer": self.dev.text().strip(),
            "publisher": self.pub.text().strip(),
            "genres": self.genres.text().strip(),
            "description": self.desc.toPlainText().strip(),
            "cover_url": self.cover.text().strip(),
            "igdb_cover_art": self.igdb_cover.text().strip(),
            "trailer_webm": self.trailer.text().strip(),
            "steam_link": self.steam.text().strip(),
            "steamdb_link": self.steamdb.text().strip(),
            "pcgw_link": self.pcgw.text().strip(),
            "igdb_link": self.igdb_link.text().strip(),
            "screenshots": to_list(self.screenshots),
            "microtrailers_extra": to_list(self.microtrailers_extra),
            "trailers": to_list(self.trailers),
            "save_location": self.save_loc.toPlainText().strip(),
            "game_drive": self.game_drive.text().strip(),
            "scene_repack": self.scene_repack.text().strip(),
            "game_modes": self.game_modes.text().strip(),
            "original_title": self.original_title.text().strip(),
            "patch_version": self.patch_version.text().strip(),
            "themes": self.themes.text().strip(),
            "player_perspective": self.perspective.text().strip(),
            "played": self.played_checkbox.isChecked(),
            "fav": self.fav_checkbox.isChecked()
        }