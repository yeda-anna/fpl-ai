"""External priors: Elo team strength and recency-weighted player form.

Two ideas borrowed from the reference material:

* FPL-Core-Insights (github.com/olbauday/FPL-Core-Insights) carries ClubElo ratings
  on every match row. End-of-last-season Elo is a far better starting point for a
  club's strength than "league average", which is what a five-game sample would
  otherwise shrink toward.
* The FPL API's per-gameweek endpoint (/event/{gw}/live/), covered in the
  "Getting started with FPL data" walkthrough, gives every player's minutes and
  starts week by week. Weighting recent weeks more heavily catches players coming
  back from injury, or dropping out of the side, long before season averages do.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import time
from typing import Any, Dict, List, Optional

import httpx

import fpl_api

REPO_RAW = "https://raw.githubusercontent.com/olbauday/FPL-Core-Insights/main/data"
ELO_CACHE = os.path.join(fpl_api.CACHE_DIR, "elo_prior.json")
ELO_TTL = 24 * 3600
ELO_MIN, ELO_MAX = 1300.0, 2300.0       # anything outside this is a malformed row


def _valid_elo(value: Any) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if ELO_MIN <= v <= ELO_MAX else None


def _team_code(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _season_label(bootstrap: Dict[str, Any]) -> str:
    """'2026-2027' style label from the first deadline in the game."""
    first = bootstrap["events"][0]["deadline_time"][:4]
    y = int(first)
    return "%d-%d" % (y, y + 1)


def fetch_elo(bootstrap: Dict[str, Any], current_gw: int) -> Dict[str, Any]:
    """Latest known Elo per FPL team code, newest match first.

    Reads this season's finished gameweeks, then the tail of last season, and keeps
    the first valid rating seen for each club. The repo's rows are occasionally
    malformed, so every value is range-checked rather than trusted.
    """
    if os.path.exists(ELO_CACHE) and time.time() - os.path.getmtime(ELO_CACHE) < ELO_TTL:
        try:
            with open(ELO_CACHE) as fh:
                return json.load(fh)
        except Exception:
            pass

    season = _season_label(bootstrap)
    y = int(season[:4])
    last = "%d-%d" % (y - 1, y)
    wanted = {t["code"] for t in bootstrap["teams"]}
    found: Dict[int, Dict[str, Any]] = {}

    sources = [(season, gw) for gw in range(current_gw, 0, -1)]
    sources += [(last, gw) for gw in range(38, 30, -1)]

    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            for s, gw in sources:
                if wanted.issubset(found.keys()):
                    break
                url = "%s/%s/By%%20Gameweek/GW%d/matches.csv" % (REPO_RAW, s, gw)
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                except Exception:
                    continue
                for row in csv.DictReader(io.StringIO(resp.text)):
                    for side in ("home", "away"):
                        code = _team_code(row.get("%s_team" % side))
                        elo = _valid_elo(row.get("%s_team_elo" % side))
                        if code is None or elo is None or code in found:
                            continue
                        found[code] = {"elo": elo, "season": s, "gw": gw}
    except Exception:
        pass

    out = {"by_code": {str(k): v for k, v in found.items()},
           "fetched": time.time(), "season": season}
    if found:
        try:
            with open(ELO_CACHE, "w") as fh:
                json.dump(out, fh)
        except Exception:
            pass
    return out


def elo_strength(bootstrap: Dict[str, Any], elo_data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Per FPL team id: Elo, and whether it was observed or filled in.

    Promoted clubs have no top-flight Elo from last season, so they are placed a
    little below the weakest club that does - promoted sides start as underdogs.
    """
    by_code = {int(k): v for k, v in (elo_data or {}).get("by_code", {}).items()}
    known = [v["elo"] for v in by_code.values()]
    fallback = (min(known) - 40.0) if known else None

    out = {}
    for t in bootstrap["teams"]:
        hit = by_code.get(t["code"])
        if hit:
            out[t["id"]] = {"elo": hit["elo"], "source": "%s GW%d" % (hit["season"], hit["gw"])}
        elif fallback is not None:
            out[t["id"]] = {"elo": fallback, "source": "promoted-club estimate"}
    return out


def fetch_recent_live(current_gw: int, lookback: int = 6) -> Dict[int, Dict[str, Any]]:
    """The FPL live payload for each recently finished gameweek."""
    out = {}
    for gw in range(max(1, current_gw - lookback + 1), current_gw + 1):
        try:
            out[gw] = fpl_api.live_final(gw)
        except Exception:
            continue
    return out
