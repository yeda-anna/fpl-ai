"""FastAPI app: serves the API and the single-page frontend."""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import analysis
import fpl_api
import solver as solver_mod
import xpts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

app = FastAPI(title="FPL Copilot (local)", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_lock = threading.Lock()
_engine = {"obj": None, "built": 0.0}
_rows_cache: Dict[str, Any] = {}
ENGINE_TTL = 900


def engine() -> xpts.Engine:
    with _lock:
        if _engine["obj"] is None or time.time() - _engine["built"] > ENGINE_TTL:
            _engine["obj"] = xpts.Engine(fpl_api.bootstrap(), fpl_api.fixtures())
            _engine["built"] = time.time()
            _rows_cache.clear()
        return _engine["obj"]


def rows_for(horizon: int, start_gw: Optional[int] = None) -> List[Dict[str, Any]]:
    """Projections for every player, memoised per horizon."""
    e = engine()
    gw = start_gw or e.next_gw
    key = "%d-%d" % (gw, horizon)
    if key not in _rows_cache:
        _rows_cache[key] = e.all_players_horizon(gw, horizon)
    return _rows_cache[key]


def estimate_free_transfers(team_id: int, current_gw: int) -> int:
    """FPL does not publish free transfers, so replay the rule over the season."""
    try:
        history = fpl_api.entry_history(team_id)
    except Exception:
        return 1
    chip_gws = {c["event"]: c["name"] for c in history.get("chips", [])}
    ft = 1
    for ev in history.get("current", []):
        gw = ev["event"]
        made = ev.get("event_transfers", 0)
        chip = chip_gws.get(gw)
        if chip in ("wildcard", "freehit"):
            ft = min(solver_mod.MAX_FREE_TRANSFERS, ft + 1)
            continue
        ft = min(solver_mod.MAX_FREE_TRANSFERS, max(0, ft - made) + 1)
    return max(1, min(solver_mod.MAX_FREE_TRANSFERS, ft))


def load_team(team_id: int, horizon: int):
    e = engine()
    rows = rows_for(horizon)
    index = {r["id"]: r for r in rows}
    entry = fpl_api.entry(team_id)
    gw = e.current_gw
    try:
        picks = fpl_api.entry_picks(team_id, gw)
    except Exception:
        raise HTTPException(404, "No squad found for team %d in GW%d." % (team_id, gw))
    squad_rows, current_squad = [], []
    for p in picks["picks"]:
        row = index.get(p["element"])
        if not row:
            continue
        squad_rows.append(row)
        current_squad.append({"id": p["element"], "purchase_price": p.get("purchase_price")})
    bank = picks.get("entry_history", {}).get("bank", 0) / 10.0
    try:
        history = fpl_api.entry_history(team_id)
        chips_used = [c["name"] for c in history.get("chips", [])]
    except Exception:
        history, chips_used = {}, []
    return {
        "engine": e, "rows": rows, "entry": entry, "picks": picks,
        "squad_rows": squad_rows, "current_squad": current_squad,
        "bank": bank, "chips_used": chips_used, "history": history,
        "free_transfers": estimate_free_transfers(team_id, gw),
    }


# --- meta ------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    e = engine()
    return {
        "current_gw": e.current_gw,
        "next_gw": e.next_gw,
        "teams": [{"id": t["id"], "name": t["name"], "short_name": t["short_name"]}
                  for t in e.bootstrap["teams"]],
        "events": [{"id": ev["id"], "name": ev["name"], "deadline": ev["deadline_time"],
                    "finished": ev.get("finished"), "average": ev.get("average_entry_score")}
                   for ev in e.events],
        "positions": {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"},
        "team_ratings": {str(tid): {k: round(v, 3) for k, v in r.items()}
                         for tid, r in e._team_rates.items()},
        "total_players": e.bootstrap.get("total_players"),
    }


@app.get("/api/players")
def players(horizon: int = Query(5, ge=1, le=10),
            position: Optional[int] = None,
            team: Optional[int] = None,
            max_price: Optional[float] = None,
            min_minutes: int = 0,
            search: Optional[str] = None,
            available_only: bool = False,
            sort: str = "xpts_total",
            limit: int = 60):
    rows = rows_for(horizon)
    out = []
    for r in rows:
        if position and r["position"] != position:
            continue
        if team and r["team"] != team:
            continue
        if max_price is not None and r["price"] > max_price:
            continue
        if r["minutes"] < min_minutes:
            continue
        if available_only and r["status"] != "a":
            continue
        if search and search.lower() not in r["web_name"].lower():
            continue
        out.append(r)
    reverse = True
    if sort == "price_asc":
        out.sort(key=lambda r: r["price"]); reverse = False
    elif sort == "value":
        out.sort(key=lambda r: -(r["xpts_total"] / max(4.0, r["price"])))
    elif sort == "xpts_next":
        out.sort(key=lambda r: -r["xpts_next"])
    elif sort == "ownership":
        out.sort(key=lambda r: -r["selected_by_percent"])
    else:
        out.sort(key=lambda r: -r["xpts_total"])
    return {"count": len(out), "horizon": horizon, "players": out[:limit]}


@app.get("/api/player/{player_id}")
def player(player_id: int, horizon: int = Query(6, ge=1, le=10),
           minutes: Optional[float] = None):
    e = engine()
    if player_id not in e.players:
        raise HTTPException(404, "Unknown player")
    row = e.player_horizon(player_id, e.next_gw, horizon, minutes)
    p = e.players[player_id]
    row["rates"] = {k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in e.player_rates(p).items()}
    row["minutes_model"] = e.minutes_model(p, minutes)
    row["season"] = {
        "goals": p["goals_scored"], "assists": p["assists"], "bonus": p["bonus"],
        "bps": p["bps"], "clean_sheets": p["clean_sheets"], "starts": p["starts"],
        "expected_goals": p["expected_goals"], "expected_assists": p["expected_assists"],
        "ict_index": p["ict_index"], "points_per_game": p["points_per_game"],
    }
    return row


@app.get("/api/entry/{team_id}")
def team(team_id: int, horizon: int = Query(5, ge=1, le=10)):
    ctx = load_team(team_id, horizon)
    split = analysis.squad_split(ctx["squad_rows"], 0)
    return {
        "entry": {
            "id": team_id,
            "name": ctx["entry"].get("name"),
            "manager": "%s %s" % (ctx["entry"].get("player_first_name", ""),
                                  ctx["entry"].get("player_last_name", "")),
            "overall_rank": ctx["entry"].get("summary_overall_rank"),
            "overall_points": ctx["entry"].get("summary_overall_points"),
            "gw_points": ctx["entry"].get("summary_event_points"),
            "value": round(ctx["entry"].get("last_deadline_value", 1000) / 10.0, 1),
        },
        "gw": ctx["engine"].current_gw,
        "next_gw": ctx["engine"].next_gw,
        "bank": ctx["bank"],
        "free_transfers": ctx["free_transfers"],
        "chips_used": ctx["chips_used"],
        "formation": split["formation"],
        "xi_xpts": split["xi_xpts"],
        "bench_xpts": split["bench_xpts"],
        "captain": analysis.light(split["captain"]) if split["captain"] else None,
        "starting_xi": [analysis.light(r) for r in split["xi"]],
        "bench": [analysis.light(r) for r in split["bench"]],
        "squad": [dict(analysis.light(r), per_gw=[{"gw": g["gw"], "xpts": g["xpts"]}
                                                  for g in r["per_gw"]])
                  for r in ctx["squad_rows"]],
        "history": [{"gw": h["event"], "points": h["points"], "rank": h["overall_rank"],
                     "transfers": h["event_transfers"], "hits": h["event_transfers_cost"]}
                    for h in ctx["history"].get("current", [])],
    }


class SolveRequest(BaseModel):
    team_id: int
    horizon: int = 5
    max_hits: int = 2
    wildcard_gw: Optional[int] = None
    free_hit_gw: Optional[int] = None
    free_transfers: Optional[int] = None
    bank: Optional[float] = None
    pool_size: int = 160


@app.post("/api/solve")
def solve(req: SolveRequest):
    ctx = load_team(req.team_id, req.horizon)
    ft = req.free_transfers if req.free_transfers is not None else ctx["free_transfers"]
    bank = req.bank if req.bank is not None else ctx["bank"]
    result = solver_mod.solve(
        ctx["rows"], ctx["current_squad"], bank, ft, req.horizon,
        max_hits=req.max_hits, wildcard_gw=req.wildcard_gw,
        free_hit_gw=req.free_hit_gw, pool_size=req.pool_size,
    )
    baseline = analysis.squad_split(ctx["squad_rows"], 0)
    result["no_transfer_baseline"] = round(baseline["xi_xpts"] + baseline["captain_xpts"], 2)
    result["free_transfers_start"] = ft
    result["bank_start"] = bank
    return result


class ChipRequest(BaseModel):
    team_id: int
    horizon: int = 8


@app.post("/api/chips")
def chips(req: ChipRequest):
    ctx = load_team(req.team_id, req.horizon)
    return analysis.chip_strategy(ctx["engine"], ctx["rows"], ctx["squad_rows"],
                                  ctx["current_squad"], ctx["bank"], ctx["free_transfers"],
                                  req.horizon, ctx["chips_used"])


@app.get("/api/rate/{team_id}")
def rate(team_id: int, horizon: int = Query(5, ge=1, le=10)):
    ctx = load_team(team_id, horizon)
    entry = {
        "name": ctx["entry"].get("name"),
        "manager": "%s %s" % (ctx["entry"].get("player_first_name", ""),
                              ctx["entry"].get("player_last_name", "")),
        "overall_rank": ctx["entry"].get("summary_overall_rank"),
        "overall_points": ctx["entry"].get("summary_overall_points"),
    }
    return analysis.rate_team(ctx["engine"], ctx["rows"], ctx["squad_rows"],
                              entry, ctx["bank"], horizon)


@app.get("/api/picks")
def picks(horizon: int = Query(5, ge=1, le=10)):
    e = engine()
    return analysis.weekly_picks(e, rows_for(horizon), e.next_gw)


@app.get("/api/compare")
def compare(a: int, b: int, horizon: int = Query(6, ge=1, le=10)):
    e = engine()
    return analysis.compare(e, rows_for(horizon), a, b)


@app.get("/api/league/{league_id}")
def league(league_id: int, horizon: int = Query(5, ge=1, le=10),
           rivals: int = Query(12, ge=2, le=25)):
    e = engine()
    standings = fpl_api.league_standings(league_id)
    return analysis.mini_league(e, rows_for(horizon), standings, e.current_gw,
                                horizon, max_rivals=rivals)


@app.get("/api/health")
def health():
    e = engine()
    return {"ok": True, "current_gw": e.current_gw, "next_gw": e.next_gw,
            "players": len(e.players), "built_at": _engine["built"]}


# --- frontend --------------------------------------------------------------
if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))
