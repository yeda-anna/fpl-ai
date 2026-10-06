"""Thin client over the official Fantasy Premier League public API, with disk caching.

All endpoints here are the same public JSON endpoints fplcopilot.com is built on.
No auth is required for any of them.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx

BASE = "https://fantasy.premierleague.com/api"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Per-endpoint cache lifetimes (seconds).
TTL = {
    "bootstrap-static": 900,
    "fixtures": 900,
    "entry": 300,
    "picks": 300,
    "history": 600,
    "live": 120,
    "live_final": 6 * 3600,
    "standings": 600,
    "summary": 1800,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
}


def _cache_path(key: str) -> str:
    safe = key.replace("/", "_").replace("?", "_").replace("=", "-").replace("&", "_")
    return os.path.join(CACHE_DIR, safe + ".json")


def _read_cache(key: str, ttl: int) -> Optional[Any]:
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > ttl:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _write_cache(key: str, payload: Any) -> None:
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except Exception:
        pass


def _stale_cache(key: str) -> Optional[Any]:
    """Last known good copy, however old - used when the live API is unreachable."""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# Offline mode: serve only what's already cached and never touch the network.
# Handy for development and tests on machines that can't reach the FPL API.
CACHE_ONLY = os.environ.get("FPL_CACHE_ONLY", "").strip().lower() in ("1", "true", "yes")


def get(path: str, cache_key: str, ttl_key: str) -> Any:
    if CACHE_ONLY:
        stale = _stale_cache(cache_key)
        if stale is not None:
            return stale
        raise RuntimeError("FPL_CACHE_ONLY is set and '%s' isn't cached" % cache_key)
    ttl = TTL.get(ttl_key, 600)
    cached = _read_cache(cache_key, ttl)
    if cached is not None:
        return cached
    url = BASE + path
    try:
        with httpx.Client(timeout=25.0, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        stale = _stale_cache(cache_key)
        if stale is not None:
            return stale
        raise
    _write_cache(cache_key, data)
    return data


# --- endpoints -------------------------------------------------------------

def bootstrap() -> Dict[str, Any]:
    """Players, teams, gameweeks, chips, scoring settings."""
    return get("/bootstrap-static/", "bootstrap-static", "bootstrap-static")


def fixtures() -> List[Dict[str, Any]]:
    """Every fixture of the season with FDR ratings."""
    return get("/fixtures/", "fixtures", "fixtures")


def entry(team_id: int) -> Dict[str, Any]:
    """A manager's profile: name, overall rank, bank, squad value."""
    return get("/entry/%d/" % team_id, "entry-%d" % team_id, "entry")


def entry_history(team_id: int) -> Dict[str, Any]:
    """Gameweek-by-gameweek history plus chips already played."""
    return get("/entry/%d/history/" % team_id, "history-%d" % team_id, "history")


def entry_picks(team_id: int, gw: int) -> Dict[str, Any]:
    """The 15 players a manager fielded in a given gameweek."""
    return get("/entry/%d/event/%d/picks/" % (team_id, gw), "picks-%d-%d" % (team_id, gw), "picks")


def entry_transfers(team_id: int) -> List[Dict[str, Any]]:
    return get("/entry/%d/transfers/" % team_id, "transfers-%d" % team_id, "entry")


def live(gw: int) -> Dict[str, Any]:
    return get("/event/%d/live/" % gw, "live-%d" % gw, "live")


def live_final(gw: int) -> Dict[str, Any]:
    """Per-player stats for a gameweek, cached long because finished weeks don't change."""
    return get("/event/%d/live/" % gw, "live-%d" % gw, "live_final")


def element_summary(player_id: int) -> Dict[str, Any]:
    """Per-fixture history for one player plus their upcoming fixtures."""
    return get("/element-summary/%d/" % player_id, "summary-%d" % player_id, "summary")


def league_standings(league_id: int, page: int = 1) -> Dict[str, Any]:
    return get(
        "/leagues-classic/%d/standings/?page_standings=%d" % (league_id, page),
        "standings-%d-%d" % (league_id, page),
        "standings",
    )
