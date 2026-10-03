"""Scout tools and the rules-based Copilot.

Covers the parts of fplcopilot.com that live in its guides rather than its solver:
price changes, penalty and set-piece takers, defensive-contribution leaders,
predicted line-ups, and a question-answering Copilot driven by the xPts model
rather than a language model.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import analysis
import solver as solver_mod
from xpts import poisson_at_least

POS_NAME = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _likelihood_label(k: int) -> str:
    a = abs(k)
    if a >= 4:
        return "Very likely"
    if a == 3:
        return "Likely"
    if a == 2:
        return "Possible"
    if a == 1:
        return "Outside chance"
    return "Unlikely"


# --- price changes ---------------------------------------------------------

def price_changes(engine, rows) -> Dict[str, Any]:
    """Tonight's likely risers and fallers, from FPL's own price-progress fields.

    `price_change_percent` runs from -100 to +100; a player changes price when it
    crosses either end. `price_change_projections` carries FPL's projection for
    tonight and the two nights after, each with a likelihood from -5 to +5.
    """
    index = {r["id"]: r for r in rows}
    risers, fallers = [], []

    for pid, row in index.items():
        p = engine.players[pid]
        pct = _f(p.get("price_change_percent"))
        projections = p.get("price_change_projections") or []
        tonight = next((x for x in projections if x.get("offset") == 0), None)
        if not tonight:
            continue
        proj_pct = _f(tonight.get("projected_percent"))
        likelihood = int(tonight.get("likelihood") or 0)

        entry = {
            "player": analysis.light(row),
            "progress": round(pct, 1),
            "projected": round(proj_pct, 1),
            "likelihood": likelihood,
            "likelihood_label": _likelihood_label(likelihood),
            "hourly_rate": p.get("price_change_hourly_rate"),
            "transfers_in": p.get("transfers_in_event", 0),
            "transfers_out": p.get("transfers_out_event", 0),
            "net_transfers": p.get("transfers_in_event", 0) - p.get("transfers_out_event", 0),
            "change_this_gw": p.get("cost_change_event", 0),
            "change_season": p.get("cost_change_start", 0),
            "horizon": [{"in_days": x.get("offset"),
                         "projected": round(_f(x.get("projected_percent")), 1),
                         "likelihood": int(x.get("likelihood") or 0)}
                        for x in projections],
        }
        if likelihood >= 2 or proj_pct >= 80:
            risers.append(entry)
        elif likelihood <= -2 or proj_pct <= -80:
            fallers.append(entry)

    risers.sort(key=lambda e: (-e["likelihood"], -e["projected"]))
    fallers.sort(key=lambda e: (e["likelihood"], e["projected"]))

    movers = sorted(index.values(), key=lambda r: -abs(
        engine.players[r["id"]].get("transfers_in_event", 0)
        - engine.players[r["id"]].get("transfers_out_event", 0)))[:15]

    return {
        "risers": risers[:18],
        "fallers": fallers[:18],
        "most_transferred": [{
            "player": analysis.light(r),
            "net": engine.players[r["id"]].get("transfers_in_event", 0)
                   - engine.players[r["id"]].get("transfers_out_event", 0),
            "in": engine.players[r["id"]].get("transfers_in_event", 0),
            "out": engine.players[r["id"]].get("transfers_out_event", 0),
        } for r in movers],
    }


# --- set pieces ------------------------------------------------------------

def set_pieces(engine, rows) -> Dict[str, Any]:
    """Penalty, free-kick and corner duties, by club."""
    index = {r["id"]: r for r in rows}
    teams = {}
    for tid, t in engine.teams.items():
        teams[tid] = {"team": t["short_name"], "name": t["name"],
                      "penalties": [], "freekicks": [], "corners": []}

    for pid, row in index.items():
        p = engine.players[pid]
        tid = p["team"]
        light = analysis.light(row)
        if p.get("penalties_order"):
            teams[tid]["penalties"].append(dict(light, order=p["penalties_order"]))
        if p.get("direct_freekicks_order"):
            teams[tid]["freekicks"].append(dict(light, order=p["direct_freekicks_order"]))
        if p.get("corners_and_indirect_freekicks_order"):
            teams[tid]["corners"].append(dict(light, order=p["corners_and_indirect_freekicks_order"]))

    for t in teams.values():
        for k in ("penalties", "freekicks", "corners"):
            t[k].sort(key=lambda x: x["order"])
            t[k] = t[k][:3]
    return {"teams": sorted(teams.values(), key=lambda t: t["team"])}


# --- defensive contribution ------------------------------------------------

def defcon(engine, rows) -> Dict[str, Any]:
    """The players clearing the defensive-contribution threshold most often.

    Defenders need 10 CBIT, midfielders and forwards 12 CBIRT, for 2 points.
    """
    out = []
    for r in rows:
        if r["position"] == 1 or r["minutes"] < 180:
            continue
        p = engine.players[r["id"]]
        rates = engine.player_rates(p)
        mins = engine.minutes_model(p)
        threshold = 10 if r["position"] == 2 else 12
        lam = rates["dc90"] * (mins["xmins"] / 90.0)
        prob = poisson_at_least(threshold, lam)
        out.append({
            "player": analysis.light(r),
            "dc_per_90": round(rates["dc90"], 2),
            "dc_total": p.get("defensive_contribution", 0),
            "threshold": threshold,
            "hit_probability": round(100 * prob, 1),
            "xpts_from_dc": round(prob * 2, 2),
            "tackles": p.get("tackles", 0),
            "cbi": p.get("clearances_blocks_interceptions", 0),
            "recoveries": p.get("recoveries", 0),
        })
    out.sort(key=lambda x: -x["hit_probability"])
    return {"players": out[:30]}


# --- predicted line-ups ----------------------------------------------------

def predicted_lineups(engine, rows) -> Dict[str, Any]:
    """Each club's most likely eleven, from start rates and availability."""
    index = {r["id"]: r for r in rows}
    by_team = {}
    for r in index.values():
        by_team.setdefault(r["team"], []).append(r)

    teams = []
    for tid, squad in by_team.items():
        scored = []
        for r in squad:
            p = engine.players[r["id"]]
            m = engine.minutes_model(p)
            scored.append((m["p_start"], m, r))
        scored.sort(key=lambda x: -x[0])

        need = {1: 1, 2: 4, 3: 4, 4: 2}
        xi, taken = [], set()
        # Two passes: fill from players who can actually start, and only fall back to
        # zero-probability names if a club has nobody else listed in that position.
        for threshold in (0.01, -1.0):
            for q in (1, 2, 3, 4):
                for pstart, m, r in scored:
                    if r["position"] != q or need[q] <= 0 or r["id"] in taken:
                        continue
                    if pstart <= threshold:
                        continue
                    xi.append({"player": analysis.light(r), "p_start": round(100 * pstart),
                               "xmins": m["xmins"], "doubt": pstart < 0.6})
                    taken.add(r["id"])
                    need[q] -= 1
        risks = [{"player": analysis.light(r), "p_start": round(100 * pstart),
                  "xmins": m["xmins"]}
                 for pstart, m, r in scored
                 if 0.3 <= pstart <= 0.75 and r["minutes"] > 90][:5]
        doubts = [{"player": analysis.light(r), "news": r["news"], "status": r["status"]}
                  for pstart, m, r in scored if r["status"] not in ("a", "u", "n") and r["news"]][:5]
        teams.append({
            "team": engine.teams[tid]["short_name"],
            "name": engine.teams[tid]["name"],
            "xi": xi,
            "rotation_risks": risks,
            "doubts": doubts,
        })
    teams.sort(key=lambda t: t["team"])
    return {"teams": teams}


