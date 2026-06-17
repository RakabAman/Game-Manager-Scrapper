# download_helper.py
import time
import requests
import hashlib
from pathlib import Path
from PyQt5.QtCore import Qt, QCoreApplication, QThread, QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QStandardItem

from cache_utils import _save_bytes_to_game_cache, _game_cache_dir_for_game, _to_relative
import config

class GameDownloadWorker(QObject):
    finished = pyqtSignal(int, dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(int, str)

    def __init__(self, game_idx: int, game: dict, parent=None):
        super().__init__(parent)
        self.game_idx = game_idx
        self.game = game
        self.cancelled = False

    def run(self):
        stats = {
            "screenshots_downloaded": 0,
            "screenshots_failed": 0,
            "microtrailers_downloaded": 0,
            "microtrailers_failed": 0,
            "cover_art_downloaded": 0,
            "cover_art_failed": 0,
        }
        try:
            # Scan existing cache
            cache_scan = self._scan_cache()
            if cache_scan["screenshot_paths"]:
                self.game["image_cache_paths"] = cache_scan["screenshot_paths"]
            if cache_scan["microtrailer_path"]:
                self.game["microtrailer_cache_path"] = cache_scan["microtrailer_path"]

            # Download cover art (igdb_cover_art) if available and not already cached
            cover_art_url = self.game.get("igdb_cover_art", "")
            if cover_art_url and not self.game.get("igdb_cover_art_cache_path"):
                result = self._download_cover_art()
                if result == "downloaded":
                    stats["cover_art_downloaded"] = 1
                elif result == "failed":
                    stats["cover_art_failed"] = 1

            # Download microtrailer
            if not cache_scan["microtrailer_path"]:
                result = self._download_microtrailer()
                if result == "downloaded":
                    stats["microtrailers_downloaded"] = 1
                elif result == "failed":
                    stats["microtrailers_failed"] = 1

            # Download missing screenshots (respecting limit)
            cached_count = len(cache_scan["screenshot_paths"])
            max_to_download = config.MAX_IMAGES_TO_DOWNLOAD - cached_count
            if max_to_download > 0 and not self.cancelled:
                downloaded, failed = self._download_screenshots(max_to_download)
                stats["screenshots_downloaded"] = downloaded
                stats["screenshots_failed"] = failed

            self.finished.emit(self.game_idx, stats)
        except Exception as e:
            self.error.emit(self.game_idx, str(e))

    def _download_cover_art(self):
        url = self.game.get("igdb_cover_art", "")
        if not url:
            return "skipped"

        # Check if we already have a path and the file exists
        existing_path = self.game.get("igdb_cover_art_cache_path", "")
        if existing_path:
            abs_path = Path(existing_path)
            if not abs_path.is_absolute():
                abs_path = config.CACHE_DIR / existing_path
            if abs_path.exists():
                return "skipped"   # already cached
            else:
                # Path exists in dict but file is missing – clear it and redownload
                del self.game["igdb_cover_art_cache_path"]

        try:
            if url.startswith("//"):
                url = "https:" + url
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameScraper/1.0"}
            response = requests.get(url, timeout=30, headers=headers)
            response.raise_for_status()
            if not response.content:
                return "failed"
            data_len = len(response.content)
            min_bytes = config.CACHE_MIN_KB * 1024
            max_bytes = config.CACHE_MAX_KB * 1024 if config.CACHE_MAX_KB else None
            if data_len < min_bytes or (max_bytes and data_len > max_bytes):
                return "failed"

            from cache_utils import _game_cache_dir_for_game
            cache_dir = _game_cache_dir_for_game(self.game)

            # Determine extension
            ext = ".jpg"
            lower_url = url.lower()
            if lower_url.endswith('.png'):
                ext = ".png"
            elif lower_url.endswith('.webp'):
                ext = ".webp"
            elif lower_url.endswith('.jpeg'):
                ext = ".jpeg"
            content_type = response.headers.get('content-type', '').lower()
            if 'png' in content_type:
                ext = ".png"
            elif 'webp' in content_type:
                ext = ".webp"
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = ".jpg"

            filename = f"coverart{ext}"
            target_path = cache_dir / filename
            target_path.write_bytes(response.content)
            saved_path_str = target_path.as_posix() if hasattr(target_path, 'as_posix') else str(target_path)
            self.game["igdb_cover_art_cache_path"] = saved_path_str
            print(f"[DOWNLOAD] Saved cover art to {saved_path_str}")
            return "downloaded"
        except Exception as e:
            print(f"[DOWNLOAD] Cover art error for {url}: {e}")
            return "failed"

    def _scan_cache(self):
        from cache_utils import scan_cache_directory_for_game
        return scan_cache_directory_for_game(self.game)

    def _download_microtrailer(self):
        microtrailer_urls = []
        if self.game.get("trailer_webm"):
            microtrailer_urls.append(self.game["trailer_webm"])
        microtrailers = self.game.get("microtrailers") or []
        if isinstance(microtrailers, list):
            microtrailer_urls.extend(microtrailers[:config.MAX_MICROTRAILERS])
        elif isinstance(microtrailers, str):
            parts = [p.strip() for p in microtrailers.split(",") if p.strip()]
            microtrailer_urls.extend(parts[:config.MAX_MICROTRAILERS])
        microtrailer_urls = list(set(u for u in microtrailer_urls if u))
        if not microtrailer_urls:
            return "skipped"
        for url in microtrailer_urls[:config.MAX_MICROTRAILERS]:
            if self.cancelled:
                return "failed"
            try:
                if url.startswith("//"):
                    url = "https:" + url
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                existing = self.game.get("image_cache_paths", [])
                if any(url_hash in Path(p).stem for p in existing if p):
                    return "skipped"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameScraper/1.0"}
                response = requests.get(url, timeout=30, headers=headers)
                response.raise_for_status()
                if not response.content:
                    continue
                data_len = len(response.content)
                min_bytes = config.CACHE_MIN_KB * 1024
                max_bytes = config.CACHE_MAX_KB * 1024 if config.CACHE_MAX_KB else None
                if data_len < min_bytes or (max_bytes and data_len > max_bytes):
                    continue
                saved_path = _save_bytes_to_game_cache(self.game, url, response.content)
                saved_path_str = saved_path.as_posix() if hasattr(saved_path, 'as_posix') else str(saved_path)
                self.game["microtrailer_cache_path"] = saved_path_str
                if "image_cache_paths" not in self.game:
                    self.game["image_cache_paths"] = []
                if saved_path_str not in self.game["image_cache_paths"]:
                    if len(self.game["image_cache_paths"]) < config.MAX_IMAGES_TO_DISPLAY:
                        self.game["image_cache_paths"].append(saved_path_str)
                    else:
                        self.game["image_cache_paths"].pop(0)
                        self.game["image_cache_paths"].append(saved_path_str)
                return "downloaded"
            except Exception as e:
                print(f"[DOWNLOAD] Microtrailer error for {url}: {e}")
        return "failed"

    def _download_screenshots(self, max_to_download):
        downloaded = 0
        failed = 0
        screenshot_urls = []
        cover_url = self.game.get("cover_url")
        if cover_url:
            screenshot_urls.append(cover_url)
        screenshots = self.game.get("screenshots") or []
        if isinstance(screenshots, list):
            screenshot_urls.extend(screenshots)
        elif isinstance(screenshots, str):
            parts = [p.strip() for p in screenshots.split(",") if p.strip()]
            screenshot_urls.extend(parts)
        screenshot_urls = list(set(u for u in screenshot_urls if u))
        if not screenshot_urls:
            return 0, 0
        existing_hashes = set()
        for p in self.game.get("image_cache_paths", []):
            if p:
                try:
                    existing_hashes.add(Path(p).stem)
                except:
                    pass
        for url in screenshot_urls:
            if downloaded >= max_to_download or self.cancelled:
                break
            try:
                if url.startswith("//"):
                    url = "https:" + url
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                if url_hash in existing_hashes:
                    continue
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameScraper/1.0"}
                response = requests.get(url, timeout=30, headers=headers)
                response.raise_for_status()
                if not response.content:
                    failed += 1
                    continue
                data_len = len(response.content)
                min_bytes = config.CACHE_MIN_KB * 1024
                max_bytes = config.CACHE_MAX_KB * 1024 if config.CACHE_MAX_KB else None
                if data_len < min_bytes or (max_bytes and data_len > max_bytes):
                    failed += 1
                    continue
                content_type = response.headers.get('content-type', '').lower()
                if content_type and 'image' not in content_type:
                    failed += 1
                    continue
                saved_path = _save_bytes_to_game_cache(self.game, url, response.content)
                saved_path_str = saved_path.as_posix() if hasattr(saved_path, 'as_posix') else str(saved_path)
                if "image_cache_paths" not in self.game:
                    self.game["image_cache_paths"] = []
                if saved_path_str not in self.game["image_cache_paths"]:
                    if len(self.game["image_cache_paths"]) < config.MAX_IMAGES_TO_DISPLAY:
                        self.game["image_cache_paths"].append(saved_path_str)
                    else:
                        self.game["image_cache_paths"].pop(0)
                        self.game["image_cache_paths"].append(saved_path_str)
                downloaded += 1
            except Exception as e:
                print(f"[DOWNLOAD] Screenshot error for {url}: {e}")
                failed += 1
        return downloaded, failed


class DownloadManager:
    def __init__(self, parent_window):
        self.parent = parent_window
        self._active_workers = []
        self._pending_games = []
        self._download_stats = None
        self._cancel_flag = False

    def cancel(self):
        if not hasattr(self, '_active_workers'):
            return
        self._cancel_flag = True
        self.parent._cancel_current_scrape = True
        for worker, thread, _ in self._active_workers:
            worker.cancelled = True
            if thread.isRunning():
                thread.quit()
                thread.wait(500)
        self._active_workers.clear()
        self._pending_games.clear()
        self.parent.progress_bar.setVisible(False)

    def download_all_screenshots(self):
        games = self.parent.games
        if not games:
            QMessageBox.information(self.parent, "Download Resources", "No games to process.")
            return
        self._cancel_flag = False
        self.parent._cancel_current_scrape = False
        self.parent.cancel_scrape_btn.setVisible(True)
        self.parent.scrape_btn.setEnabled(False)
        self._download_stats = {
            "total_games": len(games),
            "processed": 0,
            "screenshots_downloaded": 0,
            "screenshots_failed": 0,
            "microtrailers_downloaded": 0,
            "microtrailers_failed": 0,
            "start_time": time.time()
        }
        self._pending_games = list(range(len(games)))
        self._active_workers = []
        # Show progress bar
        self.parent.progress_bar.setVisible(True)
        self.parent.progress_bar.setMaximum(len(games))
        self.parent.progress_bar.setValue(0)
        for _ in range(min(config.MAX_CONCURRENT_DOWNLOADS, len(self._pending_games))):
            self._start_next_worker()

    def _start_next_worker(self):
        if not self._pending_games or self._cancel_flag or self.parent._cancel_current_scrape:
            if not self._active_workers:
                self._finish_download()
            return
        game_idx = self._pending_games.pop(0)
        game = self.parent.games[game_idx]
        title = game.get("title") or game.get("original_title") or f"Game {game_idx}"
        self.parent.status.setText(f"Downloading: {title} ({self._download_stats['processed']+1}/{self._download_stats['total_games']})")
        self.parent.progress_bar.setValue(self._download_stats["processed"])
        worker = GameDownloadWorker(game_idx, game)
        thread = QThread(self.parent)
        worker.moveToThread(thread)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        thread.started.connect(worker.run)
        thread.start()
        self._active_workers.append((worker, thread, game_idx))

    def _on_worker_finished(self, game_idx, stats):
        for i, (w, t, idx) in enumerate(self._active_workers):
            if idx == game_idx:
                t.quit()
                t.wait(500)
                self._active_workers.pop(i)
                break
        if not self._cancel_flag:
            self._download_stats["processed"] += 1
            self._download_stats["screenshots_downloaded"] += stats["screenshots_downloaded"]
            self._download_stats["screenshots_failed"] += stats["screenshots_failed"]
            self._download_stats["microtrailers_downloaded"] += stats["microtrailers_downloaded"]
            self._download_stats["microtrailers_failed"] += stats["microtrailers_failed"]
            self._update_game_cache_fields(game_idx, self.parent.games[game_idx])
            self.parent.mark_dirty()
        self._start_next_worker()

    def _on_worker_error(self, game_idx, error_msg):
        print(f"[DOWNLOAD] Error processing game {game_idx}: {error_msg}")
        self._on_worker_finished(game_idx, {"screenshots_downloaded":0, "screenshots_failed":0,
                                            "microtrailers_downloaded":0, "microtrailers_failed":0})

    def _finish_download(self):
        elapsed = time.time() - self._download_stats["start_time"]
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        total_screenshots = self._download_stats["screenshots_downloaded"]
        total_microtrailers = self._download_stats["microtrailers_downloaded"]
        summary = f"""
        ╔══════════════════════════════════════════════╗
        ║           DOWNLOAD COMPLETE                  ║
        ╚══════════════════════════════════════════════╝

        📊 STATISTICS
        • Games Processed: {self._download_stats['processed']}/{self._download_stats['total_games']}
        • Time: {minutes:02d}:{seconds:02d}

        🖼️  SCREENSHOTS
        • Newly Downloaded: {total_screenshots}
        • Failed: {self._download_stats['screenshots_failed']}

        🎬 MICROTRAILERS
        • Newly Downloaded: {total_microtrailers}
        • Failed: {self._download_stats['microtrailers_failed']}
        """
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowTitle("Download Complete")
        msg_box.setText(summary)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec_()
        self.parent.refresh_model()
        self.parent.status.setText(f"Download complete: {total_screenshots} screenshots, {total_microtrailers} microtrailers")
        self.parent.scrape_btn.setEnabled(True)
        self.parent.cancel_scrape_btn.setVisible(False)
        self.parent.progress_bar.setVisible(False)

    def _update_game_cache_fields(self, game_idx, game):
        if game_idx >= self.parent.model.rowCount():
            return
        cache_paths = game.get("image_cache_paths", [])
        if isinstance(cache_paths, list):
            cache_text = ", ".join(str(p) for p in cache_paths if p)
        else:
            cache_text = str(cache_paths)
        # COL_IMAGE_CACHE_PATHS = 27 in gui_main.py
        self.parent.model.setItem(game_idx, 27, QStandardItem(cache_text))
        microtrailer_path = game.get("microtrailer_cache_path", "")
        # COL_MICROTRAILER_CACHE_PATH = 26 in gui_main.py
        self.parent.model.setItem(game_idx, 26, QStandardItem(str(microtrailer_path)))
        title_item = self.parent.model.item(game_idx, 0)
        if title_item:
            title_item.setData(game, Qt.UserRole)