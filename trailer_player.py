#!/usr/bin/env python3
# trailer_player.py – Reliable video playback using QWebEngineView (HTML5 video)

import config
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QVBoxLayout, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtCore import Qt


class TrailerPlayerManager:
    def __init__(self, parent_window):
        self.parent = parent_window

        # --- Prepare the container ---
        container = parent_window.trailer_container
        if container.layout():
            old = container.layout()
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            del old

        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # --- Web view ---
        self.web_view = QWebEngineView()
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, False)

        self.web_view.setStyleSheet("background-color: #111; border: none; margin: 0; padding: 0;")
        self.layout.addWidget(self.web_view)

        self.status_label = getattr(parent_window, 'status', None)

    def _set_status(self, msg):
        if self.status_label:
            self.status_label.setText(msg)
        else:
            print(f"[TRAILER] {msg}")

    def play_trailer_media(self, url: str, game: dict = None):
        final_source = None
        base_url = QUrl("about:blank")  # default

        if game is not None:
            rel_path = game.get("microtrailer_cache_path")
            if rel_path:
                abs_path = config.SCRIPT_DIR / rel_path
                if abs_path.exists():
                    final_source = QUrl.fromLocalFile(str(abs_path)).toString()
                    base_url = QUrl.fromLocalFile(str(abs_path.parent))   # <-- set base to the folder
                    self._set_status("🎬 Playing from cache")
        
        if not final_source and url:
            final_source = url
            self._set_status("🌐 Streaming from network")

        if not final_source:
            self._show_unavailable("No trailer URL available.")
            return

        html = self._build_video_html(final_source)
        self.web_view.setHtml(html, base_url)   # <-- pass base_url

    def _build_video_html(self, src: str) -> str:
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

    def _show_unavailable(self, message: str):
        html = f"""
        <html><head><style>
            body {{ background: #111; color: #ccc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; text-align: center; }}
        </style></head>
        <body><div>{message}</div></body></html>
        """
        self.web_view.setHtml(html)
        self._set_status(message)