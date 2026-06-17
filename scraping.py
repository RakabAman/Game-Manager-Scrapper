# scraping.py
"""
Scraper module for GameManager (optimized version)
...
"""

from __future__ import annotations
import os
import re
import time
import json
import sys
import requests
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import config

# Optional: rapidfuzz for better fuzzy scoring
try:
    from rapidfuzz import fuzz
    HAVE_RAPIDFUZZ = True
except ImportError:
    HAVE_RAPIDFUZZ = False

# -------------------------
# Configuration / constants (can be overridden by env vars)
# -------------------------
STEAM_SEARCH_API = os.environ.get("STEAM_SEARCH_API", "https://store.steampowered.com/api/storesearch/?term={q}&cc=US&l=en")
STEAM_STORE_APP_URL = os.environ.get("STEAM_STORE_APP_URL", "https://store.steampowered.com/app/{appid}")
STEAMDB_APP_URL = os.environ.get("STEAMDB_APP_URL", "https://steamdb.info/app/{appid}")
PCGW_SEARCH_TEMPLATE = os.environ.get("PCGW_SEARCH_TEMPLATE", "https://www.pcgamingwiki.com/w/index.php?search={q}")
IGDB_URL_TEMPLATE = os.environ.get("IGDB_URL_TEMPLATE", "https://www.igdb.com/games/{slug}?utm_source=SteamDB")

HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "8.0"))
HTTP_RETRIES = int(os.environ.get("HTTP_RETRIES", "2"))
SLEEP_BETWEEN_REQUESTS = float(os.environ.get("SLEEP_BETWEEN_REQUESTS", "0.15"))

IGDB_IMAGE_BASE_URL = os.environ.get("IGDB_IMAGE_BASE_URL", "https://images.igdb.com/igdb/image/upload")
IGDB_SCREENSHOT_SIZE = os.environ.get("IGDB_SCREENSHOT_SIZE", "t_720p")
IGDB_COVER_SIZE = os.environ.get("IGDB_COVER_SIZE", "t_cover_big")

# -------------------------
# IGDB auth (Twitch) config – with fallbacks
# -------------------------
_FALLBACK_CLIENT_ID = ""
_FALLBACK_CLIENT_SECRET = ""
_FALLBACK_ACCESS_TOKEN = ""

cfg_client_id = getattr(config, 'IGDB_CLIENT_ID', "")
cfg_client_secret = getattr(config, 'IGDB_CLIENT_SECRET', "")
cfg_access_token = getattr(config, 'IGDB_ACCESS_TOKEN', "")

def _use_fallback(value: str, fallback: str) -> str:
    if not value or value == fallback:
        return fallback
    return value

IGDB_CLIENT_ID = _use_fallback(cfg_client_id, _FALLBACK_CLIENT_ID)
IGDB_CLIENT_SECRET = _use_fallback(cfg_client_secret, _FALLBACK_CLIENT_SECRET)
IGDB_ACCESS_TOKEN = _use_fallback(cfg_access_token, _FALLBACK_ACCESS_TOKEN)

_IGDB_TOKEN_CACHE = {"access_token": None, "expires_at": 0}
_MAX_TOKEN_REFRESH = 2

