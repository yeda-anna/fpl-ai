"""Chip strategy, team rating, player comparison, weekly picks and mini-league analysis."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

import solver as solver_mod

POS_NAME = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# --- helpers ---------------------------------------------------------------

def light(row: Dict[str, Any], gw_index: int = 0) -> Dict[str, Any]:
    per = row["per_gw"][gw_index] if row["per_gw"] else {"xpts": 0.0}
    return {
        "id": row["id"], "web_name": row["web_name"], "team_short": row["team_short"],
        "position": row["position"], "pos_name": POS_NAME[row["position"]],
        "price": row["price"], "xpts": round(per["xpts"], 2),
        "xpts_total": row["xpts_total"], "selected_by_percent": row["selected_by_percent"],
        "status": row["status"], "news": row["news"], "form": row["form"],
        "total_points": row["total_points"],
    }


def best_xi(squad_rows: List[Dict[str, Any]], gw_index: int = 0):
    """Pick the highest-scoring legal eleven out of fifteen players."""
    def pts(r):
        return r["per_gw"][gw_index]["xpts"] if r["per_gw"] else 0.0

    by_pos = {1: [], 2: [], 3: [], 4: []}
    for r in squad_rows:
        by_pos[r["position"]].append(r)
    for k in by_pos:
        by_pos[k].sort(key=lambda r: -pts(r))

    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            for f in range(1, 4):
                if 1 + d + m + f != 11:
                    continue
                if len(by_pos[2]) < d or len(by_pos[3]) < m or len(by_pos[4]) < f or not by_pos[1]:
                    continue
                xi = by_pos[1][:1] + by_pos[2][:d] + by_pos[3][:m] + by_pos[4][:f]
                total = sum(pts(r) for r in xi)
                if best is None or total > best[0]:
                    best = (total, xi, "%d-%d-%d" % (d, m, f))
    if best is None:
        return 0.0, [], "n/a"
    return best


def squad_split(squad_rows: List[Dict[str, Any]], gw_index: int = 0):
    total, xi, formation = best_xi(squad_rows, gw_index)
    xi_ids = {r["id"] for r in xi}
    bench = [r for r in squad_rows if r["id"] not in xi_ids]

    def pts(r):
        return r["per_gw"][gw_index]["xpts"] if r["per_gw"] else 0.0

    bench.sort(key=lambda r: -pts(r))
    captain = max(xi, key=pts) if xi else None
    return {
        "xi": xi, "bench": bench, "formation": formation,
        "xi_xpts": round(total, 2),
        "bench_xpts": round(sum(pts(r) for r in bench), 2),
        "captain": captain,
        "captain_xpts": round(pts(captain), 2) if captain else 0.0,
    }


# --- swaps for one player ------------------------------------------------------

def swap_options(rows: List[Dict[str, Any]], squad_rows: List[Dict[str, Any]],
                 current_squad: List[Dict[str, Any]], bank: float, out_id: int,
                 free_transfers: int, top: int = 6,
                 min_chance: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """The best single-transfer replacements for one player in a manager's squad.

    A replacement plays the same position, fits the money (what the player sells for
    plus the bank), keeps at most three from a club and is fit enough to play. They are
    ranked by the extra expected points over the horizon; with no free transfer left the
    four-point hit is taken off. Returns None when the player isn't in the squad.
    """
    min_chance = solver_mod.MIN_CHANCE if min_chance is None else min_chance
    owned = {r["id"]: r for r in squad_rows}
    out = owned.get(out_id)
    if out is None:
        return None
    bought_at = next((p.get("purchase_price") for p in current_squad if p["id"] == out_id), None)
    sells_for = solver_mod.selling_price(out["now_cost"], bought_at)
    budget = sells_for + int(round(bank * 10))
    club_count: Dict[int, int] = {}
    for r in squad_rows:
        if r["id"] != out_id:
            club_count[r["team"]] = club_count.get(r["team"], 0) + 1
    hit = 0 if free_transfers > 0 else solver_mod.HIT_COST

    fits, passed_over = [], 0
    for r in rows:
        if r["position"] != out["position"] or r["id"] in owned or r["status"] in ("u", "n"):
            continue
        if r["now_cost"] > budget or club_count.get(r["team"], 0) >= solver_mod.MAX_PER_CLUB:
            continue
        if r.get("chance_next", 100) < min_chance:
            passed_over += 1
            continue
        fits.append(r)

    def option(r: Dict[str, Any]) -> Dict[str, Any]:
        legs = r["per_gw"][0]["fixtures"] if r["per_gw"] else []
        gain = r["xpts_total"] - out["xpts_total"]
        d = light(r)
        d.update({
            "opp": ", ".join("%s (%s)" % (f["opponent_short"], "H" if f["home"] else "A") for f in legs) or "Blank",
            "chance_next": r.get("chance_next", 100),
            "gain_next": round(r["xpts_next"] - out["xpts_next"], 2),
            "gain_total": round(gain, 2),
            "net_total": round(gain - hit, 2),
            "bank_after": round((budget - r["now_cost"]) / 10.0, 1),
        })
        return d

    fits.sort(key=lambda r: -r["xpts_total"])
    options = [option(r) for r in fits[:top]]
    return {
        "player": dict(light(out), chance_next=out.get("chance_next", 100),
                       sells_for=round(sells_for / 10.0, 1)),
        "bank": round(bank, 1), "budget": round(budget / 10.0, 1),
        "free_transfers": free_transfers, "hit": hit,
        "options": options,
        "keep": not options or options[0]["net_total"] <= 0,       # nobody affordable beats him
        "passed_over": passed_over,
    }


# --- season so far -----------------------------------------------------------

def season_history(current: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A manager's season, gameweek by gameweek, for the rank chart on Home.

    `current` is FPL's /entry/{id}/history/ "current" list. Each week carries its
    points, overall rank and the climb since the week before (positive = up the
    table, since a smaller rank is better). Weeks FPL hasn't ranked yet (rank null
    or 0, e.g. while a gameweek is still being processed) are dropped from the
    chart. `best` and `worst` are the highest and lowest overall rank so far.
    """
    weeks: List[Dict[str, Any]] = []
    prev = None
    for ev in sorted(current or [], key=lambda e: e.get("event") or 0):
        rank = ev.get("overall_rank")
        if not rank or rank <= 0:
            continue
        weeks.append({
            "gw": ev.get("event"),
            "points": ev.get("points") or 0,
            "total": ev.get("total_points"),
            "rank": int(rank),
            "climb": (prev - int(rank)) if prev is not None else None,
            "transfers": ev.get("event_transfers") or 0,
            "hits": ev.get("event_transfers_cost") or 0,
            "bench": ev.get("points_on_bench") or 0,
        })
        prev = int(rank)
    if not weeks:
        return {"weeks": [], "best": None, "worst": None, "latest": None}
    best = min(weeks, key=lambda w: (w["rank"], w["gw"]))
    worst = max(weeks, key=lambda w: (w["rank"], -w["gw"]))
    return {
        "weeks": weeks,
        "best": {"gw": best["gw"], "rank": best["rank"]},
        "worst": {"gw": worst["gw"], "rank": worst["rank"]},
        "latest": dict(weeks[-1]),
    }


