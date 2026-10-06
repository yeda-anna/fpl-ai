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
import priors
import scout as scout_mod
import solver as solver_mod
import xpts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

app = FastAPI(title="Mug’s Game FC", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_lock = threading.Lock()
_engine = {"obj": None, "built": 0.0}
_rows_cache: Dict[str, Any] = {}
ENGINE_TTL = 900


def engine() -> xpts.Engine:
    with _lock:
        if _engine["obj"] is None or time.time() - _engine["built"] > ENGINE_TTL:
            bs = fpl_api.bootstrap()
            fx = fpl_api.fixtures()
            probe = xpts.Engine(bs, fx)           # cheap pass, just to read the calendar
            try:
                elo = priors.elo_strength(bs, priors.fetch_elo(bs, probe.current_gw))
            except Exception:
                elo = {}
            try:
                live = priors.fetch_recent_live(probe.current_gw)
            except Exception:
                live = {}
            _engine["obj"] = xpts.Engine(bs, fx, elo=elo, live_by_gw=live)
            solver_mod.configure(_engine["obj"].rules)
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


def parse_overrides(raw: Optional[str]) -> Dict[int, float]:
    """'12:70,328:0' -> {12: 70.0, 328: 0.0}. Bad pairs are skipped, not fatal."""
    out: Dict[int, float] = {}
    for part in (raw or "").split(","):
        if ":" not in part:
            continue
        pid, mins = part.split(":", 1)
        try:
            out[int(pid)] = max(0.0, min(90.0, float(mins)))
        except ValueError:
            continue
    return out


def rows_with(horizon: int, overrides: Optional[Dict[int, float]] = None):
    """Projections with the user's own minutes swapped in for any edited player.

    Edited minutes flow through every tool - the table, the solver, chips and the
    team rating all read from here - so changing one number changes every answer.
    """
    base = rows_for(horizon)
    if not overrides:
        return base
    e = engine()
    patched = []
    for r in base:
        if r["id"] in overrides:
            nr = e.player_horizon(r["id"], e.next_gw, horizon, overrides[r["id"]])
            nr["minutes_overridden"] = overrides[r["id"]]
            patched.append(nr)
        else:
            patched.append(r)
    patched.sort(key=lambda r: -r["xpts_total"])
    return patched


def estimate_free_transfers(team_id: int, current_gw: int) -> int:
    """FPL does not publish free transfers, so replay the rule over the season."""
    try:
        history = fpl_api.entry_history(team_id)
    except Exception:
        return 1
    chip_gws = {c["event"]: c["name"] for c in history.get("chips", [])}
    # Nothing is banked before GW1 - the GW1 squad is picked for free - so the
    # first rollover leaves exactly one free transfer for GW2.
    ft = 0
    for ev in history.get("current", []):
        gw = ev["event"]
        made = ev.get("event_transfers", 0)
        chip = chip_gws.get(gw)
        if chip in ("wildcard", "freehit"):
            ft = min(solver_mod.MAX_FREE_TRANSFERS, ft + 1)
            continue
        ft = min(solver_mod.MAX_FREE_TRANSFERS, max(0, ft - made) + 1)
    return max(1, min(solver_mod.MAX_FREE_TRANSFERS, ft))


def load_team(team_id: int, horizon: int, overrides: Optional[Dict[int, float]] = None):
    e = engine()
    rows = rows_with(horizon, overrides)
    index = {r["id"]: r for r in rows}
    try:
        entry = fpl_api.entry(team_id)
    except Exception:
        raise HTTPException(404, "No FPL team with ID %d." % team_id)
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
    except Exception:
        history = {}
    chips_history = [{"name": c["name"], "event": c["event"]} for c in history.get("chips", [])]
    chips_used = ["%s (GW%d)" % (c["name"], c["event"]) for c in chips_history]
    horizon_gws = list(range(e.next_gw, min(38, e.next_gw + horizon - 1) + 1))
    chips_available = {gw: [n for n in ("wildcard", "freehit", "bboost", "3xc")
                            if e.rules.chip_available(n, gw, chips_history)]
                       for gw in horizon_gws}
    return {
        "engine": e, "rows": rows, "entry": entry, "picks": picks,
        "squad_rows": squad_rows, "current_squad": current_squad,
        "bank": bank, "chips_used": chips_used, "chips_history": chips_history,
        "chips_available": chips_available, "history": history,
        "free_transfers": estimate_free_transfers(team_id, gw),
    }


def _name(e, pid):
    if not pid or pid not in e.players:
        return None
    return e.players[pid]["web_name"]


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
                    "finished": ev.get("finished"),
                    "average": ev.get("average_entry_score"),
                    "highest": ev.get("highest_score"),
                    "most_captained": _name(e, ev.get("most_captained")),
                    "most_selected": _name(e, ev.get("most_selected")),
                    "most_transferred_in": _name(e, ev.get("most_transferred_in")),
                    "top_player": _name(e, (ev.get("top_element_info") or {}).get("id")),
                    "top_player_points": (ev.get("top_element_info") or {}).get("points"),
                    "chip_plays": {c["chip_name"]: c["num_played"] for c in ev.get("chip_plays", [])},
                    "transfers_made": ev.get("transfers_made")}
                   for ev in e.events],
        "rules": e.rules.to_dict(),
        "model": {
            "elo_k": round(e.elo_k, 5),
            "elo_teams": sum(1 for v in e.elo.values() if v),
            "recent_gameweeks": sorted(e.live_by_gw.keys()),
            "loan_blocks": sum(len(v) for v in e._blocked.values()),
        },
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
            limit: int = 60,
            offset: int = 0,
            overrides: Optional[str] = None):
    rows = rows_with(horizon, parse_overrides(overrides))
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
    return {"count": len(out), "horizon": horizon, "offset": offset,
            "updated": _engine["built"], "players": out[offset:offset + limit]}


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
def team(team_id: int, horizon: int = Query(5, ge=1, le=10), overrides: Optional[str] = None):
    ctx = load_team(team_id, horizon, parse_overrides(overrides))
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
        "chips_available": ctx["chips_available"],
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
    paths: int = 3
    overrides: Optional[str] = None


