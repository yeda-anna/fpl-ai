"""Thin client over the official Fantasy Premier League public API, with disk caching.

All endpoints here are the same public JSON endpoints fplcopilot.com is built on.
No auth is required for any of them.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

import telemetry

log = telemetry.get_logger("fpl_api")

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


# A page load asks for a clean slate of the manager's own data (squad, bank,
# transfers, chips), so a transfer made on the FPL site shows up on refresh instead
# of after the cache expires. Purges are throttled per team so reloading in a loop
# can't hammer the FPL API.
REFRESH_MIN_AGE = 20
_purged: Dict[int, float] = {}


def refresh_team(team_id: int, picks_gw: Optional[int] = None) -> bool:
    """Forget cached FPL responses for one manager. True if anything was purged."""
    if CACHE_ONLY:
        return False
    now = time.time()
    if now - _purged.get(team_id, 0.0) < REFRESH_MIN_AGE:
        return False
    _purged[team_id] = now
    keys = ["entry-%d" % team_id, "history-%d" % team_id, "transfers-%d" % team_id]
    if picks_gw:
        keys.append("picks-%d-%d" % (team_id, picks_gw))
    purged = False
    for key in keys:
        try:
            # Expire rather than delete: if the FPL API is down the old copy still serves.
            os.utime(_cache_path(key), (0, 0))
            purged = True
        except OSError:
            pass
    return purged


# Offline mode: serve only what's already cached and never touch the network.
# Handy for development and tests on machines that can't reach the FPL API.
CACHE_ONLY = os.environ.get("FPL_CACHE_ONLY", "").strip().lower() in ("1", "true", "yes")


def get(path: str, cache_key: str, ttl_key: str) -> Any:
    # Logs name the endpoint kind (`ttl_key`), never the path or cache key: both carry Team IDs.
    if CACHE_ONLY:
        stale = _stale_cache(cache_key)
        if stale is not None:
            return stale
        telemetry.event(log, "fpl.cache_only_miss", logging.DEBUG, endpoint=ttl_key)
        raise RuntimeError("FPL_CACHE_ONLY is set and '%s' isn't cached" % cache_key)
    ttl = TTL.get(ttl_key, 600)
    cached = _read_cache(cache_key, ttl)
    if cached is not None:
        return cached
    url = BASE + path
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=25.0, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        stale = _stale_cache(cache_key)
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        # A 404 for an unknown team is the caller's 404, not an outage.
        level = logging.INFO if status == 404 and stale is None else (
            logging.WARNING if stale is not None else logging.ERROR)
        telemetry.event(log, "fpl.fetch_failed", level, endpoint=ttl_key, status=status,
                        error=type(exc).__name__, ms=telemetry.ms_since(start),
                        served_stale=stale is not None)
        if stale is not None:
            return stale
        raise
    telemetry.event(log, "fpl.fetch", endpoint=ttl_key, status=resp.status_code,
                    ms=telemetry.ms_since(start))
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
