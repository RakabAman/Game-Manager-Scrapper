# Game Manager

A comprehensive, open‑source game library manager with metadata scraping, media caching, and advanced export capabilities.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green?logo=qt)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Export System](#export-system)
- [Scraping & Metadata](#scraping--metadata)
- [Recent Changes](#recent-changes)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Game Manager is a powerful desktop application designed to help you organise your game collection. It scrapes rich metadata from **IGDB** and **Steam**, downloads cover art, screenshots, and micro‑trailers, and provides an intuitive interface with filtering, sorting, and export capabilities.

Originally built as a personal project, it has evolved into a full‑featured manager with support for:

- **Dynamic export** (PDF/HTML) with custom columns, hyperlinks, and row highlighting.
- **Batch scraping** with automatic metadata merging and manual matching.
- **Asset caching** (images, videos) with automatic downloading on demand.
- **Drive scanning** to import games from folders.
- **Auto‑save**, backup creation, and extensive customisation.

The entire codebase is written in **Python 3.8+** using **PyQt5** for the GUI, and all modules are contained in a single folder for easy deployment.

---

## Key Features

### 📋 Game Library Management
- **Add games** by pasting titles, importing CSV/Excel/TXT files, or scanning a drive.
- **Edit** single or multiple games with an advanced multi‑edit dialog.
- **Mark** games as played or favourite – rows are coloured accordingly.
- **Smart duplicate detection** (case‑insensitive, with Unicode normalisation).
- **Live search** and filtering by genre, drive, or any column.

### 🗲 Metadata Scraping
- Automatically fetches metadata from **IGDB** and **Steam** (title, description, genres, release date, developer, publisher, player perspective, themes, user rating, etc.).
- Handles zero‑candidate results by opening a **manual match dialog** – you can search, enter IDs, or skip.
- **Merge strategy**: Steam data is preferred for cover and description; IGDB provides additional fields (IGDB ID, cover art URL, etc.).

### 🖼️ Media & Caching
- Downloads **cover art**, **screenshots** (up to user‑defined limits), and **micro‑trailers** (GIF/WebM/MP4).
- Caches all media in a dedicated folder with URL‑based hashing – minimises redundant downloads.
- **Image viewer** with navigation and click‑to‑open original URL.
- **Micro‑trailer player** with video/GIF support (muted by default, loop option).

### 📤 Advanced Export (PDF & HTML)
- **Dynamic columns** – choose exactly which columns to include (Title, Steam ID, IGDB ID, Genres, Description, External Links, Resources, etc.).
- **Custom headers and column widths** – stored in `config.ini`.
- **Hyperlinked title** – links to the cover image URL.
- **Consolidated external links** column (Steam, IGDB, PCGamingWiki, SteamDB) – choose which to show.
- **Title enrichment** – displays played (✅), favourite (♥), version, and user rating as stars (★).
- **Row highlighting** – follows the same colour scheme as the main table (favourite, played, duplicate).
- **PDF page size** – A3 Landscape, A4 Landscape, or Letter Landscape (configurable).
- **HTML export** – fixed‑width columns, mobile‑responsive with horizontal scroll, and a print button.

### 🗂️ Drive Scanner & Asset Export
- **Scan a drive/folder** – imports all subfolders as games, with automatic duplicate detection (case‑insensitive, dash/quote normalisation).
- **Export assets to game folders** – copies cover art, screenshots, and micro‑trailers into each game’s folder (two modes: match existing folders or create new ones).

### ⚙️ Configuration & Customisation
- All settings are stored in `config.ini` (auto‑created on first run).
- **Dynamic reloading** – most settings apply immediately without restarting.
- **UI colour themes** – customise colours for played, favourite, unplayed, and duplicate rows.
- **Auto‑save** with user‑definable interval and backup creation.
- **Export columns** – fully configurable via the Settings dialog.

### 🛡️ Robustness & Usability
- **Batch operations** – scrape, download, sanitise, recache, or delete multiple games at once.
- **Cancellation** – abort long‑running scrapes or downloads with a single button.
- **Status bar** with progress bar and live statistics (total, played, remaining, cached, duplicates, unscraped).
- **Context menus** for quick actions.
- **Keyboard shortcuts** for common tasks.

---

## Installation

### Prerequisites
- **Python 3.8** or higher
- **pip** (Python package manager)

### Step‑by‑Step

1. **Clone the repository**
   git clone https://github.com/RakabAman/Game-Manager-Scrapper.git
   cd Game-Manager-Scrapper

Install dependencies
pip install PyQt5 requests beautifulsoup4 rapidfuzz reportlab pandas openpyxl lxml
Note: rapidfuzz and reportlab are optional but recommended for better performance and PDF export.

Run the application

python gui_main.py
On first launch, a config.ini file will be created in the same folder with default settings.

Building a Standalone Executable
You can use PyInstaller to create a single executable:

pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico gui_main.py
(Ensure icon.ico is present in the same directory.)

## Usage

### Main Window
- **Top panel**: Search box, genre/drive filters, and stat cards (clickable to filter).
- **Table**: Displays all games. Columns can be reordered, resized, or hidden (right‑click the header).
- **Right panel**: Tabs for **Details** (game info, description, thumbnail, external links) and **Media** (image viewer + micro‑trailer player).
- **Bottom status bar**: Shows progress and totals.

### Menus
- **File**: Add new games, open/save database, export, exit.
- **Edit**: Sanitise titles, recache, scrape selected, edit, multi‑edit, toggle played/favourite, set drive, clear save location, delete.
- **Tools**: Scan drive, export assets, scrape all metadata, download all resources, clear redundant cache, test scrape, settings.
- **View**: Refresh, show/hide columns.
- **Help**: About, documentation.

### Shortcuts
| Action | Shortcut |
|--------|----------|
| Open Database | `Ctrl+O` |
| Save Database | `Ctrl+S` |
| Export | `Ctrl+E` |
| Add New Game | `Ctrl+N` |
| Sanitise Selected | `Ctrl+Shift+S` |
| Edit Selected | `Ctrl+Shift+E` |
| Multi‑Edit | `Ctrl+Shift+M` |
| Toggle Played | `Ctrl+P` |
| Toggle Favourite | `Ctrl+F` |
| Scrape All | `F5` |
| Download Resources | `F6` |
| Recache Selected | `F7` |
| Delete Selected | `Del` |

---

## Configuration

All settings are stored in `config.ini` (created automatically). You can edit it manually or use the **Settings** dialog (`Tools → Settings`).

Key sections:

- **[General]** – Auto‑save, cache limits, default database, thumbnail visibility, console output.
- **[Scraping]** – Auto‑accept score, concurrent scrapes, timeouts.
- **[Download]** – Max images/micro‑trailers to download, concurrent downloads.
- **[UI]** – Colour codes for played, favourite, unplayed, duplicate rows; font sizes.
- **[Cache]** – Override cache directory.
- **[Sanitize]** – Lists of repack names, edition tokens, emulator tokens, mode keywords.
- **[Export]** – Description lines, PDF page size.
- **[ExportColumns]** – Selected columns, custom headers, widths, and which external links to include.
- **[Table]** – Saved column order and widths (restored on startup).
- **[DriveScanner]** – Tokens for drive naming and pattern matching.
- **[AssetExport]** – Custom filenames for artbox and trailer.
- **[API]** – IGDB credentials, Steam API endpoints, image sizes.

> **Important:** IGDB requires a client ID and secret. You can obtain these by registering an application on [IGDB](https://www.igdb.com/api). The app will fall back to hardcoded demo credentials if none are provided (limited functionality).

---

## Export System

The export system is one of the most powerful features. You can generate **PDF** or **HTML** reports of your current filtered/sorted game list.

### Customising Export Columns
1. Go to **Settings → Export** tab.
2. Select which columns to include (Title, Steam ID, IGDB ID, Version, Release Date, Description, Modes, Genres, Themes, Rating, Perspective, Developer, Publisher, Drive, Scene/Repack, Original Title, Resources, External Links, Savegame Locations).
3. For each selected column, you can:
   - Change the header text.
   - Adjust the width (percentage) – the system automatically distributes space.
4. In the **External Links** sub‑section, tick which link types to show (Steam, IGDB, PCGamingWiki, SteamDB).
5. Choose the PDF page size (A3 Landscape, A4 Landscape, or Letter Landscape).
6. Click **Apply** – settings are saved immediately.

### Export Behaviour
- **Title column** becomes a hyperlink to the cover image URL (if available).
- Played (✅) and favourite (♥) symbols are appended to the title.
- Version (from `patch_version` or `original_title_version`) is shown in parentheses.
- User rating is displayed as ★ stars plus the numeric value to one decimal place.
- **Row background** colours match the main table (favourite → pink, played → green, unplayed → light grey).
- **HTML export** is mobile‑friendly with a print button; column widths are fixed.

---

## Scraping & Metadata

The application uses a hybrid scraping strategy:

1. **IGDB** – Primary source for rich metadata (cover art, screenshots, trailers, genres, themes, player perspective, developer, publisher, user rating).
2. **Steam** – Provides additional details (cover, description, screenshots, micro‑trailers).

When you initiate a batch scrape (or scrape individual games), the system will:

- Check if the game already has an `igdb_id` or `app_id`. If missing, it searches IGDB using the game title.
- If multiple candidates are found, it opens the **MatchDialog** for manual selection.
- If no candidates are found, it still opens the MatchDialog, allowing you to enter an ID or skip.
- Once a candidate is selected (or IDs provided), it fetches metadata from both sources and merges them.
- **Manual title** is always preserved – the title you type or accept in the dialog becomes the final game title, regardless of the candidate’s name.

### Special Columns
- `igdb_cover_art` – Stores the raw IGDB cover URL (used for thumbnail generation).
- `microtrailers_extra` – A text field for additional micro‑trailer URLs (manual entry).
- `image_cache_paths` – List of relative paths to cached screenshots.
- `microtrailer_cache_path` – Relative path to the cached micro‑trailer.
- `savegame_location` – User‑defined save folder paths.

---

## Recent Changes (v2.24)

- **Manual Match Dialog Title Fix** – The title you enter is now always preserved; candidate names are stored separately.
- **Configuration Defaults Synchronised** – Default values now match the user’s `config.ini` for a consistent first‑run experience.
- **Details Panel Thumbnail** – Cover art now appears above the title with minimal gap (configurable via CSS).
- **Export Improvements** – Fixed HTML column alignment, dynamic columns, hyperlinked title, version/rating display, row highlighting, and customisable page size.
- **Duplicate Detection** – Improved Unicode normalisation for drive scanning (fixes false duplicates).
- **Zero‑Candidate Scraping** – MatchDialog now opens even when IGDB returns no results.

For a full history, see the project’s commit log or the `AI progress report.txt` included in the source.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature/fix.
3. Ensure your code is commented and follows the existing style.
4. Test thoroughly.
5. Submit a pull request with a clear description of the changes.

For major changes, please open an issue first to discuss what you would like to change.

---

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

---

## Acknowledgements

- [IGDB](https://www.igdb.com/) for providing the game metadata API.
- [Steam](https://store.steampowered.com/) for store metadata.
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework.
- [ReportLab](https://www.reportlab.com/) for PDF generation.
- All open‑source libraries used in this project.

---

**Happy gaming organising!** 🎮
