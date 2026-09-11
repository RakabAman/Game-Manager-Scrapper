#!/usr/bin/env python3
# trailer_player.py – Plays webm/mp4 videos and GIFs

import os
import requests
from PyQt5.QtCore import QUrl, QBuffer, QByteArray, QTimer
from PyQt5.QtGui import QMovie
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import config
from cache_utils import _game_cache_dir_for_game


class TrailerPlayerManager:
    def __init__(self, parent_widget=None, video_widget=None, gif_label=None,
                 media_player=None, status_bar=None):
        """
        parent_widget: the parent widget (usually the details panel)
        video_widget: QVideoWidget instance
        gif_label: QLabel for GIFs
        media_player: QMediaPlayer instance (optional; if None, we create one)
        status_bar: QStatusBar or None (for status updates)
        """
        self.parent = parent_widget
        self.video_widget = video_widget
        self.gif_label = gif_label
        self.status_bar = status_bar

        if media_player is None:
            self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        else:
            self.media_player = media_player
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setMuted(True)
        # Connect media status for looping
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

        # For loop and fallback timers
        self._fallback_timer = None
        self._current_trailer_url = None
        self._current_game = None

    def _set_status(self, text):
        if self.status_bar:
            self.status_bar.showMessage(text)
        else:
            print(f"[TRAILER] {text}")

    def play_trailer_media(self, url: str, game: dict = None):
        self._current_trailer_url = url
        self._current_game = game
        self.video_widget.set_url(url)
        self.gif_label.set_url(url, "")
        self.gif_label.hide()
        self.video_widget.show()

        # Stop current playback
        self.media_player.stop()
        if hasattr(self.gif_label, "movie") and self.gif_label.movie():
            self.gif_label.movie().stop()
            self.gif_label.clear()

        if self._fallback_timer:
            self._fallback_timer.stop()
            self._fallback_timer = None

        # ---- Try cached microtrailer ----
        if game is not None:
            rel_path = game.get("microtrailer_cache_path")
            if rel_path:
                abs_path = config.SCRIPT_DIR / rel_path
                if abs_path.exists():
                    self._set_status("🎬 Playing microtrailer from cache")
                    try:
                        media = QMediaContent(QUrl.fromLocalFile(str(abs_path)))
                        self.media_player.setMedia(media)
                        self.media_player.play()
                        # Check if playback actually starts
                        if self.media_player.state() == QMediaPlayer.PlayingState:
                            # Start a timer to verify cache playback
                            self._fallback_timer = QTimer()
                            self._fallback_timer.setSingleShot(True)
                            self._fallback_timer.timeout.connect(self._check_cache_playback)
                            self._fallback_timer.start(2000)
                            return
                    except Exception as e:
                        print(f"[TRAILER] Cache playback exception: {e}")
                else:
                    print(f"[TRAILER] Cache file missing: {abs_path}")
                    self._set_status("🎬 Microtrailer not cached – streaming from network")
            else:
                self._set_status("🎬 Microtrailer not cached – streaming from network")
        else:
            self._set_status("🎬 Streaming microtrailer from network")

        # ---- Fallback to network ----
        self._fallback_to_network()

    def _check_cache_playback(self):
        if self.media_player.state() != QMediaPlayer.PlayingState:
            self._set_status("🎬 Cache playback failed – switching to network stream")
            self._fallback_to_network()

    def _fallback_to_network(self):
        if self._fallback_timer:
            self._fallback_timer.stop()
            self._fallback_timer = None

        url = self._current_trailer_url
        if not url:
            self._set_status("No trailer URL available.")
            self.video_widget.hide()
            return

        self._set_status("🌐 Streaming microtrailer from network")
        self.media_player.stop()
        self.gif_label.hide()
        self.video_widget.show()

        lower = url.lower()
        if lower.endswith(('.gif', '.gifv')):
            self._play_gif_from_network(url)
        else:
            self._play_video_from_network(url)

    def _play_video_from_network(self, url):
        media = QMediaContent(QUrl(url))
        self.media_player.setMedia(media)
        self.media_player.setMuted(True)
        self.media_player.play()
        if self.media_player.state() != QMediaPlayer.PlayingState:
            self._set_status("Failed to play trailer.")
            self.video_widget.hide()

    def _play_gif_from_network(self, url):
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "GameScraper/1.0"})
            if r.status_code == 200 and r.content:
                movie = QMovie()
                movie.setCacheMode(QMovie.CacheAll)
                movie.setDevice(QBuffer(QByteArray(r.content)))
                if movie.isValid():
                    movie.setLoops(-1)
                    self.gif_label.setMovie(movie)
                    movie.start()
                    self.video_widget.hide()
                    self.gif_label.show()
                    self._set_status("🎬 Playing GIF microtrailer from network")
                else:
                    self._set_status("Failed to load GIF trailer.")
                    self.video_widget.hide()
            else:
                self._set_status("Failed to download GIF trailer.")
                self.video_widget.hide()
        except Exception as e:
            print(f"[TRAILER] GIF error: {e}")
            self._set_status("Failed to load GIF trailer.")
            self.video_widget.hide()

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and config.VIDEO_LOOP_ENABLED:
            self.media_player.setPosition(0)
            self.media_player.play()