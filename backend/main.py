"""FastAPI app: serves the API and the single-page frontend."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import analysis
import demo as demo_mod
import fpl_api
import leagues as leagues_mod
import matches as matches_mod
import priors
import rules as rules_mod
import scout as scout_mod
import solver as solver_mod
import telemetry
import xpts

telemetry.setup()
log = telemetry.get_logger("engine")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

app = FastAPI(title="Papa Ranjeet", version="1.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# Compress the page, the scripts (about 470 KB of animation libraries before gzip) and the JSON.
app.add_middleware(GZipMiddleware, minimum_size=1024)
# One JSON log line per request (method, route template, status, ms) - see telemetry.py.
telemetry.instrument(app)

_lock = threading.Lock()
_engine = {"obj": None, "built": 0.0}
_rows_cache: Dict[str, Any] = {}
ENGINE_TTL = 900


def engine() -> xpts.Engine:
    with _lock:
        if _engine["obj"] is None or time.time() - _engine["built"] > ENGINE_TTL:
            start = time.perf_counter()
            bs = fpl_api.bootstrap()
            fx = fpl_api.fixtures()
            probe = xpts.Engine(bs, fx)           # cheap pass, just to read the calendar
            try:
                elo = priors.elo_strength(bs, priors.fetch_elo(bs, probe.current_gw))
            except Exception as exc:
                elo = {}
                telemetry.event(log, "engine.elo_prior_unavailable", logging.WARNING,
                                error=type(exc).__name__, detail=str(exc)[:200])
            try:
                live = priors.fetch_recent_live(probe.current_gw)
            except Exception as exc:
                live = {}
                telemetry.event(log, "engine.recent_live_unavailable", logging.WARNING,
                                error=type(exc).__name__, detail=str(exc)[:200])
            _engine["obj"] = xpts.Engine(bs, fx, elo=elo, live_by_gw=live)
            solver_mod.configure(_engine["obj"].rules)
            _engine["built"] = time.time()
            _rows_cache.clear()
            e = _engine["obj"]
            telemetry.event(log, "engine.built", ms=telemetry.ms_since(start),
                            current_gw=e.current_gw, next_gw=e.next_gw, players=len(e.players),
                            elo_prior=bool(elo), recent_gws=len(live))
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


def parse_made(raw: Optional[str]) -> List[Tuple[int, int]]:
    """'417-306,12-99' -> [(417, 306), (12, 99)]: transfers the manager says they've made (out-in)."""
    out: List[Tuple[int, int]] = []
    for part in (raw or "").split(","):
        if "-" not in part:
            continue
        a, b = part.split("-", 1)
        try:
            out.append((int(a), int(b)))
        except ValueError:
            continue
    return out[:15]


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


def replay_free_transfers(history: Dict[str, Any], current_gw: int, max_ft: int) -> int:
    """Free transfers for the gameweek after `current_gw`, replayed from a manager's history."""
    chip_gws = {c["event"]: c["name"] for c in history.get("chips", [])}
    # Nothing is banked before GW1 - the GW1 squad is picked for free - so the
    # first rollover leaves exactly one free transfer for GW2.
    ft = 0
    for ev in history.get("current", []):
        gw = ev["event"]
        if gw > current_gw:
            continue    # the history is newer than our cached calendar; stay in step with the squad we show
        ft = rules_mod.roll_free_transfers(
            ft, ev.get("event_transfers", 0) or 0,
            chip_gws.get(gw) in ("wildcard", "freehit"), max_ft)
    return max(1, min(max_ft, ft))


def estimate_free_transfers(team_id: int, current_gw: int) -> int:
    """FPL does not publish free transfers, so replay the rule over the season."""
    try:
        history = fpl_api.entry_history(team_id)
    except Exception:
        return 1
    return replay_free_transfers(history, current_gw, solver_mod.MAX_FREE_TRANSFERS)


def apply_pending_transfers(squad: List[Dict[str, Any]], bank: float, transfers: List[Dict[str, Any]],
                            current_gw: int) -> Tuple[List[Dict[str, Any]], float, List[Dict[str, Any]]]:
    """Bring the squad up to date with transfers made since the last deadline.

    FPL's picks for the current gameweek are the team as it stood at that deadline;
    a transfer made now is for the next gameweek. FPL keeps it out of the public
    data until that deadline, so it usually arrives here from `made_transfers` (the
    manager tells us); any FPL does list is honoured too. Each one swaps the player out for
    the player in (keeping his slot), and the bank moves by the sale price minus
    the purchase price. Returns the new squad, bank and the transfers applied.
    """
    squad = [dict(p) for p in squad]
    pending = sorted((t for t in transfers or [] if (t.get("event") or 0) > current_gw),
                     key=lambda t: t.get("time") or "")
    applied = []
    for t in pending:
        out_id, in_id = t.get("element_out"), t.get("element_in")
        slot = next((i for i, p in enumerate(squad) if p["id"] == out_id), None)
        if slot is None or any(p["id"] == in_id for p in squad):
            continue
        squad[slot] = {"id": in_id, "purchase_price": t.get("element_in_cost")}
        bank += ((t.get("element_out_cost") or 0) - (t.get("element_in_cost") or 0)) / 10.0
        applied.append(t)
    return squad, round(bank, 1), applied


