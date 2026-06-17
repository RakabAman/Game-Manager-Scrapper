# cache_utils.py
import hashlib
import requests
from pathlib import Path
from urllib.parse import urlparse
from constants import CACHE_DIR, SCRIPT_DIR, CACHE_MIN_KB, CACHE_MAX_KB

def _to_relative(path: Path) -> str:
    try:
        return str(path.relative_to(SCRIPT_DIR))
    except ValueError:
        return str(path)

def _game_cache_dir_for_game(game: dict) -> Path:
    """
    Determine cache subdirectory for a game using:
      1. app_id (if present)
      2. igdb_id (if present)
      3. SHA256(title) (fallback)
    """
    appid = str(game.get("app_id") or "").strip()
    if appid:
        sub = f"game_{appid}"
    else:
        igdb_id = str(game.get("igdb_id") or "").strip()
        if igdb_id:
            sub = f"game_igdb_{igdb_id}"
        else:
            title = (game.get("title") or "").strip()
            if not title:
                title = "unknown"
            h = hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]
            sub = f"game_{h}"
    cache_dir = CACHE_DIR / sub
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def _save_bytes_to_game_cache(game: dict, url: str, data: bytes) -> Path:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Expected bytes, got {type(data)}")
    min_bytes = CACHE_MIN_KB * 1024
    max_bytes = CACHE_MAX_KB * 1024 if CACHE_MAX_KB else None
    data_len = len(data)
    if data_len < min_bytes:
        raise ValueError(f"Data too small ({data_len} bytes < {min_bytes} bytes)")
    if max_bytes and data_len > max_bytes:
        raise ValueError(f"Data too large ({data_len} bytes > {max_bytes} bytes)")

    cache_dir = _game_cache_dir_for_game(game)
    parsed = urlparse(url)
    path = parsed.path.lower()
    is_microtrailer = any(keyword in url.lower() for keyword in ['microtrailer', 'trailer', 'video'])

    ext = ".bin"
    if '.jpg' in path or '.jpeg' in path:
        ext = '.jpg'
    elif '.png' in path:
        ext = '.png'
    elif '.gif' in path:
        ext = '.gif'
        is_microtrailer = True
    elif '.webp' in path:
        ext = '.webp'
    elif '.webm' in path:
        ext = '.webm'
        is_microtrailer = True
    elif '.mp4' in path:
        ext = '.mp4'
        is_microtrailer = True

    if ext == ".bin":
        if data[:4] == b'\x89PNG':
            ext = '.png'
        elif data[:3] == b'\xff\xd8\xff':
            ext = '.jpg'
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            ext = '.gif'
            is_microtrailer = True
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            ext = '.webp'

        # Normalize URL: remove query parameters and force https
    norm_url = url.split('?')[0]
    if norm_url.startswith('http://'):
        norm_url = 'https://' + norm_url[7:]
    url_hash = hashlib.sha256(norm_url.encode("utf-8")).hexdigest()
    filename = f"{url_hash}{ext}"
    target_path = cache_dir / filename
    if target_path.exists():
        try:
            return target_path.relative_to(SCRIPT_DIR)
        except ValueError:
            return target_path

    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    try:
        temp_path.write_bytes(data)
        temp_path.replace(target_path)
        absolute_path = target_path.resolve()
        file_type = "microtrailer" if is_microtrailer else "screenshot"
        print(f"[CACHE] Saved {file_type}: {url} -> {absolute_path} ({data_len} bytes, {ext})")
        try:
            rel_path = target_path.relative_to(SCRIPT_DIR)
            print(f"[CACHE] Relative path: {rel_path}")
            return rel_path
        except ValueError:
            return target_path
    except Exception as e:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        raise e

def scan_cache_directory_for_game(game: dict) -> dict:
    """
    Scan the game's cache directory and return existing screenshot and microtrailer paths.
    """
    result = {"screenshot_paths": [], "microtrailer_path": ""}
    try:
        cache_dir = _game_cache_dir_for_game(game)
        if not cache_dir.exists():
            return result
        all_files = list(cache_dir.iterdir())

        # Helper to normalize URL (remove query params, force https)
        def norm_url(url: str) -> str:
            if '?' in url:
                url = url.split('?')[0]
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            return url

        # Build list of expected URLs (cover + screenshots)
        screenshot_urls = []
        cover_url = game.get("cover_url")
        if cover_url:
            screenshot_urls.append(norm_url(cover_url))
        screenshots = game.get("screenshots") or []
        if isinstance(screenshots, list):
            screenshot_urls.extend(norm_url(u) for u in screenshots if u)
        elif isinstance(screenshots, str):
            parts = [p.strip() for p in screenshots.split(",") if p.strip()]
            screenshot_urls.extend(norm_url(p) for p in parts)

        # Build list of expected microtrailer URLs (normalized)
        microtrailer_urls = []
        if game.get("trailer_webm"):
            microtrailer_urls.append(norm_url(game["trailer_webm"]))
        microtrailers = game.get("microtrailers") or []
        if isinstance(microtrailers, list):
            microtrailer_urls.extend(norm_url(u) for u in microtrailers if u)
        elif isinstance(microtrailers, str):
            parts = [p.strip() for p in microtrailers.split(",") if p.strip()]
            microtrailer_urls.extend(norm_url(p) for p in parts)

        for file_path in all_files:
            if not file_path.is_file() or file_path.suffix == ".tmp":
                continue
            try:
                if file_path.stat().st_size < CACHE_MIN_KB * 1024:
                    continue
            except Exception:
                continue

            file_stem = file_path.stem
            # Match screenshot URLs
            for url in screenshot_urls:
                if not url:
                    continue
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                if url_hash in file_stem:
                    rel_path = _to_relative(file_path)
                    if rel_path not in result["screenshot_paths"]:
                        result["screenshot_paths"].append(rel_path)
                    break
            # Match microtrailer URLs
            for url in microtrailer_urls:
                if not url:
                    continue
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                if url_hash in file_stem and file_path.suffix.lower() in ('.gif', '.webm', '.mp4'):
                    rel_path = _to_relative(file_path)
                    if not result["microtrailer_path"]:
                        result["microtrailer_path"] = rel_path
                    break
    except Exception as e:
        print(f"[SCAN CACHE] Error: {e}")
    return result