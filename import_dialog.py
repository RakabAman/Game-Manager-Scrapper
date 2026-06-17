# import_dialog.py
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QFileDialog, QCheckBox, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt
from config import APP_STYLESHEET, AUTO_SANITIZE
import drive_scanner


class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Games")
        self.setMinimumSize(400, 400)
        self.setStyleSheet(APP_STYLESHEET)

        layout = QVBoxLayout(self)

        instruction = QLabel("Enter one game per line, or load from a file / scan a folder:")
        layout.addWidget(instruction)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("e.g.:\nGame Title 1\nGame Title 2 (v1.2.3) [FitGirl Repack]\nAnother Game")
        layout.addWidget(self.text_edit)

        button_layout = QHBoxLayout()
        self.load_file_btn = QPushButton("Load from File...")
        self.scan_drive_btn = QPushButton("Scan Folder...")
        button_layout.addWidget(self.load_file_btn)
        button_layout.addWidget(self.scan_drive_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.auto_sanitize_cb = QCheckBox("Auto‑sanitize titles (extract version, repack, etc.)")
        self.auto_sanitize_cb.setChecked(AUTO_SANITIZE)
        layout.addWidget(self.auto_sanitize_cb)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_file_btn.clicked.connect(self._load_file)
        self.scan_drive_btn.clicked.connect(self._scan_drive)
        self._imported_games_from_file = []

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select import file", "",
            "Supported files (*.txt *.csv *.xlsx *.xls);;All files (*.*)"
        )
        if not path:
            print("[IMPORT] No file selected.")
            return

        self._imported_games_from_file = []
        print(f"[IMPORT] Loading file: {path}")

        try:
            if path.endswith(('.xlsx', '.xls')):
                from import_export import import_excel
                games, err = import_excel(path)
                if err:
                    QMessageBox.critical(self, "Error", f"Failed to read Excel:\n{err}")
                    print(f"[IMPORT] Excel error: {err}")
                    return
                self._imported_games_from_file = games
                titles = [g.get("title") or g.get("original_title") or "Untitled" for g in games]
                self.text_edit.setPlainText("\n".join(titles))
                print(f"[IMPORT] Loaded {len(games)} full games from Excel. Titles preview:")
                for idx, t in enumerate(titles[:5], 1):
                    print(f"[IMPORT]   {idx}. {t}")
                if len(titles) > 5:
                    print(f"[IMPORT]   ... and {len(titles)-5} more")
                QMessageBox.information(self, "File Loaded",
                    f"Loaded {len(games)} games with full metadata.\n"
                    "These will be added as complete entries when you click OK.")
                return

            elif path.endswith('.csv'):
                from import_export import import_csv
                games, err = import_csv(path)
                if err:
                    QMessageBox.critical(self, "Error", f"Failed to read CSV:\n{err}")
                    print(f"[IMPORT] CSV error: {err}")
                    return
                self._imported_games_from_file = games
                titles = [g.get("title") or g.get("original_title") or "Untitled" for g in games]
                self.text_edit.setPlainText("\n".join(titles))
                print(f"[IMPORT] Loaded {len(games)} full games from CSV. Titles preview:")
                for idx, t in enumerate(titles[:5], 1):
                    print(f"[IMPORT]   {idx}. {t}")
                if len(titles) > 5:
                    print(f"[IMPORT]   ... and {len(titles)-5} more")
                QMessageBox.information(self, "File Loaded",
                    f"Loaded {len(games)} games with full metadata.\n"
                    "These will be added as complete entries when you click OK.")
                return

            # Text file (titles only)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_edit.setPlainText(content)
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            print(f"[IMPORT] Loaded {len(lines)} titles from text file. Preview:")
            for idx, t in enumerate(lines[:5], 1):
                print(f"[IMPORT]   {idx}. {t}")
            if len(lines) > 5:
                print(f"[IMPORT]   ... and {len(lines)-5} more")
            QMessageBox.information(self, "File Loaded",
                "Loaded titles from text file.\nOnly titles will be imported (use CSV/Excel for full metadata).")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read file:\n{str(e)}")
            print(f"[IMPORT] Exception: {e}")

    def _scan_drive(self):
        main_window = self.parent()
        if not main_window:
            QMessageBox.warning(self, "Scan Drive", "Cannot access main window.")
            print("[IMPORT] Scan drive failed: no main window")
            return

        print("[IMPORT] Scanning folder for new games...")
        new_folders = drive_scanner.get_new_folders_from_drive(main_window)
        if new_folders is None:
            print("[IMPORT] Scan cancelled or error.")
            return
        if not new_folders:
            print("[IMPORT] No new folders found.")
            return

        self.text_edit.setPlainText("\n".join(new_folders))
        print(f"[IMPORT] Scan found {len(new_folders)} new folders. Preview:")
        for idx, name in enumerate(new_folders[:5], 1):
            print(f"[IMPORT]   {idx}. {name}")
        if len(new_folders) > 5:
            print(f"[IMPORT]   ... and {len(new_folders)-5} more")

    def get_imported_titles(self):
        text = self.text_edit.toPlainText()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            print(f"[IMPORT] get_imported_titles: returning {len(lines)} titles")
        return lines

    def auto_sanitize_enabled(self):
        return self.auto_sanitize_cb.isChecked()

    def get_imported_games_from_file(self):
        games = getattr(self, '_imported_games_from_file', [])
        if games:
            print(f"[IMPORT] get_imported_games_from_file: returning {len(games)} full game objects")
        return games