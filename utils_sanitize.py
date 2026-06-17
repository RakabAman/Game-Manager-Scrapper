# utils_sanitize.py
"""
Sanitizer utility for messy release titles.

Uses configuration from config module (loaded from config.ini).
"""

import re
import json
from typing import List, Dict, Optional

# Try to import config; if not available, create a dummy with defaults
try:
    import config
except ImportError:
    # Create a simple namespace with defaults
    class _Config:
        REPACK_LIST = [
            "FitGirl Repack", "DODI Repacks", "GOG", "CODEX", "RELOADED", "SKIDROW",
            "CPY", "PLAZA", "Razor1911", "FLT", "SiMPLEX", "PROPHET", "HOODLUM",
            "KaOs Krew", "TinyRepacks", "M4ckD0ge", "qoob", "JIT",
            "GoldBerg", "EMPRESS", "INSANE", "DOGE", "ANOMALY"
        ]
        EDITION_TOKENS = [
            "deluxe", "edition", "ultimate", "bundle", "pack", "premium",
            "remastered", "remake", "complete", "goty", "director's cut",
            "anniversary", "super digital", "evolved", "classified archives",
            "bonus ost", "bonus"
        ]
        EMULATOR_TOKENS = [
            "rpcs3", "ryujinx", "yuzu", "cemu", "dolphin", "pcsx2",
            "switch", "ps3", "wiiu", "ps4", "emulator", "emu"
        ]
        MODE_KEYWORDS = {
            "Multiplayer": ["multiplayer", "multi-player", "mp", "online"],
            "CO-OP": ["coop", "co-op", "co op", "cooperative"],
            "Singleplayer": ["singleplayer", "single-player", "sp"]
        }
    config = _Config()

# Basic regexes
_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')
_VERSION_RE = re.compile(r'\b(?:v|version|ver)\s*[:\-]?\s*([0-9]+(?:[._\-][0-9A-Za-z]+)*)\b', re.I)
_SIMPLE_VERSION_RE = re.compile(r'\b(v[0-9]+(?:[._][0-9]+){0,})\b', re.I)
_HOTFIX_RE = re.compile(r'\bhotfix\s*[:\-]?\s*([0-9]+)\b', re.I)
_BUILD_RE = re.compile(r'\bbuild\s*[:\-]?\s*([0-9]+(?:[._\-][0-9]+)*)\b', re.I)
_BUILD_SHORT_RE = re.compile(r'\b(?:b|bld)\s*[:\-]?\s*([0-9]{3,})\b', re.I)
_UPDATE_RE = re.compile(r'\bupdate\s*[:\-]?\s*([0-9]+(?:[._\-][0-9]+)*)\b', re.I)

_BRACKET_RE = re.compile(r'[\[\(](.*?)[\]\)]')
_SEPARATORS = re.compile(r'[._\-\u2013\u2014–—/|]+')

# Build regex patterns from config lists
_EMULATOR_RE = re.compile('|'.join(r'\b' + re.escape(tok) + r'\b' for tok in config.EMULATOR_TOKENS), re.I)
_EDITION_RE = re.compile('|'.join(r'\b' + re.escape(tok) + r'\b' for tok in config.EDITION_TOKENS), re.I)

def _find_repack(tokens: List[str]) -> Optional[str]:
    """Find repack name from tokens using REPACK_LIST."""
    repack_lower = [r.lower() for r in config.REPACK_LIST]
    for t in tokens:
        tl = t.lower().strip()
        if tl in repack_lower:
            return config.REPACK_LIST[repack_lower.index(tl)]
    for t in tokens:
        tl = t.lower().strip()
        for i, r in enumerate(repack_lower):
            if r and r in tl:
                return config.REPACK_LIST[i]
        for i, r in enumerate(repack_lower):
            if tl and tl in r:
                return config.REPACK_LIST[i]
    for t in tokens:
        if t.upper() in config.REPACK_LIST:
            return t.upper()
    for t in tokens:
        for repack in config.REPACK_LIST:
            if repack.lower() in t.lower():
                return repack
            if t.lower() in repack.lower():
                return repack
    return None

def _extract_bracket_tokens(s: str) -> List[str]:
    return [m.strip() for m in _BRACKET_RE.findall(s) if m.strip()]