def _do_nothing(ctx, plan) -> float:
    """What the current squad scores across the same weeks with no transfers."""
    total = 0.0
    for t in range(len(plan["gameweeks"])):
        split = analysis.squad_split(ctx["squad_rows"], t)
        total += split["xi_xpts"] + split["captain_xpts"]     # undecayed, like the plan totals
    return total


@app.post("/api/solve")
def solve(req: SolveRequest):
    ctx = load_team(req.team_id, req.horizon, parse_overrides(req.overrides))
    ft = req.free_transfers if req.free_transfers is not None else ctx["free_transfers"]
    bank = req.bank if req.bank is not None else ctx["bank"]
    # Solve once for the optimum, then again with that plan ruled out, so the user
    # can see genuinely different routes rather than one take-it-or-leave-it answer.
    forbidden, paths = [], []
    for i in range(max(1, min(3, req.paths))):
        r = solver_mod.solve(
            ctx["rows"], ctx["current_squad"], bank, ft, req.horizon,
            max_hits=req.max_hits, wildcard_gw=req.wildcard_gw,
            free_hit_gw=req.free_hit_gw, pool_size=req.pool_size,
            time_limit=20 if i == 0 else 12, forbid=forbidden,
            gap=0.005 if i == 0 else 0.01,
        )
        if not r.get("feasible") or not r["gameweeks"]:
            break
        sig = r.pop("signature", [])
        paths.append(r)
        if not sig:
            break
        forbidden.append(sig)

    if not paths:
        raise HTTPException(500, "The solver could not find a feasible plan.")

    # Each solve stops within a small optimality gap, so a later "alternative" can
    # edge out the first one. Rank by score so Path 1 is always the best found.
    paths.sort(key=lambda p: -p["total_xpts"])

    baseline = analysis.squad_split(ctx["squad_rows"], 0)
    result = dict(paths[0])
    # Template rating: how much the plan's first starting XI looks like everyone
    # else's. 100 = the eleven most-owned players; low = a differential-heavy side.
    own = sorted((r.get("selected_by_percent", 0.0) for r in ctx["rows"]), reverse=True)
    top11 = (sum(own[:11]) / 11.0) if own else 1.0

    def template_rating(p):
        xi = p["gameweeks"][0]["starting_xi"] if p["gameweeks"] else []
        if not xi or top11 <= 0:
            return 0
        return int(round(100 * min(1.0, (sum(x["selected_by_percent"] for x in xi) / len(xi)) / top11)))

    result["paths"] = [{"label": "Path %d" % (i + 1),
                        "total_xpts": p["total_xpts"],
                        "total_hits": p["total_hits"],
                        "template_rating": template_rating(p),
                        "gain_vs_nothing": round(p["total_xpts"] - _do_nothing(ctx, p), 2),
                        "gameweeks": p["gameweeks"]} for i, p in enumerate(paths)]
    result["no_transfer_baseline"] = round(baseline["xi_xpts"] + baseline["captain_xpts"], 2)
    result["free_transfers_start"] = ft
    result["bank_start"] = bank
    return result


