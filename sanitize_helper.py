# sanitize_helper.py
from utils_sanitize import sanitize_original_title
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItem

def sanitize_selected_rows(games, model, rows):
    """
    Sanitize the original_title field for selected rows and update game dict and model.
    Returns the number of rows updated.
    """
    updated_count = 0
    for row in rows:
        if row < 0 or row >= len(games):
            continue
        game = games[row]
        original_title = game.get("original_title") or ""
        if not original_title:
            continue
        
        # Call sanitize function (no repack_file argument needed)
        san = sanitize_original_title(original_title)
        
        base_title = san.get("base_title", "")
        version = san.get("version", "")
        repack = san.get("repack", "")
        notes = san.get("notes", "")
        modes = san.get("modes", [])
        
        # Update game dictionary with extracted fields
        game["original_title_base"] = base_title
        game["original_title_version"] = version
        game["original_notes"] = notes
        
        if not game.get("scene_repack") and repack:
            game["scene_repack"] = repack
        
        if not game.get("game_modes") and modes:
            game["game_modes"] = ", ".join(modes)
        
        if not game.get("patch_version") and version:
            game["patch_version"] = version
        
        current_title = game.get("title", "")
        if (not current_title or current_title == original_title) and base_title:
            game["title"] = base_title
        
        # Optionally store cleaned version of original_title
        if san.get('cleaned_title'):
            game["original_title"] = san['cleaned_title']
        elif base_title and version:
            clean_version = f"{base_title} {version}".strip()
            if clean_version and clean_version != original_title:
                game["original_title"] = clean_version
        
        updated_count += 1
        _update_model_row(games, model, row)
    
    return updated_count

def _update_model_row(games, model, row_index):
    """
    Update the model for a single row after sanitization.
    """
    if row_index < 0 or row_index >= len(games):
        return
    game = games[row_index]
    
    # Column indices (must match GameManager constants)
    COL_TITLE = 0
    COL_SCENE = 11
    COL_GAME_MODES = 6
    COL_VERSION = 1
    COL_ORIGINAL = 13
    
    if model:
        # Update title cell
        item = model.item(row_index, COL_TITLE)
        if item:
            item.setText(game.get("title", ""))
            item.setData(game, Qt.UserRole)
        
        # Update scene/repack
        item = model.item(row_index, COL_SCENE)
        if item:
            item.setText(game.get("scene_repack", ""))
        
        # Update game modes
        item = model.item(row_index, COL_GAME_MODES)
        if item:
            item.setText(game.get("game_modes", ""))
        
        # Update version
        item = model.item(row_index, COL_VERSION)
        if item:
            item.setText(game.get("patch_version", ""))
        
        # Update original title
        item = model.item(row_index, COL_ORIGINAL)
        if item:
            item.setText(game.get("original_title", ""))