def _extract_version(s: str) -> Optional[str]:
    if not s:
        return None
    m = _VERSION_RE.search(s)
    if m:
        return 'v' + m.group(1).replace(' ', '')
    m2 = _BUILD_RE.search(s)
    if m2:
        return "Build " + m2.group(1).replace(' ', '')
    m2b = _BUILD_SHORT_RE.search(s)
    if m2b:
        return "Build " + m2b.group(1)
    m3 = _HOTFIX_RE.search(s)
    if m3:
        return f"Hotfix {m3.group(1)}"
    m4 = _UPDATE_RE.search(s)
    if m4:
        return f"Update {m4.group(1)}"
    m5 = re.search(r'\bv?([0-9]{6,}[0-9_\-0-9]*)\b', s)
    if m5:
        return 'v' + m5.group(1)
    return None

def _extract_modes(s: str) -> List[str]:
    found = set()
    low = s.lower()
    for mode, keys in config.MODE_KEYWORDS.items():
        for k in keys:
            if k in low:
                found.add(mode)
    if not found:
        return ["Singleplayer"]
    if "Singleplayer" not in found:
        found.add("Singleplayer")
    return sorted(found)

def _clean_text_for_title(s: str) -> str:
    s2 = _SEPARATORS.sub(' ', s)
    s2 = re.sub(r'[\"\"\(\)\[\]\{\}:;,+=<>@#\$%\^&\*~`]', ' ', s2)
    s2 = re.sub(r'\s+', ' ', s2).strip()
    def smart_title(tok: str) -> str:
        if tok.upper() in ("PC", "GOG", "PS4", "PS5", "PS3", "NS", "SNES", "XBOX", "XBOX360", "XBOXONE"):
            return tok.upper()
        if tok == "`n":
            return "`N"
        return tok.capitalize()
    parts = s2.split(' ')
    parts = [smart_title(p) for p in parts if p]
    return ' '.join(parts)

def _strip_editions_and_modes(s: str) -> str:
    s2 = re.sub(r'\+\s*Multiplayer', ' ', s, flags=re.I)
    s2 = re.sub(r'\+\s*CO-OP', ' ', s2, flags=re.I)
    s2 = _EDITION_RE.sub(' ', s2)
    s2 = _EMULATOR_RE.sub(' ', s2)
    s2 = re.sub(r'\b(multiplayer|multi-player|mp|online|coop|co-op|co op|cooperative)\b', ' ', s2, flags=re.I)
    for tok in config.EMULATOR_TOKENS:
        s2 = re.sub(r'\b' + re.escape(tok) + r'\b', ' ', s2, flags=re.I)
    return s2

def sanitize_original_title(raw: str) -> Dict:
    """
    Parse a messy original title string into structured parts.

    Returns dict:
      {
        "base_title": str,
        "version": str or "",
        "repack": str or "",
        "modes": [ ... ],
        "cleaned_title": str,
        "tokens": [ ... ],
        "notes": str
      }
    """
    if not raw:
        return {
            "base_title": "",
            "version": "",
            "repack": "",
            "modes": ["Singleplayer"],
            "cleaned_title": "",
            "tokens": [],
            "notes": ""
        }

    s = raw.strip()
    bracket_tokens = _extract_bracket_tokens(s)
    version = _extract_version(s)
    if not version:
        for t in bracket_tokens:
            v = _extract_version(t)
            if v:
                version = v
                break

    tokens = bracket_tokens[:]
    trailing = re.split(r'[-:]', re.sub(r'[\[\]\(\)]', '', s))
    trailing = [t.strip() for t in trailing if t.strip()]
    if len(trailing) > 1:
        tokens.extend(trailing[1:])
    raw_lower = s.lower()
    for repack in config.REPACK_LIST:
        if repack.lower() in raw_lower:
            tokens.append(repack)
            break
    repack = _find_repack(tokens)

    modes = _extract_modes(s)

    s_no_brackets = _BRACKET_RE.sub('', s)
    if version:
        ver_esc = re.escape(version)
        ver_pattern = ver_esc.replace(r'\-', r'[-_\s]').replace(r'\_', r'[_\-\s]')
        try:
            s_no_brackets = re.sub(r'(?i)' + ver_pattern, '', s_no_brackets)
        except re.error:
            s_no_brackets = re.sub(re.escape(version), '', s_no_brackets, flags=re.I)
    if repack:
        repack_esc = re.escape(repack)
        try:
            repack_pattern = r'[\s\-_\[]*' + repack_esc + r'[\s\-_\]]*'
            s_no_brackets = re.sub(repack_pattern, ' ', s_no_brackets, flags=re.I)
        except re.error:
            s_no_brackets = re.sub(re.escape(repack), '', s_no_brackets, flags=re.I)
        s_no_brackets = re.sub(r'[\-\:]+\s*$', '', s_no_brackets)

    s_no_brackets = _strip_editions_and_modes(s_no_brackets)
    s_no_brackets = re.sub(r'\s*\+\s*.*$', '', s_no_brackets)
    base_candidate = _clean_text_for_title(s_no_brackets)
    base_candidate = re.sub(r'\b(v[0-9][\d._\-]*)\b', '', base_candidate, flags=re.I).strip()
    base_candidate = re.sub(r'\b(build\s*[0-9_ \-]+)\b', '', base_candidate, flags=re.I).strip()
    base_candidate = re.sub(r'\b(update\s*[0-9._\-]+)\b', '', base_candidate, flags=re.I).strip()
    base_candidate = re.sub(r'\s+', ' ', base_candidate).strip()

    cleaned_title = _clean_text_for_title(raw)

    used = set()
    if version:
        used.add(version.lower())
    if repack:
        used.add(repack.lower())
    leftover = []
    for t in tokens:
        tl = t.lower()
        if any(u in tl for u in used):
            continue
        if _YEAR_RE.search(t):
            continue
        if _EMULATOR_RE.search(t):
            continue
        leftover.append(t)
    notes = "; ".join(leftover).strip()

    return {
        "base_title": base_candidate,
        "version": version or "",
        "repack": repack or "",
        "modes": modes,
        "cleaned_title": cleaned_title,
        "tokens": tokens,
        "notes": notes
    }

