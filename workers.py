# workers.py
import time
import requests
import hashlib
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from config import CACHE_MIN_KB, CACHE_MAX_KB
import scraping
from cache_utils import _save_bytes_to_game_cache, _game_cache_dir_for_game

class ImageFetchWorker(QObject):
    finished = pyqtSignal(int, str, str)  # row_index, url, saved_path
    error = pyqtSignal(int, str, str)     # row_index, url, error_msg

    def __init__(self, row_index: int, url: str, game: dict = None, parent=None):
        super().__init__(parent)
        self.row_index = row_index
        self.url = (url or "").strip()
        self.game = game or {}
        self.cancelled = False

    def run(self):
        try:
            if not self.url:
                self.error.emit(self.row_index, self.url, "Empty URL")
                return
            url = self.url
            if url.startswith("//"):
                url = "https:" + url

            if self._is_already_cached(url):
                cache_path = self._get_existing_cache_path(url)
                if cache_path:
                    self.finished.emit(self.row_index, url, str(cache_path))
                    return

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameScraper/1.0",
                "Accept": "image/webp,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            with requests.get(url, stream=True, timeout=30, headers=headers) as response:
                response.raise_for_status()
                chunks = []
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        self.error.emit(self.row_index, self.url, "Cancelled")
                        return
                    if chunk:
                        chunks.append(chunk)
                data = b"".join(chunks)

            if not data:
                self.error.emit(self.row_index, self.url, "No data fetched")
                return

            saved_path = _save_bytes_to_game_cache(self.game, url, data)
            saved_path_str = saved_path.as_posix() if hasattr(saved_path, 'as_posix') else str(saved_path)
            self.finished.emit(self.row_index, url, saved_path_str)

        except Exception as e:
            self.error.emit(self.row_index, self.url, str(e))

    def _is_already_cached(self, url: str) -> bool:
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        screenshot_paths = self.game.get("screenshot_cache_paths", [])
        for path in screenshot_paths:
            if path and url_hash in Path(path).stem:
                return True
        microtrailer_path = self.game.get("microtrailer_cache_path", "")
        if microtrailer_path and url_hash in Path(microtrailer_path).stem:
            return True
        return False

    def _get_existing_cache_path(self, url: str):
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        screenshot_paths = self.game.get("screenshot_cache_paths", [])
        for path_str in screenshot_paths:
            if path_str and url_hash in Path(path_str).stem:
                return Path(path_str)
        microtrailer_path = self.game.get("microtrailer_cache_path", "")
        if microtrailer_path and url_hash in Path(microtrailer_path).stem:
            return Path(microtrailer_path)
        return None


class ScrapeBatchWorker(QObject):
    progress = pyqtSignal(str)
    row_started = pyqtSignal(int, int, str)
    row_finished = pyqtSignal(int, dict)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, rows_to_process: list, games_ref: list, parent=None):
        super().__init__(parent)
        self.rows = list(rows_to_process)
        self.games_ref = games_ref
        self.cancelled = False

    def run(self):
        processed = 0
        total = len(self.rows)
        try:
            for idx, row_index in enumerate(self.rows, start=1):
                if self.cancelled:
                    self.progress.emit("Batch scrape cancelled by user.")
                    break
                if row_index < 0 or row_index >= len(self.games_ref):
                    continue
                game = self.games_ref[row_index]
                title = game.get("title") or game.get("original_title") or ""
                self.row_started.emit(row_index, total, title)

                appid = str(game.get("app_id") or "").strip()
                if appid:
                    self.row_finished.emit(row_index, {})
                    processed += 1
                    time.sleep(0.05)
                    continue

                try:
                    meta = scraping.scrape_igdb_then_steam(
                        None, title, auto_accept_score=92, fetch_pcgw_save=False
                    ) or {}
                    if meta:
                        if "__candidates__" in meta:
                            self.row_finished.emit(row_index, meta)
                        else:
                            has_data = any(meta.get(k) for k in ['app_id', 'developer', 'publisher', 'genres'])
                            if has_data:
                                self.row_finished.emit(row_index, meta)
                            else:
                                self.row_finished.emit(row_index, {})
                    else:
                        self.row_finished.emit(row_index, {})
                except Exception:
                    try:
                        candidates = scraping.find_candidates_for_title_igdb(title, max_candidates=8)
                        self.row_finished.emit(row_index, {"__candidates__": candidates})
                    except Exception:
                        self.row_finished.emit(row_index, {"__candidates__": []})
                processed += 1
                time.sleep(0.12)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit(processed)