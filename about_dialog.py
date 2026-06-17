# about_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QWidget, QScrollArea,
    QFrame, QHBoxLayout, QPushButton,
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import Qt, QUrl
from config import APP_STYLESHEET

def show_about_dialog(parent=None):
    """Show the about dialog with gaming resource tabs."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("About Game Manager & Gaming Resources")
    dialog.setMinimumSize(800, 500)
    dialog.setStyleSheet(APP_STYLESHEET)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(10)

    # Header
    header_label = QLabel("<h2>Game Manager v2.18</h2>")
    header_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(header_label)

    # Tab widget
    tab_widget = QTabWidget()

    # ------------------------------
    # Tab 1: About
    # ------------------------------
    about_tab = QWidget()
    about_layout = QVBoxLayout(about_tab)
    about_layout.setContentsMargins(20, 20, 20, 20)
    about_layout.setSpacing(15)

    about_text = """
    <h3>By Rakab Aman</h3>
    <p>A comprehensive game database management tool with metadata scraping capabilities.</p>

    <p><b>Main Features:</b></p>
    <ul>
        <li>Import/Export from CSV, JSON, SQLite</li>
        <li>IGDB and Steam metadata scraping</li>
        <li>Image and video caching with 16:9 aspect ratio</li>
        <li>Batch operations on selected games</li>
        <li>PDF/HTML export functionality</li>
        <li>Recaching system for automatic redownloading</li>
        <li>Clickable assets (URLs)</li>
        <li>Game sanitization and duplicate detection</li>
        <li>User rating system</li>
    </ul>

    <p><b>Architecture:</b></p>
    <ul>
        <li>Main window with table view and details panel</li>
        <li>Worker threads for background operations</li>
        <li>Caching system for images and metadata</li>
        <li>Dialog-based editing and matching</li>
    </ul>

    <p>Built with PyQt5 and Python 3.8+</p>
    """

    about_label = QLabel(about_text)
    about_label.setWordWrap(True)
    about_label.setOpenExternalLinks(True)
    about_layout.addWidget(about_label)
    about_layout.addStretch()

    tab_widget.addTab(about_tab, "📋 About")

    # ------------------------------
    # Tab 2: Download Games
    # ------------------------------
    download_tab = QWidget()
    download_layout = QVBoxLayout(download_tab)
    download_layout.setContentsMargins(10, 10, 10, 10)

    download_scroll = QScrollArea()
    download_scroll.setWidgetResizable(True)
    download_scroll.setFrameShape(QFrame.NoFrame)

    download_content = QWidget()
    download_content_layout = QVBoxLayout(download_content)
    download_content_layout.setContentsMargins(5, 5, 5, 5)
    download_content_layout.setSpacing(8)

    download_links = [
        ("CS.RIN.RU", "https://cs.rin.ru/forum/",
         "Download / Torrent / Signup / PW: cs.rin.ru / csrin.org / .onion"),
        ("CS.RIN Tools", "https://cs.rin.ru/forum/viewtopic.php?f=29&t=124692",
         "Search Guide (Important) / Status / Enhancements / Steam Buttons"),
        ("SteamRIP", "https://steamrip.com/",
         "Download / Pre-Installed / Subreddit / Discord"),
        ("AnkerGames", "https://anakgames.com/",
         "Download / Pre-Installed / Subreddit / Discord"),
        ("GOG Games", "https://gog-games.com/",
         "Download / Torrent / GOG Games Only / .onion"),
        ("UnionCrax", "https://unioncrax.biz/",
         "Download / Pre-Installed / Status / Discord"),
        ("AstralGames", "https://astralgames.net/",
         "Download / Achievements / Pre-Installed / Discord"),
        ("Online Fix", "https://online-fix.me/",
         "Download / Torrent / Multiplayer / Signup / PW: online-fix.me / Use Translator / Telegram / Discord"),
        ("SteamUnderground", "https://steamunderground.org/",
         "Download / Pre-Installed / Discord"),
        ("Ova Games", "https://www.ovagames.com/",
         "Download / PW: www.ovagames.com / Redirect Bypass Required"),
        ("Torrminatorr", "https://forum.torrminatorr.com/",
         "Download / Forum / Sign-Up Required"),
        ("Reloaded Steam", "https://reloaded.steam.com/",
         "Download / Pre-Installed / Discord"),
        ("SteamGG", "https://steamgg.com/",
         "Download / Pre-Installed / Subreddit / Discord"),
        ("World of PC Games", "https://worldofpcgames.net/",
         "Download / Pre-Installed / Use Adblock / Site Info / Subreddit"),
        ("Games4U", "https://games4u.com/",
         "Download / Use Adblock / Sources on DDL Pages"),
        ("CG Games", "https://www.cg-games.net/",
         "Download"),
        ("GamePCFull", "https://gamepcfull.com/",
         "Download"),
        ("IRC Games", "https://wiki.fmhy.net/pages/7d088d/",
         "Download Games via IRC"),
        ("FreeToGame", "https://www.freetogame.com/",
         "F2P Games / Trackers"),
        ("TendingNow", "https://tendingnow.com/",
         "F2P Games / Trackers"),
        ("Acid Play", "https://acid-play.com/",
         "F2P Games / Trackers"),
    ]

    for name, url, description in download_links:
        link_text = f'<a href="{url}" style="text-decoration: none; color: #3498db; font-weight: 600;">{name}</a> - {description}'
        link_label = QLabel(link_text)
        link_label.setOpenExternalLinks(True)
        link_label.setTextFormat(Qt.RichText)
        link_label.setWordWrap(True)
        link_label.setStyleSheet("margin: 2px 0; padding: 3px 0; border-bottom: 1px dotted #eee;")
        download_content_layout.addWidget(link_label)

    download_content_layout.addStretch()
    download_scroll.setWidget(download_content)
    download_layout.addWidget(download_scroll)

    tab_widget.addTab(download_tab, "⬇️ Download Games")

    # ------------------------------
    # Tab 3: Game Repacks
    # ------------------------------
    repacks_tab = QWidget()
    repacks_layout = QVBoxLayout(repacks_tab)
    repacks_layout.setContentsMargins(10, 10, 10, 10)

    repacks_scroll = QScrollArea()
    repacks_scroll.setWidgetResizable(True)
    repacks_scroll.setFrameShape(QFrame.NoFrame)

    repacks_content = QWidget()
    repacks_content_layout = QVBoxLayout(repacks_content)
    repacks_content_layout.setContentsMargins(5, 5, 5, 5)
    repacks_content_layout.setSpacing(8)

    repack_links = [
        ("FitGirl Repacks", "https://fitgirl-repacks.site/",
         "Download / Torrent / ROM Repacks / Unofficial Launcher"),
        ("KaOsKrew", "http://kaoskrew.org/",
         "Download / Torrent / Discord"),
        ("ARMGDDN Browser", "https://armgddn.com/",
         "Download / Telegram / Discord"),
        ("Gnarly Repacks", "https://gnarly-repacks.site/",
         "Download / PW: gnarly"),
        ("DODI Repacks", "https://dodi-repacks.site/",
         "Torrent / Redirect Bypass / Site Warning / Discord"),
        ("Elamigos", "https://www.elamigos-games.com/",
         "Download"),
        ("FreeGOGPCGames", "https://freegogpcgames.com/",
         "GOG Games Torrent Uploads / Hash Note"),
        ("Game-Repack", "https://game-repack.site/",
         "Various game repacks"),
        ("Xatab Repacks", "https://xatab-repack.site/",
         "Russian repacker with English games"),
        ("TinyRepacks", "https://www.tiny-repacks.win/",
         "Extremely small repacks"),
        ("CPG Repacks", "https://cpgrepacks.site/",
         "Canadian repacker"),
        ("RG Mechanics", "https://rg-mechanics.org/",
         "Russian repacker"),
        ("Repack Games", "https://repack-games.com/",
         "Multi-language repacks"),
    ]

    for name, url, description in repack_links:
        link_text = f'<a href="{url}" style="text-decoration: none; color: #e74c3c; font-weight: 600;">{name}</a> - {description}'
        link_label = QLabel(link_text)
        link_label.setOpenExternalLinks(True)
        link_label.setTextFormat(Qt.RichText)
        link_label.setWordWrap(True)
        link_label.setStyleSheet("margin: 2px 0; padding: 3px 0; border-bottom: 1px dotted #eee;")
        repacks_content_layout.addWidget(link_label)

    repacks_content_layout.addStretch()
    repacks_scroll.setWidget(repacks_content)
    repacks_layout.addWidget(repacks_scroll)

    tab_widget.addTab(repacks_tab, "🎮 Game Repacks")

    # ------------------------------
    # Tab 4: Discord Communities
    # ------------------------------
    discord_tab = QWidget()
    discord_layout = QVBoxLayout(discord_tab)
    discord_layout.setContentsMargins(10, 10, 10, 10)

    discord_scroll = QScrollArea()
    discord_scroll.setWidgetResizable(True)
    discord_scroll.setFrameShape(QFrame.NoFrame)

    discord_content = QWidget()
    discord_content_layout = QVBoxLayout(discord_content)
    discord_content_layout.setContentsMargins(5, 5, 5, 5)
    discord_content_layout.setSpacing(8)

    discord_links = [
        ("Gamers Unlimited", "https://discord.gg/MNqtzwq8W",
         "Gaming community Discord"),
        ("Pubs Lounge", "https://discord.gg/pubslounge",
         "General gaming and community Discord"),
        ("SteamAutoCrack", "https://discord.gg/Y4xcZ4fD",
         "Gaming and emulation Discord"),
        ("Nucleus Co-op", "https://discord.gg/distro-nucleusco-op-142649962839277568",
         "Co-op gaming and distribution Discord"),
        ("Piracy Lords", "https://discord.gg/piracylords",
         "Gaming piracy community Discord"),
        ("Anti Denuvo Sanctuary", "https://discord.com/invite/anti-denuvo-sanctuary",
         "Denuvo cracking and anti-DRM community"),
    ]

    for name, url, description in discord_links:
        link_text = f'<a href="{url}" style="text-decoration: none; color: #7289da; font-weight: 600;">{name}</a> - {description}'
        link_label = QLabel(link_text)
        link_label.setOpenExternalLinks(True)
        link_label.setTextFormat(Qt.RichText)
        link_label.setWordWrap(True)
        link_label.setStyleSheet("margin: 2px 0; padding: 3px 0; border-bottom: 1px dotted #eee;")
        discord_content_layout.addWidget(link_label)

    discord_content_layout.addStretch()
    discord_scroll.setWidget(discord_content)
    discord_layout.addWidget(discord_scroll)

    tab_widget.addTab(discord_tab, "💬 Discord")

    layout.addWidget(tab_widget, 1)

    # Button row
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    wiki_button = QPushButton("🌐 Open Complete FMHY Gaming Wiki")
    wiki_button.clicked.connect(lambda: QDesktopServices.openUrl(
        QUrl("https://github.com/fmhy/FMHY/wiki/%F0%9F%8E%AE-Gaming---Emulation")
    ))
    wiki_button.setStyleSheet("""
        QPushButton {
            background-color: #3498db;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
    """)

    close_button = QPushButton("Close")
    close_button.clicked.connect(dialog.accept)

    button_layout.addWidget(wiki_button)
    button_layout.addWidget(close_button)

    layout.addLayout(button_layout)

    dialog.exec_()