"""Anonymous usage counts: daily visitors, new vs returning, demo vs real team,
and which pages and features get used.

Nothing here can tell one person from another. The browser keeps a single flag of
its own (`fplai_seen`, the date it first opened the app) and sends one "visit" a day
with three yes/no facts: had it been here before, and is it looking at the demo team
or a real one. Page views are a page name from the app's own list. Feature use is
counted on the server from the route template (`/api/solve`), never the path, so no
Team ID, league ID, IP address or cookie is ever stored or logged.

Counts live in one small JSON file, a day per key, kept for `KEEP_DAYS`. Point
`STATS_DIR` at a Railway volume to keep them across deploys; without one they start
again on each deploy (the summary says so). Python 3.9-compatible.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

import telemetry

log = telemetry.get_logger("usage")

KEEP_DAYS = 120
MODES = ("team", "demo", "none")        # a real team, the demo team, no team yet
# the app's own pages (TABS in app.js): a view outside this list isn't counted
PAGES = (
    "home/squad", "home/grade", "home/picks",
    "plan/transfers", "plan/chips",
    "players/projections", "players/compare", "players/prices", "players/lineups",
    "players/setpieces", "players/defcon",
    "matches/predictions",
    "leagues/league",
    "ask/copilot",
)
# server routes worth counting as features, by template
FEATURES = {
    "/api/entry/{team_id}": "Team loaded",
    "/api/solve": "Transfer plan",
    "/api/entry/{team_id}/swaps/{player_id}": "Swap ideas",
    "/api/chips": "Chip strategy",
    "/api/rate/{team_id}": "Grade my team",
    "/api/picks": "Weekly picks",
    "/api/compare": "Compare players",
    "/api/player/{player_id}": "Player page",
    "/api/matches": "Match predictions",
    "/api/entry/{team_id}/leagues": "My leagues",
    "/api/league/{league_id}": "Mini-league analysis",
    "/api/scout": "Scout",
    "/api/lineups": "Predicted line-ups",
    "/api/copilot": "Copilot question",
    "/api/players": "Projections table",
}

_lock = threading.Lock()


def _dir() -> str:
    return os.environ.get("STATS_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")


def _path() -> str:
    return os.path.join(_dir(), "usage.json")


def persistent() -> bool:
    """True when STATS_DIR is set, i.e. the counts are meant to outlive a deploy."""
    return bool(os.environ.get("STATS_DIR"))


def _today() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


def _load() -> Dict[str, Any]:
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("days"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"since": _today(), "days": {}}


def _save(data: Dict[str, Any]) -> None:
    keep = sorted(data["days"])[-KEEP_DAYS:]
    data["days"] = {d: data["days"][d] for d in keep}
    os.makedirs(_dir(), exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, _path())


def _day(data: Dict[str, Any], day: str) -> Dict[str, Any]:
    d = data["days"].setdefault(day, {})
    for k in ("visits", "new", "returning"):
        d.setdefault(k, 0)
    for k in ("modes", "views", "features"):
        d.setdefault(k, {})
    return d


def _bump(fn) -> None:
    with _lock:
        data = _load()
        fn(_day(data, _today()))
        try:
            _save(data)
        except OSError as exc:
            telemetry.event(log, "usage.save_failed", logging.WARNING, error=type(exc).__name__)


def record_visit(returning: bool, mode: str) -> None:
    """One browser's first open of the day."""
    mode = mode if mode in MODES else "none"

    def bump(d):
        d["visits"] += 1
        d["returning" if returning else "new"] += 1
        d["modes"][mode] = d["modes"].get(mode, 0) + 1
    _bump(bump)
    telemetry.event(log, "usage.visit", returning=bool(returning), mode=mode)


def record_view(page: str) -> bool:
    """A page of the app was opened. Returns False for a name outside PAGES."""
    if page not in PAGES:
        return False

    def bump(d):
        d["views"][page] = d["views"].get(page, 0) + 1
    _bump(bump)
    telemetry.event(log, "usage.view", page=page)
    return True


def record_route(method: str, template: Optional[str], status: int) -> None:
    """Count a feature when its route answers successfully (called for every request)."""
    name = FEATURES.get(template or "")
    if not name or status >= 400 or method not in ("GET", "POST"):
        return

    def bump(d):
        d["features"][name] = d["features"].get(name, 0) + 1
    _bump(bump)


def summary(days: int = 30) -> Dict[str, Any]:
    """Totals for today, the last 7 and the last `days` days, and a row per day."""
    with _lock:
        data = _load()
    today = dt.datetime.utcnow().date()
    span = [(today - dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]

    def total(keys: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {"visits": 0, "new": 0, "returning": 0, "modes": {}, "views": {}, "features": {}}
        for k in keys:
            d = data["days"].get(k)
            if not d:
                continue
            for f in ("visits", "new", "returning"):
                out[f] += d.get(f, 0)
            for f in ("modes", "views", "features"):
                for name, n in d.get(f, {}).items():
                    out[f][name] = out[f].get(name, 0) + n
        for f in ("views", "features"):
            out[f] = sorted(({"name": k, "count": v} for k, v in out[f].items()), key=lambda x: (-x["count"], x["name"]))
        return out

    return {
        "since": data.get("since"),
        "persistent": persistent(),
        "today": total(span[-1:]),
        "week": total(span[-7:]),
        "period": total(span),
        "days": [{"day": k, "visits": data["days"].get(k, {}).get("visits", 0),
                  "new": data["days"].get(k, {}).get("new", 0)} for k in span],
        "period_days": days,
    }
