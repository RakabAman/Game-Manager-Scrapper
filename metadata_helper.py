# metadata_helper.py
import re
from pathlib import Path
from PyQt5.QtGui import QStandardItem
from PyQt5.QtCore import Qt, QTimer

def _clean_igdb_id(value):
    """Extract numeric ID from IGDB URL if possible; otherwise return empty string."""
    if not value:
        return ""
    s = str(value).strip()
    # If it's a URL like https://www.igdb.com/games/12345 or /games/12345
    # Look for a numeric sequence after /games/ or /game/
    match = re.search(r'/games?/(\d+)', s, re.IGNORECASE)
    if match:
        return match.group(1)
    # If the whole string is a number, return it
    if s.isdigit():
        return s
    # Otherwise, we cannot extract a numeric ID – return empty
    # The link will be stored in igdb_link, so we don't lose it.
    return ""

def merge_and_apply_metadata(games, model, row_index, metadata, window_ref=None, preserve_title=False):
    """
    Merge scraped metadata into game dict and update model.
    If preserve_title=True, the game's 'title' field and the title column are not overwritten.
    """
    if not metadata or row_index < 0 or row_index >= len(games):
        return

    game = games[row_index]
    title = game.get("title", "Unknown")
    print(f"\n[MERGE] Merging metadata for row {row_index}: {title}")

    # Preserve existing cache paths and save locations (unchanged)
    existing_image_cache_paths = game.get("image_cache_paths", [])
    existing_microtrailer_cache_path = game.get("microtrailer_cache_path", "")
    existing_save_locations = game.get("savegame_locations", []) or game.get("savegame_location", [])

    updated_fields = []

    # Extract app_id from various sources (unchanged)
    app_id_sources = [
        metadata.get("app_id"),
        metadata.get("steam_app_id"),
        metadata.get("steam_id"),
    ]
    app_id = None
    for source in app_id_sources:
        if source:
            if isinstance(source, str) and source.strip():
                app_id = str(source).strip()
                break
            elif isinstance(source, (int, float)):
                app_id = str(int(source))
                break
    if app_id and app_id not in ("N/A", "0"):
        old = game.get("app_id", "")
        if old != app_id:
            game["app_id"] = app_id
            updated_fields.append("app_id")

    # Field mapping loop – skip 'title' if preserve_title is True
    for key, value in metadata.items():
        if key == "__candidates__":
            continue
        if key in ("app_id", "steam_app_id", "steam_id"):
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        # Skip updating title when preserve_title is True
        if preserve_title and key == "title":
            continue

        # Special handling for igdb_id – clean URL to numeric ID
        if key == "igdb_id":
            cleaned = _clean_igdb_id(value)
            if game.get("igdb_id") != cleaned:
                game["igdb_id"] = cleaned
                updated_fields.append("igdb_id")
            continue

        if key in ("screenshots", "microtrailers", "trailers", "shortcut_links", "videos"):
            if isinstance(value, str):
                if "," in value:
                    value = [item.strip() for item in value.split(",") if item.strip()]
                else:
                    value = [value.strip()] if value.strip() else []
            if not isinstance(value, list):
                value = [value]
            old_value = game.get(key, [])
            if old_value != value:
                game[key] = value
                updated_fields.append(key)
            continue

        old_value = game.get(key)
        if old_value != value:
            game[key] = value
            updated_fields.append(key)

    # Extract first microtrailer as trailer_webm (unchanged)
    microtrailers = metadata.get("microtrailers")
    if microtrailers and isinstance(microtrailers, list) and len(microtrailers) > 0:
        first = microtrailers[0]
        if first and not game.get("trailer_webm"):
            game["trailer_webm"] = first
            updated_fields.append("trailer_webm")

    # Extract app_id from steam_link if missing (unchanged)
    if not game.get("app_id") and metadata.get("steam_link"):
        match = re.search(r"/app/(\d+)", metadata["steam_link"])
        if match:
            game["app_id"] = match.group(1)
            if "app_id" not in updated_fields:
                updated_fields.append("app_id")

    # Restore preserved paths (unchanged)
    if existing_image_cache_paths:
        game["image_cache_paths"] = existing_image_cache_paths
    if existing_microtrailer_cache_path:
        game["microtrailer_cache_path"] = existing_microtrailer_cache_path
    if existing_save_locations:
        game["savegame_locations"] = existing_save_locations

    # Update model if needed
    if updated_fields and model:
        # Column indices (must match GameManager constants)
        COL_TITLE = 0
        COL_STEAMID = 3
        COL_DEV = 10
        COL_PUB = 11
        COL_GENRES = 6
        COL_RELEASE = 8
        COL_DESCRIPTION = 21
        COL_COVER_URL = 23
        COL_TRAILER = 17
        COL_STEAM_LINK = 20
        COL_STEAMDB = 18
        COL_PCWIKI = 19
        COL_IGDB_ID = 15
        COL_THEMES = 9
        COL_PERSPECTIVE = 13
        COL_MICROTRAILERS = 24
        COL_USER_RATING = 30
        COL_IMAGE_CACHE_PATHS = 27
        COL_MICROTRAILER_CACHE_PATH = 26
        COL_SAVE_LOCATION = 28
        COL_IGDB_COVER_ART = 31

        column_map = {
            "title": COL_TITLE,
            "app_id": COL_STEAMID,
            "developer": COL_DEV,
            "publisher": COL_PUB,
            "genres": COL_GENRES,
            "release_date": COL_RELEASE,
            "description": COL_DESCRIPTION,
            "cover_url": COL_COVER_URL,
            "trailer_webm": COL_TRAILER,
            "steam_link": COL_STEAM_LINK,
            "steamdb_link": COL_STEAMDB,
            "pcgw_link": COL_PCWIKI,
            "igdb_id": COL_IGDB_ID,
            "themes": COL_THEMES,
            "player_perspective": COL_PERSPECTIVE,
            "microtrailers": COL_MICROTRAILERS,
            "user_rating": COL_USER_RATING,
            "image_cache_paths": COL_IMAGE_CACHE_PATHS,
            "microtrailer_cache_path": COL_MICROTRAILER_CACHE_PATH,
            "savegame_locations": COL_SAVE_LOCATION,
            "igdb_cover_art": COL_IGDB_COVER_ART,
        }
        for field in updated_fields:
            if field in column_map:
                col = column_map[field]
                # Skip updating title column if preserve_title is True
                if preserve_title and field == "title":
                    continue
                value = game.get(field, "")
                if field in ("microtrailers", "image_cache_paths", "savegame_locations"):
                    if isinstance(value, list):
                        display = ", ".join(str(x) for x in value if x)
                    else:
                        display = str(value)
                else:
                    display = str(value)
                item = model.item(row_index, col)
                if item:
                    item.setText(display)
                else:
                    model.setItem(row_index, col, QStandardItem(display))

        # Ensure cache columns are updated (unchanged)
        if existing_image_cache_paths:
            col = COL_IMAGE_CACHE_PATHS
            display = ", ".join(str(x) for x in existing_image_cache_paths if x)
            item = model.item(row_index, col)
            if item:
                item.setText(display)
            else:
                model.setItem(row_index, col, QStandardItem(display))
        if existing_microtrailer_cache_path:
            col = COL_MICROTRAILER_CACHE_PATH
            item = model.item(row_index, col)
            if item:
                item.setText(existing_microtrailer_cache_path)
            else:
                model.setItem(row_index, col, QStandardItem(existing_microtrailer_cache_path))

        # Store game data in title cell (unchanged)
        title_item = model.item(row_index, COL_TITLE)
        if title_item:
            title_item.setData(game, Qt.UserRole)

    # If window_ref exists, update UI (unchanged)
    if window_ref:
        selected_rows = window_ref._selected_source_rows()
        if row_index in selected_rows:
            QTimer.singleShot(100, lambda: window_ref.show_details_for_source_row(row_index))
        window_ref.update_counters()