# --- chip strategy ---------------------------------------------------------

def chip_strategy(engine, rows, squad_rows, current_squad, bank, free_transfers,
                  horizon, chips_history=None):
    """Score every gameweek for every chip, then rank whole chip plans.

    Bench Boost and Triple Captain are read straight off the projected squad.
    Free Hit and Wildcard each need their own optimisation - a Free Hit is the best
    possible eleven for one week, a Wildcard is a fresh squad kept from then on.
    """
    history = list(chips_history or [])
    R = engine.rules

    def can(name, gw):
        # 2026/27 runs two sets of chips: one for GW1-19, one for GW20-38
        return R.chip_available(name, gw, history)

    index = {r["id"]: r for r in rows}
    gws = [g["gw"] for g in rows[0]["per_gw"]] if rows else []

    baseline = []
    for t, gw in enumerate(gws):
        split = squad_split(squad_rows, t)
        baseline.append({
            "gw": gw,
            "xi_xpts": split["xi_xpts"],
            "bench_xpts": split["bench_xpts"],
            "captain": split["captain"]["web_name"] if split["captain"] else None,
            "captain_xpts": split["captain_xpts"],
            "total": round(split["xi_xpts"] + split["captain_xpts"], 2),
        })

    options = {"BB": [], "TC": [], "FH": [], "WC": []}

    for t, gw in enumerate(gws):
        base = baseline[t]
        if can("bboost", gw):
            options["BB"].append({"gw": gw, "gain": round(base["bench_xpts"], 2),
                                  "detail": "Bench projects %.1f pts" % base["bench_xpts"]})
        if can("3xc", gw):
            options["TC"].append({"gw": gw, "gain": round(base["captain_xpts"], 2),
                                  "detail": "Extra captain leg: %s" % (base["captain"] or "-")})

    # Free Hit: best legal eleven money can buy for a single week.
    if any(can("freehit", g) for g in gws):
        budget = bank + sum(r["price"] for r in squad_rows)
        for t, gw in enumerate(gws):
            if not can("freehit", gw):
                continue
            fh = _one_week_dream_team(rows, t, budget)
            gain = round(fh["total"] - baseline[t]["total"], 2)
            options["FH"].append({"gw": gw, "gain": gain,
                                  "detail": "Ideal XI projects %.1f vs your %.1f"
                                            % (fh["total"], baseline[t]["total"]),
                                  "xi": fh["xi"], "captain": fh["captain"]})

    # Wildcard: re-solve the rest of the horizon with one free rebuild.
    if current_squad and any(can("wildcard", g) for g in gws[:4]):
        base_plan = solver_mod.solve(rows, current_squad, bank, free_transfers, len(gws),
                                     max_hits=2, pool_size=95, time_limit=8)
        base_total = base_plan["total_xpts"]
        for t, gw in enumerate(gws[:min(len(gws), 4)]):
            if not can("wildcard", gw):
                continue
            wc = solver_mod.solve(rows, current_squad, bank, free_transfers, len(gws),
                                  max_hits=2, wildcard_gw=gw, pool_size=95, time_limit=8)
            options["WC"].append({"gw": gw, "gain": round(wc["total_xpts"] - base_total, 2),
                                  "detail": "Rebuild in GW%d is worth %.1f pts over the horizon"
                                            % (gw, wc["total_xpts"] - base_total)})

    for k in options:
        options[k].sort(key=lambda o: -o["gain"])

    # Rank complete plans: one gameweek per chip, no two chips in the same week.
    plans = []
    names = [k for k in ("WC", "FH", "BB", "TC") if options[k]]

    def recurse(i, used_gws, chosen, total):
        if i == len(names):
            if chosen:
                plans.append({"picks": list(chosen), "total_gain": round(total, 2)})
            return
        key = names[i]
        for opt in options[key][:5]:
            if opt["gw"] in used_gws:
                continue
            chosen.append({"chip": key, "gw": opt["gw"], "gain": opt["gain"],
                           "detail": opt["detail"]})
            recurse(i + 1, used_gws | {opt["gw"]}, chosen, total + opt["gain"])
            chosen.pop()
        recurse(i + 1, used_gws, chosen, total)      # or skip this chip for now

    recurse(0, set(), [], 0.0)
    plans.sort(key=lambda p: -p["total_gain"])

    return {
        "baseline": baseline,
        "options": options,
        "best_plans": plans[:8],
        "chips_used": sorted({"%s (GW%d)" % (h["name"], h["event"]) for h in history}),
        "windows": {name: R.chip_windows_left(name, gws[0] if gws else 1, history)
                    for name in ("wildcard", "freehit", "bboost", "3xc")},
    }