# Quick test harness (uses config values)
if __name__ == "__main__":
    examples = [
        "100 in 1 Game Collection [FitGirl Repack]",
        "Age of Wonders 4 Premium Edition v1.011.001.110650  [FitGirl Repack]",
        "Alien Rogue Incursion Evolved Edition - Deluxe [FitGirl Repack]",
        "Ambrosia Sky Act One + Bonus OST [FitGirl Repack]",
        "Anima Gate of Memories - I and II Remaster [FitGirl Repack]",
        "Atelier Ryza Secret Trilogy Deluxe Pack [FitGirl Repack]",
        "Atelier Yumia The Alchemist of Memories & the Envisioned Land - Deluxe Edition v1.42 [FitGirl Repack]",
        "Baby Steps Hotfix 2 (26.09.2025) [FitGirl Repack]",
        "Bad Cheese v1.00.035 [FitGirl Repack]",
        "Battleborn Build 2151336 + Reborn Project Mod [FitGirl Repack]",
        "Big Dig Energy [FitGirl Repack]",
        "Bleak.Faith.Forsaken-GOG",
        "Bleak.Faith.Forsaken-RLD",
        "Bleak.Faith.Forsaken-CODEX",
        "Brew [FitGirl Repack]",
        "Bygone Dreams v1.0.0.4 [FitGirl Repack]",
        "Chip `n Clawz vs. The Brainioids v1.0.22358 [FitGirl Repack]",
        "Commandos Origins - Deluxe Edition & Classified Archives v1.5.0.88858 [FitGirl Repack]",
        "Cronos The New Dawn - Deluxe Edition v20250831_2044-321866  [FitGirl Repack]",
        "Cult of the Lamb The One Who Waits Bundle v1.4.3.588 [FitGirl Repack]",
        "Daemon X Machina Titanic Scion - Super Digital Deluxe Edition v1.2.0 [FitGirl Repack]",
        "Dead Island 2 Ultimate Edition v7.0.0 +  Multiplayer [FitGirl Repack]",
        "The Legend of Zelda Breath of the Wild [RPCS3]",
        "Super Mario Odyssey [Yuzu]",
        "Persona 5 Royal [Ryujinx Repack]",
        "Bloodborne [RPCS3 Emulator] v1.09",
        "God of War Ragnarok [PS4 Emulator] [FitGirl Repack]",
        "Indiana Jones And The Great Circle Update 4",
        "Starfield Update 1.9.51",
        "Cyberpunk 2077 Update 2.1 + Phantom Liberty",
        "The Witcher 3 Update 4.04 [GOG]",
        "Baldur's Gate 3 Update 17 [FitGirl Repack]",
        "Hogwarts Legacy Update 5 Build 1145830"
    ]
    print("Loaded repacks from config:", config.REPACK_LIST[:12], "...")
    import json
    results = []
    for ex in examples:
        out = sanitize_original_title(ex)
        results.append({"input": ex, "parsed": out})
    print(json.dumps(results, indent=2, ensure_ascii=False))