import os
import re
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QDialog, QVBoxLayout, QLabel,
    QComboBox, QHBoxLayout, QPushButton, QLineEdit, QDialogButtonBox
)

from utils_sanitize import sanitize_original_title
import config
from config import AUTO_SANITIZE
# Add these imports at the top of drive_scanner.py (if not already present)
import sys
import ctypes
from pathlib import Path
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARN] Pillow not installed. Icon conversion disabled. Install with: pip install Pillow")

import unicodedata   # add this near the other imports

# ----- Helper for normalised duplicate keys (improved) -----
def _normalise_key(drive, orig_title):
    if not drive or not orig_title:
        return None
    # NFKC normalises curly quotes, dashes, ligatures, etc.
    norm_drive = unicodedata.normalize('NFKC', drive.strip().lower())
    norm_title = unicodedata.normalize('NFKC', orig_title.strip().lower())
    # collapse multiple spaces (e.g. "  " -> " ")
    norm_drive = ' '.join(norm_drive.split())
    norm_title = ' '.join(norm_title.split())
    return (norm_drive, norm_title)

# ----------------------------------------------------------------------
# Helper: Get game_drive selection from user
# ----------------------------------------------------------------------
def _get_drive_selection(parent_window):
    existing_drives = sorted(set(
        g.get("game_drive", "") for g in parent_window.games if g.get("game_drive")
    ))

    dialog = QDialog(parent_window)
    dialog.setWindowTitle("Select Game Drive")
    dialog.setMinimumWidth(400)
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Choose the game drive that these folders belong to:"))

    combo = QComboBox()
    for drive in existing_drives:
        combo.addItem(drive)
    combo.addItem("--- Enter manually ---")
    combo.setEditable(False)
    layout.addWidget(combo)

    manual_entry = QLineEdit()
    manual_entry.setPlaceholderText("Enter drive name (e.g., Drive D, E:\\Games, etc.)")
    manual_entry.setMinimumHeight(config.TEXT_BOX_HEIGHT)   # <-- added
    manual_entry.setVisible(False)
    layout.addWidget(manual_entry)

    def on_combo_changed(idx):
        is_manual = combo.currentText() == "--- Enter manually ---"
        manual_entry.setVisible(is_manual)
        if is_manual:
            manual_entry.setFocus()
            manual_entry.selectAll()
        else:
            manual_entry.clear()

    combo.currentIndexChanged.connect(on_combo_changed)
    on_combo_changed(combo.currentIndex())

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec_() != QDialog.Accepted:
        return None

    selected = combo.currentText()
    if selected == "--- Enter manually ---":
        selected = manual_entry.text().strip()
        if not selected:
            QMessageBox.warning(parent_window, "Drive Scanner", "No drive name entered.")
            return None
    return selected


# ----------------------------------------------------------------------
# Drive Scanner Worker
# ----------------------------------------------------------------------
class DriveScannerWorker(QObject):
    finished = pyqtSignal(list)
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, root_folder: str, game_drive: str, parent=None):
        super().__init__(parent)
        self.root_folder = root_folder
        self.game_drive = game_drive
        self.cancelled = False

    def run(self):
        try:
            print(f"[DRIVE_SCAN] Scanning folder: {self.root_folder}")
            print(f"[DRIVE_SCAN] Game drive to assign: {self.game_drive}")
            if not os.path.isdir(self.root_folder):
                self.error.emit("Invalid folder path")
                return

            subfolders = [
                f for f in os.listdir(self.root_folder)
                if os.path.isdir(os.path.join(self.root_folder, f))
            ]
            total = len(subfolders)
            print(f"[DRIVE_SCAN] Found {total} subfolders")

            new_games = []
            for i, folder_name in enumerate(subfolders):
                if self.cancelled:
                    print("[DRIVE_SCAN] Cancelled by user")
                    return
                self.progress.emit(i + 1, total)
                print(f"[DRIVE_SCAN] Processing {i+1}/{total}: {folder_name}")

                game = {
                    "original_title": folder_name,
                    "game_drive": self.game_drive
                }
                if config.AUTO_SANITIZE:
                    san = sanitize_original_title(folder_name)
                    game["title"] = san.get("base_title") or folder_name
                    game["original_title_base"] = san.get("base_title", "")
                    game["original_title_version"] = san.get("version", "")
                    game["scene_repack"] = san.get("repack", "")
                    game["original_notes"] = san.get("notes", "")
                    game["game_modes"] = ", ".join(san.get("modes", []))
                else:
                    game["title"] = folder_name
                new_games.append(game)

            print(f"[DRIVE_SCAN] Scan complete, found {len(new_games)} games")
            self.finished.emit(new_games)

        except Exception as e:
            print(f"[DRIVE_SCAN] Error: {e}")
            self.error.emit(str(e))