def _one_week_dream_team(rows, gw_index, budget):
    """Greedy-then-repair best XI under a budget - the Free Hit question."""
    cands = [r for r in rows if r["status"] not in ("i", "u", "n", "s")]
    for r in cands:
        r["_p"] = r["per_gw"][gw_index]["xpts"] if r["per_gw"] else 0.0
    cands.sort(key=lambda r: -r["_p"])

    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            for f in range(1, 4):
                if 1 + d + m + f != 11:
                    continue
                need = {1: 1, 2: d, 3: m, 4: f}
                xi, spend, per_club = [], 0.0, {}
                for r in cands:
                    q = r["position"]
                    if need.get(q, 0) <= 0:
                        continue
                    if per_club.get(r["team"], 0) >= 3:
                        continue
                    xi.append(r)
                    spend += r["price"]
                    per_club[r["team"]] = per_club.get(r["team"], 0) + 1
                    need[q] -= 1
                    if sum(need.values()) == 0:
                        break
                if sum(need.values()) != 0:
                    continue
                # if over budget, swap the worst value picks down
                while spend > budget - 16.0 and len(xi) > 0:
                    worst = min(xi, key=lambda r: r["_p"] / max(0.1, r["price"]))
                    repl = next((c for c in cands
                                 if c["position"] == worst["position"]
                                 and c["price"] < worst["price"]
                                 and c["id"] not in {x["id"] for x in xi}), None)
                    if not repl:
                        break
                    spend += repl["price"] - worst["price"]
                    xi[xi.index(worst)] = repl
                total = sum(r["_p"] for r in xi)
                cap = max(xi, key=lambda r: r["_p"]) if xi else None
                score = total + (cap["_p"] if cap else 0)
                if best is None or score > best["total"]:
                    best = {"total": round(score, 2), "formation": "%d-%d-%d" % (d, m, f),
                            "xi": [light(r, gw_index) for r in xi],
                            "captain": light(cap, gw_index) if cap else None,
                            "cost": round(spend, 1)}
    return best or {"total": 0.0, "xi": [], "captain": None, "formation": "n/a", "cost": 0.0}