# -------------------------
# Helper functions
# -------------------------
def _http_get(url: str, params: dict = None, timeout: float = HTTP_TIMEOUT) -> Optional[requests.Response]:
    headers = {"User-Agent": "GameScraper/2.0 (compatible; GameManager)"}
    for attempt in range(HTTP_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                time.sleep(1.0)
        except (requests.RequestException, requests.Timeout) as e:
            if attempt == HTTP_RETRIES:
                print(f"[SCRAPE] HTTP GET failed for {url}: {e}")
        time.sleep(0.15 + attempt * 0.1)
    return None


def _slugify(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _score_name(target: str, candidate: str) -> int:
    if not target or not candidate:
        return 0
    if HAVE_RAPIDFUZZ:
        try:
            return int(fuzz.token_set_ratio(target, candidate))
        except Exception:
            pass
    a = re.sub(r'\s+', ' ', target.lower()).strip()
    b = re.sub(r'\s+', ' ', candidate.lower()).strip()
    if not a or not b:
        return 0
    common = sum(1 for ch in a if ch in b)
    return int(100 * common / max(1, max(len(a), len(b))))


def _normalize_image_url(url: str, size: Optional[str] = None) -> str:
    if not url:
        return ""
    if url.startswith(('http://', 'https://', '//')):
        if size and "images.igdb.com" in url:
            url = re.sub(r'/t_[^/]+/', f'/{size}/', url)
        return url
    if url.startswith('/'):
        return 'https:' + url
    if len(url) < 20 and '.' not in url:
        return f"{IGDB_IMAGE_BASE_URL}/{size or IGDB_SCREENSHOT_SIZE}/{url}.jpg"
    return f"https://{url}" if not url.startswith('//') else f"https:{url}"


# -------------------------
# Steam search functionality
# -------------------------
def _steam_search_api(title: str) -> List[Dict]:
    q = quote_plus(title)
    url = STEAM_SEARCH_API.format(q=q)
    print(f"[SCRAPE] Steam API search: {url}")
    r = _http_get(url)
    if not r:
        return []
    try:
        data = r.json()
    except json.JSONDecodeError:
        return []
    items = data.get("items") or []
    print(f"[SCRAPE] Steam API found {len(items)} candidates")
    return [
        {
            "id": str(it.get("id", "")),
            "name": it.get("name", ""),
            "tiny_image": it.get("tiny_image"),
            "source": "steam_api"
        }
        for it in items
    ]


def _steam_search_html(title: str) -> List[Dict]:
    url = f"https://store.steampowered.com/search/?term={quote_plus(title)}"
    print(f"[SCRAPE] Steam HTML search: {url}")
    r = _http_get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []
    for a in soup.select("a.search_result_row"):
        href = a.get("href", "")
        match = re.search(r"/app/(\d+)", href)
        if match:
            name_elem = a.select_one(".title")
            name = name_elem.get_text(" ", strip=True) if name_elem else ""
            candidates.append({
                "id": match.group(1),
                "name": name,
                "tiny_image": None,
                "source": "steam_html"
            })
    print(f"[SCRAPE] Steam HTML found {len(candidates)} candidates")
    return candidates


def find_candidates_for_title(title: str, max_candidates: int = 8) -> List[Dict]:
    if not title or len(title.strip()) < 2:
        return []
    candidates = _steam_search_api(title)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if not candidates:
        candidates = _steam_search_html(title)
    scored = []
    for candidate in candidates[:max_candidates]:
        candidate_name = candidate.get("name", "")
        score = _score_name(title, candidate_name)
        scored.append({
            "id": candidate.get("id"),
            "name": candidate_name,
            "score": score,
            "source": candidate.get("source", "unknown")
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def get_app_id_from_title(title: str, auto_accept_score: int = 92) -> Optional[str]:
    if not title:
        return None
    candidates = _steam_search_api(title)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if not candidates:
        candidates = _steam_search_html(title)
    if not candidates:
        return None
    best = max(candidates, key=lambda it: _score_name(title, it.get("name", "")))
    best_score = _score_name(title, best.get("name", ""))
    if best_score >= auto_accept_score:
        print(f"[SCRAPE] Auto-accepted Steam AppID {best['id']} (score {best_score})")
        return str(best.get("id"))
    else:
        print(f"[SCRAPE] Steam best candidate '{best.get('name')}' score {best_score} below threshold {auto_accept_score}")
        return None


def adaptive_to_microtrailer(url: str, ext: str = "webm") -> str:
    if not url:
        return ""
    if "?" in url:
        base, query = url.split("?", 1)
        query = "?" + query
    else:
        base, query = url, ""
    parts = base.split("/")
    if parts:
        parts[-1] = f"microtrailer.{ext}"
    return "/".join(parts) + query


def get_store_metadata(app_id: str, title: str, fetch_pcgw_save: bool = False) -> Dict[str, Any]:
    if not app_id:
        print(f"[SCRAPE] No Steam AppID provided for '{title}'")
        return {
            "title": title or "",
            "release_date": "",
            "developer": "",
            "publisher": "",
            "genres": "",
            "description": "",
            "cover_url": "",
            "trailer_webm": "",
            "screenshots": [],
            "microtrailers": [],
            "steam_link": "",
            "steamdb_link": STEAMDB_APP_URL.format(appid=""),
            "pcgw_link": PCGW_SEARCH_TEMPLATE.format(q=quote_plus(title or "")),
            "igdb_link": IGDB_URL_TEMPLATE.format(slug=_slugify(title or "")),
            "save_location": "",
            "source": "steam"
        }
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    print(f"[SCRAPE] Fetching Steam metadata for app_id {app_id}: {url}")
    r = _http_get(url)
    steamdb_link = STEAMDB_APP_URL.format(appid=app_id)
    microtrailers = []
    trailer_webm = ""
    if r:
        try:
            payload = r.json().get(str(app_id), {})
            if payload.get("success"):
                info = payload.get("data", {})
                print(f"[SCRAPE] Steam API success for app_id {app_id}, name: {info.get('name')}")
                movies = info.get("movies") or []
                for movie in movies:
                    dash_url = movie.get("dash_av1") or movie.get("dash_h264") or movie.get("hls_h264")
                    if dash_url:
                        micro_url = adaptive_to_microtrailer(dash_url, ext="webm")
                        if micro_url and micro_url not in microtrailers:
                            microtrailers.append(micro_url)
                for movie in movies:
                    for fmt in ("webm", "mp4"):
                        video_data = movie.get(fmt)
                        if isinstance(video_data, dict):
                            for quality in ("max", "480", "360"):
                                video_url = video_data.get(quality)
                                if video_url and video_url not in microtrailers:
                                    microtrailers.append(video_url)
                trailer_webm = microtrailers[0] if microtrailers else ""
                screenshots = [
                    _normalize_image_url(s.get("path_full", ""))
                    for s in info.get("screenshots", [])
                    if s.get("path_full")
                ][:10]
                release_info = info.get("release_date", {})
                release_date = release_info.get("date", "") if isinstance(release_info, dict) else info.get("release_date", "")
                game_title = info.get("name", "") or title or ""
                return {
                    "title": game_title,
                    "release_date": release_date,
                    "developer": ", ".join(info.get("developers", []) or []),
                    "publisher": ", ".join(info.get("publishers", []) or []),
                    "genres": ", ".join([g.get("description", "") for g in info.get("genres", []) if g.get("description")]),
                    "description": info.get("short_description", "") or "",
                    "cover_url": _normalize_image_url(info.get("header_image", "") or ""),
                    "trailer_webm": trailer_webm,
                    "screenshots": screenshots,
                    "microtrailers": microtrailers[:2],
                    "steam_link": STEAM_STORE_APP_URL.format(appid=app_id),
                    "steamdb_link": steamdb_link,
                    "pcgw_link": PCGW_SEARCH_TEMPLATE.format(q=quote_plus(game_title)),
                    "igdb_link": IGDB_URL_TEMPLATE.format(slug=_slugify(game_title)),
                    "save_location": "",
                    "source": "steam",
                    "steam_app_id": app_id
                }
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"[SCRAPE] Error parsing Steam metadata for app_id {app_id}: {e}")
    else:
        print(f"[SCRAPE] Steam API returned no response for app_id {app_id}")
    return {
        "title": title or "",
        "release_date": "",
        "developer": "",
        "publisher": "",
        "genres": "",
        "description": "",
        "cover_url": "",
        "trailer_webm": "",
        "screenshots": [],
        "microtrailers": [],
        "steam_link": STEAM_STORE_APP_URL.format(appid=app_id),
        "steamdb_link": steamdb_link,
        "pcgw_link": PCGW_SEARCH_TEMPLATE.format(q=quote_plus(title or "")),
        "igdb_link": IGDB_URL_TEMPLATE.format(slug=_slugify(title or "")),
        "save_location": "",
        "source": "steam",
        "steam_app_id": app_id
    }


# -------------------------
# IGDB API integration (with fallback credentials and token refresh limit)
# -------------------------
def _fetch_igdb_token_via_twitch() -> str:
    if not IGDB_CLIENT_ID or not IGDB_CLIENT_SECRET:
        print("[SCRAPE] Warning: IGDB_CLIENT_ID or IGDB_CLIENT_SECRET not set")
        return ""
    now = int(time.time())
    if (_IGDB_TOKEN_CACHE.get("access_token") and _IGDB_TOKEN_CACHE.get("expires_at", 0) - 30 > now):
        return _IGDB_TOKEN_CACHE["access_token"]
    try:
        r = requests.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": IGDB_CLIENT_ID,
                "client_secret": IGDB_CLIENT_SECRET,
                "grant_type": "client_credentials"
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            token = data.get("access_token", "")
            expires_in = int(data.get("expires_in", 0))
            if token:
                _IGDB_TOKEN_CACHE["access_token"] = token
                _IGDB_TOKEN_CACHE["expires_at"] = now + max(30, expires_in)
                print("[SCRAPE] Fetched new IGDB token")
                return token
    except requests.RequestException as e:
        print(f"[SCRAPE] Error fetching IGDB token: {e}")
    return ""


def _get_igdb_token() -> str:
    if IGDB_ACCESS_TOKEN and IGDB_ACCESS_TOKEN != _FALLBACK_ACCESS_TOKEN:
        # User provided a custom token (not the fallback) – use it directly
        return IGDB_ACCESS_TOKEN
    return _fetch_igdb_token_via_twitch()


def _igdb_query(endpoint: str, query: str, timeout: float = 10.0) -> Optional[List[Dict]]:
    for attempt in range(_MAX_TOKEN_REFRESH + 1):
        token = _get_igdb_token()
        if not token:
            print("[SCRAPE] Error: No IGDB access token available")
            return None
        headers = {
            "Client-ID": IGDB_CLIENT_ID,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        try:
            r = requests.post(
                f"https://api.igdb.com/v4/{endpoint}",
                data=query.encode("utf-8"),
                headers=headers,
                timeout=timeout
            )
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                print(f"[SCRAPE] IGDB token expired (attempt {attempt+1}/{_MAX_TOKEN_REFRESH+1}), refreshing...")
                # Invalidate the cached token
                _IGDB_TOKEN_CACHE["access_token"] = None
                _IGDB_TOKEN_CACHE["expires_at"] = 0
                continue
            else:
                print(f"[SCRAPE] IGDB query failed with status {r.status_code}: {r.text[:200]}")
                return None
        except requests.RequestException as e:
            print(f"[SCRAPE] IGDB API request failed: {e}")
            return None
    print("[SCRAPE] IGDB query failed after maximum retries")
    return None


def _format_igdb_image_url(image_id: str, size: str = IGDB_SCREENSHOT_SIZE) -> str:
    if not image_id:
        return ""
    image_id = image_id.split('.')[0]
    return f"{IGDB_IMAGE_BASE_URL}/{size}/{image_id}.jpg"


# -------------------------
# IGDB candidate functions
# -------------------------
def find_candidates_for_title_igdb(title: str, max_candidates: int = 8) -> List[Dict]:
    if not title or len(title.strip()) < 2:
        return []
    query = f'''
        search "{title}";
        fields 
            id,
            name,
            summary,
            cover.image_id,
            first_release_date,
            platforms.name,
            genres.name,
            rating,
            rating_count,
            aggregated_rating;
        limit {max_candidates};
    '''
    print(f"[SCRAPE] Searching IGDB for '{title}'")
    results = _igdb_query("games", query) or []
    candidates = []
    for item in results:
        item_id = item.get("id")
        item_name = item.get("name", "")
        if not item_id or not item_name:
            continue
        score = _score_name(title, item_name)
        cover_url = ""
        cover_image_id = item.get("cover", {}).get("image_id")
        if cover_image_id:
            cover_url = _format_igdb_image_url(cover_image_id, size=IGDB_COVER_SIZE)
        release_year = ""
        first_release = item.get("first_release_date")
        if first_release:
            try:
                release_year = time.strftime("%Y", time.gmtime(first_release))
            except:
                pass
        user_rating = item.get("rating")
        critic_rating = item.get("aggregated_rating")
        rating_display = ""
        if user_rating is not None:
            rating_display = f"⭐ {user_rating:.1f}/100"
            rating_count = item.get("rating_count")
            if rating_count:
                rating_display += f" ({rating_count} ratings)"
        elif critic_rating is not None:
            rating_display = f"🎯 {critic_rating:.1f}/100"
        genres = ", ".join([g.get("name", "") for g in item.get("genres", [])][:3])
        candidates.append({
            "id": str(item_id),
            "name": item_name,
            "score": score,
            "source": "igdb",
            "tiny_image": cover_url,
            "release_year": release_year,
            "user_rating": user_rating,
            "critic_rating": critic_rating,
            "rating_display": rating_display,
            "genres": genres,
            "description_preview": (item.get("summary", "") or "")[:120] + "..." if item.get("summary") else "",
            "is_igdb": True
        })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"[SCRAPE] IGDB found {len(candidates)} candidates")
    return candidates


def get_igdb_id_from_title(title: str, auto_accept_score: int = 92) -> Optional[str]:
    if not title:
        return None
    candidates = find_candidates_for_title_igdb(title, max_candidates=5)
    if not candidates:
        return None
    best = max(candidates, key=lambda it: it.get("score", 0))
    best_score = best.get("score", 0)
    if best_score >= auto_accept_score:
        print(f"[SCRAPE] Auto-accepted IGDB ID {best['id']} (score {best_score})")
        return str(best.get("id"))
    else:
        print(f"[SCRAPE] IGDB best candidate '{best['name']}' score {best_score} below threshold {auto_accept_score}")
        return None


def igdb_scraper(title: str, auto_accept_score: int = 92, igdb_id: Optional[str] = None) -> Dict[str, Any]:
    print(f"[SCRAPE] igdb_scraper called with title='{title}', igdb_id={igdb_id}")
    if not title or len(title.strip()) < 2:
        return {"__error__": "Invalid title provided"}
    if igdb_id:
        query = f'''
            fields 
                id,
                name,
                slug,
                genres.name,
                themes.name,
                summary,
                screenshots.image_id,
                cover.image_id,
                artworks.image_id,
                player_perspectives.name,
                videos.video_id,
                involved_companies.company.name,
                involved_companies.developer,
                involved_companies.publisher,
                rating,
                rating_count,
                aggregated_rating,
                aggregated_rating_count,
                first_release_date,
                websites.url,
                websites.category;
            where id = {igdb_id};
            limit 1;
        '''
        print(f"[SCRAPE] Querying IGDB by ID {igdb_id}")
        results = _igdb_query("games", query) or []
        if not results:
            print(f"[SCRAPE] No IGDB game found with ID {igdb_id}, falling back to title search")
            return igdb_scraper(title, auto_accept_score, igdb_id=None)
        exact_match = results[0]
        print(f"[SCRAPE] IGDB ID {igdb_id} found: '{exact_match.get('name')}'")
    else:
        query = f'''
            search "{title}";
            fields 
                id,
                name,
                slug,
                genres.name,
                themes.name,
                summary,
                screenshots.image_id,
                cover.image_id,
                artworks.image_id,
                player_perspectives.name,
                videos.video_id,
                involved_companies.company.name,
                involved_companies.developer,
                involved_companies.publisher,
                rating,
                rating_count,
                aggregated_rating,
                aggregated_rating_count,
                first_release_date,
                websites.url,
                websites.category;
            limit 5;
        '''
        print(f"[SCRAPE] Searching IGDB for '{title}'")
        results = _igdb_query("games", query) or []
        if not results:
            candidates = find_candidates_for_title_igdb(title)
            # Always return __candidates__ (even empty) to trigger manual dialog
            return {"__candidates__": candidates, "__action__": "select_igdb_candidate", "title": title, "source": "igdb_candidates"}
        exact_match = None
        for item in results:
            if item.get("name", "").strip().lower() == title.strip().lower():
                exact_match = item
                break
        if not exact_match and results:
            scored_results = []
            for item in results:
                item_name = item.get("name", "")
                score = _score_name(title, item_name)
                scored_results.append((score, item))
            scored_results.sort(key=lambda x: x[0], reverse=True)
            best_score, best_item = scored_results[0]
            if best_score >= auto_accept_score:
                exact_match = best_item
                print(f"[SCRAPE] Auto-accepted IGDB candidate '{best_item['name']}' with score {best_score}")
            else:
                candidates = find_candidates_for_title_igdb(title)
                return {"__candidates__": candidates, "__action__": "select_igdb_candidate", "title": title, "source": "igdb_candidates", "best_score": best_score, "auto_accept_threshold": auto_accept_score}
        if not exact_match:
            candidates = find_candidates_for_title_igdb(title)
            return {"__candidates__": candidates, "__action__": "select_igdb_candidate", "title": title, "source": "igdb_candidates"}
    # Extract developers and publishers
    developers = []
    publishers = []
    for company in exact_match.get("involved_companies", []):
        company_name = company.get("company", {}).get("name", "")
        if company.get("developer"):
            developers.append(company_name)
        if company.get("publisher"):
            publishers.append(company_name)
    # Process screenshots with high-quality URLs
    screenshots = []
    for screenshot in exact_match.get("screenshots", []):
        image_id = screenshot.get("image_id")
        if image_id:
            screenshot_url = _format_igdb_image_url(image_id, size=IGDB_SCREENSHOT_SIZE)
            screenshots.append(_normalize_image_url(screenshot_url))
    # Get cover image URL (use cover size)
    cover_image_id = exact_match.get("cover", {}).get("image_id")
    cover_url = _format_igdb_image_url(cover_image_id, size=IGDB_COVER_SIZE) if cover_image_id else ""
    igdb_cover_art = cover_url
    # Process trailers
    trailers = []
    for video in exact_match.get("videos", []):
        video_id = video.get("video_id")
        if video_id:
            trailers.append(f"https://www.youtube.com/watch?v={video_id}")
    # Get release date
    release_date = ""
    first_release = exact_match.get("first_release_date")
    if first_release:
        try:
            release_date = time.strftime("%Y-%m-%d", time.gmtime(first_release))
        except:
            release_date = str(first_release)
    slug = exact_match.get("slug", _slugify(exact_match.get("name", title)))
    igdb_link = f"https://www.igdb.com/games/{slug}"
    # Try to find Steam AppID from IGDB websites
    steam_app_id = None
    steam_link = ""
    for site in exact_match.get("websites", []):
        if site.get("category") == 13:
            steam_url = site.get("url", "")
            match = re.search(r'/app/(\d+)', steam_url)
            if match:
                steam_app_id = match.group(1)
                steam_link = STEAM_STORE_APP_URL.format(appid=steam_app_id)
                break
    # Get rating information
    user_rating = exact_match.get("rating")
    critic_rating = exact_match.get("aggregated_rating")
    rating_display = ""
    if user_rating is not None:
        rating_display = f"⭐ {user_rating:.1f}/100"
        rating_count = exact_match.get("rating_count")
        if rating_count:
            rating_display += f" ({rating_count} ratings)"
    elif critic_rating is not None:
        rating_display = f"🎯 {critic_rating:.1f}/100"
        rating_count = exact_match.get("aggregated_rating_count")
        if rating_count:
            rating_display += f" ({rating_count} critic reviews)"
    result = {
        "source": "igdb",
        "igdb_id": str(exact_match.get("id", "")),
        "title": exact_match.get("name", title),
        "description": exact_match.get("summary", ""),
        "genres": ", ".join([g.get("name", "") for g in exact_match.get("genres", [])]),
        "themes": ", ".join([t.get("name", "") for t in exact_match.get("themes", [])]),
        "player_perspective": ", ".join([p.get("name", "") for p in exact_match.get("player_perspectives", [])]),
        "developer": ", ".join(developers),
        "publisher": ", ".join(publishers),
        "cover_url": _normalize_image_url(cover_url),
        "igdb_cover_art": igdb_cover_art,
        "screenshots": screenshots,
        "trailers": trailers,
        "igdb_link": igdb_link,
        "release_date": release_date,
        "steam_app_id": steam_app_id,
        "steam_link": steam_link,
        "steamdb_link": STEAMDB_APP_URL.format(appid=steam_app_id) if steam_app_id else "",
        "pcgw_link": PCGW_SEARCH_TEMPLATE.format(q=quote_plus(exact_match.get("name", title))),
        "user_rating": user_rating,
        "user_rating_count": exact_match.get("rating_count"),
        "critic_rating": critic_rating,
        "critic_rating_count": exact_match.get("aggregated_rating_count"),
        "rating_display": rating_display,
        "scraped_by_id": igdb_id is not None
    }
    print(f"[SCRAPE] IGDB scraper returned: {result.get('title')} (igdb_id={result.get('igdb_id')})")
    return result


# -------------------------
# Metadata merging utilities
# -------------------------
IGDB_ALLOWED_KEYS = {
    "description", "player_perspective", "igdb_id", "themes", "genres",
    "screenshots", "trailers", "cover_url", "igdb_link", "title",
    "developer", "publisher", "user_rating", "user_rating_count",
    "critic_rating", "critic_rating_count", "rating_display", "igdb_cover_art",
}


def _filter_igdb_allowed(metadata: Dict) -> Dict:
    if not isinstance(metadata, dict):
        return {}
    return {key: metadata[key] for key in IGDB_ALLOWED_KEYS if key in metadata and metadata[key]}


def merge_metadata(primary: Dict, secondary: Dict) -> Dict:
    merged = primary.copy()
    def is_steam(data: Dict) -> bool:
        return any(k in data for k in ("steam_link", "steam_app_id", "steamdb_link", "microtrailers"))
    def is_igdb(data: Dict) -> bool:
        return any(k in data for k in ("igdb_link", "igdb_id", "critic_rating", "themes", "player_perspective"))
    primary_steam = is_steam(primary)
    secondary_steam = is_steam(secondary)
    primary_igdb = is_igdb(primary)
    secondary_igdb = is_igdb(secondary)
    steam_data = secondary if secondary_steam else (primary if primary_steam else {})
    igdb_data = secondary if secondary_igdb else (primary if primary_igdb else {})
    for key, steam_value in steam_data.items():
        if not steam_value:
            continue
        if isinstance(steam_value, list) and isinstance(merged.get(key), list):
            merged_list = []
            seen = set()
            for item in steam_value:
                if item and str(item) not in seen:
                    merged_list.append(item)
                    seen.add(str(item))
            for item in igdb_data.get(key, []):
                if item and str(item) not in seen:
                    merged_list.append(item)
                    seen.add(str(item))
            merged[key] = merged_list
        elif key == "cover_url":
            if steam_value:
                merged[key] = steam_value
        elif key == "description" and isinstance(steam_value, str):
            if len(steam_value) > len(merged.get(key, "")):
                merged[key] = steam_value
        elif key in ("steam_app_id", "igdb_id"):
            if steam_value:
                merged[key] = steam_value
        elif key not in merged or not merged[key]:
            merged[key] = steam_value
        elif secondary_steam and not primary_steam:
            merged[key] = steam_value
    if "igdb_cover_art" in igdb_data and igdb_data["igdb_cover_art"]:
        merged["igdb_cover_art"] = igdb_data["igdb_cover_art"]
    if "steam_app_id" in steam_data and steam_data["steam_app_id"]:
        merged["steam_app_id"] = steam_data["steam_app_id"]
    elif "steam_app_id" in igdb_data and igdb_data["steam_app_id"]:
        merged["steam_app_id"] = igdb_data["steam_app_id"]
    if "igdb_id" in igdb_data and igdb_data["igdb_id"]:
        merged["igdb_id"] = igdb_data["igdb_id"]
    elif "igdb_id" in steam_data and steam_data["igdb_id"]:
        merged["igdb_id"] = steam_data["igdb_id"]
    merged["_merge_debug"] = {
        "primary_is_steam": primary_steam,
        "secondary_is_steam": secondary_steam,
        "primary_is_igdb": primary_igdb,
        "secondary_is_igdb": secondary_igdb
    }
    return merged


# -------------------------
# Main scraping functions
# -------------------------
def scrape_igdb_then_steam(
    igdb_id: Optional[str],
    title: str,
    primary_scraper_func: Callable = igdb_scraper,
    auto_accept_score: int = 92,
    fetch_pcgw_save: bool = False,
    steam_app_id: Optional[str] = None
) -> Dict[str, Any]:
    print(f"[SCRAPE] scrape_igdb_then_steam called: igdb_id={igdb_id}, title='{title}', steam_app_id={steam_app_id}")
    primary_metadata = {}
    try:
        primary_metadata = primary_scraper_func(title, auto_accept_score=auto_accept_score, igdb_id=igdb_id) or {}
    except Exception as e:
        print(f"[SCRAPE] Error getting IGDB primary metadata: {e}")
        primary_metadata = {"__error__": f"IGDB error: {str(e)}"}
    if "__candidates__" in primary_metadata or "__error__" in primary_metadata:
        return primary_metadata
    steam_metadata = {}
    steam_app_id_to_use = None
    if steam_app_id:
        steam_app_id_to_use = steam_app_id
        print(f"[SCRAPE] Using provided Steam AppID: {steam_app_id_to_use}")
    elif not steam_app_id_to_use:
        steam_app_id_to_use = primary_metadata.get("steam_app_id")
        if steam_app_id_to_use:
            print(f"[SCRAPE] Using Steam AppID from IGDB data: {steam_app_id_to_use}")
    if not steam_app_id_to_use:
        search_title = primary_metadata.get("title", title)
        print(f"[SCRAPE] Searching Steam by title '{search_title}'")
        steam_app_id_to_use = get_app_id_from_title(search_title, auto_accept_score)
        if steam_app_id_to_use:
            print(f"[SCRAPE] Found Steam AppID by title search: {steam_app_id_to_use}")
    if steam_app_id_to_use:
        steam_metadata = get_store_metadata(steam_app_id_to_use, primary_metadata.get("title", title), fetch_pcgw_save) or {}
    else:
        print(f"[SCRAPE] No Steam AppID found for '{title}'")
    merged = merge_metadata(primary_metadata, steam_metadata)
    merged["source"] = "igdb_then_steam"
    merged["primary_source"] = "igdb"
    merged["secondary_source"] = "steam" if steam_metadata else "none"
    merged["scraped_at"] = time.time()
    merged["auto_accept_score_used"] = auto_accept_score
    if steam_app_id_to_use:
        if steam_app_id and steam_app_id == steam_app_id_to_use:
            merged["steam_app_id_source"] = "provided"
        elif primary_metadata.get("steam_app_id") == steam_app_id_to_use:
            merged["steam_app_id_source"] = "igdb"
        else:
            merged["steam_app_id_source"] = "title_search"
    if igdb_id:
        merged["igdb_id_source"] = "provided"
    elif primary_metadata.get("igdb_id"):
        merged["igdb_id_source"] = "title_search"
    print(f"[SCRAPE] Merged metadata keys: {list(merged.keys())}")
    return merged


def scrape_primary_then_igdb(
    app_id: Optional[str],
    title: str,
    auto_accept_score: int = 92,
    fetch_pcgw_save: bool = False,
    igdb_id: Optional[str] = None
) -> Dict[str, Any]:
    print(f"[SCRAPE] scrape_primary_then_igdb called: app_id={app_id}, title='{title}', igdb_id={igdb_id}")
    steam_metadata = {}
    try:
        steam_app_id_to_use = app_id
        if not steam_app_id_to_use:
            steam_app_id_to_use = get_app_id_from_title(title, auto_accept_score)
        if steam_app_id_to_use:
            steam_metadata = get_store_metadata(steam_app_id_to_use, title, fetch_pcgw_save) or {}
        else:
            candidates = find_candidates_for_title(title)
            return {"__candidates__": candidates, "__action__": "select_steam_candidate", "title": title, "source": "steam_candidates"}
    except Exception as e:
        print(f"[SCRAPE] Error getting Steam primary metadata: {e}")
        steam_metadata = {"__error__": f"Steam error: {str(e)}"}
    if "__candidates__" in steam_metadata or "__error__" in steam_metadata:
        return steam_metadata
    igdb_metadata = {}
    try:
        igdb_title = steam_metadata.get("title", title)
        igdb_metadata = igdb_scraper(igdb_title, auto_accept_score=auto_accept_score, igdb_id=igdb_id) or {}
    except Exception as e:
        print(f"[SCRAPE] Error getting IGDB metadata: {e}")
        igdb_metadata = {}
    merged = merge_metadata(steam_metadata, igdb_metadata)
    merged["source"] = "steam_then_igdb"
    merged["primary_source"] = "steam"
    merged["secondary_source"] = "igdb" if igdb_metadata else "none"
    merged["scraped_at"] = time.time()
    merged["auto_accept_score_used"] = auto_accept_score
    if app_id:
        merged["steam_app_id_source"] = "provided"
    elif steam_metadata.get("steam_app_id"):
        merged["steam_app_id_source"] = "title_search"
    if igdb_id:
        merged["igdb_id_source"] = "provided"
    elif igdb_metadata.get("igdb_id"):
        merged["igdb_id_source"] = "title_search"
    return merged


# -------------------------
# CLI Testing
# -------------------------
if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Test IGDB and Steam scraping")
    parser.add_argument("title", help="Game title to scrape")
    parser.add_argument("--igdb-id", help="IGDB ID (skip search)")
    parser.add_argument("--app-id", help="Steam AppID (skip search)")
    parser.add_argument("--auto-accept-score", type=int, default=92)
    parser.add_argument("--mode", choices=["igdb_first", "steam_first", "igdb_only", "steam_only"], default="igdb_first")
    args = parser.parse_args()
    print(f"\n{'='*60}\nTesting scraping for '{args.title}'\n{'='*60}")
    if args.mode == "igdb_first":
        result = scrape_igdb_then_steam(args.igdb_id, args.title, auto_accept_score=args.auto_accept_score, steam_app_id=args.app_id)
        print("\nFinal metadata:\n", json.dumps(result, indent=2, ensure_ascii=False))
    elif args.mode == "steam_first":
        result = scrape_primary_then_igdb(args.app_id, args.title, auto_accept_score=args.auto_accept_score, igdb_id=args.igdb_id)
        print("\nFinal metadata:\n", json.dumps(result, indent=2, ensure_ascii=False))
    elif args.mode == "igdb_only":
        result = igdb_scraper(args.title, args.auto_accept_score, args.igdb_id)
        print("\nIGDB only:\n", json.dumps(result, indent=2, ensure_ascii=False))
    elif args.mode == "steam_only":
        if args.app_id:
            result = get_store_metadata(args.app_id, args.title)
        else:
            appid = get_app_id_from_title(args.title, args.auto_accept_score)
            if appid:
                result = get_store_metadata(appid, args.title)
            else:
                result = {"error": "No Steam AppID found"}
        print("\nSteam only:\n", json.dumps(result, indent=2, ensure_ascii=False))
    print("\n" + "="*60)