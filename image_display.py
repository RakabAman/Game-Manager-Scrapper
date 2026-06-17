# image_display.py
import hashlib
from pathlib import Path

from PyQt5.QtCore import QThread, QTimer, QCoreApplication, Qt, QUrl
from PyQt5.QtGui import QPixmap, QMovie, QStandardItem, QDesktopServices
from workers import ImageFetchWorker
from cache_utils import _to_relative, scan_cache_directory_for_game
import config

def _normalize_url(url: str) -> str:
    """Remove query parameters and force https for consistent hashing."""
    if '?' in url:
        url = url.split('?')[0]
    if url.startswith('http://'):
        url = 'https://' + url[7:]
    return url
    
class ImageDisplayManager:
    def __init__(self, parent_window):
        self.parent = parent_window
        self.viewer = parent_window.viewer
        self._image_items = []
        self._current_image_index = 0
        self._in_memory_image_cache = {}

        # Sequential download queue
        self.download_queue = []
        self.download_worker = None
        self.download_thread = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_and_display_images(self, row_index: int, urls: list) -> bool:
        """
        Load images from cache (or scan disk) and download missing ones sequentially.
        Returns True if all images were already cached.
        """
        self._image_items = []
        self._current_image_index = 0
        self.viewer.clear()
        if hasattr(self.viewer, "movie") and self.viewer.movie():
            self.viewer.movie().stop()
        self.viewer.set_url("")

        if not urls:
            self.parent.status.setText("No images available")
            self._update_navigation()
            return True

        game = self.parent.games[row_index] if row_index < len(self.parent.games) else None
        if not game:
            return False

        # ---- ALWAYS scan cache directory to get all existing files ----
        # This ensures we find all cached images even if the stored list is incomplete.
        self._scan_and_update_cache_paths(game)

        cover_url = game.get("cover_url", "")
        if cover_url and cover_url.startswith("//"):
            cover_url = "https:" + cover_url

        # If Steam cover is missing, fallback to IGDB cover art
        if not cover_url:
            igdb_cover = game.get("igdb_cover_art")
            if igdb_cover:
                cover_url = igdb_cover
                # Ensure the fallback cover is included in the urls list (as first image)
                if cover_url not in urls:
                    urls.insert(0, cover_url)

        # Build list of URLs to process (cover + up to config.MAX_IMAGES_TO_DOWNLOAD screenshots)
        urls_to_process = []
        if cover_url and cover_url in urls:
            urls_to_process.append(cover_url)

        screenshot_count = 0
        for url in urls:
            if url == cover_url:
                continue
            if screenshot_count < config.MAX_IMAGES_TO_DOWNLOAD:
                urls_to_process.append(url)
                screenshot_count += 1
            else:
                break

        # Create image items
        for url in urls_to_process:
            norm_url = "https:" + url if url.startswith("//") else url
            self._image_items.append({
                "url": norm_url,
                "pixmap": None,
                "movie": None,
                "fetched": False,
                "local_path": None,
                "already_cached": False,
                "is_cover": (norm_url == cover_url)
            })

        # ---- Load from already recorded cache paths (now updated by scan) ----
        raw_paths = game.get("image_cache_paths")
        if isinstance(raw_paths, str):
            cached_paths = [p.strip() for p in raw_paths.replace(';', ',').split(",") if p.strip()]
        elif isinstance(raw_paths, list):
            cached_paths = raw_paths
        else:
            cached_paths = []

        loaded_from_cache = 0
        cache_miss_indices = []

        # ---- Special handling for cover art (stored as coverart.jpg) ----
        if cover_url:
            from cache_utils import _game_cache_dir_for_game
            cache_dir = _game_cache_dir_for_game(game)
            cover_path = cache_dir / "coverart.jpg"
            if cover_path.exists():
                for idx, item in enumerate(self._image_items):
                    if item.get("is_cover") and not item.get("fetched"):
                        pixmap = QPixmap()
                        if pixmap.load(str(cover_path)):
                            item["pixmap"] = pixmap
                            item["fetched"] = True
                            item["already_cached"] = True
                            item["local_path"] = str(cover_path.relative_to(config.CACHE_DIR))
                            loaded_from_cache += 1
                            break

        # ---- Load cached screenshots ----
        for cache_path in cached_paths:
            if not cache_path:
                continue
            try:
                abs_path = config.CACHE_DIR / cache_path
                if not abs_path.exists():
                    continue
                for idx, item in enumerate(self._image_items):
                    if item.get("fetched") or item.get("already_cached"):
                        continue
                    norm_url = _normalize_url(item["url"])
                    url_hash = hashlib.sha256(norm_url.encode("utf-8")).hexdigest()
                    orig_hash = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()
                    if url_hash == abs_path.stem or orig_hash == abs_path.stem:
                        if str(abs_path).lower().endswith('.gif'):
                            movie = QMovie(str(abs_path))
                            movie.setCacheMode(QMovie.CacheAll)
                            if movie.isValid():
                                movie.start()
                                item["movie"] = movie
                                item["fetched"] = True
                                item["already_cached"] = True
                                item["local_path"] = cache_path
                                loaded_from_cache += 1
                                break
                        else:
                            pixmap = QPixmap()
                            if pixmap.load(str(abs_path)):
                                item["pixmap"] = pixmap
                                item["fetched"] = True
                                item["already_cached"] = True
                                item["local_path"] = cache_path
                                loaded_from_cache += 1
                                break
            except Exception as e:
                print(f"[IMAGE_CACHE] Error loading {cache_path}: {e}")

        # Identify which images are still missing
        for idx, item in enumerate(self._image_items):
            if not item.get("fetched"):
                cache_miss_indices.append(idx)

        # Show the first available image immediately
        first_available = next((i for i, it in enumerate(self._image_items) if it.get("fetched")), None)
        if first_available is not None:
            self._current_image_index = first_available
            self.display_image(self._current_image_index)
            self._update_navigation()
            QTimer.singleShot(100, self.parent._force_button_refresh)

            if loaded_from_cache == len(self._image_items):
                self.parent.status.setText(f"Loaded all {len(self._image_items)} images from cache")
            elif loaded_from_cache > 0:
                self.parent.status.setText(f"Loaded {loaded_from_cache}/{len(self._image_items)} images from cache")
            else:
                self.parent.status.setText("No cached images found, downloading...")
        else:
            self.parent.status.setText("No images available")
            self.parent.image_counter.setText("No images")
            self.parent.prev_btn.setEnabled(False)
            self.parent.next_btn.setEnabled(False)

        # ---- Queue missing images for sequential download ----
        if config.AUTO_CACHE and cache_miss_indices:
            already_downloaded_non_cover = sum(1 for it in self._image_items if it.get("fetched") and not it.get("is_cover"))
            remaining_downloads = max(0, config.MAX_IMAGES_TO_DOWNLOAD - already_downloaded_non_cover)
            for idx in cache_miss_indices:
                if len(self.download_queue) >= remaining_downloads and idx > 0:
                    break
                item = self._image_items[idx]
                if item.get("fetched") or item.get("already_cached"):
                    continue
                if not item.get("is_cover") and len(self.download_queue) >= remaining_downloads:
                    continue
                self.download_queue.append((row_index, item["url"], game))
                print(f"[IMAGE_QUEUE] Added to queue: {item['url']}")
            self._process_download_queue()
        else:
            if not config.AUTO_CACHE and cache_miss_indices:
                self.parent.status.setText("Auto‑cache is off. Missing images not downloaded.")

        return loaded_from_cache == len(self._image_items)     
    
    # ------------------------------------------------------------------
    # Cache scanning
    # ------------------------------------------------------------------
    def _scan_and_update_cache_paths(self, game: dict) -> bool:
        """Scan the game's cache folder and update the game dict + model."""
        result = scan_cache_directory_for_game(game)
        updated = False
        if result["screenshot_paths"]:
            game["image_cache_paths"] = result["screenshot_paths"]
            try:
                row = self.parent.games.index(game)
                # Column 27 = COL_IMAGE_CACHE_PATHS in gui_main.py
                self.parent.model.setItem(row, 27,
                                          QStandardItem(", ".join(result["screenshot_paths"])))
            except ValueError:
                pass
            updated = True
        if result["microtrailer_path"]:
            game["microtrailer_cache_path"] = result["microtrailer_path"]
            try:
                row = self.parent.games.index(game)
                # Column 26 = COL_MICROTRAILER_CACHE_PATH in gui_main.py
                self.parent.model.setItem(row, 26, QStandardItem(result["microtrailer_path"]))
            except ValueError:
                pass
            updated = True
        return updated

    # ------------------------------------------------------------------
    # Sequential download queue
    # ------------------------------------------------------------------
    def _process_download_queue(self):
        """Start the next download from the queue if none is running."""
        if self.download_worker is not None or not self.download_queue:
            return
        row_index, url, game = self.download_queue.pop(0)
        self.download_worker = ImageFetchWorker(row_index, url, game)
        self.download_thread = QThread(self.parent)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_thread.start()
        print(f"[IMAGE_QUEUE] Started download for {url}")

    def _on_download_finished(self, row_index: int, url: str, rel_path: str):
        """Called when a single image download completes."""
        for item in self._image_items:
            if item.get("url") == url:
                item["fetched"] = True
                item["local_path"] = rel_path
                try:
                    abs_path = config.SCRIPT_DIR / rel_path
                    if abs_path.exists():
                        if str(abs_path).lower().endswith('.gif'):
                            movie = QMovie(str(abs_path))
                            movie.setCacheMode(QMovie.CacheAll)
                            if movie.isValid():
                                movie.start()
                                item["movie"] = movie
                        else:
                            pixmap = QPixmap()
                            if pixmap.load(str(abs_path)):
                                item["pixmap"] = pixmap
                except Exception as e:
                    print(f"[ERROR] Loading cached image after download: {e}")
                break

        game = self.parent.games[row_index] if row_index < len(self.parent.games) else None
        if game:
            is_microtrailer = any(ext in url.lower() for ext in ('.gif', '.webm', '.mp4', 'microtrailer'))
            if is_microtrailer:
                game["microtrailer_cache_path"] = rel_path
                # Column 26 = COL_MICROTRAILER_CACHE_PATH
                self.parent.model.setItem(row_index, 26, QStandardItem(rel_path))
            paths = game.get("image_cache_paths", [])
            if rel_path not in paths:
                paths.append(rel_path)
                game["image_cache_paths"] = paths[:config.MAX_IMAGES_TO_DISPLAY]
                # Column 27 = COL_IMAGE_CACHE_PATHS
                self.parent.model.setItem(row_index, 27, QStandardItem(", ".join(paths)))

        current_item = self._image_items[self._current_image_index] if self._image_items else None
        if current_item and current_item.get("url") == url:
            self.display_image(self._current_image_index)

        cached_count = len([i for i in self._image_items if i.get("fetched")])
        self.parent.status.setText(f"{cached_count}/{len(self._image_items)} images loaded")

        self.download_worker = None
        self.download_thread = None
        self._process_download_queue()

    def _on_download_error(self, row_index: int, url: str, error_msg: str):
        print(f"[IMAGE_QUEUE] Error downloading {url}: {error_msg}")
        self.parent.status.setText(f"Download error: {error_msg}")
        self.download_worker = None
        self.download_thread = None
        self._process_download_queue()

    # ------------------------------------------------------------------
    # Image display & navigation
    # ------------------------------------------------------------------
    def display_image(self, index: int):
        if not self._image_items or index is None or index < 0 or index >= len(self._image_items):
            self.viewer.clear()
            self.viewer.set_url("")
            self._update_navigation()
            return
        item = self._image_items[index]
        url = item.get("url") or ""
        try:
            current_movie = getattr(self.viewer, "movie", None)
            if current_movie:
                try:
                    current_movie.stop()
                except:
                    pass

            if item.get("movie") and item["movie"].isValid():
                self.viewer.setMovie(item["movie"])
                item["movie"].start()
                self.viewer.set_url(url)
            elif item.get("pixmap") and not item["pixmap"].isNull():
                pixmap = item["pixmap"]
                viewer_size = self.viewer.size()
                scaled = pixmap.scaled(viewer_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.viewer.setPixmap(scaled)
                self.viewer.set_url(url)
            else:
                self.viewer.clear()
                self.viewer.set_url("")

            if hasattr(self.parent, 'open_image_btn'):
                if url:
                    self.parent.open_image_btn.setEnabled(True)
                    self.parent.open_image_btn.setToolTip(f"Open in browser: {url}")
                else:
                    self.parent.open_image_btn.setEnabled(False)

            self._update_navigation()
        except Exception as e:
            print(f"[ERROR] display_image: {e}")
            self.viewer.clear()
            self.viewer.set_url("")
            if hasattr(self.parent, 'open_image_btn'):
                self.parent.open_image_btn.setEnabled(False)
            self._update_navigation()

    def _update_navigation(self):
        if hasattr(self.parent, 'prev_btn'):
            self.parent.prev_btn.show()
        if hasattr(self.parent, 'next_btn'):
            self.parent.next_btn.show()
        if hasattr(self.parent, 'open_image_btn'):
            self.parent.open_image_btn.show()
        if hasattr(self.parent, 'image_counter'):
            self.parent.image_counter.show()

        if not self._image_items:
            self.parent.prev_btn.setEnabled(False)
            self.parent.next_btn.setEnabled(False)
            self.parent.open_image_btn.setEnabled(False)
            self.parent.image_counter.setText("No images")
            return

        has_multiple = len(self._image_items) > 1
        self.parent.prev_btn.setEnabled(has_multiple)
        self.parent.next_btn.setEnabled(has_multiple)
        if len(self._image_items) == 1:
            self.parent.image_counter.setText("1/1")
        else:
            self.parent.image_counter.setText(f"{self._current_image_index + 1}/{len(self._image_items)}")
        QTimer.singleShot(50, self.parent._position_navigation_buttons)

    def next_image(self):
        if not self._image_items:
            return
        self._current_image_index = (self._current_image_index + 1) % len(self._image_items)
        self.display_image(self._current_image_index)
        self._update_navigation()

    def prev_image(self):
        if not self._image_items:
            return
        self._current_image_index = (self._current_image_index - 1) % len(self._image_items)
        self.display_image(self._current_image_index)
        self._update_navigation()

    def open_current_image_url(self):
        if not self._image_items or self._current_image_index is None:
            return
        item = self._image_items[self._current_image_index]
        url = item.get("url", "")
        if url:
            QDesktopServices.openUrl(QUrl(url))
            self.parent.status.setText("Opened image URL in browser")