# --- rate my team ----------------------------------------------------------

_BENCH_CACHE: Dict[Any, Any] = {}


def optimal_squad(rows, budget: float, horizon: int):
    """The best legal squad money can buy right now, found by the MIP solver.

    This is the yardstick for the team rating: not an abstract "perfect team" but
    the strongest fifteen your own budget could field over the same horizon.
    """
    key = (round(budget, 1), horizon, id(rows))
    if key in _BENCH_CACHE:
        return _BENCH_CACHE[key]
    plan = solver_mod.solve(rows, [], budget, 1, horizon, max_hits=0,
                            pool_size=130, time_limit=12, gap=0.01)
    index = {r["id"]: r for r in rows}
    gw0 = plan["gameweeks"][0] if plan.get("gameweeks") else None
    squad = []
    if gw0 and plan.get("feasible"):
        squad = [index[p["id"]] for p in gw0["starting_xi"] + gw0["bench"] if p["id"] in index]
    if len(squad) != solver_mod.SQUAD_SIZE:
        squad = []          # caller falls back to the greedy benchmark
    if len(_BENCH_CACHE) > 32:
        _BENCH_CACHE.clear()
    _BENCH_CACHE[key] = squad
    return squad


def _closeness(ratio: float, floor: float = 0.65, ceil: float = 0.95) -> float:
    """Map 'share of the best possible' onto 0-100.

    65% of the optimum is easy - any sensible squad gets there - so that is zero.
    The optimum is a free rebuild no real manager can make, so 95% of it already
    counts as perfect. The scale is spent on the range that separates managers.
    """
    return round(max(0.0, min(1.0, (ratio - floor) / (ceil - floor))) * 100.0, 1)


