##!/usr/bin/env python3
# ui_header.py – Top header bar with hamburger and two placeholders

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt
import config

class HeaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(56)
        self.apply_theme()  # use method to set initial style

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Hamburger button
        self.menu_btn = QPushButton("☰")
        self.menu_btn.setFixedSize(40, 40)
        scaled_menu = int(22 * config.GLOBAL_FONT_SCALE)
        self.menu_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {scaled_menu}px;
                border: none;
                background: transparent;
                color: {config.PRIMARY_COLOR};
            }}
            QPushButton:hover {{
                background: rgba(0,0,0,0.05);
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.menu_btn)

        # Central placeholder
        self.center_container = QWidget()
        self.center_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.center_container, 1)

        # Stats container (right side)
        self.stats_container = QWidget()
        self.stats_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.stats_layout = QHBoxLayout(self.stats_container)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_layout.setSpacing(6)
        layout.addWidget(self.stats_container)

    def apply_theme(self):
        """Re-apply stylesheet using current config values.

        Called automatically by config.refresh_all() whenever settings
        change -- no manual wiring needed from gui_main.
        """
        self.setStyleSheet(f"""
            QWidget#header {{
                background-color: {config.LIGHT_BG};
                border-bottom: 1px solid {config.BORDER_COLOR};
            }}
        """)
        # Also update menu button (if exists)
        
        if hasattr(self, 'menu_btn'):
            scaled_menu = int(22 * config.GLOBAL_FONT_SCALE)
            self.menu_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: {scaled_menu}px;
                    border: none;
                    background: transparent;
                    color: {config.PRIMARY_COLOR};
                }}
                QPushButton:hover {{
                    background: rgba(0,0,0,0.05);
                    border-radius: 4px;
                }}
            """)

    def set_center_widget(self, widget):
        """Replace the center area with a custom widget."""
        if self.center_container.layout():
            while self.center_container.layout().count():
                child = self.center_container.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        else:
            layout = QHBoxLayout(self.center_container)
            layout.setContentsMargins(0, 0, 0, 0)
        self.center_container.layout().addWidget(widget)

    def set_stats(self, stats_widget):
        """Replace the stats area."""
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.stats_layout.addWidget(stats_widget)