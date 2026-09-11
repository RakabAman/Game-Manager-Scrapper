#!/usr/bin/env python3
# ui_sidebar.py – Collapsible sidebar with grouped action buttons

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFrame,
    QSizePolicy,
    QSplitter,
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
import config

class SidebarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)          # start collapsed
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.apply_theme()  # initial style

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Group: File
        self._add_group_label(layout, "File")
        self.btn_open = self._add_button(layout, "📂 Open DB")
        self.btn_save = self._add_button(layout, "💾 Save DB")
        self.btn_import = self._add_button(layout, "📥 Import")
        self.btn_export = self._add_button(layout, "📤 Export")
        layout.addWidget(self._separator())

        # Group: Tools
        self._add_group_label(layout, "Tools")
        self.btn_scrape = self._add_button(layout, "🔄 Scrape Metadata")
        self.btn_download = self._add_button(layout, "⬇ Download Resources")
        self.btn_test = self._add_button(layout, "🗲 Test Scrape")
        self.btn_scan = self._add_button(layout, "🗂️ Scan Drive")
        self.btn_cancel = self._add_button(layout, "✕ Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setStyleSheet(
            self.btn_cancel.styleSheet() + f"QPushButton {{ color: {config.ACCENT_COLOR}; }}"
        )
        layout.addWidget(self._separator())

        # Group: Edit
        self._add_group_label(layout, "Edit")
        self.btn_sanitize = self._add_button(layout, "🧹 Sanitize")
        self.btn_multi = self._add_button(layout, "📝 Multi-Edit")
        layout.addWidget(self._separator())

        # Group: Settings & Help
        self.btn_settings = self._add_button(layout, "⚙️ Settings")
        self.btn_help = self._add_button(layout, "❓ Help")

        layout.addStretch()

        # Placeholder slots
        self.btn_open.clicked.connect(lambda: None)
        self.btn_save.clicked.connect(lambda: None)
        self.btn_import.clicked.connect(lambda: None)
        self.btn_export.clicked.connect(lambda: None)
        self.btn_scrape.clicked.connect(lambda: None)
        self.btn_download.clicked.connect(lambda: None)
        self.btn_test.clicked.connect(lambda: None)
        self.btn_scan.clicked.connect(lambda: None)
        self.btn_cancel.clicked.connect(lambda: None)
        self.btn_sanitize.clicked.connect(lambda: None)
        self.btn_multi.clicked.connect(lambda: None)
        self.btn_settings.clicked.connect(lambda: None)
        self.btn_help.clicked.connect(lambda: None)

    def apply_theme(self):
        """Re-apply sidebar and button styles using current config.

        Called automatically by config.refresh_all() -- no manual wiring
        needed from gui_main.
        """
        self.setStyleSheet(f"""
            QWidget#sidebar {{
                background-color: {config.LIGHT_BG};
                border-right: 1px solid {config.BORDER_COLOR};
            }}
        """)
        # Update all buttons and labels
        for child in self.findChildren(QPushButton):
            if child is self.btn_cancel:
                child.setStyleSheet(
                    child.styleSheet() + f"QPushButton {{ color: {config.ACCENT_COLOR}; }}"
                )
            elif not child.isEnabled():
                # group label – no font-size change
                child.setStyleSheet(f"""
                    QPushButton {{
                        font-weight: bold;
                        color: {config.PRIMARY_COLOR};
                        border: none;
                        padding: 4px 0;
                        text-align: left;
                        background: transparent;
                    }}
                """)
            else:
                # Use 13px base (scaled) to match gui_main_2's button text
                scaled_btn = int(13 * config.GLOBAL_FONT_SCALE)
                child.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        padding: 8px 12px;
                        border-radius: 4px;
                        background: transparent;
                        font-size: {scaled_btn}px;
                        color: {config.PRIMARY_COLOR};
                    }}
                    QPushButton:hover {{
                        background: {config.HOVER_COLOR};
                    }}
                """)

    def _add_group_label(self, layout, text):
        label = QPushButton(text)
        label.setEnabled(False)
        label.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold;
                color: {config.PRIMARY_COLOR};
                border: none;
                padding: 4px 0;
                text-align: left;
                background: transparent;
            }}
        """)
        layout.addWidget(label)

    def _add_button(self, layout, text):
        btn = QPushButton(text)
        btn.setFlat(True)
        scaled_btn = int(13 * config.GLOBAL_FONT_SCALE)  # Use 13px base
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 8px 12px;
                border-radius: 4px;
                background: transparent;
                font-size: {scaled_btn}px;
                color: {config.PRIMARY_COLOR};
            }}
            QPushButton:hover {{
                background: {config.HOVER_COLOR};
            }}
        """)
        layout.addWidget(btn)
        return btn

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {config.BORDER_COLOR}; max-height: 1px; margin: 4px 0;")
        return line

    def set_expanded(self, expanded: bool):
        target = 220 if expanded else 0

        if hasattr(self, "anim") and self.anim is not None:
            self.anim.stop()

        self.anim = QPropertyAnimation(
            self,
            b"maximumWidth",
            self
        )

        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.anim.setStartValue(self.width())
        self.anim.setEndValue(target)

        self.anim.start()