def rate_team(engine, rows, squad_rows, entry, bank, horizon):
    split = squad_split(squad_rows, 0)
    all_sorted = sorted(rows, key=lambda r: -r["xpts_total"])
    squad_total = sum(r["xpts_total"] for r in squad_rows)
    value = sum(r["price"] for r in squad_rows) + bank

    best = optimal_squad(rows, value, horizon) or _benchmark_squad(all_sorted)
    best_total = sum(r["xpts_total"] for r in best) or 1e-6
    best_split = squad_split(best, 0) if best else split
    best_value = best_total / max(0.1, sum(r["price"] for r in best) or value)

    flagged = [r for r in squad_rows if r["status"] != "a"]
    premium = [r for r in squad_rows if r["price"] >= 9.0]
    dead = [r for r in squad_rows if r["xpts_total"] < horizon * 1.2]
    diffs = [r for r in squad_rows if r["selected_by_percent"] < 10.0]
    templates = [r for r in squad_rows if r["selected_by_percent"] > 35.0]
    starters_flagged = [r for r in split["xi"] if r["status"] != "a"]

    scores = {
        # how much of the best affordable squad's output you'd get
        "projection": _closeness(squad_total / best_total),
        # next week's best XI against the optimum's best XI
        "structure": _closeness(split["xi_xpts"] / max(1e-6, best_split["xi_xpts"])),
        # a bench worth about 8 points a week is one you can actually use
        "bench": round(min(100.0, split["bench_xpts"] / 8.0 * 100), 1),
        # flags hurt, and flags in the starting eleven hurt more
        "fitness": round(max(0.0, 100 - 10.0 * len(flagged) - 12.0 * len(starters_flagged)), 1),
        # points per £m against what the optimum squeezes from the same money
        "value": _closeness((squad_total / max(0.1, value)) / max(1e-6, best_value)),
    }
    overall = round(0.45 * scores["projection"] + 0.15 * scores["structure"]
                    + 0.10 * scores["bench"] + 0.15 * scores["fitness"]
                    + 0.15 * scores["value"], 1)
    grade = ("A+" if overall >= 90 else "A" if overall >= 82 else "B+" if overall >= 74
             else "B" if overall >= 65 else "C+" if overall >= 56 else "C" if overall >= 45 else "D")

    notes = []
    if flagged:
        notes.append("%d flagged player%s in your squad: %s. Clear these before anything else."
                     % (len(flagged), "" if len(flagged) == 1 else "s",
                        ", ".join(r["web_name"] for r in flagged)))
    if dead:
        notes.append("Projecting under 1.2 points a week: %s. These are the transfers that pay."
                     % ", ".join(r["web_name"] for r in dead[:4]))
    gap = best_total - squad_total
    if gap > 3:
        notes.append("The best squad your £%.1fm could buy projects %.1f more points over %d gameweeks. "
                      "The upgrades on the right close most of that gap."
                      % (value, gap, horizon))
    if split["bench_xpts"] < 4:
        notes.append("Your bench projects only %.1f points next gameweek, which makes a Bench Boost weak "
                     "and leaves you exposed to a late injury." % split["bench_xpts"])
    if len(premium) < 2:
        notes.append("You own %d player at £9.0m or above. Elite attackers carry most of the ceiling, "
                     "and a squad without them tends to track the average." % len(premium))
    if len(diffs) < 2:
        notes.append("Almost everything you own is widely held, so you will move with the pack. "
                     "One or two picks under 10% ownership give you a way to climb.")
    if len(templates) >= 8:
        notes.append("%d of your players are owned by over 35%% of managers — a very template squad. "
                     "Safe, but hard to gain rank with." % len(templates))
    if bank >= 3.0:
        notes.append("You have £%.1fm in the bank. Money on the sidelines scores nothing." % bank)
    if not notes:
        notes.append("No structural problems stand out. Your squad projects close to the best your budget allows.")

    owned = {s["id"] for s in squad_rows}
    upgrades = []
    for r in squad_rows:
        better = [c for c in all_sorted
                  if c["position"] == r["position"] and c["price"] <= r["price"] + bank
                  and c["id"] not in owned and c["status"] == "a"]
        if better:
            b = better[0]
            g = b["xpts_total"] - r["xpts_total"]
            if g > 1.5:
                upgrades.append({"out": light(r), "in": light(b), "gain": round(g, 2)})
    upgrades.sort(key=lambda u: -u["gain"])

    return {
        "grade": grade, "overall": overall, "scores": scores,
        "squad_xpts": round(squad_total, 2),
        "benchmark_xpts": round(best_total, 2),
        "benchmark_squad": [light(r) for r in best],
        "efficiency": round(100 * squad_total / best_total, 1),
        "formation": split["formation"],
        "xi_xpts": split["xi_xpts"], "bench_xpts": split["bench_xpts"],
        "captain": light(split["captain"]) if split["captain"] else None,
        "squad_value": round(value, 1), "bank": round(bank, 1),
        "flagged": [light(r) for r in flagged],
        "differentials": [light(r) for r in diffs],
        "notes": notes,
        "top_upgrades": upgrades[:6],
        "entry": entry,
    }