class ChipRequest(BaseModel):
    team_id: int
    horizon: int = 8
    overrides: Optional[str] = None


@app.post("/api/chips")
def chips(req: ChipRequest):
    ctx = load_team(req.team_id, req.horizon, parse_overrides(req.overrides))
    return analysis.chip_strategy(ctx["engine"], ctx["rows"], ctx["squad_rows"],
                                  ctx["current_squad"], ctx["bank"], ctx["free_transfers"],
                                  req.horizon, ctx["chips_history"])


@app.get("/api/rate/{team_id}")
def rate(team_id: int, horizon: int = Query(5, ge=1, le=10), overrides: Optional[str] = None):
    ctx = load_team(team_id, horizon, parse_overrides(overrides))
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


@app.get("/api/scout")
def scout(horizon: int = Query(5, ge=1, le=10)):
    """Price changes, set-piece duties and defensive-contribution leaders."""
    e = engine()
    rows = rows_for(horizon)
    return {
        "gw": e.next_gw,
        "prices": scout_mod.price_changes(e, rows),
        "set_pieces": scout_mod.set_pieces(e, rows),
        "defcon": scout_mod.defcon(e, rows),
    }


@app.get("/api/lineups")
def lineups(horizon: int = Query(1, ge=1, le=10)):
    e = engine()
    return scout_mod.predicted_lineups(e, rows_for(horizon))


class CopilotRequest(BaseModel):
    question: str
    team_id: Optional[int] = None
    horizon: int = 5
    overrides: Optional[str] = None


@app.post("/api/copilot")
def copilot(req: CopilotRequest):
    e = engine()
    ov = parse_overrides(req.overrides)
    rows = rows_with(req.horizon, ov)
    ctx = None
    if req.team_id:
        try:
            ctx = load_team(req.team_id, req.horizon, ov)
        except HTTPException:
            ctx = None
    return scout_mod.copilot(e, rows, req.question, ctx, req.horizon)


@app.get("/healthz")
def healthz():
    """Liveness for the platform's health check - answers instantly, no model build."""
    return {"ok": True, "model_ready": _engine["obj"] is not None}


@app.on_event("startup")
def _warm_up():
    """Build the model in the background so the first visitor doesn't wait for it."""
    def build():
        try:
            engine()
        except Exception:
            pass        # first real request will retry and surface the error
    threading.Thread(target=build, daemon=True).start()


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