def made_transfers(e, squad: List[Dict[str, Any]], made: List[Tuple[int, int]],
                   current_gw: int) -> List[Dict[str, Any]]:
    """Transfers the manager entered by hand, shaped like FPL's own transfer records.

    FPL keeps a transfer for the coming gameweek private (only the logged-in
    manager sees it) until that deadline passes, so the public data can't show it.
    These go after any FPL already lists, for the next gameweek, so once the
    deadline passes and the picks carry them they no longer match and drop out.
    The player out sells at FPL's selling price; a swap across positions is ignored.
    """
    owned = {p["id"]: p.get("purchase_price") for p in squad}
    out = []
    for i, (out_id, in_id) in enumerate(made):
        po, pi = e.players.get(out_id), e.players.get(in_id)
        if not po or not pi or po["element_type"] != pi["element_type"]:
            continue
        sale = solver_mod.selling_price(po["now_cost"], owned.get(out_id))
        out.append({"element_out": out_id, "element_in": in_id, "event": current_gw + 1,
                    "element_out_cost": sale, "element_in_cost": pi["now_cost"],
                    "time": "~manual-%02d" % i, "manual": True})
        owned.setdefault(in_id, pi["now_cost"])
    return out


def load_team(team_id: int, horizon: int, overrides: Optional[Dict[int, float]] = None,
              made: Optional[List[Tuple[int, int]]] = None):
    e = engine()
    rows = rows_with(horizon, overrides)
    index = {r["id"]: r for r in rows}
    gw = e.current_gw
    if team_id == demo_mod.DEMO_ID:      # the made-up demo team: no FPL account needed
        fake = demo_mod.team(e.bootstrap["elements"], e.events, gw, e.rules.quota,
                             e.rules.club_limit, e.rules.budget, allowed=set(index))
        entry, picks, demo_history = fake["entry"], fake["picks"], fake["history"]
    else:
        demo_history = None
        try:
            entry = fpl_api.entry(team_id)
        except Exception:
            raise HTTPException(404, "No FPL team with ID %d." % team_id)
        try:
            picks = fpl_api.entry_picks(team_id, gw)
        except Exception:
            raise HTTPException(404, "No squad found for team %d in GW%d." % (team_id, gw))
    current_squad = [{"id": p["element"], "purchase_price": p.get("purchase_price")} for p in picks["picks"]]
    bank = picks.get("entry_history", {}).get("bank", 0) / 10.0
    try:
        transfers = [] if demo_history is not None else fpl_api.entry_transfers(team_id)
    except Exception:
        transfers = []
    transfers = list(transfers or []) + made_transfers(e, current_squad, made or [], gw)
    current_squad, bank, pending = apply_pending_transfers(current_squad, bank, transfers, gw)
    current_squad = [p for p in current_squad if p["id"] in index]
    squad_rows = [index[p["id"]] for p in current_squad]
    if demo_history is not None:
        history = demo_history
        ft = replay_free_transfers(history, gw, solver_mod.MAX_FREE_TRANSFERS)
    else:
        try:
            history = fpl_api.entry_history(team_id)
        except Exception:
            history = {}
        ft = estimate_free_transfers(team_id, gw)
    # transfers already made for the coming gameweek use up its free transfers (not under a Wildcard / Free Hit)
    chip_next = {c["name"] for c in history.get("chips", []) if (c.get("event") or 0) > gw}
    if pending and not chip_next & {"wildcard", "freehit"}:
        ft = max(0, ft - len(pending))
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
        "free_transfers": ft, "pending_transfers": pending,
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
    elif sort == "p_goal":
        out.sort(key=lambda r: -r.get("p_goal_next", 0.0))
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
def team(team_id: int, horizon: int = Query(5, ge=1, le=10), overrides: Optional[str] = None,
         made: Optional[str] = None, fresh: bool = False):
    if fresh and team_id != demo_mod.DEMO_ID:       # a page load: re-read this manager from FPL rather than from the cache
        fpl_api.refresh_team(team_id, engine().current_gw)
    ctx = load_team(team_id, horizon, parse_overrides(overrides), parse_made(made))
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
            "demo": bool(ctx["entry"].get("demo")),
        },
        "gw": ctx["engine"].current_gw,
        "next_gw": ctx["engine"].next_gw,
        "bank": ctx["bank"],
        "free_transfers": ctx["free_transfers"],
        "pending_transfers": [{"gw": t.get("event"), "out": _name(ctx["engine"], t.get("element_out")),
                               "in": _name(ctx["engine"], t.get("element_in")),
                               "out_id": t.get("element_out"), "in_id": t.get("element_in"),
                               "manual": bool(t.get("manual")), "time": None if t.get("manual") else t.get("time")}
                              for t in ctx["pending_transfers"]],
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
        "season": analysis.season_history(ctx["history"].get("current", [])),
    }