def _benchmark_squad(all_sorted):
    """A strong, legal 100m squad - what a good manager could plausibly own."""
    need = {1: 2, 2: 5, 3: 5, 4: 3}
    budget, spend, squad, per_club = 100.0, 0.0, [], {}
    for r in all_sorted:
        q = r["position"]
        if need.get(q, 0) <= 0 or per_club.get(r["team"], 0) >= 3:
            continue
        remaining = sum(need.values()) - 1
        if spend + r["price"] + remaining * 4.3 > budget:
            continue
        squad.append(r)
        spend += r["price"]
        per_club[r["team"]] = per_club.get(r["team"], 0) + 1
        need[q] -= 1
        if sum(need.values()) == 0:
            break
    return squad


# --- weekly picks ----------------------------------------------------------

def weekly_picks(engine, rows, gw):
    avail = [r for r in rows if r["status"] == "a" and r["minutes"] > 0]
    captains = sorted(avail, key=lambda r: -r["per_gw"][0]["xpts"])[:8]
    diffs = sorted([r for r in avail if r["selected_by_percent"] < 15.0],
                   key=lambda r: -r["xpts_total"])[:10]
    by_pos = {}
    for q in (1, 2, 3, 4):
        pool = [r for r in avail if r["position"] == q]
        pool.sort(key=lambda r: -r["xpts_total"])
        by_pos[POS_NAME[q]] = [light(r) for r in pool[:8]]
    value = sorted(avail, key=lambda r: -(r["xpts_total"] / max(4.0, r["price"])))[:10]
    dream = _one_week_dream_team(rows, 0, 100.0)
    return {
        "gw": gw,
        "captains": [light(r) for r in captains],
        "differentials": [light(r) for r in diffs],
        "by_position": by_pos,
        "best_value": [light(r) for r in value],
        "dream_team": dream,
    }


# --- compare ---------------------------------------------------------------

def compare(engine, rows, id_a, id_b):
    index = {r["id"]: r for r in rows}
    a, b = index.get(id_a), index.get(id_b)
    if not a or not b:
        return {"error": "player not found"}

    def profile(r):
        p = engine.players[r["id"]]
        rates = engine.player_rates(p)
        mins = engine.minutes_model(p)
        return {
            "id": r["id"], "web_name": r["web_name"], "team_short": r["team_short"],
            "pos_name": POS_NAME[r["position"]], "price": r["price"],
            "selected_by_percent": r["selected_by_percent"], "form": r["form"],
            "total_points": r["total_points"], "minutes": r["minutes"],
            "xpts_next": r["xpts_next"], "xpts_total": r["xpts_total"],
            "value": round(r["xpts_total"] / max(4.0, r["price"]), 3),
            "xg90": round(rates["xg90"], 3), "xa90": round(rates["xa90"], 3),
            "dc90": round(rates["dc90"], 2), "bps90": round(rates["bps90"], 1),
            "xmins": mins["xmins"], "p_start": mins["p_start"],
            "status": r["status"], "news": r["news"],
            "per_gw": [{"gw": g["gw"], "xpts": g["xpts"],
                        "opp": ", ".join("%s (%s)" % (f["opponent_short"], "H" if f["home"] else "A")
                                         for f in g["fixtures"]) or "BLANK"}
                       for g in r["per_gw"]],
        }

    pa, pb = profile(a), profile(b)
    margin = pa["xpts_total"] - pb["xpts_total"]
    winner = pa if margin >= 0 else pb
    loser = pb if margin >= 0 else pa
    reasons = []
    if abs(margin) < 0.8:
        verdict = "Too close to call - take the cheaper option or the one who fits your structure."
    else:
        verdict = ("%s by %.1f xPts over the next %d gameweeks."
                   % (winner["web_name"], abs(margin), len(pa["per_gw"])))
    if winner["price"] < loser["price"]:
        reasons.append("%s is also %.1fm cheaper, so the gap is bigger than it looks."
                       % (winner["web_name"], loser["price"] - winner["price"]))
    if winner["xmins"] < loser["xmins"] - 12:
        reasons.append("Minutes risk: %s projects %.0f minutes against %.0f for %s."
                       % (winner["web_name"], winner["xmins"], loser["xmins"], loser["web_name"]))
    if winner["selected_by_percent"] < 10 and loser["selected_by_percent"] > 25:
        reasons.append("%s is also a differential at %.1f%% ownership against %.1f%%."
                       % (winner["web_name"], winner["selected_by_percent"],
                          loser["selected_by_percent"]))
    return {"a": pa, "b": pb, "verdict": verdict, "reasons": reasons,
            "margin": round(margin, 2)}


