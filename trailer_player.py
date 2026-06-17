# trailer_player.py
import requests
from PyQt5.QtCore import QUrl, QBuffer, QByteArray, QTimer
from PyQt5.QtGui import QMovie
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from config import SCRIPT_DIR, VIDEO_LOOP_ENABLED

class TrailerPlayerManager:
    def __init__(self, parent_window):
        self.parent = parent_window
        self.media_player = parent_window.media_player
        self.video_widget = parent_window.video_widget
        self.trailer_gif_label = parent_window.trailer_gif_label
        self._current_trailer_url = ""

    def play_trailer_media(self, url: str):
        self._current_trailer_url = url
        self.video_widget.set_url(url)
        self.trailer_gif_label.set_url(url, "")
        # Check cached microtrailer first
        try:
            rel_path = self.parent.games[self.parent._current_row].get("microtrailer_cache_path")
            if rel_path:
                abs_path = SCRIPT_DIR / rel_path
                if abs_path.exists():
                    media = QMediaContent(QUrl.fromLocalFile(str(abs_path)))
                    self.media_player.setMedia(media)
                    self.media_player.play()
                    return
        except:
            pass

        self.media_player.stop()
        if hasattr(self.trailer_gif_label, "movie") and self.trailer_gif_label.movie():
            self.trailer_gif_label.movie().stop()
            self.trailer_gif_label.clear()

        if not url:
            return

        lower = url.lower()
        if lower.endswith(".gif"):
            try:
                r = requests.get(url, timeout=8, headers={"User-Agent": "GameScraper/1.0"})
                if r.status_code == 200 and r.content:
                    movie = QMovie()
                    movie.setCacheMode(QMovie.CacheAll)
                    movie.setDevice(QBuffer(QByteArray(r.content)))
                    if movie.isValid():
                        self.trailer_gif_label.setMovie(movie)
                        movie.start()
                        self.video_widget.hide()
                        self.trailer_gif_label.show()
                    else:
                        print("[DEBUG] GIF invalid")
            except Exception as e:
                print(f"[DEBUG] GIF error: {e}")
                self.parent.status.setText("Failed to load GIF trailer.")
        else:
            self.trailer_gif_label.hide()
            self.video_widget.show()
            qurl = QUrl(url)
            media = QMediaContent(qurl)
            self.media_player.setMedia(media)
            self.media_player.setMuted(True)
            self.media_player.play()
            # Check if playback failed after 2 seconds
            def check():
                if self.media_player.state() != 1:
                    self.parent.trailer_container.hide()
            QTimer.singleShot(2000, check)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and VIDEO_LOOP_ENABLED:
            self.media_player.setPosition(0)
            self.media_player.play()