@app.get("/api/entry/{team_id}/swaps/{player_id}")
def swaps(team_id: int, player_id: int, horizon: int = Query(5, ge=1, le=10),
          overrides: Optional[str] = None, made: Optional[str] = None):
    """Who to swap one of this manager's players for: the best single transfers."""
    ctx = load_team(team_id, horizon, parse_overrides(overrides), parse_made(made))
    out = analysis.swap_options(ctx["rows"], ctx["squad_rows"], ctx["current_squad"], ctx["bank"],
                                player_id, ctx["free_transfers"])
    if out is None:
        raise HTTPException(404, "That player isn't in this squad.")
    out["horizon"] = horizon
    out["next_gw"] = ctx["engine"].next_gw
    return out


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
    made: Optional[str] = None
    min_chance: Optional[int] = None     # chance of playing needed to buy or captain (default solver.MIN_CHANCE)


def _do_nothing(ctx, plan) -> float:
    """What the current squad scores across the same weeks with no transfers."""
    total = 0.0
    for t in range(len(plan["gameweeks"])):
        split = analysis.squad_split(ctx["squad_rows"], t)
        total += split["xi_xpts"] + split["captain_xpts"]     # undecayed, like the plan totals
    return total


@app.post("/api/solve")
def solve(req: SolveRequest):
    ctx = load_team(req.team_id, req.horizon, parse_overrides(req.overrides), parse_made(req.made))
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
            gap=0.005 if i == 0 else 0.01, min_chance=req.min_chance,
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
    result["min_chance"] = paths[0].get("min_chance") if paths else None
    result["passed_over"] = paths[0].get("passed_over", []) if paths else []
    result["free_transfers_start"] = ft
    result["bank_start"] = bank
    return result


class ChipRequest(BaseModel):
    team_id: int
    horizon: int = 8
    overrides: Optional[str] = None
    made: Optional[str] = None


@app.post("/api/chips")
def chips(req: ChipRequest):
    ctx = load_team(req.team_id, req.horizon, parse_overrides(req.overrides), parse_made(req.made))
    return analysis.chip_strategy(ctx["engine"], ctx["rows"], ctx["squad_rows"],
                                  ctx["current_squad"], ctx["bank"], ctx["free_transfers"],
                                  req.horizon, ctx["chips_history"])


@app.get("/api/rate/{team_id}")
def rate(team_id: int, horizon: int = Query(5, ge=1, le=10), overrides: Optional[str] = None,
         made: Optional[str] = None):
    ctx = load_team(team_id, horizon, parse_overrides(overrides), parse_made(made))
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
           rivals: int = Query(12, ge=2, le=25), entry: Optional[int] = None):
    """Rivals' squads and who is likeliest to win. With `entry`, that manager is always
    in the table, even when they sit outside the top `rivals`."""
    e = engine()
    standings = fpl_api.league_standings(league_id)
    also = []
    if entry is not None:
        try:
            mine = fpl_api.entry(entry)
            rank = next((x.get("entry_rank") for x in (mine.get("leagues") or {}).get("classic") or []
                         if x.get("id") == league_id), None)
            row = leagues_mod.find_entry_row(entry, rank, standings, fpl_api.league_standings, league_id)
            if row:
                also.append(row)
        except Exception:
            pass                               # the analysis still works without them
    return analysis.mini_league(e, rows_for(horizon), standings, e.current_gw,
                                horizon, max_rivals=rivals, also=also)


@app.get("/api/entry/{team_id}/leagues")
def team_leagues(team_id: int):
    """Every mini-league a manager is in, with their place, the leader and the gap in each."""
    if team_id == demo_mod.DEMO_ID:           # a made-up team is in no leagues
        return dict(leagues_mod.empty(team_id, demo_mod.NAME, "Demo Manager"), demo=True)
    try:
        profile = fpl_api.entry(team_id)
    except Exception:
        raise HTTPException(404, "No FPL team with ID %d." % team_id)
    return leagues_mod.my_leagues(profile, team_id, fpl_api.league_standings)


@app.get("/api/matches")
def match_predictions(gw: Optional[int] = Query(None, ge=1, le=38)):
    """Every match in a gameweek: who is likeliest to win, the likeliest score, and the odds."""
    e = engine()
    week = gw or e.next_gw
    out = matches_mod.gameweek(e, week)
    ev = next((x for x in e.events if x["id"] == week), {})
    out.update(first=1, last=len(e.events) or 38, current_gw=e.current_gw, next_gw=e.next_gw,
               deadline=ev.get("deadline_time"), finished=bool(ev.get("finished")))
    return out


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
    made: Optional[str] = None