# --- copilot ---------------------------------------------------------------

INTENTS = [
    ("captain", ["captain", "armband", "triple captain", "who should i cap"]),
    ("hit", ["hit", "-4", "minus 4", "worth taking", "point hit"]),
    ("transfer", ["transfer", "sell", "buy", "swap", "move on", "bring in"]),
    ("rate", ["rate", "how good", "score my", "my team any good", "grade"]),
    ("chip", ["wildcard", "free hit", "bench boost", "triple", "chip"]),
    ("differential", ["differential", "punt", "under the radar", "low owned", "rank climb"]),
    ("bench", ["bench", "who do i start", "starting xi", "line up", "lineup"]),
    ("price", ["price", "rise", "fall", "value", "money"]),
]


def detect_intent(question: str) -> str:
    q = (question or "").lower()
    best, score = "overview", 0
    for intent, keys in INTENTS:
        hits = sum(1 for k in keys if k in q)
        if hits > score:
            best, score = intent, hits
    return best


def copilot(engine, rows, question: str, ctx: Optional[Dict[str, Any]] = None,
            horizon: int = 5) -> Dict[str, Any]:
    """Answer an FPL question from the model's own numbers.

    This is deliberately rule-based: every claim below is read off the xPts engine
    or the solver, so the answer can always be traced back to a number on the site.
    """
    intent = detect_intent(question)
    index = {r["id"]: r for r in rows}
    squad = ctx.get("squad_rows") if ctx else None
    answer, points, table = "", [], None

    def top(seq, n=5):
        return sorted(seq, key=lambda r: -r["per_gw"][0]["xpts"])[:n]

    if intent == "captain":
        pool = squad or rows
        picks = top([r for r in pool if r["status"] == "a"], 5)
        best = picks[0]
        gw_no = rows[0]["per_gw"][0]["gw"]
        gap = (best["xpts_next"] - picks[1]["xpts_next"]) if len(picks) > 1 else 0.0
        if gap >= 0.05:
            answer = ("Captain %s. He projects %.2f xPts in GW%d, %.2f clear of %s."
                      % (best["web_name"], best["xpts_next"], gw_no, gap, picks[1]["web_name"]))
        else:
            answer = ("%s and %s are level at the top for GW%d, both around %.2f xPts. "
                      "Either is defensible; take the higher-owned one if you are protecting rank."
                      % (best["web_name"], picks[1]["web_name"] if len(picks) > 1 else "—",
                         gw_no, best["xpts_next"]))
        if squad:
            points.append("Picked from your own fifteen, so this is actionable right now.")
        if 0.05 <= gap < 0.4 and len(picks) > 1:
            points.append("It is close — %s is within %.2f xPts, so ownership should decide it."
                          % (picks[1]["web_name"], gap))
        table = {"title": "Captain options", "columns": ["Player", "Team", "xPts"],
                 "rows": [[r["web_name"], r["team_short"], round(r["xpts_next"], 2)] for r in picks]}

    elif intent == "hit" and ctx:
        plans = {}
        for h in (0, 1, 2):
            plans[h] = solver_mod.solve(rows, ctx["current_squad"], ctx["bank"],
                                        ctx["free_transfers"], horizon, max_hits=h,
                                        pool_size=120, time_limit=12)
        base = plans[0]["total_xpts"]
        gains = {h: plans[h]["total_xpts"] - base for h in (1, 2)}
        best_h = max(gains, key=lambda h: gains[h]) if max(gains.values()) > 0 else 0
        if best_h == 0 or gains[best_h] <= 0.5:
            answer = ("No — take the free transfer only. Paying for extra moves gains at most %.2f xPts "
                      "over %d gameweeks, which does not cover the 4 points." % (max(gains.values()), horizon))
        else:
            answer = ("Yes, a %d-point hit is worth it. It gains %.2f xPts over %d gameweeks net of the charge."
                      % (best_h * 4, gains[best_h], horizon))
            moves = plans[best_h]["gameweeks"][0]
            for i, p in enumerate(moves["transfers_in"]):
                out = moves["transfers_out"][i] if i < len(moves["transfers_out"]) else None
                points.append("%s → %s" % (out["web_name"] if out else "–", p["web_name"]))
        table = {"title": "Plan value by hits allowed", "columns": ["Max hits", "Plan xPts", "Gain"],
                 "rows": [[h, round(plans[h]["total_xpts"], 2),
                           round(plans[h]["total_xpts"] - base, 2)] for h in (0, 1, 2)]}

    elif intent == "transfer" and ctx:
        plan = solver_mod.solve(rows, ctx["current_squad"], ctx["bank"],
                                ctx["free_transfers"], horizon, max_hits=1,
                                pool_size=140, time_limit=15)
        gw = plan["gameweeks"][0]
        if gw["transfers_in"]:
            moves = ", ".join("%s out, %s in" % (gw["transfers_out"][i]["web_name"], p["web_name"])
                              for i, p in enumerate(gw["transfers_in"])
                              if i < len(gw["transfers_out"]))
            answer = "The solver's move for GW%d is %s." % (gw["gw"], moves)
            points.append("That plan is worth %.2f xPts across %d gameweeks."
                          % (plan["total_xpts"], horizon))
            if gw["hits"]:
                points.append("It takes a %d-point hit, already netted off." % (gw["hits"] * 4))
        else:
            answer = ("Roll your transfer. No single move improves the next %d gameweeks "
                      "by enough to be worth making now." % horizon)
        worst = sorted(squad or [], key=lambda r: r["xpts_total"])[:3]
        table = {"title": "Weakest links in your squad", "columns": ["Player", "Team", "xPts (%dGW)" % horizon],
                 "rows": [[r["web_name"], r["team_short"], round(r["xpts_total"], 2)] for r in worst]}

    elif intent == "rate" and ctx:
        rating = analysis.rate_team(engine, rows, squad, ctx.get("entry", {}),
                                    ctx["bank"], horizon)
        answer = ("Your squad grades %s — %d out of 100. It projects %.1f xPts over %d gameweeks, "
                  "against %.1f for a strong budget-legal benchmark squad."
                  % (rating["grade"], round(rating["overall"]), rating["squad_xpts"],
                     horizon, rating["benchmark_xpts"]))
        points = rating["notes"][:3]

    elif intent == "chip" and ctx:
        ch = analysis.chip_strategy(engine, rows, squad, ctx["current_squad"], ctx["bank"],
                                    ctx["free_transfers"], horizon, ctx.get("chips_history"))
        if ch["best_plans"]:
            plan = ch["best_plans"][0]
            names = {"WC": "Wildcard", "FH": "Free Hit", "BB": "Bench Boost", "TC": "Triple Captain"}
            answer = ("Best chip plan in this window: "
                      + "; ".join("%s in GW%d (+%.1f)" % (names[c["chip"]], c["gw"], c["gain"])
                                  for c in plan["picks"])
                      + " — worth about %.1f xPts in total." % plan["total_gain"])
            points = [c["detail"] for c in plan["picks"]]
        else:
            answer = "You have no chips left to play in this window."

    elif intent == "differential":
        diffs = sorted([r for r in rows if r["selected_by_percent"] < 12 and r["status"] == "a"
                        and r["minutes"] > 180], key=lambda r: -r["xpts_total"])[:6]
        answer = ("The strongest low-owned picks are %s."
                  % ", ".join("%s (%.1f%% owned, %.1f xPts)"
                              % (r["web_name"], r["selected_by_percent"], r["xpts_total"])
                              for r in diffs[:3]))
        table = {"title": "Differentials under 12% owned",
                 "columns": ["Player", "Team", "Owned", "xPts (%dGW)" % horizon],
                 "rows": [[r["web_name"], r["team_short"], "%.1f%%" % r["selected_by_percent"],
                           round(r["xpts_total"], 2)] for r in diffs]}

    elif intent == "bench" and squad:
        split = analysis.squad_split(squad, 0)
        answer = ("Start this eleven in %s: %s. Captain %s."
                  % (split["formation"], ", ".join(r["web_name"] for r in split["xi"]),
                     split["captain"]["web_name"] if split["captain"] else "–"))
        points.append("Bench in order: " + ", ".join(r["web_name"] for r in split["bench"]))
        points.append("That XI projects %.2f xPts, the bench another %.2f."
                      % (split["xi_xpts"], split["bench_xpts"]))

    elif intent == "price":
        pc = price_changes(engine, rows)
        up = pc["risers"][:3]
        down = pc["fallers"][:3]
        answer = ("Likely to rise: %s. Likely to fall: %s."
                  % (", ".join(r["player"]["web_name"] for r in up) or "nobody tonight",
                     ", ".join(r["player"]["web_name"] for r in down) or "nobody tonight"))
        points.append("Price moves are worth about 0.1m each — never let one drive a transfer "
                      "you would not otherwise make.")

    else:
        best = top([r for r in rows if r["status"] == "a"], 3)
        answer = ("Over the next %d gameweeks the model likes %s."
                  % (horizon, ", ".join("%s (%.1f xPts)" % (r["web_name"], r["xpts_total"])
                                        for r in sorted(rows, key=lambda r: -r["xpts_total"])[:3])))
        points.append("Ask about your captain, whether a hit is worth it, which transfer to make, "
                      "chip timing, differentials, your bench order or price changes.")

    return {"question": question, "intent": intent, "answer": answer,
            "points": points, "table": table, "has_team": bool(ctx)}
