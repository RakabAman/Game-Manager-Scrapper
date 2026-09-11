from PyQt5.QtCore import QThread, QTimer, QCoreApplication, Qt, QUrl, QBuffer, QByteArray
from PyQt5.QtGui import QPixmap, QMovie, QStandardItem, QDesktopServices, QKeyEvent
from PyQt5.QtWidgets import QDialog, QStackedWidget, QPushButton, QLabel, QHBoxLayout, QWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QSize             # new, for type hint
from workers import ImageFetchWorker
from cache_utils import (
    _to_relative,
    scan_cache_directory_for_game,
    _game_cache_dir_for_game,
    _save_bytes_to_game_cache,
    resolve_cover_art_cache_path,          # new
)
from widgets import ClickableImageViewer, AspectRatioWidget
import config
import hashlib
import requests   # optional, for synchronous fallback
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

def _normalize_url(url: str) -> str:
    if '?' in url:
        url = url.split('?')[0]
    if url.startswith('http://'):
        url = 'https://' + url[7:]
    return url
    
class ImageDisplayManager:
    def __init__(self, parent_window, viewer=None):
        self.parent = parent_window
        if viewer is not None:
            self.viewer = viewer
        else:
            self.viewer = parent_window.viewer if hasattr(parent_window, 'viewer') else None
        self._image_items = []
        self._current_image_index = 0
        self._in_memory_image_cache = {}

        self.download_queue = []
        self.download_worker = None
        self.download_thread = None

    def _safe_set_status(self, text):
        if hasattr(self.parent, 'status'):
            self.parent.status.setText(text)
        else:
            print(f"[IMAGE_DISPLAY] {text}")

    def fetch_and_display_images(self, row_index: int, urls: list,
                                 on_image_ready: callable = None,
                                 cover_type: str = None,
                                 save_to_cache: bool = True) -> bool:
        """
        Load images from cache and enqueue missing ones.
        If cover_type is provided, it will be passed to the download worker
        so that the file is saved as {cover_type}_coverart.<ext>.
        """
        self.download_queue.clear()
        self._image_items = []
        self._current_image_index = 0
        self._on_image_ready_callback = on_image_ready

        if self.viewer:
            self.viewer.clear()
            if hasattr(self.viewer, "movie") and self.viewer.movie():
                self.viewer.movie().stop()
            self.viewer.set_url("")

        if not urls:
            self._safe_set_status("No images available")
            self._update_navigation()
            return True

        game = self.parent.games[row_index] if row_index < len(self.parent.games) else None
        if not game:
            return False

        urls = list(urls)
        self._scan_and_update_cache_paths(game)

        # Build cover_url
        cover_url = game.get("cover_url", "")
        if cover_url and cover_url.startswith("//"):
            cover_url = "https:" + cover_url

        if not cover_url:
            igdb_cover = game.get("igdb_cover_art")
            if igdb_cover:
                cover_url = igdb_cover
                if cover_url not in urls:
                    urls.insert(0, cover_url)

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

        # Build image items
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

        # ---- Load from cache ----
        raw_paths = game.get("image_cache_paths")
        if isinstance(raw_paths, str):
            cached_paths = [p.strip() for p in raw_paths.replace(';', ',').split(",") if p.strip()]
        elif isinstance(raw_paths, list):
            cached_paths = raw_paths
        else:
            cached_paths = []

        loaded_from_cache = 0

        # Special handling for cover art using resolve_cover_art_cache_path
        if cover_url:
            # Use the provided cover_type if any, else auto-detect
            detect_type = cover_type
            if not detect_type:
                if cover_url == game.get("cover_url"):
                    detect_type = 'steam'
                elif cover_url == game.get("igdb_cover_art"):
                    detect_type = 'igdb'
            cover_path = resolve_cover_art_cache_path(game, cover_type=detect_type)
            if cover_path and cover_path.exists():
                for idx, item in enumerate(self._image_items):
                    if item.get("is_cover") and not item.get("fetched"):
                        pixmap = QPixmap()
                        if pixmap.load(str(cover_path)):
                            item["pixmap"] = pixmap
                            item["fetched"] = True
                            item["already_cached"] = True
                            try:
                                item["local_path"] = str(cover_path.relative_to(config.CACHE_DIR))
                            except ValueError:
                                item["local_path"] = str(cover_path)
                            loaded_from_cache += 1
                            if self._on_image_ready_callback:
                                self._on_image_ready_callback(item["url"], pixmap, None, idx)
                            break

        # Load cached screenshots from image_cache_paths
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
                                if self._on_image_ready_callback:
                                    self._on_image_ready_callback(item["url"], None, movie, idx)
                                break
                        else:
                            pixmap = QPixmap()
                            if pixmap.load(str(abs_path)):
                                item["pixmap"] = pixmap
                                item["fetched"] = True
                                item["already_cached"] = True
                                item["local_path"] = cache_path
                                loaded_from_cache += 1
                                if self._on_image_ready_callback:
                                    self._on_image_ready_callback(item["url"], pixmap, None, idx)
                                break
            except Exception as e:
                print(f"[IMAGE_CACHE] Error loading {cache_path}: {e}")

        # Show first available image
        first_available = next((i for i, it in enumerate(self._image_items) if it.get("fetched")), None)
        if first_available is not None:
            self._current_image_index = first_available
            self.display_image(self._current_image_index)
            self._update_navigation()
            if hasattr(self.parent, '_force_button_refresh'):
                QTimer.singleShot(100, self.parent._force_button_refresh)

        # ---- Queue missing images ----
        cache_miss_indices = [idx for idx, it in enumerate(self._image_items) if not it.get("fetched")]
        if cache_miss_indices:
            already_downloaded_non_cover = sum(1 for it in self._image_items if it.get("fetched") and not it.get("is_cover"))
            remaining_downloads = max(0, config.MAX_IMAGES_TO_DOWNLOAD - already_downloaded_non_cover)

            for idx in cache_miss_indices:
                item = self._image_items[idx]
                if not item.get("is_cover") and len(self.download_queue) >= remaining_downloads:
                    break
                if item.get("fetched") or item.get("already_cached"):
                    continue

                # Determine cover_type per item (if not explicitly provided)
                item_cover_type = cover_type
                if not item_cover_type:
                    if item["url"] == game.get("cover_url"):
                        item_cover_type = 'steam'
                    elif item["url"] == game.get("igdb_cover_art"):
                        item_cover_type = 'igdb'

                self.download_queue.append((row_index, item["url"], game, save_to_cache, idx, item_cover_type))

            if self.download_queue:
                self._safe_set_status(f"Fetching {len(self.download_queue)} images from network...")
                self._process_download_queue()

        return loaded_from_cache == len(self._image_items)
    
    def _scan_and_update_cache_paths(self, game: dict) -> bool:
        result = scan_cache_directory_for_game(game)
        updated = False
        if result["screenshot_paths"]:
            game["image_cache_paths"] = result["screenshot_paths"]
            try:
                row = self.parent.games.index(game)
                self.parent.model.setItem(row, self.parent.COL_IMAGE_CACHE_PATHS,
                                          QStandardItem(", ".join(result["screenshot_paths"])))
            except ValueError:
                pass
            updated = True
        if result["microtrailer_path"]:
            game["microtrailer_cache_path"] = result["microtrailer_path"]
            try:
                row = self.parent.games.index(game)
                self.parent.model.setItem(row, self.parent.COL_MICROTRAILER_CACHE_PATH, QStandardItem(result["microtrailer_path"]))
            except ValueError:
                pass
            updated = True
        return updated

    def _process_download_queue(self):
        if self.download_worker is not None or not self.download_queue:
            return
        row_index, url, game, save_to_cache, item_index, cover_type = self.download_queue.pop(0)
        self.download_worker = ImageFetchWorker(
            row_index, url, game,
            save_to_cache=save_to_cache,
            cover_type=cover_type
        )
        self.download_thread = QThread(self.parent)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.finished.connect(
            lambda ri, u, rp, d, idx=item_index: self._on_download_finished(ri, u, rp, d, idx)
        )
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.error.connect(self.download_thread.quit)
        self.download_thread.finished.connect(self.download_worker.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.start()
        
    def _on_download_finished(self, row_index: int, url: str, rel_path: str, data: bytes, item_index: int):
        if item_index < len(self._image_items):
            item = self._image_items[item_index]
            item["fetched"] = True
            item["local_path"] = rel_path
            if rel_path:
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
            elif data:
                try:
                    if url.lower().endswith('.gif') or (len(data) >= 6 and data[:6] in (b'GIF87a', b'GIF89a')):
                        movie = QMovie()
                        movie.setCacheMode(QMovie.CacheAll)
                        movie.setDevice(QBuffer(QByteArray(data)))
                        if movie.isValid():
                            movie.start()
                            item["movie"] = movie
                    else:
                        pixmap = QPixmap()
                        if pixmap.loadFromData(data):
                            item["pixmap"] = pixmap
                except Exception as e:
                    print(f"[ERROR] Displaying image from data: {e}")

            # Call the callback if provided
            if self._on_image_ready_callback:
                pixmap = item.get("pixmap")
                movie = item.get("movie")
                self._on_image_ready_callback(item["url"], pixmap, movie, item_index)

        # Update model if saved to cache
        game = self.parent.games[row_index] if row_index < len(self.parent.games) else None
        if game and rel_path:
            is_microtrailer = any(ext in url.lower() for ext in ('.gif', '.webm', '.mp4', 'microtrailer'))
            if is_microtrailer:
                game["microtrailer_cache_path"] = rel_path
                self.parent.model.setItem(row_index, self.parent.COL_MICROTRAILER_CACHE_PATH, QStandardItem(rel_path))
            paths = game.get("image_cache_paths", [])
            if rel_path not in paths:
                paths.append(rel_path)
                game["image_cache_paths"] = paths[:config.MAX_IMAGES_TO_DISPLAY]
                self.parent.model.setItem(row_index, self.parent.COL_IMAGE_CACHE_PATHS, QStandardItem(", ".join(paths)))

        # Update internal viewer if this image is currently displayed
        if self._image_items and self._current_image_index < len(self._image_items):
            current_item = self._image_items[self._current_image_index]
            if current_item.get("url") == url:
                self.display_image(self._current_image_index)

        cached_count = len([i for i in self._image_items if i.get("fetched")])
        self._safe_set_status(f"{cached_count}/{len(self._image_items)} images loaded")

        self.download_worker = None
        self.download_thread = None
        self._process_download_queue()
    
    def _on_download_error(self, row_index: int, url: str, error_msg: str):
        print(f"[IMAGE_QUEUE] Error downloading {url}: {error_msg}")
        self._safe_set_status(f"Download error: {error_msg}")
        self.download_worker = None
        self.download_thread = None
        self._process_download_queue()

    def display_image(self, index: int):
        if not self._image_items or index is None or index < 0 or index >= len(self._image_items):
            if self.viewer:
                self.viewer.clear()
                self.viewer.set_url("")
            self._update_navigation()
            return
        item = self._image_items[index]
        url = item.get("url") or ""
        if self.viewer is None:
            return
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

            if hasattr(self.parent, 'expand_btn'):
                self.parent.expand_btn.setEnabled(bool(url))

            self._update_navigation()
        except Exception as e:
            print(f"[ERROR] display_image: {e}")
            if self.viewer:
                self.viewer.clear()
                self.viewer.set_url("")
            if hasattr(self.parent, 'open_image_btn'):
                self.parent.open_image_btn.setEnabled(False)
            if hasattr(self.parent, 'expand_btn'):
                self.parent.expand_btn.setEnabled(False)
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
            if hasattr(self.parent, 'prev_btn'):
                self.parent.prev_btn.setEnabled(False)
            if hasattr(self.parent, 'next_btn'):
                self.parent.next_btn.setEnabled(False)
            if hasattr(self.parent, 'open_image_btn'):
                self.parent.open_image_btn.setEnabled(False)
            if hasattr(self.parent, 'expand_btn'):
                self.parent.expand_btn.setEnabled(False)
            if hasattr(self.parent, 'image_counter'):
                self.parent.image_counter.setText("No images")
            return

        has_multiple = len(self._image_items) > 1
        if hasattr(self.parent, 'prev_btn'):
            self.parent.prev_btn.setEnabled(has_multiple)
        if hasattr(self.parent, 'next_btn'):
            self.parent.next_btn.setEnabled(has_multiple)
        if hasattr(self.parent, 'image_counter'):
            if len(self._image_items) == 1:
                self.parent.image_counter.setText("1/1")
            else:
                self.parent.image_counter.setText(f"{self._current_image_index + 1}/{len(self._image_items)}")
        if hasattr(self.parent, '_position_navigation_buttons'):
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
            self._safe_set_status("Opened image URL in browser")

    def get_cover_art_pixmap(self, game: dict, target_size: QSize = None) -> QPixmap:
        """
        Return cover art as QPixmap. First checks the cache (Steam/IGDB/hash),
        if missing, downloads synchronously and saves with the correct cover_type.
        """
        # 1. Try to find cached cover using resolve_cover_art_cache_path
        cover_path = resolve_cover_art_cache_path(game)
        if cover_path and cover_path.exists():
            pixmap = QPixmap(str(cover_path))
            if not pixmap.isNull():
                if target_size and not target_size.isNull():
                    return pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return pixmap

        # 2. No cached file – attempt to download
        cover_url = game.get("cover_url") or game.get("igdb_cover_art")
        if not cover_url:
            return QPixmap()

        # Determine cover_type for correct naming
        cover_type = None
        if cover_url == game.get("cover_url"):
            cover_type = 'steam'
        elif cover_url == game.get("igdb_cover_art"):
            cover_type = 'igdb'

        try:
            response = requests.get(cover_url, timeout=10)
            if response.status_code == 200:
                rel_path = _save_bytes_to_game_cache(game, cover_url, response.content, cover_type=cover_type)
                if rel_path:
                    abs_path = config.SCRIPT_DIR / rel_path
                    pixmap = QPixmap()
                    if pixmap.load(str(abs_path)):
                        if target_size and not target_size.isNull():
                            return pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        return pixmap
        except Exception as e:
            print(f"[COVER ART] Download failed: {e}")
        return QPixmap()       
# image_display.py (modified ScreenshotViewerDialog only)
# ... (all imports and ImageDisplayManager remain exactly as before) ...

class ScreenshotViewerDialog(QDialog):
    def __init__(self, main_window, media_items, initial_index=0):
        super().__init__(main_window)
        self.main_window = main_window
        self.media_items = media_items
        self.current_index = initial_index

        self.setWindowTitle("Media Viewer")
        self.setWindowModality(Qt.WindowModal)
        self.resize(1280, 720)

        # --- Central stacked widget (fills the whole window) ---
        self.stacked = QStackedWidget(self)
        self.stacked.setStyleSheet(f"background: {config.IMAGE_VIEWER_BACKGROUND};")
        self.stacked.setGeometry(0, 0, self.width(), self.height())

        # Image viewer (unchanged)
        self.image_viewer = ClickableImageViewer()
        self.image_viewer.setAlignment(Qt.AlignCenter)
        self.image_viewer.setStyleSheet("background: transparent;")
        self.stacked.addWidget(self.image_viewer)

        # --- NEW: Video viewer using QWebEngineView (like TrailerPlayerManager) ---

        self.video_view = QWebEngineView()
        settings = self.video_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, False)
        self.video_view.setStyleSheet("background: #111; border: none; margin: 0; padding: 0;")
        self.stacked.addWidget(self.video_view)

        # --- Overlay navigation widget (floating on top) ---
        self.overlay_widget = QWidget(self)
        self.overlay_widget.setStyleSheet("background: rgba(0,0,0,150); border-radius: 8px;")
        self.overlay_widget.setFixedHeight(60)

        overlay_layout = QHBoxLayout(self.overlay_widget)
        overlay_layout.setContentsMargins(10, 5, 10, 5)
        overlay_layout.setSpacing(10)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(50, 40)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.4); }
        """)
        self.prev_btn.clicked.connect(self.prev_item)

        self.counter_label = QLabel("1/1")
        self.counter_label.setStyleSheet(f"color: {config.VIEWER_COUNTER_COLOR}; font-size: 14px;")
        self.counter_label.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(50, 40)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 18px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.4); }
        """)
        self.next_btn.clicked.connect(self.next_item)

        overlay_layout.addWidget(self.prev_btn)
        overlay_layout.addStretch()
        overlay_layout.addWidget(self.counter_label)
        overlay_layout.addStretch()
        overlay_layout.addWidget(self.next_btn)

        # Image display manager (unchanged – used only for on‑demand image fetching)
        self.image_display = ImageDisplayManager(self.main_window, self.image_viewer)

        self._load_current()
        QTimer.singleShot(10, self.center_dialog)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.stacked.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, 'overlay_widget'):
            ow = self.overlay_widget
            ow.setGeometry(0, self.height() - ow.height() - 10, self.width(), ow.height())
            ow.raise_()

    def center_dialog(self):
        parent_center = self.main_window.geometry().center()
        self.move(parent_center - self.rect().center())

    def _load_current(self):
        if self.current_index < 0 or self.current_index >= len(self.media_items):
            return

        item = self.media_items[self.current_index]
        if item["type"] == "image":
            self.stacked.setCurrentIndex(0)   # image page
            pixmap = item.get("pixmap")
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(self.image_viewer.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_viewer.setPixmap(scaled)
            else:
                url = item.get("url")
                if url:
                    self.image_viewer.setText("🖼️")
                    self.image_display.fetch_and_display_images(
                        0, [url],
                        on_image_ready=lambda u, pix, mov, idx: self._on_image_fetched(pix)
                    )
                else:
                    self.image_viewer.setText("🖼️")
        else:  # video
            self.stacked.setCurrentIndex(1)   # video page
            url = item.get("url", "")
            if url:
                # Build the same HTML as TrailerPlayerManager (looping, muted, autoplay)
                html = self._build_video_html(url)
                self.video_view.setHtml(html, QUrl("about:blank"))
            else:
                self.video_view.setHtml("<body style='background:#111;color:#ccc;text-align:center;padding-top:40%;'>No video source</body>")

        self.update_buttons()

    def _build_video_html(self, src: str) -> str:
        """Generate HTML with a looping video, just like TrailerPlayerManager."""
        # If it's not a remote URL, treat as local file
        if not src.startswith(("http://", "https://")):
            src = QUrl.fromLocalFile(src).toString()
        safe_src = src.replace("'", "\\'")
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    background-color: #111;
                    overflow: hidden;
                }}
                video {{
                    display: block;
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    background-color: #111;
                }}
            </style>
        </head>
        <body>
            <video id="player" src="{safe_src}" autoplay loop muted playsinline></video>
            <script>
                var video = document.getElementById('player');
                video.onerror = function() {{
                    var msg = document.createElement('div');
                    msg.style.cssText = 'position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); color:#ccc; font-size:16px; text-align:center;';
                    msg.innerText = '⚠ Video failed to load. Click the ▶ button to open in your browser.';
                    document.body.appendChild(msg);
                }};
            </script>
        </body>
        </html>
        """

    def _on_image_fetched(self, pixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(self.image_viewer.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_viewer.setPixmap(scaled)
        else:
            self.image_viewer.setText("🖼️")

    def prev_item(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current()

    def next_item(self):
        if self.current_index < len(self.media_items) - 1:
            self.current_index += 1
            self._load_current()

    def update_buttons(self):
        count = len(self.media_items)
        self.prev_btn.setEnabled(count > 1 and self.current_index > 0)
        self.next_btn.setEnabled(count > 1 and self.current_index < count - 1)
        self.counter_label.setText(f"{self.current_index+1}/{count}" if count else "0/0")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Left:
            self.prev_item()
        elif event.key() == Qt.Key_Right:
            self.next_item()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # No media player to stop – the web view will be destroyed
        super().closeEvent(event)