# ----------------------------------------------------------------------
# Main scan_drive function (append only, no overwrite)
# ----------------------------------------------------------------------
_scan_in_progress = False

# ========== REPLACE THE EXISTING scan_drive() FUNCTION ==========

def scan_drive(parent_window):
    global _scan_in_progress
    if _scan_in_progress:
        QMessageBox.warning(parent_window, "Drive Scanner", "A scan is already in progress.")
        return False

    game_drive = _get_drive_selection(parent_window)
    if not game_drive:
        return False

    root_folder = QFileDialog.getExistingDirectory(
        parent_window,
        "Select Folder Containing Game Subfolders"
    )
    if not root_folder:
        return False

    _scan_in_progress = True
    parent_window.progress_bar.setVisible(True)
    parent_window.progress_bar.setMaximum(0)
    parent_window.progress_bar.setValue(0)
    parent_window.status.setText("Scanning folders...")
    parent_window.cancel_scrape_btn.setVisible(True)
    parent_window.scrape_btn.setEnabled(False)
    parent_window._cancel_current_scrape = False

    worker = DriveScannerWorker(root_folder, game_drive)
    thread = QThread(parent_window)
    worker.moveToThread(thread)

    def on_progress(current, total):
        parent_window.progress_bar.setMaximum(total)
        parent_window.progress_bar.setValue(current)
        parent_window.status.setText(f"Scanning folders... {current}/{total}")

    def on_finished(new_games):
        global _scan_in_progress
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)

        if not new_games:
            QMessageBox.information(parent_window, "Drive Scanner", "No folders found to add.")
            parent_window.status.setText("Scan complete: no folders found")
            _scan_in_progress = False
            return

        # Build existing pairs (normalised)
        existing_pairs = set()
        for g in parent_window.games:
            drive = g.get("game_drive", "")
            orig = g.get("original_title", "")
            key = _normalise_key(drive, orig)
            if key:
                existing_pairs.add(key)

        print(f"[DRIVE_SCAN] existing_pairs size: {len(existing_pairs)}")

        unique_new = []
        skipped = 0
        for candidate in new_games:
            cand_key = _normalise_key(candidate.get("game_drive", ""), candidate.get("original_title", ""))
            if cand_key and cand_key in existing_pairs:
                skipped += 1
                print(f"[DRIVE_SCAN] Skipping duplicate: {cand_key}")
            else:
                unique_new.append(candidate)

        print(f"[DRIVE_SCAN] {len(new_games)} candidates, {skipped} duplicates, {len(unique_new)} new unique games")

        if not unique_new:
            QMessageBox.information(
                parent_window,
                "Drive Scanner",
                f"Scanned {len(new_games)} subfolders, but all already exist in the library.\nNo new games added."
            )
            parent_window.status.setText("Scan complete: no new games (all duplicates)")
            _scan_in_progress = False
            return

        before = len(parent_window.games)
        parent_window.games.extend(unique_new)
        after = len(parent_window.games)
        added = after - before

        parent_window.refresh_model()
        parent_window._mark_dirty()

        QMessageBox.information(
            parent_window,
            "Drive Scanner",
            f"Scanned {len(new_games)} subfolders.\n"
            f"Skipped {skipped} duplicates.\n"
            f"Added {added} new games.\n\n"
            f"Game drive set to: {game_drive}"
        )
        parent_window.status.setText(f"Scan complete. Added {added} new games (skipped {skipped} duplicates).")
        _scan_in_progress = False

    def on_error(err):
        global _scan_in_progress
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)
        QMessageBox.critical(parent_window, "Scan Error", err)
        parent_window.status.setText("Scan error.")
        _scan_in_progress = False

    def on_cancel():
        global _scan_in_progress
        print("[DRIVE_SCAN] Cancel requested")
        parent_window._cancel_current_scrape = True
        worker.cancelled = True
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)
        parent_window.status.setText("Scan cancelled.")
        _scan_in_progress = False

    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)

    try:
        parent_window.cancel_scrape_btn.clicked.disconnect()
    except:
        pass
    parent_window.cancel_scrape_btn.clicked.connect(on_cancel)

    thread.started.connect(worker.run)
    thread.start()
    return True


