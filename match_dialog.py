# match_dialog.py
"""
MatchDialog - a PyQt5 dialog to present fuzzy candidates and let the user pick one.
Updated: Restored original design with enhanced IGDB and Steam search buttons.
Fixed: Thread destruction error and IGDB search issues.
Removed "Apply + Next" button.
Apply button is now enabled only when a candidate has either an IGDB ID or a Steam ID.
Open candidate button now respects the currently selected tab (IGDB or Steam).

Usage:
  dlg = MatchDialog(original_item, candidates, parent=window)
  if dlg.exec_() == QDialog.Accepted:
      result = dlg.result_dict
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTextEdit, QLineEdit, QCheckBox, QMessageBox, QWidget,
    QApplication, QGroupBox, QFormLayout, QSplitter, QFrame, QTabWidget
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QSize, QCoreApplication, QThread, pyqtSignal, QObject, QTimer
import webbrowser
import requests
from urllib.parse import quote_plus
import sys
import argparse
import time
import json
from typing import Dict, List, Optional, Any
import config

# Use scraping module for all candidate searches
try:
    import scraping
    HAVE_SCRAPING = True
except Exception as e:
    print(f"Warning: Could not import scraping module: {e}")
    scraping = None
    HAVE_SCRAPING = False


class ImageLoader(QThread):
    """Thread for loading images in background to prevent UI freeze."""
    image_loaded = pyqtSignal(str, QPixmap)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
    
    def run(self):
        if not self.url:
            return
        
        try:
            resp = requests.get(self.url, timeout=5)
            if resp.status_code == 200 and resp.content:
                pixmap = QPixmap()
                pixmap.loadFromData(resp.content)
                self.image_loaded.emit(self.url, pixmap)
        except Exception:
            pass
    
    def __del__(self):
        self.quit()
        self.wait()

class MetadataFetcher(QThread):
    """Fetch full metadata for a candidate (IGDB or Steam) in background."""
    metadata_ready = pyqtSignal(dict, str)

    def __init__(self, candidate: dict, source: str):
        super().__init__()
        self.candidate = candidate
        self.source = source

    def run(self):
        try:
            source_str = self.candidate.get('source', '').lower()
            # Skip fetching for test/dummy candidates
            if source_str == 'test' or source_str.startswith('manual'):
                self.metadata_ready.emit(self.candidate, self.source)
                return

            if self.source == 'igdb':
                igdb_id = self.candidate.get('id') or self.candidate.get('igdb_id')
                title = self.candidate.get('name') or self.candidate.get('title')
                # Only fetch if ID is numeric and not obviously dummy (e.g., 12345)
                if igdb_id and str(igdb_id).isdigit() and int(igdb_id) > 10000:
                    result = scraping.igdb_scraper(title, igdb_id=igdb_id, auto_accept_score=0)
                    if result and '__error__' not in result and '__candidates__' not in result:
                        self.metadata_ready.emit(result, 'igdb')
                        return
            else:  # steam
                steam_id = self.candidate.get('steam_id') or self.candidate.get('id') or self.candidate.get('steam_app_id')
                if steam_id and str(steam_id).isdigit() and int(steam_id) > 10000:
                    result = scraping.get_store_metadata(steam_id, self.candidate.get('name', ''))
                    if result and result.get('title'):
                        self.metadata_ready.emit(result, 'steam')
                        return
            # Fallback: emit original candidate
            self.metadata_ready.emit(self.candidate, self.source)
        except Exception as e:
            print(f"[MetadataFetcher] Error: {e}")
            self.metadata_ready.emit(self.candidate, self.source)
            
class MatchDialog(QDialog):
    """
    original_item: dict with keys 'title','original_title','description'
    candidates: list of dicts with keys 'id','name','score','source' (optional other keys)
    Updated for IGDB: 'id' is IGDB ID, 'steam_id' for Steam AppID
    """

    def __init__(self, original_item: dict, candidates: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resolve ambiguous match - IGDB & Steam")
        self.resize(920, 560)
        self.original = original_item or {}
        self.candidates = candidates or []
        self.result_dict = None
        
        # Image cache to avoid reloading
        self.image_cache = {}
        # Track active image loaders
        self.current_igdb_desc = ""
        self.current_steam_desc = ""
        self.active_image_loaders = []
        self.active_fetchers = []      # <-- add
        self.fetcher_igdb = None       # <-- add
        self.fetcher_steam = None      # <-- add
        # Initialize UI
        self.init_ui()
        
        # Select first candidate if present
        if self.igdb_list.count():
            self.igdb_list.setCurrentRow(0)
        
        # Auto-search missing sources if we have a title
        title = self.manual_title.text().strip()
        if title:
            if self.igdb_list.count() == 0:
                QTimer.singleShot(100, self.search_igdb_by_title)
            if self.steam_list.count() == 0:
                QTimer.singleShot(200, self.search_steam_by_title)

    def init_ui(self):
        """Initialize the user interface with side-by-side previews."""
        main_layout = QHBoxLayout()
        
        # Left: candidate list and search controls
        left_widget = QWidget()
        left_widget.setMaximumWidth(400)
        left_layout = QVBoxLayout()
        
        # Search controls group
        search_group = QGroupBox("Search Controls")
        search_layout = QVBoxLayout()
        
        # Horizontal layout for search buttons
        search_buttons_row1 = QHBoxLayout()
        search_buttons_row2 = QHBoxLayout()
        
        # IGDB search buttons
        self.igdb_search_title_btn = QPushButton("Search IGDB by Title")
        self.igdb_search_id_btn = QPushButton("Lookup IGDB by ID")
        
        # Steam search buttons
        self.steam_search_title_btn = QPushButton("Search Steam by Title")
        self.steam_search_id_btn = QPushButton("Lookup Steam by ID")
        
        # Combined search button
        self.search_both_btn = QPushButton("Search Both (IGDB & Steam)")
        self.search_both_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        search_buttons_row1.addWidget(self.igdb_search_title_btn)
        search_buttons_row1.addWidget(self.igdb_search_id_btn)
        search_buttons_row2.addWidget(self.steam_search_title_btn)
        search_buttons_row2.addWidget(self.steam_search_id_btn)
        
        search_layout.addLayout(search_buttons_row1)
        search_layout.addLayout(search_buttons_row2)
        search_layout.addWidget(self.search_both_btn)
        
        # Manual search input
        search_layout.addWidget(QLabel("Manual Title:"))
        self.manual_title = QLineEdit(self.original.get('title', ''))
        self.manual_title.setMinimumHeight(config.TEXT_BOX_HEIGHT)   # <-- added
        search_layout.addWidget(self.manual_title)
        
        # Manual IDs
        ids_layout = QHBoxLayout()
        ids_layout.addWidget(QLabel("IGDB ID:"))
        self.manual_igdb_id = QLineEdit(self.original.get('igdb_id', ''))
        self.manual_igdb_id.setMaximumWidth(150)
        self.manual_igdb_id.setMinimumHeight(config.TEXT_BOX_HEIGHT)  # <-- added
        ids_layout.addWidget(self.manual_igdb_id)
        
        ids_layout.addWidget(QLabel("Steam ID:"))
        self.manual_steam_id = QLineEdit(self.original.get('steam_id', '') or self.original.get('app_id', ''))
        self.manual_steam_id.setMaximumWidth(150)
        self.manual_steam_id.setMinimumHeight(config.TEXT_BOX_HEIGHT) # <-- added
        ids_layout.addWidget(self.manual_steam_id)
        
        search_layout.addLayout(ids_layout)
        
        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group)
        
        # Candidate lists with tabs
        self.tabs_widget = QTabWidget()
        
        # IGDB tab
        igdb_tab = QWidget()
        igdb_layout = QVBoxLayout()
        self.igdb_list = QListWidget()
        self.igdb_list.setAlternatingRowColors(True)
        igdb_layout.addWidget(self.igdb_list)
        igdb_tab.setLayout(igdb_layout)
        self.tabs_widget.addTab(igdb_tab, "IGDB Results")
        
        # Steam tab
        steam_tab = QWidget()
        steam_layout = QVBoxLayout()
        self.steam_list = QListWidget()
        self.steam_list.setAlternatingRowColors(True)
        steam_layout.addWidget(self.steam_list)
        steam_tab.setLayout(steam_layout)
        self.tabs_widget.addTab(steam_tab, "Steam Results")
        
        left_layout.addWidget(self.tabs_widget, 1)
        
        # Load more buttons
        self.load_more_igdb_btn = QPushButton("Load More IGDB Candidates (+10)")
        self.load_more_steam_btn = QPushButton("Load More Steam Candidates (+10)")
        load_more_layout = QHBoxLayout()
        load_more_layout.addWidget(self.load_more_igdb_btn)
        load_more_layout.addWidget(self.load_more_steam_btn)
        left_layout.addLayout(load_more_layout)
        
        left_widget.setLayout(left_layout)
        main_layout.addWidget(left_widget)
        
        # Right: side-by-side previews
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        # Original item info
        self.title_label = QLabel(f"<b>Original:</b> {self.original.get('original_title') or self.original.get('title','')}")
        self.title_label.setWordWrap(True)
        right_layout.addWidget(self.title_label)
        
        # Splitter for IGDB and Steam previews
        self.preview_splitter = QSplitter(Qt.Horizontal)
        
        # ---- IGDB Preview ----
        igdb_preview_widget = QWidget()
        igdb_preview_layout = QVBoxLayout(igdb_preview_widget)
        igdb_preview_layout.setAlignment(Qt.AlignTop)
        
        igdb_header = QLabel("<b>IGDB Candidate</b>")
        igdb_header.setAlignment(Qt.AlignCenter)
        igdb_preview_layout.addWidget(igdb_header)
        
        self.cover_igdb = QLabel()
        self.cover_igdb.setFixedSize(QSize(120, 160))
        self.cover_igdb.setAlignment(Qt.AlignCenter)
        self.cover_igdb.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.cover_igdb.setText("IGDB\nNo cover")
        igdb_preview_layout.addWidget(self.cover_igdb, alignment=Qt.AlignCenter)
        
        self.igdb_meta = QLabel()
        self.igdb_meta.setWordWrap(True)
        self.igdb_meta.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.igdb_meta.setOpenExternalLinks(True)
        igdb_preview_layout.addWidget(self.igdb_meta)
        
        # ---- Steam Preview ----
        steam_preview_widget = QWidget()
        steam_preview_layout = QVBoxLayout(steam_preview_widget)
        steam_preview_layout.setAlignment(Qt.AlignTop)
        
        steam_header = QLabel("<b>Steam Candidate</b>")
        steam_header.setAlignment(Qt.AlignCenter)
        steam_preview_layout.addWidget(steam_header)
        
        self.cover_steam = QLabel()
        self.cover_steam.setFixedSize(QSize(240, 120))
        self.cover_steam.setAlignment(Qt.AlignCenter)
        self.cover_steam.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.cover_steam.setText("Steam\nNo cover")
        
        steam_preview_layout.addWidget(self.cover_steam, alignment=Qt.AlignCenter)
        
        self.steam_meta = QLabel()
        self.steam_meta.setWordWrap(True)
        self.steam_meta.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.steam_meta.setOpenExternalLinks(True)
        steam_preview_layout.addWidget(self.steam_meta)
        
        self.preview_splitter.addWidget(igdb_preview_widget)
        self.preview_splitter.addWidget(steam_preview_widget)
        self.preview_splitter.setSizes([300, 300])
        
        right_layout.addWidget(self.preview_splitter, 1)
        
        # ---- Combined Description Area ----
        desc_group = QGroupBox("Candidate Descriptions")
        desc_layout = QVBoxLayout(desc_group)
        self.desc_preview = QTextEdit()
        self.desc_preview.setReadOnly(True)
        self.desc_preview.setMinimumHeight(150)
        desc_layout.addWidget(self.desc_preview)
        right_layout.addWidget(desc_group)
        
        # Action buttons (Apply + Next removed)
        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Selected")
        self.skip_btn = QPushButton("Skip")
        self.open_btn = QPushButton("Open Candidate Page")
        self.overwrite_chk = QCheckBox("Overwrite existing fields")
        
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.skip_btn)
        right_layout.addLayout(btn_row)
        right_layout.addWidget(self.overwrite_chk)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 10pt;")
        right_layout.addWidget(self.status_label)
        
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget)
        
        self.setLayout(main_layout)
        
        # Connect signals
        self.igdb_list.currentItemChanged.connect(lambda current, previous: self._update_igdb_preview(current))
        self.igdb_list.itemClicked.connect(lambda item: self._update_igdb_preview(item))
        self.steam_list.currentItemChanged.connect(lambda current, previous: self._update_steam_preview(current))
        self.steam_list.itemClicked.connect(lambda item: self._update_steam_preview(item))
        self.apply_btn.clicked.connect(self.on_apply)
        self.skip_btn.clicked.connect(self.reject)
        self.open_btn.clicked.connect(self.on_open_candidate)
        self.igdb_search_title_btn.clicked.connect(self.search_igdb_by_title)
        self.igdb_search_id_btn.clicked.connect(self.lookup_igdb_by_id)
        self.steam_search_title_btn.clicked.connect(self.search_steam_by_title)
        self.steam_search_id_btn.clicked.connect(self.lookup_steam_by_id)
        self.search_both_btn.clicked.connect(self.search_both_by_title)
        self.load_more_igdb_btn.clicked.connect(lambda: self.load_more_candidates('igdb', 10))
        self.load_more_steam_btn.clicked.connect(lambda: self.load_more_candidates('steam', 10))
        
        # Initialize button states
        self.apply_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        
        # Populate initial candidates
        self._populate_initial_candidates()
            
    def closeEvent(self, event):
        # Stop all fetchers
        for fetcher in self.active_fetchers:
            if fetcher.isRunning():
                fetcher.quit()
                fetcher.wait()
        self.active_fetchers.clear()
        # Stop image loaders
        for loader in self.active_image_loaders:
            if loader.isRunning():
                loader.quit()
                loader.wait()
        self.active_image_loaders.clear()
        event.accept()
        
    def _populate_initial_candidates(self):
        """Separate initial candidates into IGDB and Steam lists."""
        for cand in self.candidates:
            source = cand.get("source", "").lower()
            if 'igdb' in source:
                self._add_candidate_to_list(cand, 'igdb')
            elif 'steam' in source:
                self._add_candidate_to_list(cand, 'steam')
            else:
                self._add_candidate_to_list(cand, 'igdb')
        
        # Manually trigger preview for first IGDB candidate
        if self.igdb_list.count():
            first_item = self.igdb_list.item(0)
            if first_item:
                self._update_igdb_preview(first_item)
                
    def _update_igdb_preview(self, item):
        """Update the IGDB preview panel when a candidate is selected."""
        if not item:
            self.cover_igdb.setText("IGDB\nNo cover")
            self.cover_igdb.setPixmap(QPixmap())
            self.igdb_meta.setText("")
            self.apply_btn.setEnabled(False)
            self.current_igdb_desc = ""
            self._update_combined_description()
            return

        c = item.data(Qt.UserRole)
        # Enable Apply button only if candidate has an IGDB ID (or Steam ID from this tab, but this is IGDB tab)
        has_igdb_id = bool(c.get('id') or c.get('igdb_id'))
        has_steam_id = bool(c.get('steam_id') or c.get('steam_app_id') or c.get('app_id'))
        self.apply_btn.setEnabled(has_igdb_id or has_steam_id)   # now allows Steam ID also
        self.open_btn.setEnabled(True)

        # Stop existing IGDB fetcher
        if self.fetcher_igdb and self.fetcher_igdb.isRunning():
            self.fetcher_igdb.quit()
            self.fetcher_igdb.wait()
            if self.fetcher_igdb in self.active_fetchers:
                self.active_fetchers.remove(self.fetcher_igdb)

        if '_full_metadata' in c:
            self._display_igdb_candidate(c['_full_metadata'])
        else:
            self.igdb_meta.setText("<i>Loading full metadata...</i>")
            self.current_igdb_desc = "Loading description..."
            self._update_combined_description()
            self.fetcher_igdb = MetadataFetcher(c, 'igdb')
            self.active_fetchers.append(self.fetcher_igdb)
            self.fetcher_igdb.metadata_ready.connect(lambda meta, src: self._on_igdb_metadata_fetched(meta, item))
            self.fetcher_igdb.start()
            
    def _display_igdb_candidate(self, c: dict):
        """Display IGDB candidate data."""
        # Cover
        cover_url = c.get('cover_url') or c.get('igdb_cover_url') or c.get('tiny_image')
        if cover_url:
            self.load_image_async(cover_url, 'igdb')
        else:
            self.cover_igdb.setText("IGDB\nNo cover")
            self.cover_igdb.setPixmap(QPixmap())
        
        # Metadata
        igdb_id = c.get('id') or c.get('igdb_id') or ""
        meta_html = f"<b>{c.get('name','') or c.get('title','')}</b><br>"
        if igdb_id:
            meta_html += f"IGDB ID: {igdb_id}<br>"
        if c.get('genres'):
            meta_html += f"Genres: {c.get('genres')}<br>"
        if c.get('developer'):
            meta_html += f"Developer: {c.get('developer')}<br>"
        if c.get('publisher'):
            meta_html += f"Publisher: {c.get('publisher')}<br>"
        if c.get('release_date'):
            meta_html += f"Release: {c.get('release_date')}<br>"
        meta_html += f"Score: {int(c.get('score',0))}%<br>Source: {c.get('source','')}"
        if c.get('rating_display'):
            meta_html += f"<br>Rating: {c.get('rating_display')}"
        self.igdb_meta.setText(meta_html)
        # Update manual fields
        if c.get('name') or c.get('title'):
            self.manual_title.setText(c.get('name') or c.get('title'))
        igdb_id = c.get('id') or c.get('igdb_id') or ""
        self.manual_igdb_id.setText(str(igdb_id) if igdb_id else "N/A")
        # Do NOT clear Steam ID field (leave as is)
        
        # Description
        desc = c.get('description') or c.get('summary') or ''
        self.current_igdb_desc = desc
        self._update_combined_description()

    def _update_steam_preview(self, item):
        """Update the Steam preview panel when a candidate is selected."""
        if not item:
            self.cover_steam.setText("Steam\nNo cover")
            self.cover_steam.setPixmap(QPixmap())
            self.steam_meta.setText("")
            self.apply_btn.setEnabled(False)
            self.current_steam_desc = ""
            self._update_combined_description()
            return

        c = item.data(Qt.UserRole)
        # Enable Apply button if candidate has either IGDB or Steam ID
        has_igdb_id = bool(c.get('id') or c.get('igdb_id'))
        has_steam_id = bool(c.get('steam_id') or c.get('steam_app_id') or c.get('app_id'))
        self.apply_btn.setEnabled(has_igdb_id or has_steam_id)
        self.open_btn.setEnabled(True)

        # Stop existing Steam fetcher
        if self.fetcher_steam and self.fetcher_steam.isRunning():
            self.fetcher_steam.quit()
            self.fetcher_steam.wait()
            if self.fetcher_steam in self.active_fetchers:
                self.active_fetchers.remove(self.fetcher_steam)

        if '_full_metadata' in c:
            self._display_steam_candidate(c['_full_metadata'])
        else:
            self.steam_meta.setText("<i>Loading full metadata...</i>")
            self.current_steam_desc = "Loading description..."
            self._update_combined_description()
            self.fetcher_steam = MetadataFetcher(c, 'steam')
            self.active_fetchers.append(self.fetcher_steam)
            self.fetcher_steam.metadata_ready.connect(lambda meta, src: self._on_steam_metadata_fetched(meta, item))
            self.fetcher_steam.start()
        
    def _display_steam_candidate(self, c: dict):
        """Display Steam candidate data."""
        # Cover
        cover_url = c.get('cover_url') or c.get('tiny_image') or c.get('header_image')
        steam_id = c.get('steam_id') or c.get('steam_app_id') or c.get('app_id')
        if steam_id and not cover_url:
            cover_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{steam_id}/header.jpg"
        if cover_url:
            self.load_image_async(cover_url, 'steam')
        else:
            self.cover_steam.setText("Steam\nNo cover")
            self.cover_steam.setPixmap(QPixmap())
        
        # Metadata
        steam_id = c.get('steam_id') or c.get('steam_app_id') or c.get('app_id') or ""
        meta_html = f"<b>{c.get('name','') or c.get('title','')}</b><br>"
        if steam_id:
            meta_html += f"Steam ID: {steam_id}<br>"
        if c.get('genres'):
            meta_html += f"Genres: {c.get('genres')}<br>"
        if c.get('developer'):
            meta_html += f"Developer: {c.get('developer')}<br>"
        if c.get('publisher'):
            meta_html += f"Publisher: {c.get('publisher')}<br>"
        if c.get('release_date'):
            meta_html += f"Release: {c.get('release_date')}<br>"
        meta_html += f"Score: {int(c.get('score',0))}%<br>Source: {c.get('source','')}"
        self.steam_meta.setText(meta_html)
        # Update manual fields
        if c.get('name') or c.get('title'):
            self.manual_title.setText(c.get('name') or c.get('title'))
        steam_id = c.get('steam_id') or c.get('steam_app_id') or c.get('app_id') or ""
        self.manual_steam_id.setText(str(steam_id) if steam_id else "N/A")
        # Do NOT clear IGDB ID field
        # Description
        desc = c.get('description') or c.get('summary') or ''
        self.current_steam_desc = desc
        self._update_combined_description()

    def _on_igdb_metadata_fetched(self, metadata, list_item):
        # Check if the list item still exists and belongs to the IGDB list
        try:
            # Verify the item is still in the list
            row = self.igdb_list.row(list_item)
            if row == -1:
                return  # Item no longer in list
            # Also verify the item hasn't been replaced
            if self.igdb_list.item(row) is not list_item:
                return
            c = list_item.data(Qt.UserRole)
            if c is None:
                return
            c['_full_metadata'] = metadata
            list_item.setData(Qt.UserRole, c)
            # Only update preview if this item is currently selected
            if self.igdb_list.currentItem() == list_item:
                self._display_igdb_candidate(metadata)
        except RuntimeError:
            # Item was deleted
            pass

    def _on_steam_metadata_fetched(self, metadata, list_item):
        try:
            row = self.steam_list.row(list_item)
            if row == -1:
                return
            if self.steam_list.item(row) is not list_item:
                return
            c = list_item.data(Qt.UserRole)
            if c is None:
                return
            c['_full_metadata'] = metadata
            list_item.setData(Qt.UserRole, c)
            if self.steam_list.currentItem() == list_item:
                self._display_steam_candidate(metadata)
        except RuntimeError:
            pass
            
    def _update_combined_description(self):
        """Combine IGDB and Steam descriptions into the single text area."""
        html = ""
        if self.current_igdb_desc:
            html += f"<b>🎮 IGDB Description:</b><br>{self.current_igdb_desc}<br><br>"
        if self.current_steam_desc:
            html += f"<b>🖥️ Steam Description:</b><br>{self.current_steam_desc}"
        if not html:
            html = "<i>No descriptions available</i>"
        self.desc_preview.setHtml(html)
    
    # -------------------------
    # Candidate list helpers
    # -------------------------
    def _add_candidate_to_list(self, candidate: dict, list_type: str = 'igdb'):
        """Add a single candidate to the appropriate list."""
        name = candidate.get("name") or candidate.get("title") or ""
        source = candidate.get("source") or ""
        score = int(candidate.get("score", 0))
        igdb_id = candidate.get("id") or candidate.get("igdb_id") or ""
        steam_id = candidate.get("steam_id") or candidate.get("steam_app_id") or candidate.get("app_id") or ""
        
        label = f"{name}"
        if igdb_id:
            label += f" [IGDB:{igdb_id}]"
        if steam_id:
            label += f" [Steam:{steam_id}]"
        label += f"  [{source}]  ({score}%)"
        
        # Add rating if available
        if candidate.get("rating_display"):
            label += f" - {candidate['rating_display']}"
        
        it = QListWidgetItem(label)
        it.setData(Qt.UserRole, candidate)
        
        if list_type == 'igdb':
            self.igdb_list.addItem(it)
            # Select if it's the first one
            if self.igdb_list.count() == 1:
                self.igdb_list.setCurrentRow(0)
        else:
            self.steam_list.addItem(it)
            if self.steam_list.count() == 1:
                self.steam_list.setCurrentRow(0)

    # -------------------------
    # Search functions
    # -------------------------
    def search_igdb_by_title(self):
        """Search IGDB by game title."""
        if not HAVE_SCRAPING:
            QMessageBox.warning(self, "Search unavailable", "Scraping module not available.")
            return
        
        title = self.manual_title.text().strip()
        if not title:
            QMessageBox.information(self, "Search", "Please enter a title to search.")
            return
        
        self.status_label.setText("Searching IGDB...")
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        
        try:
            QCoreApplication.processEvents()
            
            # Clear Steam ID when searching IGDB by title
            #self.manual_steam_id.clear()
            
            # Use scraping module to find IGDB candidates
            candidates = scraping.find_candidates_for_title_igdb(title, max_candidates=12)
            
            if not candidates:
                self.status_label.setText("No IGDB candidates found.")
                QMessageBox.information(self, "No results", "No IGDB candidates found for this title.")
                return
            
            # Clear and populate IGDB list
            self.igdb_list.clear()
            for candidate in candidates:
                self._add_candidate_to_list(candidate, 'igdb')
            
            self.status_label.setText(f"Found {len(candidates)} IGDB candidates.")
            
        except Exception as e:
            self.status_label.setText(f"IGDB search failed: {str(e)[:50]}...")
            QMessageBox.warning(self, "Search Error", f"IGDB search failed: {e}")
        finally:
            self.setCursor(old_cursor)
            QCoreApplication.processEvents()

    def lookup_igdb_by_id(self):
        """Lookup specific game by IGDB ID only."""
        if not HAVE_SCRAPING:
            QMessageBox.warning(self, "Lookup unavailable", "Scraping module not available.")
            return
        
        igdb_id = self.manual_igdb_id.text().strip()
        if not igdb_id:
            QMessageBox.information(self, "Lookup", "Please enter an IGDB ID.")
            return
        
        self.status_label.setText("Looking up IGDB ID...")
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        
        try:
            QCoreApplication.processEvents()
            
            # Clear Steam ID when searching IGDB by ID (mutual exclusive)
           # self.manual_steam_id.clear()
            
            # Try to get IGDB data by ID
            candidate_data = None
            
            # Try to use the scraping module's functions based on what's available
            try:
                # Option 1: Check if there's a direct ID lookup function
                if hasattr(scraping, 'get_game_by_igdb_id'):
                    result = scraping.get_game_by_igdb_id(igdb_id)
                    if result and not result.get("__error__"):
                        candidate_data = result
                
                # Option 2: Try the standard igdb_scraper function
                if not candidate_data and hasattr(scraping, 'igdb_scraper'):
                    # Use a descriptive title to trigger a search
                    result = scraping.igdb_scraper(f"id:{igdb_id}", auto_accept_score=0)
                    if "__error__" not in result:
                        # Check if it's a single result or multiple candidates
                        if "__candidates__" in result:
                            # Search for our ID in candidates
                            for cand in result["__candidates__"]:
                                cand_id = str(cand.get("id") or cand.get("igdb_id") or "")
                                if cand_id == igdb_id:
                                    candidate_data = cand
                                    break
                        else:
                            # Single result
                            result_id = str(result.get("id") or result.get("igdb_id") or "")
                            if result_id == igdb_id:
                                candidate_data = result
                
                # Option 3: Try to fetch from IGDB API directly (fallback)
                if not candidate_data:
                    # This is a direct API call that might work if you have IGDB API access
                    candidate_data = self._fetch_igdb_data_directly(igdb_id)
                    
            except Exception as e:
                print(f"Error in IGDB lookup: {e}")
            
            # If we still don't have data, create minimal candidate
            if not candidate_data:
                candidate_data = {
                    "id": igdb_id,
                    "igdb_id": igdb_id,
                    "name": f"IGDB Game ID: {igdb_id}",
                    "score": 100,
                    "source": "igdb_manual_id_only",
                    "description": "Could not fetch metadata. The game may not exist or the scraping module doesn't support direct ID lookups.",
                    "genres": "Unknown",
                    "developer": "Unknown"
                }
            
            # Print scraped metadata to console
            print("\n=== IGDB ID Scraped Metadata ===")
            print(f"IGDB ID: {igdb_id}")
            if candidate_data and "description" in candidate_data and candidate_data["description"]:
                print(f"Name: {candidate_data.get('name', 'Unknown')}")
                print(f"Source: {candidate_data.get('source', 'N/A')}")
                print(f"Has description: {'Yes' if candidate_data.get('description') else 'No'}")
                print(f"Has cover: {'Yes' if candidate_data.get('cover_url') else 'No'}")
            else:
                print("⚠ Minimal metadata only - consider using title search")
            print("=================================\n")
            
            # Clear and populate IGDB list
            self.igdb_list.clear()
            self._add_candidate_to_list(candidate_data, 'igdb')
            self.status_label.setText(f"Found IGDB game: {candidate_data.get('name', 'Unknown')}")
            
        except Exception as e:
            error_msg = str(e)
            self.status_label.setText(f"IGDB lookup failed")
            QMessageBox.warning(self, "Lookup Error", 
                f"IGDB lookup may not be fully supported by the scraping module.\n\n"
                f"Error: {error_msg[:100]}\n\n"
                f"Try using 'Search IGDB by Title' for better results.")
        finally:
            self.setCursor(old_cursor)
            QCoreApplication.processEvents()
    
    def _fetch_igdb_data_directly(self, igdb_id):
        """Fallback method to try direct IGDB API call."""
        try:
            # You would need to have IGDB API credentials set up for this
            # This is just a template - you'd need to implement actual API call
            print(f"[INFO] Attempting direct IGDB API call for ID: {igdb_id}")
            
            # Example structure (you'd need to implement the actual API call):
            # headers = {'Client-ID': 'your_client_id', 'Authorization': 'Bearer your_token'}
            # response = requests.post('https://api.igdb.com/v4/games', 
            #                         headers=headers,
            #                         data=f'fields name,summary,cover.url,genres.name,developers.name; where id = {igdb_id};')
            
            # For now, return None to indicate we can't fetch directly
            return None
            
        except Exception as e:
            print(f"Direct IGDB API call failed: {e}")
            return None

    def search_steam_by_title(self):
        """Search Steam by game title."""
        if not HAVE_SCRAPING:
            QMessageBox.warning(self, "Search unavailable", "Scraping module not available.")
            return
        
        title = self.manual_title.text().strip()
        if not title:
            QMessageBox.information(self, "Search", "Please enter a title to search.")
            return
        
        self.status_label.setText("Searching Steam...")
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        
        try:
            QCoreApplication.processEvents()
            
            # Use scraping module to find Steam candidates
            candidates = scraping.find_candidates_for_title(title, max_candidates=12)
            
            if not candidates:
                self.status_label.setText("No Steam candidates found.")
                QMessageBox.information(self, "No results", "No Steam candidates found for this title.")
                return
            
            # Clear and populate Steam list
            self.steam_list.clear()
            for candidate in candidates:
                # Convert to our format
                formatted = {
                    "id": candidate.get("id", ""),
                    "steam_id": candidate.get("id", ""),
                    "steam_app_id": candidate.get("id", ""),
                    "name": candidate.get("name", title),
                    "score": candidate.get("score", 0),
                    "source": candidate.get("source", "steam"),
                    "tiny_image": candidate.get("tiny_image", ""),
                    "cover_url": candidate.get("cover_url", ""),
                    "description": candidate.get("description", "")
                }
                self._add_candidate_to_list(formatted, 'steam')
            
            self.status_label.setText(f"Found {len(candidates)} Steam candidates.")
            
        except Exception as e:
            self.status_label.setText(f"Steam search failed: {str(e)[:50]}...")
            QMessageBox.warning(self, "Search Error", f"Steam search failed: {e}")
        finally:
            self.setCursor(old_cursor)
            QCoreApplication.processEvents()
            
    def lookup_steam_by_id(self):
        """Lookup specific game by Steam AppID only."""
        if not HAVE_SCRAPING:
            QMessageBox.warning(self, "Lookup unavailable", "Scraping module not available.")
            return
        
        steam_id = self.manual_steam_id.text().strip()
        if not steam_id:
            QMessageBox.information(self, "Lookup", "Please enter a Steam AppID.")
            return
        
        self.status_label.setText("Looking up Steam ID...")
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        
        try:
            QCoreApplication.processEvents()
            
            # Clear IGDB ID when searching Steam by ID (mutual exclusive)
            # self.manual_igdb_id.clear()
            
            # Use get_store_metadata with empty title since we're searching by ID only
            result = scraping.get_store_metadata(steam_id, "")
            
            if not result.get("title"):
                self.status_label.setText("Steam lookup failed: Invalid AppID or no data")
                QMessageBox.warning(self, "Lookup Error", "Steam lookup failed: Invalid AppID or no data")
                return
            
            # Create candidate
            candidate = {
                "id": steam_id,
                "steam_id": steam_id,
                "steam_app_id": steam_id,
                "name": result.get("title", f"Steam App {steam_id}"),
                "score": 100,
                "source": "steam_manual_id_only",
                "genres": result.get("genres", ""),
                "developer": result.get("developer", ""),
                "publisher": result.get("publisher", ""),
                "cover_url": result.get("cover_url", ""),
                "description": result.get("description", ""),
                "release_date": result.get("release_date", "")
            }
            
            # Print scraped metadata to console
            print("\n=== Steam ID Scraped Metadata ===")
            print(f"Steam ID: {steam_id}")
            print(f"Full data: {json.dumps(result, indent=2, default=str)}")
            print("==================================\n")
            
            # Clear and populate Steam list with the found candidate
            self.steam_list.clear()
            self._add_candidate_to_list(candidate, 'steam')
            self.status_label.setText(f"Found Steam game: {candidate['name']}")
            
        except Exception as e:
            self.status_label.setText(f"Steam lookup failed: {str(e)[:50]}...")
            QMessageBox.warning(self, "Lookup Error", f"Steam lookup failed: {e}")
        finally:
            self.setCursor(old_cursor)
            QCoreApplication.processEvents()

    def search_both_by_title(self):
        """Search both IGDB and Steam using title only."""
        if not HAVE_SCRAPING:
            QMessageBox.warning(self, "Search unavailable", "Scraping module not available.")
            return
        
        title = self.manual_title.text().strip()
        if not title:
            QMessageBox.information(self, "Search", "Please enter a title to search.")
            return
        
        self.status_label.setText("Searching IGDB and Steam...")
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        
        try:
            QCoreApplication.processEvents()
            
            # Clear both ID fields for combined search
            self.manual_igdb_id.clear()
            self.manual_steam_id.clear()
            
            # Search IGDB
            igdb_candidates = []
            try:
                igdb_candidates = scraping.find_candidates_for_title_igdb(title, max_candidates=6)
            except Exception as e:
                print(f"IGDB search error: {e}")
            
            # Search Steam
            steam_candidates = []
            try:
                steam_raw = scraping.find_candidates_for_title(title, max_candidates=6)
                for candidate in steam_raw:
                    formatted = {
                        "id": candidate.get("id", ""),
                        "steam_id": candidate.get("id", ""),
                        "steam_app_id": candidate.get("id", ""),
                        "name": candidate.get("name", title),
                        "score": candidate.get("score", 0),
                        "source": candidate.get("source", "steam"),
                        "tiny_image": candidate.get("tiny_image", ""),
                        "cover_url": candidate.get("cover_url", ""),
                        "description": candidate.get("description", "")
                    }
                    steam_candidates.append(formatted)
            except Exception as e:
                print(f"Steam search error: {e}")
            
            # Clear and populate both lists
            self.igdb_list.clear()
            self.steam_list.clear()
            
            for candidate in igdb_candidates:
                self._add_candidate_to_list(candidate, 'igdb')
            
            for candidate in steam_candidates:
                self._add_candidate_to_list(candidate, 'steam')
            
            total_found = len(igdb_candidates) + len(steam_candidates)
            self.status_label.setText(f"Found {len(igdb_candidates)} IGDB + {len(steam_candidates)} Steam = {total_found} total candidates.")
            
        except Exception as e:
            self.status_label.setText(f"Combined search failed: {str(e)[:50]}...")
            QMessageBox.warning(self, "Search Error", f"Combined search failed: {e}")
        finally:
            self.setCursor(old_cursor)
            QCoreApplication.processEvents()
            
    # -------------------------
    # Candidate selection preview
    # -------------------------
          

    def load_image_async(self, url: str, target: str):
        """Load image asynchronously for a specific cover (igdb or steam)."""
        if not url or url in self.image_cache:
            # If already cached, apply directly
            if url in self.image_cache:
                self._apply_cached_image(url, target)
            return
        
        # Clean up finished loaders
        self.active_image_loaders = [loader for loader in self.active_image_loaders if loader.isRunning()]
        
        # Create loader with target info
        loader = ImageLoader(url)
        # Use a lambda to capture target
        loader.image_loaded.connect(lambda u, p: self.on_image_loaded(u, p, target))
        loader.finished.connect(lambda: self.active_image_loaders.remove(loader) if loader in self.active_image_loaders else None)
        self.active_image_loaders.append(loader)
        loader.start()
        print(f"[Match_dialog] Loading image for {target}: {url}")
        
    def _apply_cached_image(self, url: str, target: str):
        """Apply a cached pixmap to the correct cover label, scaled to fit 3:4 box."""
        pixmap = self.image_cache.get(url)
        target_label = self.cover_igdb if target == 'igdb' else self.cover_steam
        if pixmap and not pixmap.isNull():
            # Scale to fit inside label while preserving aspect ratio
            scaled = pixmap.scaled(target_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            target_label.setPixmap(scaled)
            target_label.setText("")
        else:
            target_label.setText(f"{target.upper()}\nNo cover")
            target_label.setPixmap(QPixmap())
            
    def on_image_loaded(self, url: str, pixmap: QPixmap, target: str):
        """Handle image loaded signal and update the correct cover."""
        self.image_cache[url] = pixmap
        # Determine which cover should receive this image based on current selection
        current_igdb = self.igdb_list.currentItem()
        current_steam = self.steam_list.currentItem()
        
        # If the image belongs to the currently selected candidate of the matching source
        if target == 'igdb' and current_igdb:
            c = current_igdb.data(Qt.UserRole)
            cand_url = c.get('cover_url') or c.get('igdb_cover_url') or c.get('tiny_image')
            if cand_url == url:
                self._apply_cached_image(url, 'igdb')
        elif target == 'steam' and current_steam:
            c = current_steam.data(Qt.UserRole)
            cand_url = c.get('tiny_image') or c.get('cover_url')
            if cand_url == url:
                self._apply_cached_image(url, 'steam')
        print(f"[Match_dialog] Image loaded for {target}: {url} (pixmap size: {pixmap.width()}x{pixmap.height()})")
        
    # -------------------------
    # Open candidate in browser (respects active tab)
    # -------------------------
    def on_open_candidate(self):
        """Open the currently selected candidate's page in a web browser.
           If the active tab is IGDB, open IGDB page (using slug).
           If the active tab is Steam, open Steam store page.
        """
        # Determine which list is active based on the visible tab
        if not hasattr(self, 'tabs_widget'):
            # Fallback: check selection directly
            current_item = self.igdb_list.currentItem() or self.steam_list.currentItem()
            if not current_item:
                self.status_label.setText("No candidate selected.")
                return
            # Default to IGDB for old behavior
            c = current_item.data(Qt.UserRole)
            slug = c.get('slug')
            if slug:
                webbrowser.open(f"https://www.igdb.com/games/{slug}")
            else:
                steam_id = c.get('steam_id') or c.get('steam_app_id') or c.get('app_id')
                if steam_id:
                    webbrowser.open(f"https://store.steampowered.com/app/{steam_id}")
            return

        current_tab = self.tabs_widget.currentIndex()
        if current_tab == 0:  # IGDB tab
            current_item = self.igdb_list.currentItem()
            if not current_item:
                self.status_label.setText("No IGDB candidate selected.")
                return
            c = current_item.data(Qt.UserRole)
            # Use slug if available, otherwise create one from the game name
            slug = c.get('slug')
            if not slug:
                name = c.get('name') or c.get('title')
                if name:
                    import re
                    slug = name.lower()
                    slug = re.sub(r'[^\w\s-]', '', slug)  # Remove punctuation
                    slug = re.sub(r'[-\s]+', '-', slug)   # Replace spaces/hyphens with a single hyphen
                    slug = slug.strip('-')
                else:
                    # Fallback: search by name
                    if name:
                        webbrowser.open(f"https://www.igdb.com/search?query={quote_plus(name)}")
                        return
                    else:
                        self.status_label.setText("No game name available to search.")
                        return

            webbrowser.open(f"https://www.igdb.com/games/{slug}")

        else:  # Steam tab
            current_item = self.steam_list.currentItem()
            if not current_item:
                self.status_label.setText("No Steam candidate selected.")
                return
            c = current_item.data(Qt.UserRole)
            steam_id = c.get('steam_id') or c.get('steam_app_id') or c.get('app_id') or c.get('id')
            if steam_id:
                webbrowser.open(f"https://store.steampowered.com/app/{steam_id}")
            else:
                self.status_label.setText("No Steam AppID to open.")
                
                
    # -------------------------
    # Load more candidates
    # -------------------------
    def load_more_candidates(self, source: str, increment: int = 10):
        """Load additional candidates for IGDB or Steam by increasing the limit."""
        title = self.manual_title.text().strip()
        if not title:
            QMessageBox.information(self, "Load More", "Please enter a title first.")
            return
        
        # Determine current limit: we don't store it, so we'll just re‑search with a higher limit.
        # Simple approach: ask user for a new limit or just add increment to a guessed limit.
        # Better: keep a counter. For simplicity, we'll re‑run the search with a higher limit.
        # We'll use a hidden attribute to remember the last limit used.
        if not hasattr(self, '_last_igdb_limit'):
            self._last_igdb_limit = 12
        if not hasattr(self, '_last_steam_limit'):
            self._last_steam_limit = 12
        
        if source == 'igdb':
            new_limit = self._last_igdb_limit + increment
            self._last_igdb_limit = new_limit
            self.status_label.setText(f"Searching IGDB with limit {new_limit}...")
            old_cursor = self.cursor()
            self.setCursor(Qt.WaitCursor)
            try:
                QCoreApplication.processEvents()
                candidates = scraping.find_candidates_for_title_igdb(title, max_candidates=new_limit)
                # Clear and repopulate IGDB list
                self.igdb_list.clear()
                for cand in candidates:
                    self._add_candidate_to_list(cand, 'igdb')
                self.status_label.setText(f"Loaded {len(candidates)} IGDB candidates (limit {new_limit}).")
            except Exception as e:
                self.status_label.setText(f"IGDB load more failed: {str(e)[:50]}")
            finally:
                self.setCursor(old_cursor)
        elif source == 'steam':
            new_limit = self._last_steam_limit + increment
            self._last_steam_limit = new_limit
            self.status_label.setText(f"Searching Steam with limit {new_limit}...")
            old_cursor = self.cursor()
            self.setCursor(Qt.WaitCursor)
            try:
                QCoreApplication.processEvents()
                raw_candidates = scraping.find_candidates_for_title(title, max_candidates=new_limit)
                candidates = []
                for cand in raw_candidates:
                    
                    formatted = {
                        "id": cand.get("id", ""),
                        "steam_id": cand.get("id", ""),
                        "steam_app_id": cand.get("id", ""),
                        "name": cand.get("name", title),
                        "score": cand.get("score", 0),
                        "source": cand.get("source", "steam"),
                        "tiny_image": cand.get("tiny_image", ""),
                        "cover_url": cand.get("cover_url", ""),
                        "description": cand.get("description", "")
                    }
                    candidates.append(formatted)
                self.steam_list.clear()
                for cand in candidates:
                    self._add_candidate_to_list(cand, 'steam')
                self.status_label.setText(f"Loaded {len(candidates)} Steam candidates (limit {new_limit}).")
            except Exception as e:
                self.status_label.setText(f"Steam load more failed: {str(e)[:50]}")
            finally:
                self.setCursor(old_cursor)

    # -------------------------
    # Collect result
    # -------------------------
    def _collect_result(self, current_item, active_tab):
        # Manual title is the final title (user can edit it freely)
        manual_title = self.manual_title.text().strip()
        if not manual_title:
            manual_title = self.original.get('title', 'Untitled')
        
        manual_igdb_id = self.manual_igdb_id.text().strip()
        manual_steam_id = self.manual_steam_id.text().strip()
        
        candidate = current_item.data(Qt.UserRole) if current_item else None
        overwrite = self.overwrite_chk.isChecked()
        
        res = {
            "chosen_candidate": candidate,
            "applied_by": "user",
            "overwrite": overwrite,
            # Final title is always the manual title
            "title": manual_title,
        }
        
        # Store the candidate's original name under the correct source
        if candidate and candidate.get('name'):
            if active_tab == 0:   # IGDB tab active
                res['igdb_title'] = candidate.get('name')
            else:                 # Steam tab active
                res['steam_title'] = candidate.get('name')
        
        # IDs: manual input takes precedence over candidate
        if manual_igdb_id and manual_igdb_id != "N/A":
            res['igdb_id'] = manual_igdb_id
        elif candidate and candidate.get('id'):
            res['igdb_id'] = candidate.get('id')
        elif candidate and candidate.get('igdb_id'):
            res['igdb_id'] = candidate.get('igdb_id')
        else:
            res['igdb_id'] = "N/A"
        
        if manual_steam_id and manual_steam_id != "N/A":
            res['steam_id'] = manual_steam_id
            res['app_id'] = manual_steam_id
        elif candidate and candidate.get('steam_id'):
            res['steam_id'] = candidate.get('steam_id')
            res['app_id'] = candidate.get('steam_id')
        elif candidate and candidate.get('steam_app_id'):
            res['steam_id'] = candidate.get('steam_app_id')
            res['app_id'] = candidate.get('steam_app_id')
        elif candidate and candidate.get('app_id'):
            res['steam_id'] = candidate.get('app_id')
            res['app_id'] = candidate.get('app_id')
        else:
            res['steam_id'] = "N/A"
            res['app_id'] = "N/A"
        
        # Additional metadata from candidate (genres, developer, etc.)
        if candidate:
            for key in ['genres', 'developer', 'publisher', 'description', 'cover_url',
                        'release_date', 'rating_display', 'score', 'source']:
                if key in candidate and candidate[key]:
                    res[key] = candidate[key]
        
        if 'genres' not in res or not res['genres']:
            res['genres'] = "N/A"
        
        # Debug output
        print("\n=== SELECTED GAME OUTPUT ===")
        print(f"Manual Title (final): {res['title']}")
        print(f"IGDB ID: {res['igdb_id']}")
        print(f"Steam ID: {res['steam_id']}")
        if 'igdb_title' in res:
            print(f"IGDB Candidate Title: {res['igdb_title']}")
        if 'steam_title' in res:
            print(f"Steam Candidate Title: {res['steam_title']}")
        print(f"Overwrite: {overwrite}")
        print("=== END SELECTION ===\n")
        
        return res
 
    def on_apply(self):
        # Determine which tab is active (0 = IGDB, 1 = Steam)
        active_tab = self.tabs_widget.currentIndex()
        if active_tab == 0:
            current = self.igdb_list.currentItem()
        else:
            current = self.steam_list.currentItem()
        
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a candidate from the active tab.")
            return
        self.result_dict = self._collect_result(current, active_tab)
        self.accept()

# ============================================================================
# CLI Testing Functionality (unchanged)
# ============================================================================

def test_dialog_cli():
    """Test the MatchDialog from command line."""
    parser = argparse.ArgumentParser(description="Test MatchDialog GUI")
    parser.add_argument("title", help="Game title to test with")
    parser.add_argument("--steam-id", help="Optional Steam AppID to include")
    parser.add_argument("--igdb-id", help="Optional IGDB ID to include")
    parser.add_argument("--generate-candidates", action="store_true",
                       help="Generate test candidates from scraping module")
    parser.add_argument("--max-candidates", type=int, default=5,
                       help="Maximum number of candidates to generate")
    
    args = parser.parse_args()
    
    print(f"[+] Testing MatchDialog with:")
    print(f"    Title: {args.title}")
    print(f"    Steam ID: {args.steam_id or 'None'}")
    print(f"    IGDB ID: {args.igdb_id or 'None'}")
    print(f"    Generate candidates: {args.generate_candidates}")
    print(f"    Max candidates: {args.max_candidates}")
    print("-" * 60)
    
    # Create original item
    original_item = {
        'title': args.title,
        'original_title': args.title,
        'description': f"Test description for {args.title}",
        'app_id': args.steam_id or '',
        'steam_id': args.steam_id or '',
        'igdb_id': args.igdb_id or ''
    }
    
    # Create candidates
    candidates = []
    
    if args.generate_candidates and HAVE_SCRAPING:
        print("[+] Generating candidates from scraping module...")
        try:
            # Get IGDB candidates
            igdb_candidates = scraping.find_candidates_for_title_igdb(
                args.title, 
                max_candidates=args.max_candidates
            )
            
            for cand in igdb_candidates:
                candidates.append(cand)
            
            # Get Steam candidates
            steam_candidates = scraping.find_candidates_for_title(
                args.title, 
                max_candidates=args.max_candidates
            )
            
            for cand in steam_candidates:
                # Convert to our format
                formatted_cand = {
                    "id": cand.get("id", ""),
                    "steam_id": cand.get("id", ""),
                    "steam_app_id": cand.get("id", ""),
                    "name": cand.get("name", args.title),
                    "score": cand.get("score", 0),
                    "source": cand.get("source", "steam"),
                    "tiny_image": cand.get("tiny_image", "")
                }
                candidates.append(formatted_cand)
            
            print(f"[+] Generated {len(candidates)} candidates")
            
        except Exception as e:
            print(f"[-] Error generating candidates: {e}")
            # Create dummy candidates as fallback
            candidates = [
                {
                    "id": args.igdb_id or "12345",
                    "name": f"{args.title} (Enhanced Edition)",
                    "score": 95,
                    "source": "test",
                    "steam_id": args.steam_id or "67890",
                    "steam_app_id": args.steam_id or "67890",
                    "igdb_id": args.igdb_id or "12345",
                    "genres": "Action, Adventure",
                    "developer": "Test Developer",
                    "cover_url": ""
                }
            ]
    else:
        # Create some dummy candidates for testing
        candidates = [
            {
                "id": args.igdb_id or "12345",
                "name": f"{args.title} (Enhanced Edition)",
                "score": 95,
                "source": "test",
                "steam_id": args.steam_id or "67890",
                "steam_app_id": args.steam_id or "67890",
                "igdb_id": args.igdb_id or "12345",
                "genres": "Action, Adventure",
                "developer": "Test Developer",
                "cover_url": ""
            },
            {
                "id": "67891",
                "name": f"{args.title} 2",
                "score": 85,
                "source": "test",
                "steam_id": "67891",
                "steam_app_id": "67891",
                "igdb_id": "12346",
                "genres": "RPG",
                "developer": "Another Developer"
            }
        ]
        print("[+] Using test candidates")
    
    # Print candidate summary
    if candidates:
        print(f"\n[+] Candidates to display ({len(candidates)}):")
        for i, cand in enumerate(candidates, 1):
            print(f"  {i}. {cand.get('name')} "
                  f"(Score: {cand.get('score')}%, "
                  f"Steam: {cand.get('steam_id', 'N/A')}, "
                  f"IGDB: {cand.get('igdb_id', 'N/A')})")
    
    print("\n[+] Starting GUI application...")
    print("    Note: Close the dialog to see the result")
    print("    Use the new buttons to search IGDB/Steam by title or ID")
    print("-" * 60)
    
    # Start Qt application
    app = QApplication(sys.argv)
    
    # Create and show dialog
    dialog = MatchDialog(original_item, candidates)
    result = dialog.exec_()
    
    # Clean up threads
    for loader in dialog.active_image_loaders:
        if loader.isRunning():
            loader.quit()
            loader.wait()
    
    # Process result
    if result == QDialog.Accepted:
        print("\n[+] Dialog accepted!")
        print("    Result dictionary:")
        for key, value in dialog.result_dict.items():
            if key == 'chosen_candidate' and value:
                print(f"      {key}:")
                for subkey, subvalue in value.items():
                    print(f"        {subkey}: {subvalue}")
            else:
                print(f"      {key}: {value}")
    else:
        print("\n[+] Dialog rejected or skipped")
    
    print("\n[+] Test completed")
    return 0


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    # Check if we're being called from command line with arguments
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        # Run CLI test
        sys.exit(test_dialog_cli())
    else:
        # If no arguments, show usage
        print("MatchDialog - Interactive Game Matching Dialog")
        print("\nUsage for GUI testing:")
        print("  python match_dialog.py \"Game Title\" [options]")
        print("\nOptions:")
        print("  --steam-id APPID          Add specific Steam AppID")
        print("  --igdb-id IGDBID          Add specific IGDB ID")
        print("  --generate-candidates     Generate real candidates using scraping module")
        print("  --max-candidates NUM      Maximum candidates to generate (default: 5)")
        print("\nNew features:")
        print("  • Search IGDB by Title button")
        print("  • Lookup IGDB by ID button (ID only, no title used)")
        print("  • Search Steam by Title button")
        print("  • Lookup Steam by ID button (ID only, no title used)")
        print("  • Search Both (IGDB & Steam) by Title button")
        print("  • Separate IGDB and Steam candidate lists")
        print("  • Console output for selected games")
        print("  • Console output for scraped metadata")
        print("  • Mutual exclusive ID fields when searching by ID")
        print("  • Open candidate page respects the selected tab (IGDB or Steam)")
        print("\nExamples:")
        print("  python match_dialog.py \"Cyberpunk 2077\" --generate-candidates")
        print("  python match_dialog.py \"The Witcher 3\" --steam-id 292030 --igdb-id 1942")
        print("\nFor GUI integration, import MatchDialog class directly.")