# --- mini-leagues ----------------------------------------------------------

def mini_league(engine, rows, standings, gw, horizon, sims=4000, max_rivals=12, also=None):
    """Rival ownership, differentials and a Monte Carlo on who wins the league.

    `also`: extra standings rows (the manager asking) to include even if they are not
    in the top `max_rivals`."""
    import fpl_api
    index = {r["id"]: r for r in rows}
    results = standings.get("standings", {}).get("results", [])[:max_rivals]
    have = {r["entry"] for r in results}
    results = results + [r for r in (also or []) if r.get("entry") not in have]

    managers = []
    for res in results:
        try:
            picks = fpl_api.entry_picks(res["entry"], gw)
        except Exception:
            continue
        squad = [index[p["element"]] for p in picks["picks"] if p["element"] in index]
        if not squad:
            continue
        split = squad_split(squad, 0)
        managers.append({
            "entry": res["entry"], "name": res["entry_name"],
            "player_name": res["player_name"], "rank": res["rank"],
            "total": res["total"],
            "squad_ids": [r["id"] for r in squad],
            "xi_ids": [r["id"] for r in split["xi"]],
            "captain_id": split["captain"]["id"] if split["captain"] else None,
            "xi_xpts": split["xi_xpts"],
            "projected": round(split["xi_xpts"] + split["captain_xpts"], 2),
        })

    n = max(1, len(managers))
    own_count, cap_count = {}, {}
    for m in managers:
        for pid in m["squad_ids"]:
            own_count[pid] = own_count.get(pid, 0) + 1
        if m["captain_id"]:
            cap_count[m["captain_id"]] = cap_count.get(m["captain_id"], 0) + 1

    ownership = sorted(
        [{"player": light(index[pid]), "owned_by": c,
          "pct": round(100.0 * c / n, 1)} for pid, c in own_count.items()],
        key=lambda o: -o["owned_by"])

    effective = []
    for pid, c in own_count.items():
        eo = 100.0 * (c + cap_count.get(pid, 0)) / n
        effective.append({"player": light(index[pid]), "effective_ownership": round(eo, 1)})
    effective.sort(key=lambda o: -o["effective_ownership"])

    differentials = sorted(
        [{"player": light(index[pid]), "league_pct": round(100.0 * own_count.get(pid, 0) / n, 1)}
         for pid in index
         if own_count.get(pid, 0) <= max(1, n // 6) and index[pid]["xpts_total"] > 3.5 * horizon / 5.0
         and index[pid]["status"] == "a"],
        key=lambda o: -o["player"]["xpts_total"])[:12]

    # Monte Carlo: each manager's projected total over the horizon, with noise.
    rng = random.Random(7)
    wins = {m["entry"]: 0 for m in managers}
    top3 = {m["entry"]: 0 for m in managers}
    horizon_mean = {}
    for m in managers:
        total = 0.0
        for pid in m["xi_ids"]:
            total += index[pid]["xpts_total"]
        if m["captain_id"] and m["captain_id"] in index:
            total += index[m["captain_id"]]["per_gw"][0]["xpts"]
        horizon_mean[m["entry"]] = total

    for _ in range(sims):
        scores = []
        for m in managers:
            mu = horizon_mean[m["entry"]]
            sigma = math.sqrt(max(1.0, mu)) * 2.4      # FPL scores are heavily overdispersed
            scores.append((m["entry"], m["total"] + rng.gauss(mu, sigma)))
        scores.sort(key=lambda s: -s[1])
        wins[scores[0][0]] += 1
        for e, _s in scores[:3]:
            top3[e] += 1

    for m in managers:
        m["win_probability"] = round(100.0 * wins[m["entry"]] / sims, 1)
        m["top3_probability"] = round(100.0 * top3[m["entry"]] / sims, 1)
        m["horizon_xpts"] = round(horizon_mean[m["entry"]], 1)
    managers.sort(key=lambda m: -m["win_probability"])

    return {
        "league": standings.get("league", {}),
        "gw": gw, "rivals_analysed": len(managers), "sims": sims,
        "managers": managers,
        "ownership": ownership[:25],
        "effective_ownership": effective[:15],
        "differentials": differentials,
    }