@app.post("/api/copilot")
def copilot(req: CopilotRequest):
    e = engine()
    ov = parse_overrides(req.overrides)
    rows = rows_with(req.horizon, ov)
    ctx = None
    if req.team_id is not None:      # 0 is the demo team
        try:
            ctx = load_team(req.team_id, req.horizon, ov, parse_made(req.made))
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
            # The first real request retries and surfaces the error; log it so a
            # bad boot (FPL down, empty offline cache) is visible in the deploy logs.
            telemetry.event(log, "engine.warmup_failed", logging.ERROR, exc_info=True)
    threading.Thread(target=build, daemon=True).start()


@app.get("/api/health")
def health():
    e = engine()
    return {"ok": True, "current_gw": e.current_gw, "next_gw": e.next_gw,
            "players": len(e.players), "built_at": _engine["built"]}


# --- frontend --------------------------------------------------------------
# Browsers (and home-screen apps on iOS especially) hold on to a page they've
# seen before. To make every visit pick up the latest build and data:
#   * index.html and every /api/ answer are `no-store`: a phone never keeps its
#     own copy, so a refresh (or back/forward, which `no-store` also keeps out of
#     the back/forward cache) always fetches the page afresh;
#   * each /static/*.css|js reference in it is rewritten to `?v=<content hash>`,
#     so a changed file gets a new URL and those URLs can be cached forever;
#   * the page carries a build id; app.js compares it with /version when the app
#     comes back to the foreground and reloads if a newer build has shipped.
# Nothing to bump by hand.
NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache", "Expires": "0"}
# Files may sit in a sub-folder (/static/vendor/gsap.min.js); names only ever come from index.html.
_ASSET_REF = re.compile(r'(/static/([\w.-]+(?:/[\w.-]+)*\.(?:css|js)))(?:\?v=[\w.-]*)?(?=["\'])')
_page = {"key": None, "html": "", "build": ""}
_page_lock = threading.Lock()


def _file_key(name: str):
    st = os.stat(os.path.join(FRONTEND, name))
    return (name, st.st_mtime_ns, st.st_size)


def _render_index():
    """index.html with fingerprinted assets, rebuilt only when a file changes."""
    html_path = os.path.join(FRONTEND, "index.html")
    with _page_lock:
        with open(html_path, encoding="utf-8") as fh:
            raw = fh.read()
        names = sorted(set(m.group(2) for m in _ASSET_REF.finditer(raw)
                           if os.path.isfile(os.path.join(FRONTEND, m.group(2)))))
        key = tuple([_file_key("index.html")] + [_file_key(n) for n in names])
        if _page["key"] != key:
            digests = {}
            for n in names:
                with open(os.path.join(FRONTEND, n), "rb") as fh:
                    digests[n] = hashlib.sha256(fh.read()).hexdigest()[:12]

            def stamp(m):
                name = m.group(2)
                return "%s?v=%s" % (m.group(1), digests[name]) if name in digests else m.group(0)

            html = _ASSET_REF.sub(stamp, raw)
            build = hashlib.sha256(
                (raw + "".join(digests[n] for n in names)).encode("utf-8")).hexdigest()[:12]
            html = html.replace("</head>", '<meta name="app-build" content="%s">\n</head>' % build, 1)
            _page.update(key=key, html=html, build=build)
        return _page["html"], _page["build"]


@app.middleware("http")
async def cache_policy(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        if request.query_params.get("v") and path.endswith((".css", ".js")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
    elif path.startswith("/api/"):
        for name, value in NO_STORE.items():
            response.headers[name] = value
    return response


if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/version")
def version():
    """The current frontend build, for open apps to notice a new deploy."""
    _, build = _render_index()
    return JSONResponse({"build": build}, headers=NO_STORE)


_OG_LINK = re.compile(r'(<meta property="og:(?:image|url)" content=")/')
_HOST = re.compile(r"^[A-Za-z0-9.-]+(?::\d+)?$")


def _origin(request: Request) -> str:
    """This deploy's own address (behind Railway's proxy), for link previews. '' if unsure."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host = host.split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    if not _HOST.match(host) or proto not in ("http", "https"):
        return ""
    return "%s://%s" % (proto, host)


@app.api_route("/", methods=["GET", "HEAD"])
def index(request: Request):
    html, _ = _render_index()
    origin = _origin(request)
    if origin:       # link previews need absolute addresses
        html = _OG_LINK.sub(lambda m: m.group(1) + origin + "/", html)
    return HTMLResponse(html, headers=NO_STORE)