def get_new_folders_from_drive(parent_window):
    """
    Opens dialogs to select game drive and folder, scans subfolders,
    filters out those already existing in the current library (based on game_drive + original_title),
    returns a list of folder names (original_title) that are new, or None if cancelled/error.
    """
    game_drive = _get_drive_selection(parent_window)
    if not game_drive:
        return None
    root_folder = QFileDialog.getExistingDirectory(parent_window, "Select Folder Containing Game Subfolders")
    if not root_folder:
        return None

    from PyQt5.QtWidgets import QProgressDialog, QApplication
    progress = QProgressDialog("Scanning folders...", "Cancel", 0, 0, parent_window)
    progress.setWindowModality(Qt.WindowModal)
    progress.setCancelButton(None)
    progress.show()
    QApplication.processEvents()

    worker = DriveScannerWorker(root_folder, game_drive)
    thread = QThread()
    worker.moveToThread(thread)

    result = []
    error_msg = None

    def on_finished(new_games):
        nonlocal result
        result = new_games
        thread.quit()

    def on_error(err):
        nonlocal error_msg
        error_msg = err
        thread.quit()

    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    thread.started.connect(worker.run)
    thread.start()

    while thread.isRunning():
        QApplication.processEvents()
        if progress.wasCanceled():
            worker.cancelled = True
            thread.quit()
            thread.wait()
            progress.close()
            return None
    progress.close()

    if error_msg:
        QMessageBox.critical(parent_window, "Scan Error", error_msg)
        return None

    if not result:
        QMessageBox.information(parent_window, "Scan Drive", "No folders found.")
        return None

    # Filter duplicates based on existing games in the main window
    existing_pairs = set()
    for g in parent_window.games:
        drive = g.get("game_drive", "")
        orig = g.get("original_title", "")
        key = _normalise_key(drive, orig)
        if key:
            existing_pairs.add(key)

    new_folders = []
    skipped = 0
    for candidate in result:
        key = _normalise_key(candidate.get("game_drive", ""), candidate.get("original_title", ""))
        if key and key in existing_pairs:
            skipped += 1
        else:
            new_folders.append(candidate.get("original_title", ""))

    if not new_folders:
        QMessageBox.information(
            parent_window,
            "Scan Drive",
            f"Found {len(result)} folders, but all already exist in your library.\nNo new games to import."
        )
        return None

    QMessageBox.information(
        parent_window,
        "Scan Drive",
        f"Found {len(result)} folders.\n{len(new_folders)} are new and will be added to the import list.\nSkipped {skipped} duplicates."
    )
    return new_folders   
    
class AssetCopyWorker(QObject):
    finished = pyqtSignal(int, int)
    progress = pyqtSignal(int, int, str)
    error = pyqtSignal(str)

    def __init__(self, games: List[Dict], target_root: str, mode: int, parent=None):
        super().__init__(parent)
        self.games = games
        self.target_root = target_root
        self.mode = mode
        self.cancelled = False

    def _sanitise_for_folder(self, name: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*]', '', name)
        safe = safe.strip('. ')
        return safe

    def _find_cached_cover(self, game):
        cover_url = game.get("cover_url", "")
        igdb_cover_url = game.get("igdb_cover_art", "")
        cache_paths = game.get("image_cache_paths", [])

        # Use local variable, do NOT modify global config.CACHE_DIR
        cache_dir = Path(config.CACHE_DIR)
        if not cache_dir.is_absolute():
            cache_dir = config.SCRIPT_DIR / cache_dir
        print(f"[ASSET] Using cache directory: {cache_dir}")

        def find_by_hash(url):
            if not url:
                return None
            url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
            if cache_dir.exists():
                for root, dirs, files in os.walk(cache_dir):
                    for f in files:
                        if url_hash in f and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            return Path(root) / f
            return None

        # ... rest of method unchanged (but remove the config.CACHE_DIR = ... line)

        # Method 1: by URL hash from cover_url or igdb_cover_art
        cover_path = find_by_hash(cover_url)
        if cover_path:
            print(f"[ASSET] Found cover by cover_url hash: {cover_path}")
            return cover_path
        cover_path = find_by_hash(igdb_cover_url)
        if cover_path:
            print(f"[ASSET] Found cover by igdb_cover_art hash: {cover_path}")
            return cover_path

        # Method 2: look for coverart.jpg in game cache directory
        try:
            from cache_utils import _game_cache_dir_for_game
            game_cache_dir = _game_cache_dir_for_game(game)
            if game_cache_dir.exists():
                coverart_path = game_cache_dir / "coverart.jpg"
                if coverart_path.exists():
                    print(f"[ASSET] Found coverart.jpg in game cache dir: {coverart_path}")
                    return coverart_path
                # Also check for any jpg/png that might be cover (avoid screenshot names)
                for f in game_cache_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                        if 'screenshot' not in f.stem.lower():
                            print(f"[ASSET] Found likely cover in game cache dir: {f}")
                            return f
        except Exception as e:
            print(f"[ASSET] Error scanning game cache dir: {e}")

        # Method 3: first entry in image_cache_paths
        if cache_paths:
            rel_path = cache_paths[0]
            candidate = cache_dir / rel_path
            if candidate.exists():
                print(f"[ASSET] Found cover via cache_paths: {candidate}")
                return candidate
            else:
                print(f"[ASSET] Cache path missing: {candidate}")

        print(f"[ASSET] Cover not found for game: {game.get('title', 'unknown')}")
        return None

    def _create_folder_icon(self, folder_path: str):
        """Create high-quality ICO with 256×256 size and verify it."""
        print(f"[ICON] Creating folder icon in {folder_path}")
        try:
            from PIL import Image
        except ImportError:
            print("[ICON] Pillow not installed")
            return

        artbox_jpg = os.path.join(folder_path, "artbox.jpg")
        artbox_ico = os.path.join(folder_path, "artbox.ico")
        desktop_ini = os.path.join(folder_path, "desktop.ini")

        if not os.path.isfile(artbox_jpg):
            print("[ICON] artbox.jpg missing")
            return

        # --- Generate multi-size ICO with 256×256 as primary ---
        try:
            img = Image.open(artbox_jpg)
            # Convert to RGBA (supports transparency, better quality)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Desired sizes (including 256×256)
            sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            icons = []
            for w, h in sizes:
                try:
                    resized = img.resize((w, h), Image.Resampling.LANCZOS)
                except AttributeError:
                    resized = img.resize((w, h), Image.LANCZOS)
                icons.append(resized)

            # Save multi‑size ICO
            icons[0].save(artbox_ico, format='ICO', sizes=sizes, append_images=icons[1:])
            print(f"[ICON] Saved ICO with sizes: {sizes}")

            # --- Verify the ICO file (optional but helpful) ---
            verify = Image.open(artbox_ico)
            print(f"[ICON] Verification: {verify.info}")  # shows available sizes
            verify.close()

        except Exception as e:
            print(f"[ICON] Multi‑size save failed: {e}, trying single 256×256")
            try:
                # Fallback: just save a single 256×256 ICO
                img256 = img.resize((256, 256), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
                img256.save(artbox_ico, format='ICO', sizes=[(256, 256)])
                print("[ICON] Saved single-size 256×256 ICO")
            except Exception as e2:
                print(f"[ICON] Fallback failed: {e2}")
                return

        # --- Create desktop.ini ---
        try:
            with open(desktop_ini, 'w', encoding='utf-8') as f:
                f.write("[.ShellClassInfo]\nIconResource=artbox.ico,0\n")
            print("[ICON] desktop.ini created")
        except Exception as e:
            print(f"[ICON] Failed to write desktop.ini: {e}")
            return

        # --- Set hidden attributes on icon and desktop.ini ---
        if sys.platform == 'win32':
            import ctypes
            FILE_ATTRIBUTE_HIDDEN = 0x02
            FILE_ATTRIBUTE_READONLY = 0x01
            FILE_ATTRIBUTE_SYSTEM = 0x04

            ctypes.windll.kernel32.SetFileAttributesW(artbox_ico, FILE_ATTRIBUTE_HIDDEN)
            ctypes.windll.kernel32.SetFileAttributesW(desktop_ini, FILE_ATTRIBUTE_HIDDEN)

            # Mark the folder as read-only + system (tells Windows to use desktop.ini)
            try:
                ctypes.windll.kernel32.SetFileAttributesW(folder_path, FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_SYSTEM)
                print("[ICON] Folder marked as read-only + system")
            except Exception as e:
                print(f"[ICON] Failed to set folder attributes: {e}")

            # Notify Windows Explorer to reload icons
            try:
                SHCNE_ASSOCCHANGED = 0x08000000
                SHCNF_IDLIST = 0x0000
                ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
                print("[ICON] Explorer refresh requested")
            except:
                pass
                
    def run(self):
        total = len(self.games)
        success = 0
        print(f"[ASSET] Starting export, mode={self.mode}, target={self.target_root}, games={total}")

        # Resolve cache directory once
        config.CACHE_DIR = Path(config.CACHE_DIR)
        if not config.CACHE_DIR.is_absolute():
            config.CACHE_DIR = config.SCRIPT_DIR / config.CACHE_DIR
        print(f"[ASSET] Absolute cache dir: {config.CACHE_DIR}")

        existing_folders = {}
        if self.mode == 0 and os.path.exists(self.target_root):
            for item in os.listdir(self.target_root):
                item_path = os.path.join(self.target_root, item)
                if os.path.isdir(item_path):
                    existing_folders[item] = item_path
            print(f"[ASSET] Found {len(existing_folders)} existing folders for mode 0")

        for i, game in enumerate(self.games):
            if self.cancelled:
                print("[ASSET] Cancelled by user")
                break

            title = game.get("title") or game.get("original_title") or f"Game_{i}"
            self.progress.emit(i + 1, total, title)

            original_title = game.get("original_title")
            if not original_title:
                print(f"[ASSET] Game {i}: no original_title, skipping")
                continue

            # Determine target folder
            if self.mode == 0:
                target_folder = existing_folders.get(original_title)
                if not target_folder:
                    print(f"[ASSET] No matching folder for '{original_title}'")
                    continue
                print(f"[ASSET] Matching folder: {target_folder}")
            else:
                folder_name = game.get("title")
                if not folder_name:
                    folder_name = original_title
                safe_name = self._sanitise_for_folder(folder_name)
                if not safe_name:
                    safe_name = f"Game_{i}"
                target_folder = os.path.join(self.target_root, safe_name)
                try:
                    os.makedirs(target_folder, exist_ok=True)
                    print(f"[ASSET] Created folder: {target_folder}")
                except Exception as e:
                    print(f"[ASSET] Failed to create folder {target_folder}: {e}")
                    continue

            # ---- Copy cover art ----
            cover_path = self._find_cached_cover(game)
            if cover_path and cover_path.exists():
                dest = os.path.join(target_folder, "artbox.jpg")
                try:
                    shutil.copy2(cover_path, dest)
                    print(f"[ASSET] Copied cover to {dest}")
                    # Create icon after cover is copied
                    self._create_folder_icon(target_folder)
                except Exception as e:
                    print(f"[ASSET] Failed to copy cover {cover_path}: {e}")
            else:
                print(f"[ASSET] No cover art found for {title}")

            # ---- Copy screenshots ----
            cache_paths = game.get("image_cache_paths", [])
            for idx, rel_path in enumerate(cache_paths, start=1):
                if not rel_path:
                    continue
                abs_path = config.CACHE_DIR / rel_path
                if not abs_path.exists():
                    print(f"[ASSET] Screenshot missing: {abs_path}")
                    continue
                if cover_path and abs_path.samefile(cover_path):
                    continue
                ext = abs_path.suffix.lower()
                if ext in ('.jpg', '.jpeg', '.png', '.webp'):
                    dest = os.path.join(target_folder, f"screenshot_{idx}{ext}")
                    try:
                        shutil.copy2(abs_path, dest)
                        print(f"[ASSET] Copied screenshot {idx} to {dest}")
                    except Exception as e:
                        print(f"[ASSET] Failed to copy screenshot {abs_path}: {e}")

            # ---- Copy microtrailer ----
            micro_path = game.get("microtrailer_cache_path", "")
            if micro_path:
                abs_path = config.CACHE_DIR / micro_path
                if abs_path.exists():
                    ext = abs_path.suffix.lower()
                    if ext in ('.gif', '.webm', '.mp4'):
                        dest_name = f"trailer{ext}"
                        dest = os.path.join(target_folder, dest_name)
                        try:
                            shutil.copy2(abs_path, dest)
                            print(f"[ASSET] Copied trailer to {dest}")
                        except Exception as e:
                            print(f"[ASSET] Failed to copy trailer {abs_path}: {e}")
                else:
                    print(f"[ASSET] Trailer file not found: {abs_path}")

            success += 1

        print(f"[ASSET] Export finished: {success} of {total} games processed")
        self.finished.emit(success, total)
        
        
def copy_assets_to_drive(parent_window):
    ordered_games = parent_window._get_current_display_order()
    if not ordered_games:
        QMessageBox.information(parent_window, "Export Assets", "No games to process.")
        return

    target = QFileDialog.getExistingDirectory(parent_window, "Select Target Drive/Folder")
    if not target:
        return

    # Mode selection dialog
    mode_dialog = QDialog(parent_window)
    mode_dialog.setWindowTitle("Export Mode")
    mode_dialog.setMinimumWidth(400)
    layout = QVBoxLayout(mode_dialog)
    layout.addWidget(QLabel("Choose export mode:"))
    btn_layout = QHBoxLayout()
    btn_match = QPushButton("Match Existing Folders\n(Copy only cover art into folders that exactly match original_title)")
    btn_create = QPushButton("Create New Folders\n(Create folders using sanitised title and copy all assets)")
    btn_cancel = QPushButton("Cancel")
    btn_layout.addWidget(btn_match)
    btn_layout.addWidget(btn_create)
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)

    mode = None
    def set_mode(m):
        nonlocal mode
        mode = m
        mode_dialog.accept()
    btn_match.clicked.connect(lambda: set_mode(0))
    btn_create.clicked.connect(lambda: set_mode(1))
    btn_cancel.clicked.connect(mode_dialog.reject)

    if mode_dialog.exec_() != QDialog.Accepted or mode is None:
        return

    reply = QMessageBox.question(
        parent_window,
        "Confirm Export",
        f"Export assets for {len(ordered_games)} games?\n\nTarget: {target}\nMode: {'Match existing folders' if mode == 0 else 'Create new folders'}",
        QMessageBox.Yes | QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return

    # Setup UI
    parent_window.progress_bar.setVisible(True)
    parent_window.progress_bar.setMaximum(len(ordered_games))
    parent_window.progress_bar.setValue(0)
    parent_window.status.setText("Starting asset export...")
    parent_window.cancel_scrape_btn.setVisible(True)
    parent_window.scrape_btn.setEnabled(False)
    parent_window._cancel_current_scrape = False

    worker = AssetCopyWorker(ordered_games, target, mode)
    thread = QThread(parent_window)
    worker.moveToThread(thread)

    def on_progress(current, total, title):
        parent_window.progress_bar.setMaximum(total)
        parent_window.progress_bar.setValue(current)
        parent_window.status.setText(f"Exporting: {title} ({current}/{total})")

    def on_finished(success, total):
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)
        parent_window.status.setText(f"Export complete: {success} of {total} games processed.")
        QMessageBox.information(
            parent_window,
            "Asset Export",
            f"Successfully processed {success} of {total} games.\nAssets copied to:\n{target}"
        )
        # Restore cancel button connection
        try:
            parent_window.cancel_scrape_btn.clicked.disconnect()
        except:
            pass
        parent_window.cancel_scrape_btn.clicked.connect(parent_window.force_cancel_operation)

    def on_error(err):
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)
        QMessageBox.critical(parent_window, "Export Error", err)
        parent_window.status.setText("Export error.")
        try:
            parent_window.cancel_scrape_btn.clicked.disconnect()
        except:
            pass
        parent_window.cancel_scrape_btn.clicked.connect(parent_window.force_cancel_operation)

    def on_cancel():
        print("[DRIVE_ASSET] Cancel requested by user")
        parent_window._cancel_current_scrape = True
        worker.cancelled = True
        thread.quit()
        thread.wait()
        parent_window.progress_bar.setVisible(False)
        parent_window.cancel_scrape_btn.setVisible(False)
        parent_window.scrape_btn.setEnabled(True)
        parent_window.status.setText("Export cancelled.")
        try:
            parent_window.cancel_scrape_btn.clicked.disconnect()
        except:
            pass
        parent_window.cancel_scrape_btn.clicked.connect(parent_window.force_cancel_operation)

    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    # Temporarily connect cancel button to our handler
    try:
        parent_window.cancel_scrape_btn.clicked.disconnect()
    except:
        pass
    parent_window.cancel_scrape_btn.clicked.connect(on_cancel)

    thread.started.connect(worker.run)
    thread.start()